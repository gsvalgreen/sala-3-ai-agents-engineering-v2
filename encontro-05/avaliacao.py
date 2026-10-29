"""
avaliacao.py — as peças do Encontro 5: evals, observabilidade e custo.

Não existe assert em linguagem natural. O que substitui o assert é uma TAXA de acerto sobre um
conjunto conhecido de casos (o golden set), medida várias vezes, porque o modelo não responde
igual duas vezes. Este módulo mede o agente da Aula 4 desse jeito, camada por camada.

O sistema avaliado é o agente único da Aula 4 (o agente que decide buscar), em três versões:
    v1   produção: o agente da Aula 4, como está
    v2   PR #42, "prompt enxuto": um colega encurtou o prompt de sistema para economizar tokens
    v3   o mesmo prompt da v1, num modelo mais barato
Cada versão foi gravada AMOSTRAS vezes em cada caso (replay com amostras, ver comum/modelo.py).

A pirâmide de avaliação
    avaliar_busca(casos)        1. unit de ferramenta: a busca devolve a página certa? (sem modelo)
    passos(rodada)              2. step-level: o agente chamou a ferramenta certa, do jeito certo?
    trajetoria(rodada)          3. trajetória: o caminho até a resposta foi razoável?
    (a régua, em rodar)         4. outcome: desfecho, fontes e valor certos?
    julgar(rodada, juiz)        4b. outcome com LLM-as-judge, para o que a régua não vê
    online(rodada)              5. online: o que dá para medir em produção, sem gabarito

Variância e regressão
    placar(*rodadas)            acerto com intervalo de confiança, pass^k, custo, latência
    variacoes(rodada, id)       as respostas de um caso, amostra por amostra
    teste_aa(rodada)            a mesma versão contra ela mesma: o tamanho do ruído
    comparar(base, nova)        a diferença é regressão ou ruído?

Observabilidade e custo
    cascata(rodada, id)         o trace de um atendimento como spans no tempo (waterfall)
    painel(*rodadas)            qualidade, custo, latência e loops, lado a lado
    slis(rodada) / checar_slos(slos, *rodadas)   SLIs medidos e o gate de deploy
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
E4 = RAIZ / "encontro-04"
for _p in (RAIZ, RAIZ / "encontro-02", E4, PASTA):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

if not (E4 / "busca.py").exists() or not (E4 / "multiagente.py").exists():
    raise ImportError(
        f"O Encontro 5 usa o agente e a busca do Encontro 4, e a pasta {E4} não foi encontrada (ou está incompleta).\n"
        "Atualize o repositório com o Encontro 4 (Sync fork / git pull) antes de rodar o Encontro 5.")

import busca                                   # noqa: E402  (encontro-04/busca.py: a busca do Encontro 3, já indexada)
import multiagente as ma                       # noqa: E402  (o agente da Aula 4)
from comum import medidor, modelo              # noqa: E402
from comum.resultado import Resultado          # noqa: E402

DADOS = PASTA / "dados"
# Os vetores das consultas deste encontro ficam em encontro-05/dados (o índice continua o do Encontro 4).
busca.ARQ_CONSULTAS = DADOS / "consultas-aurora.npz"

GOLDEN = PASTA / "golden-aurora.json"
BANCO = PASTA / "banco-producao.json"
AMOSTRAS = 5

GRAVACOES = {
    "principal": DADOS / "replay-principal.jsonl",   # v1 e v2
    "barato": DADOS / "replay-barato.jsonl",         # v3
    "juiz": DADOS / "replay-juiz.jsonl",             # os dois juízes
}

# Preenchido pelo preparo/gravar_replay.py, que lê preparo/config.json. Só vale na gravação.
AO_VIVO: dict[str, dict] = {}

# Cores das versões (as três primeiras da paleta categórica validada, iguais em todos os gráficos)
COR = {"v1": "#2a78d6", "v2": "#eb6834", "v3": "#1baf7a"}
TINTA, TINTA_2, GRADE, FUNDO = "#0b0b0b", "#52514e", "#e5e4e0", "#fcfcfb"


# ======================================================================= as versões do agente

SISTEMA_ENXUTO = """Você responde dúvidas de colaboradores da Aurora Tecnologia com base nas políticas internas.
Busque a regra uma vez e responda direto, em uma ou duas frases.
Cite em "fontes" os ids dos documentos usados. Se a busca não trouxer a informação, use o desfecho "nao_sei".
Para encerrar, chame a ferramenta responder ou a ferramenta escalar_para_rh."""

VERSOES = {
    "v1": {"nome": "v1 · produção", "gravacao": "principal", "sistema": ma.SISTEMA_MONOLITO,
           "descricao": "o agente único da Aula 4, como está em produção"},
    "v2": {"nome": "v2 · prompt enxuto (PR #42)", "gravacao": "principal", "sistema": SISTEMA_ENXUTO,
           "descricao": "um colega encurtou o prompt: menos regras, 'busque uma vez', respostas curtas"},
    "v3": {"nome": "v3 · modelo mais barato", "gravacao": "barato", "sistema": ma.SISTEMA_MONOLITO,
           "descricao": "o prompt da v1, num modelo que custa menos por token"},
}


def agente(versao: str):
    """O agente único da Aula 4 com o prompt de sistema da versão. Mesma busca, mesmo contrato, mesma camada."""
    v = VERSOES[versao]
    nome = "buscar_politicas"
    contratos = {nome: ma._contrato_busca("RH, TI, benefícios e financeiro (viagens e reembolso)", True,
                                          ma.TODOS_OS_ESPACOS)}

    def arquitetura(pergunta, registro, trace):
        ma._registrar_busca(nome, None)
        ma._evento(trace, "agente", "acessa", "todos os espaços", espacos=["*"])
        return ma.loop_agente("agente", pergunta, v["sistema"], contratos, registro, trace)

    arquitetura.nome, arquitetura.versao = v["nome"], versao
    return arquitetura


# ======================================================================= instrumentação

_medidas: list[tuple[int, int, float]] = []    # cada chamada ao modelo: tokens de entrada, de saída, segundos
_evidencias: list[dict] = []                   # cada busca: o que pediu, o que voltou, quanto demorou
_registrar_original = medidor.registrar
_buscar_original = busca.buscar


def _registrar(tokens_entrada: int, tokens_saida: int, segundos: float) -> None:
    _medidas.append((tokens_entrada, tokens_saida, segundos))
    _registrar_original(tokens_entrada, tokens_saida, segundos)


def _buscar(pergunta, espacos=None, k=3, **kw):
    inicio = time.perf_counter()
    resultados = _buscar_original(pergunta, espacos, k, **kw)
    _evidencias.append({"pergunta": pergunta, "espacos": espacos, "resultados": resultados,
                        "segundos": time.perf_counter() - inicio})
    return resultados


medidor.registrar = _registrar
busca.buscar = _buscar


# ======================================================================= preparar

_estado = {"modo": None, "ativa": None}


def _cabecalho(arquivo: Path) -> dict:
    if not arquivo.exists():
        return {}
    with open(arquivo, encoding="utf-8") as f:
        primeira = json.loads(f.readline() or "{}")
    return primeira.get("_cabecalho", {})


def preparar(modo: str | None = "usar") -> None:
    """Confere as gravações e a busca. modo "usar" (turma) ou "gravar" (professor, via preparo/).

    A variável de ambiente AURORA_REPLAY_MODO, quando existe, vence o argumento.
    """
    modo = os.getenv("AURORA_REPLAY_MODO", modo) or None
    _estado.update(modo=modo, ativa=None)
    if modo == "usar":
        faltando = [n for n, a in GRAVACOES.items() if not a.exists()]
        if faltando:
            raise FileNotFoundError(f"Gravações não encontradas: {', '.join(faltando)}. "
                                    "O professor precisa rodar o preparo/gravar_replay.py.")
    for nome, arquivo in GRAVACOES.items():
        cab = _cabecalho(arquivo)
        if cab:
            print(f"Gravação {nome:<9} {cab.get('modelo')} · US$ {cab.get('preco_entrada')} / "
                  f"{cab.get('preco_saida')} por milhão de tokens (entrada / saída) · {cab.get('criado_em')}")
    print(f"Busca: {len(busca.indice().chunks)} trechos da wiki da Aurora")


def _ativar(gravacao: str) -> None:
    """Liga a gravação certa para a versão (ou para o juiz). Trocar de gravação não relê o arquivo."""
    if _estado["ativa"] == gravacao:
        return
    modo = _estado["modo"]
    if modo is None:
        raise RuntimeError("Rode av.preparar() antes.")
    if modo == "gravar":
        cfg = AO_VIVO[gravacao]
        modelo.MODELO = cfg["modelo"]
        modelo.EXTRA = dict(cfg.get("parametros", {}))
        medidor.PRECO_ENTRADA, medidor.PRECO_SAIDA = cfg["preco_entrada"], cfg["preco_saida"]
    modelo.replay(GRAVACOES[gravacao], modo)
    _estado["ativa"] = gravacao


def carregar_golden() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def carregar_banco() -> list[dict]:
    """As perguntas da primeira semana em produção. Não têm gabarito: quem escreve é o grupo."""
    return json.loads(BANCO.read_text(encoding="utf-8"))


# ======================================================================= rodar

def _rodar_caso(arquitetura, caso: dict, versao: str, amostra: int) -> dict:
    medicao = medidor.zerar()
    _medidas.clear()
    _evidencias.clear()
    registro, trace = [], []
    erro = ""
    try:
        resultado = arquitetura(caso["pergunta"], registro, trace)
    except modelo.RespostaNaoGravada:
        raise
    except Exception as e:                                   # um caso que quebra não derruba a rodada...
        if _estado["modo"] == "gravar":                      # ...exceto na gravação: lá, o erro tem de aparecer
            raise RuntimeError(f"Falhou o caso {caso['id']} ({versao}, amostra {amostra}): {type(e).__name__}: {e}") from e
        resultado, erro = Resultado("invalido"), f"{type(e).__name__}: {e}"

    # cada evento "modelo" do trace ganha os segundos daquela chamada; cada busca, o que ela devolveu
    chamadas = [e for e in trace if e["evento"] == "modelo"]
    for e, (_, _, seg) in zip(chamadas, _medidas):
        e["segundos"] = round(seg, 3)
    ferramentas = [e for e in trace if e["evento"] == "ferramenta"]
    for e, ev in zip(ferramentas, _evidencias):
        e["segundos"] = round(ev["segundos"], 4)

    if "esperado" in caso:
        acertou, motivo = ma.avaliar(resultado, caso) if not erro else (False, f"erro: {erro}")
    else:
        acertou, motivo = None, (f"erro: {erro}" if erro else "sem gabarito")
    consultas = [r["args"].get("pergunta", "") for r in registro if r["ferramenta"].startswith("buscar")]
    return {
        "id": caso["id"], "categoria": caso.get("categoria", "produção"), "pergunta": caso["pergunta"],
        "versao": versao, "amostra": amostra,
        "acertou": acertou, "motivo": motivo, "desfecho": resultado.desfecho, "fontes": resultado.fontes,
        "resposta": resultado.resposta, "rota_certa": ma.rota_certa(caso, trace) if "rota" in caso else None,
        "agentes": ["agente"], "buscas": len(consultas), "consultas": consultas,
        "args_busca": [r["args"] for r in registro if r["ferramenta"].startswith("buscar")],
        "evidencias": [r for ev in _evidencias for r in ev["resultados"]],
        "bateu_limite": any(e["evento"] == "parou" for e in trace),
        "chamadas_modelo": medicao.chamadas, "tokens_entrada": medicao.tokens_entrada,
        "tokens_saida": medicao.tokens_saida, "custo_usd": medicao.custo_usd,
        "segundos": medicao.segundos_no_modelo + sum(ev["segundos"] for ev in _evidencias),
        "trace": trace,
    }


def rodar(versao: str, casos: list[dict], amostras=None, mostrar: bool = False) -> dict:
    """Roda uma versão em todos os casos, AMOSTRAS vezes cada. Devolve a rodada (todas as linhas)."""
    amostras = range(AMOSTRAS) if amostras is None else ([amostras] if isinstance(amostras, int) else amostras)
    _ativar(VERSOES[versao]["gravacao"])
    arquitetura = agente(versao)
    linhas = []
    try:
        for a in amostras:
            modelo.amostra(a)
            for caso in casos:
                linhas.append(_rodar_caso(arquitetura, caso, versao, a))
                if mostrar:
                    l = linhas[-1]
                    marca = {True: "ok ", False: "ERR", None: "   "}[l["acertou"]]
                    print(f"  amostra {a}  {l['id']:<4}{marca}  {l['desfecho']:<10}{l['motivo']}")
    finally:
        modelo.amostra(0)
    erros = [l for l in linhas if l["motivo"].startswith("erro:")]
    if erros:
        print(f"Atenção: {len(erros)} de {len(linhas)} atendimentos de {VERSOES[versao]['nome']} deram erro. "
              f"O primeiro: {erros[0]['motivo'][:300]}")
    return {"nome": VERSOES[versao]["nome"], "versao": versao, "config": {"versao": versao}, "linhas": linhas}


def recorte(rodada: dict, amostras=None, casos=None) -> dict:
    """Uma parte da rodada: só algumas amostras e/ou só alguns casos."""
    if isinstance(amostras, int):
        amostras = [amostras]
    ids = {c["id"] if isinstance(c, dict) else c for c in casos} if casos is not None else None
    linhas = [l for l in rodada["linhas"]
              if (amostras is None or l["amostra"] in amostras) and (ids is None or l["id"] in ids)]
    sufixo = f" · amostra {','.join(map(str, amostras))}" if amostras is not None else ""
    return {**rodada, "nome": rodada["nome"] + sufixo, "linhas": linhas}


def juntar(*rodadas: dict, nome: str | None = None) -> dict:
    """Junta rodadas da MESMA versão (por exemplo, o golden set da turma e o do grupo)."""
    base = rodadas[0]
    return {**base, "nome": nome or base["nome"], "linhas": [l for r in rodadas for l in r["linhas"]]}


# ======================================================================= camada 1: unit de ferramenta

def avaliar_busca(casos: list[dict], k: int = 3, mostrar: bool = True) -> dict:
    """A busca sozinha, sem modelo: a página obrigatória vem entre os k primeiros resultados?

    Usa a pergunta do colaborador como consulta, na wiki inteira. É o placar da nota de chunking
    do Encontro 3, agora como o degrau de baixo da pirâmide.
    """
    linhas = []
    for caso in casos:
        obrig = caso.get("esperado", {}).get("fontes_obrigatorias", [])
        if not obrig:
            continue
        ids = [r["id"] for r in _buscar_original(caso["pergunta"], None, k)]
        achou = [f for f in obrig if f in ids]
        pos = min((ids.index(f) + 1 for f in achou), default=None)
        linhas.append({"id": caso["id"], "ok": len(achou) == len(obrig), "posicao": pos, "devolveu": ids})
    n_ok = sum(l["ok"] for l in linhas)
    if mostrar:
        for l in linhas:
            print(f"  {l['id']:<4}{'ok ' if l['ok'] else 'ERR'}  posição {l['posicao'] or '-'}   {', '.join(l['devolveu'])}")
        print(f"\nbusca acertou {n_ok}/{len(linhas)} (a página obrigatória entre os {k} primeiros)")
    return {"acertos": n_ok, "total": len(linhas), "linhas": linhas}


# ======================================================================= camada 2: step-level

def _checar_passos(l: dict, caso: dict) -> dict:
    cat = caso.get("categoria", "")
    out = {}
    if cat != "escalar":                       # escalar a elegibilidade não exige busca
        out["buscou_quando_devia"] = (l["buscas"] > 0) == (cat != "sem-busca")
    termo = caso.get("termo_exato")
    if termo:
        out["termo_exato_na_busca"] = bool(l["consultas"]) and termo.lower() in l["consultas"][0].lower()
    rota = caso.get("rota")
    espacos = [a.get("espaco") for a in l["args_busca"] if a.get("espaco")]
    if rota and espacos:
        out["espaco_certo"] = all(e in rota for e in espacos)
    return out


def passos(rodada: dict, casos: list[dict], mostrar: bool = True) -> dict:
    """Step-level: o agente buscou quando devia? Levou o termo exato para a busca? Filtrou o espaço certo?"""
    por_id = {c["id"]: c for c in casos}
    contagem: dict[str, list[int]] = {}
    falhas: dict[str, list[str]] = {}
    for l in rodada["linhas"]:
        for chave, ok in _checar_passos(l, por_id[l["id"]]).items():
            c = contagem.setdefault(chave, [0, 0])
            c[0] += ok
            c[1] += 1
            if not ok:
                falhas.setdefault(chave, []).append(f"{l['id']}/a{l['amostra']}")
    if mostrar:
        nomes = {"buscou_quando_devia": "buscou nas dúvidas e não buscou em cumprimentos",
                 "termo_exato_na_busca": "levou o termo exato (809, AUR-S2) para a 1ª busca",
                 "espaco_certo": "quando filtrou um espaço, era o espaço certo"}
        for chave, (ok, n) in contagem.items():
            exemplos = ", ".join(sorted(set(falhas.get(chave, [])))[:6])
            print(f"  {nomes[chave]:<55}{ok:>4}/{n:<4}{'  falhou em: ' + exemplos if exemplos else ''}")
    return {k: v[0] / v[1] for k, v in contagem.items()}


# ======================================================================= camada 3: trajetória

def trajetoria(rodada: dict, mostrar: bool = True) -> dict:
    """O caminho: quantas chamadas, buscas repetidas, atendimentos que bateram no limite de passos."""
    ls = rodada["linhas"]
    repetidas = [l for l in ls if len(l["consultas"]) != len(set(c.strip().lower() for c in l["consultas"]))]
    limite = [l for l in ls if l["bateu_limite"]]
    chamadas = np.array([l["chamadas_modelo"] for l in ls])
    out = {"chamadas_media": float(chamadas.mean()), "chamadas_max": int(chamadas.max()),
           "repetiu_busca": len(repetidas) / len(ls), "bateu_limite": len(limite) / len(ls)}
    if mostrar:
        print(f"  chamadas ao modelo por atendimento: média {out['chamadas_media']:.1f}, máximo {out['chamadas_max']}")
        print(f"  repetiu a mesma busca:              {len(repetidas)}/{len(ls)} atendimentos")
        print(f"  bateu no limite de {ma.MAX_PASSOS} passos:         {len(limite)}/{len(ls)} atendimentos"
              + (f"  ({', '.join(sorted({l['id'] for l in limite}))})" if limite else ""))
        dist = np.bincount(chamadas)
        print("  distribuição de chamadas por atendimento:")
        for n, q in enumerate(dist):
            if q:
                print(f"    {n:>2} chamadas  {'█' * max(1, round(40 * q / len(ls)))} {q}")
    return out


# ======================================================================= camada 4b: LLM-as-judge

_VEREDITO_INGENUO = {
    "nome": "veredito",
    "descricao": "Registra a avaliação da resposta.",
    "parametros": {"type": "object", "properties": {
        "justificativa": {"type": "string", "description": "Uma ou duas frases."},
        "nota": {"type": "integer", "minimum": 1, "maximum": 5,
                 "description": "1 = péssima, 5 = excelente"}},
        "required": ["justificativa", "nota"], "additionalProperties": False},
}

_VEREDITO_EVIDENCIA = {
    "nome": "veredito",
    "descricao": "Registra a avaliação da resposta, critério por critério. Escreva a justificativa primeiro.",
    "parametros": {"type": "object", "properties": {
        "justificativa": {"type": "string",
                          "description": "Duas ou três frases, citando o trecho que sustenta ou contradiz a resposta."},
        "fiel": {"type": "boolean", "description": "Toda afirmação da resposta está nos trechos?"},
        "responde": {"type": "boolean", "description": "A resposta trata do que foi perguntado?"},
        "desfecho_adequado": {"type": "boolean", "description": "O desfecho é o que a rubrica pede?"}},
        "required": ["justificativa", "fiel", "responde", "desfecho_adequado"], "additionalProperties": False},
}

JUIZ_INGENUO = """Você avalia respostas de um assistente de atendimento interno (RH, TI e benefícios) de uma empresa.
Dê uma nota de 1 a 5 para a qualidade da resposta à pergunta do colaborador.
Chame a ferramenta veredito."""

JUIZ_EVIDENCIA = """Você avalia respostas de um assistente de atendimento interno da Aurora Tecnologia.
Você recebe a pergunta do colaborador, os TRECHOS das políticas que o assistente leu, o desfecho e a resposta.
Julgue apenas com base nos trechos. Não use conhecimento próprio sobre empresas ou leis.

