"""
agente_busca.py — as peças da demonstração do Encontro 3: o agente que decide buscar.

Usado pelos notebooks 03 (loop à mão) e 04 (LangChain). Os dois usam exatamente
a mesma busca, a mesma camada do Encontro 2, os mesmos casos e o mesmo placar.
Assim, a única diferença entre eles é o framework.

    buscar_politicas    a ferramenta de busca: a configuração final do notebook 01
    CONTRATOS           o contrato da ferramenta, no formato do Encontro 2
    plugar_na_camada    registra a ferramenta na camada.py do Encontro 2
    rodar_fixo          a busca roda sempre, antes do modelo (o "workflow")
    rodar               roda uma arquitetura nos casos e mede
    placar / detalhe    imprimem o resultado
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
for _p in (RAIZ, RAIZ / "encontro-02"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import camada                                    # noqa: E402  (a camada do Encontro 2)
import rag_aurora as r                           # noqa: E402
from comum import medidor, modelo                # noqa: E402
from comum.avaliar import avaliar as _avaliar_e1  # noqa: E402
from comum.resultado import Resultado            # noqa: E402


def _carregar(nome: str, arquivo: Path):
    spec = importlib.util.spec_from_file_location(nome, arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# As mesmas regras de resposta dos Encontros 1 e 2.
_politica = _carregar("politica_de_resposta_e1", RAIZ / "encontro-01" / "politica_de_resposta.py")
REGRAS, FORMATO_JSON = _politica.REGRAS, _politica.FORMATO_JSON

# As ferramentas de encerramento (responder, escalar_para_rh) do agente do Encontro 2.
ENCERRAMENTO = _carregar("agente_e2", RAIZ / "encontro-02" / "agente.py").ENCERRAMENTO

CASOS = PASTA / "casos-agente.json"
MAX_PASSOS = 8


def carregar_casos() -> list[dict]:
    return json.loads(CASOS.read_text(encoding="utf-8"))


# ============================================================== a busca

ESPACOS = ["wiki-rh", "wiki-ti", "wiki-beneficios", "wiki-financeiro"]
_indice: dict = {}


def preparar_indice(modelo_embeddings: str = r.MODELO_PADRAO) -> None:
    """Indexa a wiki uma vez: corte por estrutura, vetor + BM25. Leva alguns segundos."""
    if _indice:
        return
    chunks = r.chunks_por_estrutura(r.carregar_corpus())
    emb = r.Embeddings(modelo_embeddings)
    _indice.update(vet=r.IndiceVetorial(chunks, emb), lex=r.IndiceLexico(chunks))


def buscar_politicas(pergunta: str, espaco: str | None = None) -> dict:
    """A implementação da ferramenta: a configuração final do notebook 01.

    Híbrida (vetor + BM25), só fontes oficiais, só a versão vigente de cada política.
    Devolve o registro completo; a camada corta nos campos do contrato.
    """
    preparar_indice()
    candidatos = r.busca_hibrida(_indice["vet"], _indice["lex"], pergunta, k=18,
                                 filtro={"autoridade": "oficial"})
    if espaco:
        candidatos = [(c, s) for c, s in candidatos if c.metadata["espaco"] == espaco]
    melhores = r.so_a_versao_vigente(candidatos)[:3]
    return {"resultados": [{
        "id": c.metadata["id"],
        "titulo": c.metadata["titulo"],
        "secao": c.metadata.get("secao", ""),
        "espaco": c.metadata["espaco"],
        "vigencia": c.metadata["vigencia"],
        "autoridade": c.metadata["autoridade"],
        "chunk_id": c.metadata["chunk_id"],
        "relevancia": nota,
        "trecho": c.page_content,
    } for c, nota in melhores]}


NOME = "buscar_politicas"
CONTRATO = {
    "descricao": (
        "Busca nas políticas oficiais e vigentes da Aurora: RH, TI, benefícios e financeiro "
        "(viagens e reembolso). Devolve até 3 trechos, cada um com o id da página para citar "
        "como fonte. Use quando a resposta depende de uma regra da empresa. Pode buscar de novo "
        "com outras palavras se os trechos não responderem. Não use para cumprimentos, "
        "agradecimentos ou perguntas sobre o que você consegue fazer."
    ),
    "parametros": {
        "type": "object",
        "properties": {
            "pergunta": {"type": "string", "maxLength": 300,
                         "description": "O que buscar, com as palavras-chave da dúvida (códigos e números incluídos)."},
            "espaco": {"type": "string", "enum": ESPACOS,
                       "description": "Opcional: restringe a busca a um espaço da wiki."},
        },
        "required": ["pergunta"],
        "additionalProperties": False,
    },
    "saida": ["id", "titulo", "secao", "vigencia", "trecho"],
}
CONTRATOS = {NOME: CONTRATO}


def plugar_na_camada(implementacao=buscar_politicas) -> None:
    """Registra a ferramenta na camada do Encontro 2: mesma validação, mesmo corte, mesmo registro.

    O notebook 04 chama de novo com a implementação feita em LangChain: o contrato não muda.
    """
    camada.IMPLEMENTACOES = {**camada.IMPLEMENTACOES, NOME: implementacao}
    camada.CONTEXTO = {**camada.CONTEXTO, NOME: "busca"}


# ------------------------------------------------- busca na web (opcional)

def incluir_busca_web(contratos: dict) -> dict:
    """Acrescenta a busca na web do Encontro 2 ao catálogo (precisa de SERPER_API_KEY)."""
    busca_web = _carregar("busca_web", RAIZ / "encontro-02" / "mcp_aurora" / "busca_web.py")
    camada.IMPLEMENTACOES = {**camada.IMPLEMENTACOES, busca_web.NOME: busca_web.buscar_na_web}
    camada.CONTEXTO = {**camada.CONTEXTO, busca_web.NOME: "web"}
    return {**contratos, busca_web.NOME: busca_web.CONTRATO}


# ============================================================== arquitetura fixa

SISTEMA_FIXO = REGRAS + "\n\n" + FORMATO_JSON


def rodar_fixo(pergunta: str, registro: list) -> Resultado:
    """Busca fixa: o código busca sempre, coloca os trechos no prompt e o modelo responde uma vez."""
    trechos = camada.executar(NOME, {"pergunta": pergunta}, CONTRATOS, registro)
    mensagem = f"Documentos encontrados pela busca:\n{trechos}\n\nPergunta do colaborador: {pergunta}"
    resposta = modelo.chamar([modelo.mensagem_do_usuario(mensagem)], sistema=SISTEMA_FIXO)
    return Resultado.de_json(resposta.texto)


# ============================================================== medir

def avaliar(resultado: Resultado, caso: dict) -> tuple[bool, str]:
    """A régua dos Encontros 1 e 2 (desfecho e fontes) mais o valor certo na resposta."""
    ok, motivo = _avaliar_e1(resultado, caso)
    if not ok:
        return ok, motivo
    texto = resultado.resposta.lower()
    algum = caso.get("resposta_contem_algum")
    if algum and not any(a.lower() in texto for a in algum):
        return False, f"a resposta não traz {algum[0]!r}"
    errado = [a for a in caso.get("resposta_nao_contem", []) if a.lower() in texto]
    if errado:
        return False, f"a resposta traz {errado[0]!r}, que é o valor errado"
    return True, "ok"


def rodar(arquitetura, casos: list[dict], nome: str, contratos: dict | None = None) -> dict:
    """Roda arquitetura(pergunta, registro) -> Resultado em cada caso e mede."""
    linhas = []
    for caso in casos:
        medicao = medidor.zerar()
        registro: list = []
        inicio = time.perf_counter()
        try:
            resultado = arquitetura(caso["pergunta"], registro)
            ok, motivo = avaliar(resultado, caso)
        except Exception as erro:            # um caso que quebra não derruba a rodada
            resultado, ok, motivo = Resultado("invalido"), False, f"erro: {type(erro).__name__}: {erro}"
        linhas.append({
            "id": caso["id"], "categoria": caso["categoria"], "acertou": ok, "motivo": motivo,
            "desfecho": resultado.desfecho, "fontes": resultado.fontes, "resposta": resultado.resposta,
            "buscas": sum(1 for x in registro if x["ferramenta"] == NOME),
            "buscas_web": sum(1 for x in registro if x["ferramenta"] == "buscar_na_web"),
            "sequencia": [x["ferramenta"] + ("" if x["status"] == "ok" else "!" + x["erro"]) for x in registro],
            "chamadas_modelo": medicao.chamadas, "tokens_entrada": medicao.tokens_entrada,
            "tokens_saida": medicao.tokens_saida, "custo_usd": medicao.custo_usd,
            "segundos": time.perf_counter() - inicio,
        })
        print(f"  {caso['id']:<4}{'ok ' if ok else 'ERR'}  buscas={linhas[-1]['buscas']}  {motivo}")
    return {"nome": nome, "linhas": linhas}


def resumo(rodada: dict) -> dict:
    ls = rodada["linhas"]
    n = len(ls)
    acertos = sum(l["acertou"] for l in ls)
    custo = sum(l["custo_usd"] for l in ls)
    return {
        "arquitetura": rodada["nome"], "acertos": f"{acertos}/{n}",
        "buscas/caso": round(sum(l["buscas"] for l in ls) / n, 2),
        "chamadas ao modelo/caso": round(sum(l["chamadas_modelo"] for l in ls) / n, 2),
        "tokens/caso": round(sum(l["tokens_entrada"] + l["tokens_saida"] for l in ls) / n),
        "custo total (US$)": round(custo, 4),
        "custo/acerto (US$)": round(custo / acertos, 5) if acertos else None,
        "segundos/caso": round(sum(l["segundos"] for l in ls) / n, 1),
    }


def placar(*rodadas: dict) -> None:
    """Uma linha por arquitetura."""
    linhas = [resumo(x) for x in rodadas]
    cols = list(linhas[0])
    larg = {c: max(len(c), *(len(str(l[c])) for l in linhas)) for c in cols}
    print("  ".join(c.ljust(larg[c]) for c in cols))
    for l in linhas:
        print("  ".join(str(l[c]).ljust(larg[c]) for c in cols))


def detalhe(*rodadas: dict) -> None:
    """Caso a caso, lado a lado: acertou, buscas e o que deu errado."""
    print("caso  categoria     " + "".join(f"{x['nome'][:30]:<34}" for x in rodadas))
    for i, l0 in enumerate(rodadas[0]["linhas"]):
        celulas = []
        for x in rodadas:
            l = x["linhas"][i]
            marca = "ok " if l["acertou"] else "ERR"
            celulas.append(f"{marca} b={l['buscas']} {'' if l['acertou'] else l['motivo'][:20]}"[:32].ljust(34))
        print(f"{l0['id']:<6}{l0['categoria']:<14}" + "".join(celulas))


# ============================================================== guardar e comparar

RESULTADOS = PASTA / "resultados"


def salvar(*rodadas: dict) -> Path:
    """Guarda as rodadas em resultados/ (fora do Git), para o notebook 04 comparar."""
    RESULTADOS.mkdir(exist_ok=True)
    arquivo = RESULTADOS / f"agente-{time.strftime('%Y%m%d-%H%M%S')}.json"
    arquivo.write_text(json.dumps({"provedor": modelo.PROVEDOR, "modelo": modelo.MODELO,
                                   "rodadas": list(rodadas)}, ensure_ascii=False, indent=1), encoding="utf-8")
    return arquivo


def carregar_ultimas() -> list[dict]:
    """As rodadas salvas mais recentes (as do notebook 03), ou [] se não houver."""
    arquivos = sorted(RESULTADOS.glob("agente-*.json")) if RESULTADOS.exists() else []
    if not arquivos:
        return []
    dados = json.loads(arquivos[-1].read_text(encoding="utf-8"))
    return dados["rodadas"]