Rubrica:
1. fiel: todo número, prazo, valor e condição da resposta aparece nos trechos. Uma afirmação que não está
   nos trechos torna a resposta infiel, mesmo que pareça plausível.
2. responde: a resposta trata do que foi perguntado. Se os trechos não trazem a informação, responder é
   dizer claramente que não encontrou.
3. desfecho_adequado:
   - "responder" quando os trechos sustentam a resposta (cumprimentos e agradecimentos: "responder", sem trechos);
   - "nao_sei" quando os trechos não trazem a informação;
   - "escalar" quando a pessoa pergunta se ELA tem direito a um benefício: elegibilidade é analisada pelo RH,
     mesmo que os trechos tragam a regra geral.
Escreva a justificativa primeiro, depois os três critérios. Chame a ferramenta veredito."""

JUIZES = {"ingenuo": (JUIZ_INGENUO, _VEREDITO_INGENUO), "evidencia": (JUIZ_EVIDENCIA, _VEREDITO_EVIDENCIA)}


def _trechos(linha: dict, maximo: int = 6) -> str:
    vistos, partes = set(), []
    for r in linha["evidencias"]:
        if r["chunk_id"] in vistos:
            continue
        vistos.add(r["chunk_id"])
        partes.append(f"[{r['id']}] {r['titulo']} > {r['secao'] or 'introdução'} (vigência {r['vigencia']}):\n"
                      f"{' '.join(r['trecho'].split())}")
        if len(partes) == maximo:
            break
    return "\n\n".join(partes) or "(o assistente não fez nenhuma busca)"


def _entrada_do_juiz(linha: dict, juiz: str) -> str:
    if juiz == "ingenuo":
        return f"Pergunta do colaborador:\n{linha['pergunta']}\n\nResposta do assistente:\n{linha['resposta']}"
    return (f"Pergunta do colaborador:\n{linha['pergunta']}\n\nTrechos que o assistente leu:\n{_trechos(linha)}\n\n"
            f"Desfecho escolhido: {linha['desfecho']}\nFontes citadas: {', '.join(linha['fontes']) or '(nenhuma)'}\n\n"
            f"Resposta do assistente:\n{linha['resposta']}")


def julgar(rodada: dict, juiz: str = "evidencia", mostrar: bool = False) -> dict:
    """Passa cada linha da rodada por um juiz. Guarda em linha['juiz_<juiz>']: aprovado, critérios, justificativa.

    juiz "ingenuo":   vê só a pergunta e a resposta, e dá uma nota de 1 a 5 (aprova com 4 ou 5).
    juiz "evidencia": vê também os trechos que o agente leu, e segue uma rubrica de três critérios.
    O juiz é outro modelo, com a sua própria gravação. Devolve o custo de julgar a rodada.
    """
    sistema, ferramenta = JUIZES[juiz]
    anterior = _estado["ativa"]
    _ativar("juiz")
    custo = 0.0
    try:
        for l in rodada["linhas"]:
            if l["desfecho"] == "invalido" and not l["resposta"]:
                l[f"juiz_{juiz}"] = {"aprovado": False, "justificativa": "saída fora do contrato", "custo_usd": 0.0}
                continue
            medicao = medidor.zerar()
            r = modelo.chamar([modelo.mensagem_do_usuario(_entrada_do_juiz(l, juiz))], sistema=sistema,
                              ferramentas=[ferramenta], max_tokens=400, exigir_ferramenta="veredito")
            args = r.chamadas[0].args if r.chamadas else {}
            if juiz == "ingenuo":
                nota = int(args.get("nota", 0) or 0)
                v = {"aprovado": nota >= 4, "nota": nota}
            else:
                crit = {k: bool(args.get(k)) for k in ("fiel", "responde", "desfecho_adequado")}
                v = {"aprovado": all(crit.values()), **crit}
            v["justificativa"] = str(args.get("justificativa", ""))
            v["custo_usd"] = medicao.custo_usd
            custo += medicao.custo_usd
            l[f"juiz_{juiz}"] = v
            if mostrar:
                print(f"  {l['id']:<4}a{l['amostra']}  {'aprova' if v['aprovado'] else 'REPROVA':<8}{v['justificativa'][:110]}")
    finally:
        if anterior:
            _ativar(anterior)
    return {"juiz": juiz, "custo_usd": custo, "linhas": len(rodada["linhas"])}


def concordancia(rodada: dict, juiz: str = "evidencia", mostrar: bool = True) -> list[dict]:
    """Régua (gabarito) contra juiz, nas linhas que têm as duas notas. Devolve as discordâncias."""
    chave = f"juiz_{juiz}"
    ls = [l for l in rodada["linhas"] if l["acertou"] is not None and chave in l]
    tab = {(True, True): 0, (True, False): 0, (False, True): 0, (False, False): 0}
    discord = []
    for l in ls:
        par = (l["acertou"], l[chave]["aprovado"])
        tab[par] += 1
        if par[0] != par[1]:
            discord.append(l)
    if mostrar and ls:
        n = len(ls)
        print(f"juiz '{juiz}' contra a régua, em {n} respostas\n")
        print(f"{'':<26}{'juiz aprova':>14}{'juiz reprova':>14}")
        print(f"{'régua: certo':<26}{tab[(True, True)]:>14}{tab[(True, False)]:>14}")
        print(f"{'régua: errado':<26}{tab[(False, True)]:>14}{tab[(False, False)]:>14}")
        print(f"\nconcordam em {(tab[(True, True)] + tab[(False, False)]) / n:.0%} das respostas")
        print(f"o juiz APROVOU {tab[(False, True)]} respostas que a régua reprova, "
              f"e REPROVOU {tab[(True, False)]} que a régua aprova")
    return discord


def mostrar_discordancias(discord: list[dict], juiz: str = "evidencia", maximo: int = 6) -> None:
    """Uma discordância por caso: quem está certo, a régua ou o juiz? É aí que um humano decide."""
    vistos = set()
    for l in discord:
        if l["id"] in vistos:
            continue
        vistos.add(l["id"])
        v = l[f"juiz_{juiz}"]
        print(f"── {l['id']} (amostra {l['amostra']}) · {l['pergunta']}")
        print(f"   resposta: {l['desfecho']} · fontes {l['fontes']} · “{' '.join(l['resposta'].split())[:220]}”")
        print(f"   régua: {'CERTO' if l['acertou'] else 'ERRADO'} ({l['motivo']})")
        print(f"   juiz:  {'APROVA' if v['aprovado'] else 'REPROVA'} · {v['justificativa'][:260]}\n")
        if len(vistos) == maximo:
            break


# ======================================================================= variância e regressão

def _por_caso(rodada: dict) -> dict[str, list[bool]]:
    out: dict[str, list[bool]] = {}
    for l in rodada["linhas"]:
        if l["acertou"] is not None:
            out.setdefault(l["id"], []).append(bool(l["acertou"]))
    return out


def _matriz(pc: dict[str, list[bool]], ids: list[str]) -> np.ndarray:
    k = min(len(pc[i]) for i in ids)
    return np.array([pc[i][:k] for i in ids], dtype=float)


def _bootstrap(a: np.ndarray, b: np.ndarray | None = None, n: int = 4000, semente: int = 7) -> tuple[float, float]:
    """Intervalo de 90% do acerto médio (ou da diferença b - a), em dois níveis.

    a e b são matrizes casos x amostras de 0 e 1. A cada rodada do bootstrap, sorteia os CASOS com
    reposição e, dentro de cada caso, sorteia as AMOSTRAS com reposição: as duas fontes de incerteza
    entram no intervalo, a de ter poucos casos e a de o modelo variar.
    """
    if a.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(semente)
    n_casos, k = a.shape
    casos = rng.integers(0, n_casos, size=(n, n_casos))

    def media(m):
        amostras = rng.integers(0, m.shape[1], size=(n, n_casos, m.shape[1]))
        return m[casos[..., None], amostras].mean(axis=(1, 2))

    medias = media(a) if b is None else media(b) - media(a)
    return float(np.percentile(medias, 5)), float(np.percentile(medias, 95))


def acerto(rodada: dict) -> dict:
    """Acerto médio (a chance de acertar um caso numa tentativa), com intervalo de 90%, e pass^k."""
    pc = _por_caso(rodada)
    taxas = np.array([np.mean(v) for v in pc.values()])
    k = min((len(v) for v in pc.values()), default=0)
    ic = _bootstrap(_matriz(pc, list(pc))) if pc else (float("nan"), float("nan"))
    return {"media": float(taxas.mean()) if len(taxas) else float("nan"), "ic": ic,
            "pass_k": float(np.mean([all(v) for v in pc.values()])) if pc else float("nan"), "k": k,
            "instaveis": sorted((i for i, v in pc.items() if 0 < sum(v) < len(v)),
                                key=lambda i: abs(np.mean(pc[i]) - 0.5)),     # o mais instável primeiro
            "casos": len(pc)}


def _percentil(xs, p):
    return float(np.percentile(xs, p)) if len(xs) else float("nan")


def slis(rodada: dict) -> dict:
    """Os indicadores de nível de serviço (SLIs) de uma rodada."""
    ls = rodada["linhas"]
    n = len(ls)
    seg = [l["segundos"] for l in ls]
    custo = sum(l["custo_usd"] for l in ls)
    com_gab = [l for l in ls if l["acertou"] is not None]
    acertos = sum(bool(l["acertou"]) for l in com_gab)
    julgadas = [l for l in ls if "juiz_evidencia" in l]
    out = {
        "acerto": acertos / len(com_gab) if com_gab else None,
        "resolvidos": sum(l["desfecho"] == "responder" for l in ls) / n,
        "escalados": sum(l["desfecho"] == "escalar" for l in ls) / n,
        "nao_sei": sum(l["desfecho"] == "nao_sei" for l in ls) / n,
        "invalidos": sum(l["desfecho"] == "invalido" for l in ls) / n,
        "bateu_limite": sum(l["bateu_limite"] for l in ls) / n,
        "p50_segundos": _percentil(seg, 50), "p95_segundos": _percentil(seg, 95),
        "chamadas_por_atendimento": sum(l["chamadas_modelo"] for l in ls) / n,
        "tokens_por_atendimento": sum(l["tokens_entrada"] + l["tokens_saida"] for l in ls) / n,
        "custo_por_atendimento": custo / n,
        "custo_por_acerto": (sum(l["custo_usd"] for l in com_gab) / acertos) if acertos else None,
        "aprovado_pelo_juiz": (sum(l["juiz_evidencia"]["aprovado"] for l in julgadas) / len(julgadas)) if julgadas else None,
        "atendimentos": n,
    }
    return out


def placar(*rodadas: dict) -> list[dict]:
    """Uma linha por versão: acerto com intervalo, pass^k, casos instáveis, custo e latência."""
    linhas = []
    for r in rodadas:
        a, s = acerto(r), slis(r)
        linhas.append({
            "versão": r["nome"],
            "acerto": f"{a['media']:.0%}" if a["casos"] else "-",
            "IC 90%": f"{a['ic'][0]:.0%}–{a['ic'][1]:.0%}" if a["casos"] else "-",
            f"pass^{a['k']}": f"{a['pass_k']:.0%}" if a["casos"] else "-",
            "instáveis": f"{len(a['instaveis'])}/{a['casos']}" if a["casos"] else "-",
            "US$/atend.": f"{s['custo_por_atendimento']:.5f}",
            "US$/acerto": f"{s['custo_por_acerto']:.5f}" if s["custo_por_acerto"] else "-",
            "p95 (s)": f"{s['p95_segundos']:.1f}",
            "loops": f"{s['bateu_limite']:.0%}",
        })
    _imprimir(linhas)
    return linhas


def _imprimir(linhas: list[dict]) -> None:
    if not linhas:
        return
    cols = list(linhas[0])
    larg = {c: max(len(c), *(len(str(l[c])) for l in linhas)) for c in cols}
    print("  ".join(c.ljust(larg[c]) for c in cols))
    for l in linhas:
        print("  ".join(str(l[c]).ljust(larg[c]) for c in cols))


def variacoes(rodada: dict, caso_id: str, largura: int = 150) -> None:
    """O mesmo caso, amostra por amostra: a mesma pergunta, com o mesmo prompt, respondida várias vezes."""
    ls = [l for l in rodada["linhas"] if l["id"] == caso_id]
    print(f"{caso_id} · {ls[0]['pergunta']}\n{rodada['nome']}\n")
    for l in ls:
        marca = {True: "ok ", False: "ERR", None: "   "}[l["acertou"]]
        texto = " ".join(l["resposta"].split())
        print(f"  amostra {l['amostra']}  {marca}  {l['desfecho']:<10} {l['chamadas_modelo']} chamadas · "
              f"{l['segundos']:.1f}s · fontes {l['fontes']}")
        print(f"             “{texto[:largura]}{'…' if len(texto) > largura else ''}”")
        if l["acertou"] is False:
            print(f"             régua: {l['motivo']}")


def instaveis(rodada: dict) -> None:
    """Os casos que às vezes acertam e às vezes erram: o lugar onde o não-determinismo aparece."""
    pc = _por_caso(rodada)
    inst = {i: v for i, v in pc.items() if 0 < sum(v) < len(v)}
    print(f"{len(inst)} de {len(pc)} casos são instáveis em {rodada['nome']}:")
    for i, v in sorted(inst.items(), key=lambda x: sum(x[1])):
        print(f"  {i:<4}{''.join('●' if x else '○' for x in v)}  {sum(v)}/{len(v)}")


def _comparar_taxas(a: dict, b: dict) -> tuple[float, tuple[float, float], list]:
    pa, pb = _por_caso(a), _por_caso(b)
    ids = [i for i in pa if i in pb]
    deltas = np.array([np.mean(pb[i]) - np.mean(pa[i]) for i in ids])
    ic = _bootstrap(_matriz(pa, ids), _matriz(pb, ids))
    return float(deltas.mean()), ic, [(i, np.mean(pa[i]), np.mean(pb[i])) for i in ids]


def teste_aa(rodada: dict, mostrar: bool = True) -> list[float]:
    """Teste A/A: a mesma versão contra ela mesma. Cada amostra é "rodar a suíte uma vez".

    Se rodar a mesma versão duas vezes já muda o placar em X pontos, uma mudança de X pontos entre
    duas versões não prova nada. Devolve as diferenças de acerto entre todos os pares de amostras.
    """
    amostras = sorted({l["amostra"] for l in rodada["linhas"]})
    por_amostra = {a: acerto(recorte(rodada, [a]))["media"] for a in amostras}
    difs = [por_amostra[j] - por_amostra[i] for n, i in enumerate(amostras) for j in amostras[n + 1:]]
    if mostrar:
        print(f"{rodada['nome']}: a suíte rodada {len(amostras)} vezes, sem mudar NADA\n")
        for a, m in por_amostra.items():
            print(f"  rodada {a + 1}: acerto {m:.0%}  {'█' * round(m * 40)}")
        print(f"\n  entre duas rodadas quaisquer, o acerto mudou até {max(abs(d) for d in difs):.0%} "
              f"(em média {np.mean(np.abs(difs)):.0%}), só por acaso")
    return difs


def comparar(base: dict, nova: dict, limiar: float = 0.4, mostrar: bool = True) -> dict:
    """A nova versão é melhor, pior, ou não dá para dizer? Diferença por caso, pareada, com intervalo de 90%.

    Veredito: "regressão" se o intervalo inteiro está abaixo de zero, "melhora" se está acima,
    e "não dá para afirmar" se o intervalo cruza o zero. Lista os casos que mudaram pelo menos `limiar`.
    """
    media, ic, porcaso = _comparar_taxas(base, nova)
    if ic[1] < 0:
        veredito = "regressão"
    elif ic[0] > 0:
        veredito = "melhora"
    else:
        veredito = "não dá para afirmar"
    piores = [(i, x, y) for i, x, y in porcaso if y - x <= -limiar]
    melhores = [(i, x, y) for i, x, y in porcaso if y - x >= limiar]
    if mostrar:
        print(f"{base['nome']}  →  {nova['nome']}")
        print(f"  diferença média de acerto: {media:+.0%}   (intervalo de 90%: {ic[0]:+.0%} a {ic[1]:+.0%})")
        print(f"  veredito: {veredito.upper()}\n")
        if len(porcaso) < 15:
            print(f"  atenção: só {len(porcaso)} casos. Com tão poucos, o intervalo é frágil: um caso a mais ou a menos "
                  "muda o veredito.\n")
        for titulo, lista in (("pioraram", piores), ("melhoraram", melhores)):
            if lista:
                print(f"  casos que {titulo}:")
                for i, x, y in lista:
                    print(f"    {i:<4}{x:.0%} → {y:.0%}")
        if not piores and not melhores:
            print("  nenhum caso mudou de forma consistente")
    return {"media": media, "ic": ic, "veredito": veredito, "piores": [p[0] for p in piores],
            "melhores": [m[0] for m in melhores]}


# ======================================================================= observabilidade

def _linha(rodada: dict, caso_id: str, amostra: int = 0) -> dict:
    for l in rodada["linhas"]:
        if l["id"] == caso_id and l["amostra"] == amostra:
            return l
    raise KeyError(f"{caso_id} (amostra {amostra}) não está em {rodada['nome']}")


def mostrar_trace(rodada: dict, caso_id: str, amostra: int = 0, completo: bool = False) -> None:
    """O trace da Aula 4, para uma amostra."""
    ma.mostrar_trace({**rodada, "linhas": [_linha(rodada, caso_id, amostra)]}, caso_id, completo)


def spans(linha: dict) -> list[dict]:
    """O trace como spans: cada chamada ao modelo e cada busca vira um intervalo no tempo, com custo.

    É o formato das plataformas de observabilidade (Langfuse, LangSmith, OpenTelemetry): um span raiz
    para o atendimento e, dentro dele, um span por passo. Os segundos do modelo são os da gravação.
    """
    out, t, passo = [], 0.0, 0
    for e in linha["trace"]:
        if e["evento"] == "modelo":
            passo += 1
            seg = e.get("segundos", 0.0)
            custo = (e["tokens_entrada"] * medidor.PRECO_ENTRADA + e["tokens_saida"] * medidor.PRECO_SAIDA) / 1e6
            out.append({"nome": f"modelo · passo {passo} · pediu {e['detalhe']}", "tipo": "modelo",
                        "inicio": t, "fim": t + seg, "tokens": e["tokens_entrada"] + e["tokens_saida"],
                        "custo_usd": custo})
            t += seg
        elif e["evento"] == "ferramenta":
            seg = e.get("segundos", 0.0)
            try:
                args = json.loads(e["detalhe"].split("(", 1)[1][:-1])
                rotulo = args.get("pergunta", "") + (f" · {args['espaco']}" if args.get("espaco") else "")
            except (ValueError, IndexError):
                rotulo = e["detalhe"]
            out.append({"nome": f"busca · {rotulo[:60]}", "tipo": "ferramenta",
                        "inicio": t, "fim": t + seg, "tokens": 0, "custo_usd": 0.0, "devolveu": e["devolveu"]})
            t += seg
    raiz = {"nome": f"atendimento {linha['id']} · {linha['desfecho']}", "tipo": "atendimento", "inicio": 0.0,
            "fim": t, "tokens": sum(s["tokens"] for s in out), "custo_usd": sum(s["custo_usd"] for s in out)}
    return [raiz] + out


def cascata(rodada: dict, caso_id: str, amostra: int = 0, grafico: bool = True) -> list[dict]:
    """O atendimento como cascata de spans (waterfall): onde foi o tempo, onde foi o dinheiro."""
    _ativar(VERSOES[rodada["versao"]]["gravacao"])        # o preço por token da versão
    l = _linha(rodada, caso_id, amostra)
    ss = spans(l)
    print(f"{caso_id} · amostra {amostra} · {rodada['nome']} · {'ACERTOU' if l['acertou'] else 'ERROU' if l['acertou'] is False else 'sem gabarito'}")
    print(f"{l['pergunta']}\n")
    print(f"  {'span':<70}{'início':>8}{'duração':>9}{'tokens':>8}{'US$':>10}")
    for i, s in enumerate(ss):
        recuo = "" if i == 0 else "  └ "
        dur = s["fim"] - s["inicio"]
        dur_txt = f"{dur:.2f}s" if dur >= 0.01 else f"{dur * 1000:.1f}ms"
        print(f"  {(recuo + s['nome'])[:70]:<70}{s['inicio']:>7.2f}s{dur_txt:>9}"
              f"{s['tokens']:>8}{s['custo_usd']:>10.5f}")
    if grafico:
        _desenhar_cascata(ss, f"{caso_id} · {rodada['nome']}")
    return ss


def _eixos_limpos(ax):
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRADE)
    ax.tick_params(colors=TINTA_2, labelsize=9, length=0)
    ax.set_facecolor(FUNDO)


def _desenhar_cascata(ss: list[dict], titulo: str) -> None:
    import matplotlib.pyplot as plt
    cores = {"atendimento": "#9a9893", "modelo": COR["v1"], "ferramenta": COR["v3"]}
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(ss) + 1.1), facecolor=FUNDO)
    for i, s in enumerate(ss):
        largura = max(s["fim"] - s["inicio"], 0.02)
        ax.barh(i, largura, left=s["inicio"], height=0.62, color=cores[s["tipo"]])
        dur = s["fim"] - s["inicio"]
        ax.text(s["inicio"] + largura + 0.05, i, f"{dur:.2f}s" if dur >= 0.01 else f"{dur * 1000:.1f} ms",
                va="center", fontsize=8.5, color=TINTA_2)
    ax.set_yticks(range(len(ss)), [s["nome"][:46] for s in ss], fontsize=8.5, color=TINTA)
    ax.invert_yaxis()
    ax.set_xlabel("segundos desde o início do atendimento", color=TINTA_2, fontsize=9)
    ax.set_title(titulo, loc="left", fontsize=11, color=TINTA, pad=26)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=cores["modelo"], label="chamada ao modelo"),
                       Patch(color=cores["ferramenta"], label="busca")], frameon=False, fontsize=8.5,
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    ax.set_xlim(0, ss[0]["fim"] * 1.12 + 0.1)
    _eixos_limpos(ax)
    ax.grid(axis="x", color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.show()


def painel(*rodadas: dict) -> None:
    """O painel do agente: qualidade, custo, latência e loops, uma cor por versão."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    global _pct
    _pct = FuncFormatter(lambda x, _: f"{x:.0%}")
    fig, eixos = plt.subplots(2, 2, figsize=(11, 6.6), facecolor=FUNDO)
    nomes = [r["nome"] for r in rodadas]
    cores = [COR.get(r["versao"], "#9a9893") for r in rodadas]
    ys = np.arange(len(rodadas))

    ax = eixos[0, 0]                                         # acerto com intervalo
    for y, r, c in zip(ys, rodadas, cores):
        a = acerto(r)
        ax.plot([a["ic"][0], a["ic"][1]], [y, y], color=c, linewidth=2)
        ax.plot(a["media"], y, "o", color=c, markersize=9, markeredgecolor=FUNDO, markeredgewidth=2)
        ax.text(a["ic"][1] + 0.015, y, f"{a['media']:.0%}", va="center", fontsize=9, color=TINTA)
    ax.set_xlim(0, 1.1)
    ax.xaxis.set_major_formatter(_pct)
    ax.set_title("acerto (régua), com intervalo de 90%", loc="left", fontsize=10, color=TINTA)

    ax = eixos[0, 1]                                         # custo por acerto
    valores = [(slis(r)["custo_por_acerto"] or 0) * 1000 for r in rodadas]
    ax.barh(ys, valores, color=cores, height=0.55)
    for y, v in zip(ys, valores):
        ax.text(v, y, f"  US$ {v:.2f}", va="center", fontsize=9, color=TINTA)
    ax.set_xlim(0, max(valores + [1e-9]) * 1.4)
    ax.set_title("custo de mil respostas certas (US$)", loc="left", fontsize=10, color=TINTA)

    ax = eixos[1, 0]                                         # latência
    for y, r, c in zip(ys, rodadas, cores):
        seg = np.array([l["segundos"] for l in r["linhas"]])
        jitter = np.random.default_rng(3).uniform(-0.18, 0.18, len(seg))
        ax.scatter(seg, y + jitter, s=9, color=c, alpha=0.45, linewidths=0)
        p95 = np.percentile(seg, 95)
        ax.plot([p95, p95], [y - 0.3, y + 0.3], color=TINTA, linewidth=2)
        ax.text(p95, y - 0.34, f"p95 {p95:.1f}s", ha="center", va="bottom", fontsize=8.5, color=TINTA,
                bbox={"facecolor": FUNDO, "edgecolor": "none", "pad": 1})
    ax.set_title("latência por atendimento (cada ponto é um atendimento)", loc="left", fontsize=10, color=TINTA)
    ax.set_xlabel("segundos", fontsize=9, color=TINTA_2)

    ax = eixos[1, 1]                                         # loops
    valores = [slis(r)["bateu_limite"] for r in rodadas]
    ax.barh(ys, valores, color=cores, height=0.55)
    for y, v in zip(ys, valores):
        ax.text(v, y, f"  {v:.0%}", va="center", fontsize=9, color=TINTA)
    ax.set_xlim(0, max(valores + [0.05]) * 1.6)
    ax.xaxis.set_major_formatter(_pct)
    ax.set_title(f"atendimentos que bateram no limite de {ma.MAX_PASSOS} passos", loc="left", fontsize=10, color=TINTA)

    for ax in eixos.flat:
        ax.set_yticks(ys, nomes if ax in (eixos[0, 0], eixos[1, 0]) else [""] * len(ys), fontsize=9, color=TINTA)
        ax.invert_yaxis()
        _eixos_limpos(ax)
        ax.grid(axis="x", color=GRADE, linewidth=0.8)
        ax.set_axisbelow(True)
    plt.tight_layout()
    plt.show()


def mapa_de_casos(*rodadas: dict) -> None:
    """Caso por caso, versão por versão: quantas das amostras acertaram. É onde a média esconde as coisas."""
    import matplotlib.pyplot as plt
    pcs = [_por_caso(r) for r in rodadas]
    ids = [i for i in pcs[0] if all(i in pc for pc in pcs)]
    m = np.array([[np.mean(pc[i]) for pc in pcs] for i in ids])
    fig, ax = plt.subplots(figsize=(1.6 + 1.7 * len(rodadas), 0.3 * len(ids) + 1.2), facecolor=FUNDO)
    ax.imshow(m, cmap="Blues", vmin=-0.15, vmax=1.05, aspect="auto")
    for y in range(len(ids)):
        for x in range(len(rodadas)):
            v = pcs[x][ids[y]]
            ax.text(x, y, f"{sum(v)}/{len(v)}", ha="center", va="center", fontsize=8.5,
                    color=FUNDO if np.mean(v) > 0.55 else TINTA)
    ax.set_xticks(range(len(rodadas)), [r["nome"].split(" (")[0] for r in rodadas], fontsize=9, color=TINTA)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(ids)), ids, fontsize=8.5, color=TINTA)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("amostras que acertaram, por caso", loc="left", fontsize=10, color=TINTA, pad=26)
    plt.tight_layout()
    plt.show()


# ======================================================================= SLI, SLO e o gate de deploy

SLIS = {
    "acerto": ("maior", "fração dos atendimentos do golden set que a régua aprova"),
    "aprovado_pelo_juiz": ("maior", "fração aprovada pelo juiz com evidência (dá para medir em produção)"),
    "resolvidos": ("maior", "fração encerrada com resposta (desfecho 'responder')"),
    "escalados": ("menor", "fração encaminhada ao RH"),
    "nao_sei": ("menor", "fração encerrada com 'não sei'"),
    "invalidos": ("menor", "fração com saída fora do contrato"),
    "bateu_limite": ("menor", f"fração que bateu no limite de {ma.MAX_PASSOS} passos (loop)"),
    "p50_segundos": ("menor", "latência mediana, em segundos"),
    "p95_segundos": ("menor", "latência do percentil 95, em segundos"),
    "chamadas_por_atendimento": ("menor", "chamadas ao modelo por atendimento"),
    "custo_por_atendimento": ("menor", "dólares por atendimento"),
    "custo_por_acerto": ("menor", "dólares por resposta certa (custo por tarefa resolvida)"),
}


def listar_slis() -> None:
    for nome, (sentido, desc) in SLIS.items():
        print(f"  {nome:<26}{'↑' if sentido == 'maior' else '↓'}  {desc}")


def checar_slos(slos: dict, *rodadas: dict) -> dict[str, bool]:
    """O gate de deploy: cada versão cumpre cada SLO? slos = {"acerto": 0.85, "p95_segundos": 8, ...}.

    O sentido de cada SLI (quanto maior melhor, ou quanto menor) vem de SLIS.
    Devolve, para cada versão, se ela passou em todos os SLOs.
    """
    medidos = [slis(r) for r in rodadas]
    larg = max(len(r["nome"]) for r in rodadas) + 2
    print(f"{'SLO':<34}" + "".join(f"{r['nome'][:larg - 2]:<{larg}}" for r in rodadas))
    passou = {r["nome"]: True for r in rodadas}
    for nome, alvo in slos.items():
        sentido = SLIS[nome][0]
        simbolo = "≥" if sentido == "maior" else "≤"
        celulas = []
        for r, m in zip(rodadas, medidos):
            v = m[nome]
            if v is None:
                celulas.append("sem dado".ljust(larg))
                continue
            ok = v >= alvo if sentido == "maior" else v <= alvo
            passou[r["nome"]] &= ok
            celulas.append(f"{'✔ passa' if ok else '✘ FALHA'} ({_fmt(nome, v)})".ljust(larg))
        print(f"{nome + ' ' + simbolo + ' ' + _fmt(nome, alvo):<34}" + "".join(celulas))
    print(f"{'pode ir para produção?':<34}" + "".join(
        f"{'SIM' if passou[r['nome']] else 'NÃO':<{larg}}" for r in rodadas))
    return passou


def _fmt(nome: str, v: float) -> str:
    if nome.startswith("custo"):
        return f"US$ {v:.5f}"
    if nome.endswith("segundos"):
        return f"{v:.1f}s"
    if nome in ("chamadas_por_atendimento", "tokens_por_atendimento"):
        return f"{v:.1f}"
    return f"{v:.0%}"


# ======================================================================= online: sem gabarito

def online(rodada: dict) -> None:
    """O que dá para medir em produção, onde não há gabarito: desfechos, loops, custo, latência e o juiz."""
    s = slis(rodada)
    print(f"{rodada['nome']} · {s['atendimentos']} atendimentos, sem gabarito\n")
    print(f"  encerrados com resposta  {s['resolvidos']:.0%}")
    print(f"  encaminhados ao RH       {s['escalados']:.0%}")
    print(f"  'não sei'                {s['nao_sei']:.0%}")
    print(f"  saída inválida           {s['invalidos']:.0%}")
    print(f"  bateram no limite        {s['bateu_limite']:.0%}")
    print(f"  p50 / p95                {s['p50_segundos']:.1f}s / {s['p95_segundos']:.1f}s")
    print(f"  custo por atendimento    US$ {s['custo_por_atendimento']:.5f}")
    if s["aprovado_pelo_juiz"] is not None:
        print(f"  aprovado pelo juiz       {s['aprovado_pelo_juiz']:.0%}   (o único sinal de QUALIDADE aqui)")


# ======================================================================= golden set do grupo

def mostrar_pagina(pagina_id: str) -> None:
    """Uma página da wiki da Aurora, seção por seção. Para escrever o gabarito, leia a fonte."""
    chunks = [c for c in busca.indice().chunks if c["id"] == pagina_id]
    if not chunks:
        ids = sorted({c["id"] for c in busca.indice().chunks})
        raise KeyError(f"Não existe a página '{pagina_id}'. Páginas: {', '.join(ids)}")
    c0 = chunks[0]
    print(f"{pagina_id} · {c0['titulo']} · {c0['espaco']} · {c0['autoridade']} · vigência {c0['vigencia']}\n")
    for c in chunks:
        print(" ".join(c["texto"].split()))
        print()


def paginas() -> None:
    """Todas as páginas da wiki, por espaço."""
    vistas = {}
    for c in busca.indice().chunks:
        vistas.setdefault(c["id"], c)
    for pid, c in sorted(vistas.items(), key=lambda x: (x[1]["espaco"], x[0])):
        print(f"  {c['espaco']:<17}{pid:<32}{c['titulo']}  ({c['autoridade']}, {c['vigencia']})")


def caso_da_equipe(caso_id: str, desfecho: str, fontes: list[str] | None = None,
                   contem: list[str] | None = None, nao_contem: list[str] | None = None) -> dict:
    """Transforma uma pergunta do banco de produção num caso de golden set, com o gabarito do grupo.

    desfecho:   "responder", "nao_sei" ou "escalar"
    fontes:     ids das páginas que a resposta PRECISA citar
    contem:     a resposta precisa trazer pelo menos um destes textos (o valor certo, escrito de jeitos diferentes)
    nao_contem: a resposta NÃO pode trazer nenhum destes (o valor errado, de uma versão antiga, por exemplo)
    """
    pergunta = next((b["pergunta"] for b in carregar_banco() if b["id"] == caso_id), None)
    if pergunta is None:
        raise KeyError(f"{caso_id} não está no banco de produção")
    caso = {"id": caso_id, "categoria": "do grupo", "pergunta": pergunta,
            "esperado": {"desfecho": desfecho, "fontes_obrigatorias": list(fontes or [])}}
    if contem:
        caso["resposta_contem_algum"] = list(contem)
    if nao_contem:
        caso["resposta_nao_contem"] = list(nao_contem)
    return caso


def conferir_gabarito(casos: list[dict]) -> bool:
    """Confere o formato do gabarito: desfecho válido, fontes que existem, nada contraditório."""
    ids = {c["id"] for c in busca.indice().chunks}
    ok = True
    for c in casos:
        e = c["esperado"]
        problemas = []
        if e["desfecho"] not in ("responder", "nao_sei", "escalar"):
            problemas.append(f"desfecho '{e['desfecho']}' não existe")
        problemas += [f"a página '{f}' não existe" for f in e["fontes_obrigatorias"] if f not in ids]
        if e["desfecho"] != "responder" and (e["fontes_obrigatorias"] or c.get("resposta_contem_algum")):
            problemas.append("com 'nao_sei' ou 'escalar', a régua só olha o desfecho: tire fontes e 'contem'")
        if e["desfecho"] == "responder" and not c.get("resposta_contem_algum") and e["fontes_obrigatorias"]:
            problemas.append("sem 'contem', a régua aceita qualquer texto que cite a fonte (é isso mesmo?)")
        ok &= not any("não existe" in p for p in problemas)
        print(f"  {c['id']:<4}{'ok' if not problemas else '; '.join(problemas)}")
    return ok


def suspeitos(*rodadas: dict) -> None:
    """Casos que NENHUMA versão acerta em nenhuma amostra. Antes de culpar o agente, confira o gabarito."""
    pcs = [_por_caso(r) for r in rodadas]
    ids = set.intersection(*(set(pc) for pc in pcs))
    zerados = sorted(i for i in ids if all(sum(pc[i]) == 0 for pc in pcs))
    if not zerados:
        print("Nenhum caso zerado em todas as versões.")
        return
    print("Zerados em todas as versões (o gabarito pode estar errado):")
    for i in zerados:
        l = next(l for l in rodadas[0]["linhas"] if l["id"] == i)
        print(f"  {i:<4}régua: {l['motivo']}  ·  resposta: “{' '.join(l['resposta'].split())[:120]}”")


# ======================================================================= para a nota

def tabela_markdown(*rodadas: dict) -> str:
    """O placar em markdown, para colar na NOTA-EVAL.md."""
    linhas = []
    for r in rodadas:
        a, s = acerto(r), slis(r)
        linhas.append([r["nome"], f"{a['media']:.0%} ({a['ic'][0]:.0%}–{a['ic'][1]:.0%})", f"{a['pass_k']:.0%}",
                       f"{len(a['instaveis'])}/{a['casos']}", f"{s['custo_por_acerto'] or 0:.5f}",
                       f"{s['p95_segundos']:.1f}", f"{s['bateu_limite']:.0%}"])
    cab = ["versão", "acerto (IC 90%)", f"pass^{AMOSTRAS}", "instáveis", "US$/acerto", "p95 (s)", "loops"]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    return "\n".join(saida + ["| " + " | ".join(l) + " |" for l in linhas])


def gabarito_markdown(casos: list[dict]) -> str:
    """O golden set do grupo em markdown."""
    saida = ["| id | pergunta | desfecho | fontes | contém | não contém |", "|---|---|---|---|---|---|"]
    for c in casos:
        e = c["esperado"]
        saida.append(f"| {c['id']} | {c['pergunta']} | {e['desfecho']} | {', '.join(e['fontes_obrigatorias'])} | "
                     f"{' / '.join(c.get('resposta_contem_algum', []))} | {' / '.join(c.get('resposta_nao_contem', []))} |")
    return "\n".join(saida)


def slos_markdown(slos: dict, *rodadas: dict) -> str:
    """O gate de SLOs em markdown, para a nota."""
    medidos = [slis(r) for r in rodadas]
    saida = ["| SLO | " + " | ".join(r["nome"] for r in rodadas) + " |", "|---|" + "---|" * len(rodadas)]
    for nome, alvo in slos.items():
        sentido = SLIS[nome][0]
        celulas = []
        for m in medidos:
            v = m[nome]
            ok = v is not None and (v >= alvo if sentido == "maior" else v <= alvo)
            celulas.append("sem dado" if v is None else f"{'passa' if ok else '**FALHA**'} ({_fmt(nome, v)})")
        saida.append(f"| {nome} {'≥' if sentido == 'maior' else '≤'} {_fmt(nome, alvo)} | " + " | ".join(celulas) + " |")
    return "\n".join(saida)


def mais_lento(rodada: dict) -> tuple[str, int]:
    """O atendimento mais demorado da rodada: (id do caso, amostra). Bom candidato a abrir na cascata."""
    l = max(rodada["linhas"], key=lambda x: x["segundos"])
    return l["id"], l["amostra"]


def resumo_banco(rodada: dict) -> None:
    """O banco de produção, pergunta por pergunta: como a versão encerrou cada uma nas amostras, e o juiz."""
    por_id: dict[str, list[dict]] = {}
    for l in rodada["linhas"]:
        por_id.setdefault(l["id"], []).append(l)
    print(f"{'id':<5}{'desfechos nas amostras':<34}{'juiz':<7}{'pergunta'}")
    for i, ls in por_id.items():
        cont: dict[str, int] = {}
        for l in ls:
            cont[l["desfecho"]] = cont.get(l["desfecho"], 0) + 1
        desf = " · ".join(f"{d} {n}" for d, n in sorted(cont.items(), key=lambda x: -x[1]))
        julg = [l["juiz_evidencia"]["aprovado"] for l in ls if "juiz_evidencia" in l]
        juiz = f"{sum(julg)}/{len(julg)}" if julg else "-"
        print(f"{i:<5}{desf:<34}{juiz:<7}{ls[0]['pergunta'][:70]}")