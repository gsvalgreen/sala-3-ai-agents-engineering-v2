"""
multiagente.py — as peças do Encontro 4: quando dividir em vários agentes melhora, e quando só encarece.

Tudo aqui reaproveita o que a turma já construiu:
    a busca do Encontro 3 (busca.py), atrás do contrato e da camada do Encontro 2 (camada.py),
    as regras de resposta do Encontro 1 e as ferramentas de encerramento do Encontro 2.
A única coisa nova é a coordenação entre agentes. Assim, a diferença no placar vem dela.

Arquiteturas (cada uma é uma função  arquitetura(pergunta, registro, trace) -> Resultado)
    monolito()                       a linha de base: o agente da Aula 3, com a busca na wiki inteira
    roteador_especialistas(...)      um roteador escolhe UM especialista, que atende sozinho
    supervisor(...)                  um supervisor consulta quantos especialistas quiser e responde

O menu do hands-on (roteador_especialistas)
    roteador     "llm"   (um modelo decide)        | "regra" (palavras-chave, sem modelo)
    equipe       3 (rh+financeiro, ti, beneficios)  | 4 (rh, financeiro, ti, beneficios)
    handoff      "pergunta_original"                | "resumo_do_roteador"
    se_incerto   "seguir"                           | "agente_unico" (devolve ao monolito)

Medir
    rodar(arquitetura, casos)   roda e mede cada caso
    placar(...) / detalhe(...)  uma linha por arquitetura / caso a caso
    mostrar_trace(rodada, id)   abre a caixa: quem falou com quem, o que cada um recebeu, quanto custou
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
for _p in (RAIZ, RAIZ / "encontro-02", PASTA):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import busca                                       # noqa: E402  (a busca do Encontro 3, já indexada)
import camada                                      # noqa: E402  (a camada do Encontro 2)
from comum import medidor, modelo                  # noqa: E402
from comum.avaliar import avaliar as _avaliar_e1   # noqa: E402
from comum.resultado import Resultado              # noqa: E402


def _carregar(nome: str, arquivo: Path):
    spec = importlib.util.spec_from_file_location(nome, arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# As mesmas regras de resposta dos Encontros 1 a 3, e as ferramentas de encerramento do Encontro 2.
REGRAS = _carregar("politica_de_resposta_e1", RAIZ / "encontro-01" / "politica_de_resposta.py").REGRAS
ENCERRAMENTO = _carregar("agente_e2", RAIZ / "encontro-02" / "agente.py").ENCERRAMENTO

CASOS = PASTA / "casos.json"
REPLAY = PASTA / "dados" / "replay.jsonl"
MAX_PASSOS = 8


def carregar_casos() -> list[dict]:
    return json.loads(CASOS.read_text(encoding="utf-8"))


def preparar(modo: str | None = "usar", arquivo: Path | str = REPLAY) -> None:
    """Liga o replay e confere a busca. modo "usar" (turma), "gravar" (professor) ou None (ao vivo).

    A variável de ambiente AURORA_REPLAY_MODO, quando existe, vence o argumento: é assim que o
    preparo/gravar_replay.py roda os notebooks gravando, sem precisar editá-los.
    """
    modo = os.getenv("AURORA_REPLAY_MODO", modo) or None
    if modo:
        cab = modelo.replay(arquivo, modo)
        estado = modelo.estado_replay()
        print(f"Replay '{modo}': {estado['respostas_no_arquivo']} respostas gravadas"
              + (f" com {cab.get('modelo')} em {cab.get('criado_em')}" if cab else ""))
        if modo == "usar" and modelo.tem_credencial():
            print("Há chave configurada: o que não estiver gravado será chamado ao vivo, com custo.")
        elif modo == "usar":
            print("Sem chave: tudo vem da gravação, sem custo. Use as opções do menu do notebook.")
    else:
        modelo.replay(None)
        print(f"Ao vivo: {modelo.PROVEDOR} · {modelo.MODELO}")
    n = len(busca.indice().chunks)
    print(f"Busca: {n} trechos da wiki da Aurora, espaços {', '.join(busca.espacos())}")


def usar_chave(api_key: str, base_url: str = "https://openrouter.ai/api/v1", modelo_nome: str | None = None) -> None:
    """Para ir além do menu: libera chamadas ao vivo, com o mesmo modelo da gravação.

    O que estiver gravado continua vindo da gravação; só o que for novo chama a API, com custo.
    """
    os.environ.update(PROVEDOR="openai_compat", BASE_URL=base_url, API_KEY=api_key.strip())
    modelo.PROVEDOR = "openai_compat"
    modelo.MODELO = modelo_nome or modelo.estado_replay().get("modelo") or modelo.MODELO
    print(f"Chave configurada. Chamadas novas vão para {modelo.MODELO}, com custo.")


# ======================================================================= trace

def _evento(trace: list, agente: str, evento: str, detalhe: str = "", **extra) -> None:
    trace.append({"agente": agente, "evento": evento, "detalhe": detalhe, **extra})


def _chamar(trace: list, agente: str, mensagens: list, sistema: str, ferramentas: list,
            exigir: bool | str = True, max_tokens: int = 1024) -> modelo.Resposta:
    """Uma chamada ao modelo, registrada no trace com os tokens que ela gastou."""
    antes = medidor.atual()
    t_in, t_out = antes.tokens_entrada, antes.tokens_saida
    resposta = modelo.chamar(mensagens, sistema=sistema, ferramentas=ferramentas,
                             max_tokens=max_tokens, exigir_ferramenta=exigir)
    depois = medidor.atual()
    pediu = ", ".join(c.nome for c in resposta.chamadas) or "texto"
    _evento(trace, agente, "modelo", pediu, tokens_entrada=depois.tokens_entrada - t_in,
            tokens_saida=depois.tokens_saida - t_out)
    return resposta


# ======================================================================= ferramentas de busca

def _contrato_busca(descricao_area: str, com_espaco: bool, espacos: list[str]) -> dict:
    """O contrato do Encontro 3, com a área de cada agente escrita na descrição."""
    props = {"pergunta": {"type": "string", "maxLength": 300,
                          "description": "O que buscar, com as palavras-chave da dúvida (códigos e números incluídos)."}}
    if com_espaco:
        props["espaco"] = {"type": "string", "enum": espacos,
                           "description": "Opcional: restringe a busca a um espaço da wiki."}
    return {
        "descricao": (
            f"Busca nas políticas oficiais e vigentes da Aurora: {descricao_area}. Devolve até 3 trechos, "
            "cada um com o id da página para citar como fonte. Use quando a resposta depende de uma regra "
            "da empresa. Pode buscar de novo com outras palavras se os trechos não responderem. Não use para "
            "cumprimentos, agradecimentos ou perguntas sobre o que você consegue fazer."),
        "parametros": {"type": "object", "properties": props, "required": ["pergunta"],
                       "additionalProperties": False},
        "saida": ["id", "titulo", "secao", "vigencia", "trecho"],
    }


def _registrar_busca(nome: str, espacos: list[str] | None) -> None:
    """Registra na camada do Encontro 2 uma busca presa a alguns espaços da wiki."""
    if espacos is None:
        def implementacao(pergunta: str, espaco: str | None = None) -> dict:
            return {"resultados": busca.buscar(pergunta, espaco)}
    else:
        def implementacao(pergunta: str) -> dict:
            return {"resultados": busca.buscar(pergunta, espacos)}
    camada.IMPLEMENTACOES = {**camada.IMPLEMENTACOES, nome: implementacao}
    camada.CONTEXTO = {**camada.CONTEXTO, nome: "busca"}


# ======================================================================= o loop de um agente

def loop_agente(nome: str, pergunta: str, sistema: str, contratos: dict, registro: list, trace: list,
                max_passos: int = MAX_PASSOS) -> Resultado:
    """O loop dos Encontros 2 e 3: busca quando precisa e encerra com responder ou escalar_para_rh.

    exigir_ferramenta=True: a cada passo o modelo PRECISA chamar uma ferramenta, então ele nunca
    responde em texto solto e o contrato de saída é garantido pela API, não por uma frase no prompt.
    """
    ferramentas = camada.como_ferramentas(contratos) + ENCERRAMENTO
    mensagens = [modelo.mensagem_do_usuario(pergunta)]
    _evento(trace, nome, "recebeu", pergunta, sistema=sistema,
            ferramentas=[f["nome"] for f in ferramentas])

    for _ in range(max_passos):
        resposta = _chamar(trace, nome, mensagens, sistema, ferramentas)
        if not resposta.chamadas:
            return Resultado.de_json(resposta.texto)
        pares = []
        for chamada in resposta.chamadas:
            if chamada.nome == "responder":
                r = Resultado.de_dict(chamada.args)
                _evento(trace, nome, "encerrou", f"{r.desfecho} · fontes {r.fontes}", resposta=r.resposta)
                return r
            if chamada.nome == "escalar_para_rh":
                _evento(trace, nome, "encerrou", "escalar", resposta=chamada.args.get("motivo", ""))
                return Resultado("escalar", [], chamada.args.get("motivo", ""))
            texto = camada.executar(chamada.nome, chamada.args, contratos, registro)
            ids = sorted({r["id"] for r in json.loads(texto).get("resultados", [])}) if texto.startswith("{") else []
            _evento(trace, nome, "ferramenta", f"{chamada.nome}({json.dumps(chamada.args, ensure_ascii=False)})",
                    devolveu=ids)
            pares.append((chamada, texto))
        mensagens.append(modelo.mensagem_do_assistente(resposta))
        mensagens.append(modelo.mensagem_de_resultados(pares))

    _evento(trace, nome, "parou", f"passou de {max_passos} passos")
    return Resultado("escalar", [], f"Não concluí em {max_passos} passos. Encaminhado ao RH.")


# ======================================================================= arquitetura 1: o agente único

SISTEMA_MONOLITO = REGRAS + """

Você tem uma ferramenta de busca nas políticas da Aurora. Decida se precisa dela: busque quando a
resposta depende de uma regra da empresa, e não busque para cumprimentos ou agradecimentos.
Se os trechos não responderem, você pode buscar de novo com outras palavras.
Para encerrar, chame a ferramenta responder ou a ferramenta escalar_para_rh."""

TODOS_OS_ESPACOS = ["wiki-rh", "wiki-ti", "wiki-beneficios", "wiki-financeiro"]


def monolito():
    """O agente que decide buscar, do Encontro 3: um agente, uma busca na wiki inteira."""
    nome = "buscar_politicas"
    contratos = {nome: _contrato_busca("RH, TI, benefícios e financeiro (viagens e reembolso)", True,
                                       TODOS_OS_ESPACOS)}

    def arquitetura(pergunta, registro, trace):
        _registrar_busca(nome, None)
        _evento(trace, "agente único", "acessa", "todos os espaços", espacos=["*"])
        return loop_agente("agente único", pergunta, SISTEMA_MONOLITO, contratos, registro, trace)

    arquitetura.nome = "agente único (Aula 3)"
    arquitetura.config = {"arquitetura": "agente único"}
    return arquitetura


def pecas_do_agente_unico() -> tuple[str, dict, list]:
    """O prompt, os contratos e as ferramentas do agente único, para montá-lo em outro lugar.

    O notebook 03 usa estas peças para escrever o mesmo agente como um grafo em LangGraph.
    Devolve (sistema, contratos, ferramentas): os contratos vão para a camada; as ferramentas
    (busca + encerramento) vão para o modelo.
    """
    nome = "buscar_politicas"
    _registrar_busca(nome, None)
    contratos = {nome: _contrato_busca("RH, TI, benefícios e financeiro (viagens e reembolso)", True,
                                       TODOS_OS_ESPACOS)}
    return SISTEMA_MONOLITO, contratos, camada.como_ferramentas(contratos) + ENCERRAMENTO


# ======================================================================= os especialistas

# A descrição de cada especialista é o contrato que o roteador lê, como a descrição de uma
# ferramenta no Encontro 2. Estas são as descrições que um time escreveria na primeira vez.
AREAS = {
    "rh": {"titulo": "Pessoas & Cultura", "espacos": ["wiki-rh", "confluence-rh"],
           "descricao": "políticas de pessoas: férias, licenças, jornada e banco de horas, trabalho remoto, "
                        "desligamento, avaliação de desempenho, código de conduta e integração de novos colaboradores"},
    "ti": {"titulo": "TI", "espacos": ["wiki-ti"],
           "descricao": "suporte de TI: VPN e acesso remoto, códigos de erro, senhas e acesso a sistemas, "
                        "equipamentos e instalação de software"},
    "beneficios": {"titulo": "Benefícios", "espacos": ["wiki-beneficios"],
                   "descricao": "benefícios: plano de saúde, plano odontológico, vale-refeição, auxílio-creche e "
                                "demais auxílios, seguro de vida e programa de bem-estar (academia e terapia)"},
    "financeiro": {"titulo": "Financeiro", "espacos": ["wiki-financeiro"],
                   "descricao": "financeiro: viagens a trabalho, reembolso de despesas, adiantamento de viagem e "
                                "cartão corporativo"},
}
GERAL = {"titulo": "Recepção", "espacos": [],
         "descricao": "cumprimentos, agradecimentos e perguntas sobre o que o atendimento faz; não consulta políticas"}


def equipe(n: int = 3) -> dict:
    """Os especialistas de cada configuração. Com 3, o Financeiro fica dentro de RH."""
    if n == 4:
        times = {k: dict(v) for k, v in AREAS.items()}
    elif n == 3:
        times = {k: dict(v) for k, v in AREAS.items() if k != "financeiro"}
        times["rh"]["espacos"] = AREAS["rh"]["espacos"] + AREAS["financeiro"]["espacos"]
        times["rh"]["descricao"] += "; também " + AREAS["financeiro"]["descricao"].split(": ", 1)[1]
        times["rh"]["titulo"] = "Pessoas & Cultura e Financeiro"
    else:
        raise ValueError("equipe deve ser 3 ou 4")
    times["geral"] = dict(GERAL)
    return times


SISTEMA_ESPECIALISTA = REGRAS + """

Você é o especialista de {titulo} do atendimento interno da Aurora. Sua área: {descricao}.
Sua ferramenta de busca só enxerga estes espaços da wiki: {espacos}.
Busque antes de responder. Se a dúvida não for da sua área, ou se a busca não trouxer a informação,
use o desfecho "nao_sei" e diga que não encontrou isso na sua área.
Para encerrar, chame a ferramenta responder ou a ferramenta escalar_para_rh."""

SISTEMA_RECEPCAO = REGRAS + """

Você é a recepção do atendimento interno da Aurora. Responda cumprimentos e agradecimentos com
cordialidade e explique que o atendimento tira dúvidas de RH, TI, benefícios e financeiro.
Você não consulta nenhuma política: se a pessoa perguntou uma regra da empresa, use o desfecho "nao_sei".
Para encerrar, chame a ferramenta responder."""


def _sistema_de(nome: str, area: dict, extra: str = "") -> str:
    if nome == "geral":
        return SISTEMA_RECEPCAO + extra
    return SISTEMA_ESPECIALISTA.format(titulo=area["titulo"], descricao=area["descricao"],
                                       espacos=", ".join(area["espacos"])) + extra


def _contratos_de(nome: str, area: dict) -> dict:
    """Cada especialista tem a SUA busca: o filtro de espaço é o controle de acesso por fonte."""
    if not area["espacos"]:
        return {}
    return {f"buscar_politicas_{nome}": _contrato_busca(area["descricao"], False, area["espacos"])}


def especialista(nome: str, n_equipe: int = 3, extra_sistema: str = ""):
    """Um especialista sozinho, para olhar por dentro: especialista("ti")(pergunta, [], trace)."""
    area = equipe(n_equipe)[nome]
    contratos, sistema = _contratos_de(nome, area), _sistema_de(nome, area, extra_sistema)

    def atender(pergunta, registro, trace):
        if area["espacos"]:              # a busca deste especialista, presa aos espaços dele
            _registrar_busca(f"buscar_politicas_{nome}", area["espacos"])
        _evento(trace, f"especialista {nome}", "acessa", ", ".join(area["espacos"]) or "nenhum espaço",
                espacos=area["espacos"])
        return loop_agente(f"especialista {nome}", pergunta, sistema, contratos, registro, trace)

    atender.nome, atender.area = f"especialista {nome}", area
    return atender


# ======================================================================= o roteador

SISTEMA_ROTEADOR = """Você é o roteador do atendimento interno da Aurora Tecnologia.
Você não responde a dúvida: escolhe qual especialista vai atendê-la, e só um.

Especialistas:
{lista}

Chame a ferramenta encaminhar."""


def _ferramenta_encaminhar(times: dict) -> dict:
    return {
        "nome": "encaminhar",
        "descricao": "Encaminha a dúvida do colaborador para o especialista que vai atendê-la.",
        "parametros": {
            "type": "object",
            "properties": {
                "destino": {"type": "string", "enum": list(times)},
                "confianca": {"type": "string", "enum": ["alta", "media", "baixa"],
                              "description": "baixa quando a dúvida é ambígua ou parece de mais de uma área"},
                "motivo": {"type": "string", "description": "uma frase"},
                "pergunta_para_especialista": {
                    "type": "string",
                    "description": "a dúvida reescrita para o especialista, curta, só com o que importa"},
            },
            "required": ["destino", "confianca", "motivo", "pergunta_para_especialista"],
        },
    }


def rotear_com_llm(pergunta: str, times: dict, trace: list) -> dict:
    lista = "\n".join(f"- {k}: {v['descricao']}" for k, v in times.items())
    ferramenta = _ferramenta_encaminhar(times)
    resposta = _chamar(trace, "roteador", [modelo.mensagem_do_usuario(pergunta)], SISTEMA_ROTEADOR.format(lista=lista),
                       [ferramenta], exigir="encaminhar", max_tokens=400)
    args = resposta.chamadas[0].args if resposta.chamadas else {}
    destino = args.get("destino") if args.get("destino") in times else "geral"
    return {"destino": destino, "confianca": args.get("confianca", "baixa"), "motivo": args.get("motivo", ""),
            "pergunta_para_especialista": args.get("pergunta_para_especialista") or pergunta}


# A alternativa sem modelo: palavras-chave. É o workflow do Encontro 1, agora no papel de roteador.
PALAVRAS = {
    "rh": ["ferias", "licenca", "paternidade", "maternidade", "jornada", "banco de horas", "ponto", "home office",
           "remoto", "hibrido", "desligamento", "demissao", "conduta", "avaliacao", "desempenho", "integracao"],
    "ti": ["vpn", "senha", "acesso", "notebook", "computador", "equipamento", "software", "instalar", "erro",
           "sistema", "wi-fi", "wifi"],
    "beneficios": ["plano de saude", "odontologico", "dentista", "vale-refeicao", "vale refeicao", "creche",
                   "auxilio", "terapia", "psicolog", "academia", "seguro de vida", "bem-estar", "reembolso de consulta"],
    "financeiro": ["viagem", "viajar", "reembolso", "km", "quilometragem", "cartao corporativo", "adiantamento",
                   "hotel", "passagem", "despesa", "alimentacao"],
    "geral": ["bom dia", "boa tarde", "boa noite", "obrigad", "ola", "valeu", "consegue me ajudar"],
}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def rotear_com_regra(pergunta: str, times: dict, trace: list) -> dict:
    texto = _sem_acento(pergunta)
    pontos = {k: 0 for k in times}
    achadas = []
    for area, palavras in PALAVRAS.items():
        destino = area if area in times else "rh"          # com 3 especialistas, financeiro é do rh
        for p in palavras:
            if p in texto:
                pontos[destino] += 1
                achadas.append(p)
    ordem = sorted(pontos, key=lambda k: -pontos[k])
    melhor, segundo = ordem[0], ordem[1]
    if pontos[melhor] == 0:
        destino, confianca = "geral", "baixa"
    elif pontos[melhor] == pontos[segundo]:
        destino, confianca = melhor, "baixa"
    else:
        destino, confianca = melhor, "alta"
    _evento(trace, "roteador", "regra", f"palavras: {', '.join(achadas) or 'nenhuma'}",
            tokens_entrada=0, tokens_saida=0)
    return {"destino": destino, "confianca": confianca, "motivo": f"palavras: {achadas}",
            "pergunta_para_especialista": pergunta}


# ======================================================================= arquitetura 2: roteador + especialistas

MENU = {"roteador": ("llm", "regra"), "equipe": (3, 4),
        "handoff": ("pergunta_original", "resumo_do_roteador"), "se_incerto": ("seguir", "agente_unico")}


def roteador_especialistas(roteador: str = "llm", equipe_n: int = 3, handoff: str = "pergunta_original",
                           se_incerto: str = "seguir"):
    """Um roteador escolhe um especialista; o especialista atende sozinho, só com a sua parte da wiki."""
    for chave, valor in (("roteador", roteador), ("equipe", equipe_n), ("handoff", handoff),
                         ("se_incerto", se_incerto)):
        if valor not in MENU[chave]:
            raise ValueError(f"{chave} = {valor!r} não está no menu. Opções: {MENU[chave]}")
    if roteador == "regra" and handoff == "resumo_do_roteador":
        raise ValueError("O roteador por regra não reescreve a pergunta: use handoff='pergunta_original'.")

    times = equipe(equipe_n)
    atendentes = {nome: especialista(nome, equipe_n) for nome in times}
    unico = monolito()
    rotear = rotear_com_llm if roteador == "llm" else rotear_com_regra

    def arquitetura(pergunta, registro, trace):
        rota = rotear(pergunta, times, trace)
        _evento(trace, "roteador", "rota", f"→ {rota['destino']} (confiança {rota['confianca']})",
                motivo=rota["motivo"], destino=rota["destino"])
        if rota["confianca"] == "baixa" and se_incerto == "agente_unico":
            _evento(trace, "roteador", "handoff", "incerto: devolve ao agente único", texto=pergunta)
            return unico(pergunta, registro, trace)
        texto = pergunta if handoff == "pergunta_original" else rota["pergunta_para_especialista"]
        _evento(trace, "roteador", "handoff", f"→ especialista {rota['destino']}", texto=texto)
        return atendentes[rota["destino"]](texto, registro, trace)

    arquitetura.nome = (f"roteador {roteador} · {equipe_n} esp · "
                        f"{'original' if handoff == 'pergunta_original' else 'resumo'} · "
                        f"incerto→{'segue' if se_incerto == 'seguir' else 'único'}")
    arquitetura.config = {"arquitetura": "roteador + especialistas", "roteador": roteador, "equipe": equipe_n,
                          "handoff": handoff, "se_incerto": se_incerto}
    return arquitetura


def todas_as_configuracoes() -> list[dict]:
    """As combinações válidas do menu do hands-on (o professor grava todas)."""
    configs = []
    for r in MENU["roteador"]:
        for e in MENU["equipe"]:
            for h in MENU["handoff"]:
                for s in MENU["se_incerto"]:
                    if r == "regra" and h == "resumo_do_roteador":
                        continue
                    configs.append({"roteador": r, "equipe_n": e, "handoff": h, "se_incerto": s})
    return configs


# ======================================================================= arquitetura 3: supervisor

SISTEMA_SUPERVISOR = REGRAS + """

Você coordena o atendimento interno da Aurora. Você não busca nas políticas: quem busca são os
especialistas, e cada um só enxerga a sua parte da wiki. Você tem uma ferramenta para consultar cada um.
- Consulte o especialista de cada área de que a dúvida depende. Pode ser mais de um.
- Monte a resposta só com o que os especialistas trouxeram e cite as fontes que eles citaram.
- Se um especialista escalar para o RH, escale também.
- Cumprimentos e agradecimentos: responda direto, sem consultar ninguém.
Para encerrar, chame a ferramenta responder ou a ferramenta escalar_para_rh."""

# A variante frágil, para provocar a patologia: especialistas que devolvem e um supervisor que insiste.
FRAGIL_ESPECIALISTA = """
Se a dúvida tocar, mesmo de leve, em outra área além da sua, não responda nada: use o desfecho
"nao_sei" e peça ao supervisor que confirme antes com o especialista da outra área."""
FRAGIL_SUPERVISOR = """
Nunca encerre com "nao_sei". Se um especialista pedir confirmação de outra área, consulte essa outra
área e depois volte ao primeiro especialista com o que ela disse. Repita até alguém responder."""


def supervisor(equipe_n: int = 3, max_passos: int = MAX_PASSOS, fragil: bool = False):
    """O supervisor chama especialistas como ferramentas e compõe a resposta final."""
    times = {k: v for k, v in equipe(equipe_n).items() if k != "geral"}
    atendentes = {nome: especialista(nome, equipe_n, FRAGIL_ESPECIALISTA if fragil else "") for nome in times}
    sistema = SISTEMA_SUPERVISOR + (FRAGIL_SUPERVISOR if fragil else "")
    consultas = [{
        "nome": f"consultar_{nome}",
        "descricao": f"Pergunta ao especialista de {area['titulo']} ({area['descricao']}). "
                     "Ele busca na parte dele da wiki e devolve desfecho, fontes e resposta.",
        "parametros": {"type": "object", "properties": {"pergunta": {"type": "string", "maxLength": 400}},
                       "required": ["pergunta"]},
    } for nome, area in times.items()]
    ferramentas = consultas + ENCERRAMENTO

    def arquitetura(pergunta, registro, trace):
        mensagens = [modelo.mensagem_do_usuario(pergunta)]
        _evento(trace, "supervisor", "recebeu", pergunta, sistema=sistema, ferramentas=[f["nome"] for f in ferramentas])
        for _ in range(max_passos):
            resposta = _chamar(trace, "supervisor", mensagens, sistema, ferramentas)
            pares = []
            for chamada in resposta.chamadas:
                if chamada.nome == "responder":
                    r = Resultado.de_dict(chamada.args)
                    _evento(trace, "supervisor", "encerrou", f"{r.desfecho} · fontes {r.fontes}", resposta=r.resposta)
                    return r
                if chamada.nome == "escalar_para_rh":
                    _evento(trace, "supervisor", "encerrou", "escalar", resposta=chamada.args.get("motivo", ""))
                    return Resultado("escalar", [], chamada.args.get("motivo", ""))
                nome = chamada.nome.removeprefix("consultar_")
                if nome not in atendentes:
                    texto = json.dumps({"erro": "ferramenta_desconhecida", "aceitos": list(times)})
                else:
                    texto_handoff = str(chamada.args.get("pergunta", pergunta))
                    _evento(trace, "supervisor", "handoff", f"→ especialista {nome}", texto=texto_handoff, destino=nome)
                    r = atendentes[nome](texto_handoff, registro, trace)
                    texto = json.dumps({"desfecho": r.desfecho, "fontes": r.fontes, "resposta": r.resposta},
                                       ensure_ascii=False)
                pares.append((chamada, texto))
            if not pares:
                return Resultado.de_json(resposta.texto)
            mensagens.append(modelo.mensagem_do_assistente(resposta))
            mensagens.append(modelo.mensagem_de_resultados(pares))
        _evento(trace, "supervisor", "parou", f"passou de {max_passos} passos")
        return Resultado("escalar", [], f"Não concluí em {max_passos} passos. Encaminhado ao RH.")

    arquitetura.nome = f"supervisor · {equipe_n} esp" + (" · frágil" if fragil else "") + \
                       (f" · {max_passos} passos" if max_passos != MAX_PASSOS else "")
    arquitetura.config = {"arquitetura": "supervisor", "equipe": equipe_n, "fragil": fragil, "max_passos": max_passos}
    return arquitetura


# ======================================================================= medir

def avaliar(resultado: Resultado, caso: dict) -> tuple[bool, str]:
    """A régua dos Encontros 1 a 3: desfecho, fontes e, quando o caso pede, o valor certo na resposta."""
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


def _rota(trace: list) -> tuple[list[str], set]:
    """Os agentes acionados e os espaços da wiki que eles podiam ver."""
    agentes, espacos = [], set()
    for e in trace:
        if e["evento"] == "acessa":
            agentes.append(e["agente"])
            espacos |= set(e["espacos"])
    return agentes, espacos


def rota_certa(caso: dict, trace: list) -> bool | None:
    """A rota cobre os espaços de que a dúvida depende? None quando o caso não avalia rota."""
    esperado = caso.get("rota")
    if esperado is None:
        return None
    _, espacos = _rota(trace)
    if "*" in espacos:
        return True
    if not esperado:                        # cumprimento: o certo é não acionar nenhuma área
        return not espacos
    return set(esperado) <= espacos


def rodar(arquitetura, casos: list[dict], nome: str | None = None, mostrar: bool = True) -> dict:
    """Roda a arquitetura em cada caso e mede. Um caso que quebra não derruba a rodada."""
    nome = nome or getattr(arquitetura, "nome", "arquitetura")
    linhas = []
    for caso in casos:
        medicao = medidor.zerar()
        registro, trace = [], []
        try:
            resultado = arquitetura(caso["pergunta"], registro, trace)
            ok, motivo = avaliar(resultado, caso)
        except modelo.RespostaNaoGravada:
            raise
        except Exception as erro:
            resultado, ok, motivo = Resultado("invalido"), False, f"erro: {type(erro).__name__}: {erro}"
        agentes, _ = _rota(trace)
        linhas.append({
            "id": caso["id"], "categoria": caso["categoria"], "pergunta": caso["pergunta"],
            "acertou": ok, "motivo": motivo, "desfecho": resultado.desfecho, "fontes": resultado.fontes,
            "resposta": resultado.resposta, "rota_certa": rota_certa(caso, trace),
            "agentes": agentes, "buscas": sum(1 for x in registro if x["ferramenta"].startswith("buscar")),
            "chamadas_modelo": medicao.chamadas, "tokens_entrada": medicao.tokens_entrada,
            "tokens_saida": medicao.tokens_saida, "custo_usd": medicao.custo_usd,
            "segundos": medicao.segundos_no_modelo, "trace": trace,
        })
        if mostrar:
            l = linhas[-1]
            rota = {True: "rota ok", False: "ROTA ERRADA", None: ""}[l["rota_certa"]]
            print(f"  {caso['id']:<4}{'ok ' if ok else 'ERR'}  {' > '.join(agentes) or '-':<42}{rota:<12}{motivo}")
    return {"nome": nome, "config": getattr(arquitetura, "config", {}), "linhas": linhas}


def resumo(rodada: dict) -> dict:
    ls = rodada["linhas"]
    n = len(ls)
    acertos = sum(l["acertou"] for l in ls)
    custo = sum(l["custo_usd"] for l in ls)
    rotas = [l["rota_certa"] for l in ls if l["rota_certa"] is not None]
    return {
        "arquitetura": rodada["nome"], "acertos": f"{acertos}/{n}",
        "rota certa": f"{sum(rotas)}/{len(rotas)}" if rotas else "-",
        "chamadas/caso": round(sum(l["chamadas_modelo"] for l in ls) / n, 1),
        "tokens/caso": round(sum(l["tokens_entrada"] + l["tokens_saida"] for l in ls) / n),
        "custo total (US$)": round(custo, 4),
        "custo/acerto (US$)": round(custo / acertos, 5) if acertos else None,
        "seg/caso": round(sum(l["segundos"] for l in ls) / n, 1),
    }


def placar(*rodadas: dict) -> None:
    """Uma linha por arquitetura. seg/caso é o tempo de espera pelo modelo (na gravação, quando é replay)."""
    linhas = [resumo(x) for x in rodadas]
    cols = list(linhas[0])
    larg = {c: max(len(c), *(len(str(l[c])) for l in linhas)) for c in cols}
    print("  ".join(c.ljust(larg[c]) for c in cols))
    for l in linhas:
        print("  ".join(str(l[c]).ljust(larg[c]) for c in cols))


def detalhe(*rodadas: dict) -> None:
    """Caso a caso, lado a lado."""
    print("caso  categoria      " + "".join(f"{x['nome'][:30]:<34}" for x in rodadas))
    for i, l0 in enumerate(rodadas[0]["linhas"]):
        celulas = []
        for x in rodadas:
            l = x["linhas"][i]
            marca = "ok " if l["acertou"] else "ERR"
            rota = {True: "", False: " rota✗", None: ""}[l["rota_certa"]]
            celulas.append(f"{marca} {l['chamadas_modelo']}ch{rota} {'' if l['acertou'] else l['motivo'][:16]}"[:32]
                           .ljust(34))
        print(f"{l0['id']:<6}{l0['categoria']:<15}" + "".join(celulas))


def mostrar_trace(rodada: dict, caso_id: str, completo: bool = False) -> None:
    """Abre a caixa de um caso: cada agente, o que recebeu, o que pediu, o que a busca devolveu, quanto custou.

    completo=True mostra também o prompt de sistema e as ferramentas de cada agente.
    """
    linha = next(l for l in rodada["linhas"] if l["id"] == caso_id)
    print(f"{caso_id} · {linha['pergunta']}")
    print(f"arquitetura: {rodada['nome']}\n")
    por_agente: dict[str, list[int]] = {}
    for e in linha["trace"]:
        recuo = "  " if e["agente"] in ("roteador", "supervisor") else "      "
        if e["evento"] == "modelo":
            por_agente.setdefault(e["agente"], [0, 0, 0])
            por_agente[e["agente"]][0] += 1
            por_agente[e["agente"]][1] += e["tokens_entrada"]
            por_agente[e["agente"]][2] += e["tokens_saida"]
            print(f"{recuo}[{e['agente']}] modelo pediu: {e['detalhe']}   "
                  f"({e['tokens_entrada']} tokens de entrada, {e['tokens_saida']} de saída)")
        elif e["evento"] == "recebeu":
            print(f"{recuo}[{e['agente']}] recebeu: {e['detalhe']}")
            if completo:
                print(f"{recuo}   ferramentas: {', '.join(e['ferramentas'])}")
                print("\n".join(f"{recuo}   | {x}" for x in e["sistema"].splitlines()))
        elif e["evento"] == "ferramenta":
            print(f"{recuo}[{e['agente']}] {e['detalhe']}  →  {e['devolveu'] or 'nada'}")
        elif e["evento"] == "rota":
            print(f"{recuo}[roteador] {e['detalhe']}  · {e['motivo']}")
        elif e["evento"] == "handoff":
            print(f"{recuo}[{e['agente']}] passa adiante {e['detalhe']}: “{e['texto']}”")
        elif e["evento"] in ("encerrou", "parou", "acessa", "regra"):
            texto = e["detalhe"] + (f" · “{e['resposta'][:160]}”" if e.get("resposta") else "")
            print(f"{recuo}[{e['agente']}] {e['evento']}: {texto}")
    print(f"\nresultado: {'ACERTOU' if linha['acertou'] else 'ERROU'} ({linha['motivo']})")
    print("custo por agente:")
    for agente, (ch, ent, sai) in por_agente.items():
        custo = (ent * medidor.PRECO_ENTRADA + sai * medidor.PRECO_SAIDA) / 1_000_000
        print(f"  {agente:<26}{ch} chamadas · {ent:>6} + {sai:>4} tokens · US$ {custo:.5f}")


# ======================================================================= experimentos (hands-on)

def registrar(experimentos: list[dict], rodada: dict) -> None:
    """Guarda a rodada para comparar depois (substitui uma rodada de mesmo nome)."""
    experimentos[:] = [e for e in experimentos if e["nome"] != rodada["nome"]]
    experimentos.append(rodada)


def tabela_markdown(experimentos: list[dict]) -> str:
    """O placar em markdown, para colar na nota de arquitetura."""
    linhas = [resumo(e) for e in experimentos]
    cols = list(linhas[0])
    saida = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    saida += ["| " + " | ".join(str(l[c]) for c in cols) + " |" for l in linhas]
    return "\n".join(saida)


def onde_mudou(base: dict, outra: dict) -> None:
    """Os casos em que as duas rodadas discordam: é ali que a arquitetura fez diferença."""
    print(f"{'caso':<6}{base['nome'][:34]:<36}{outra['nome'][:34]}")
    algum = False
    for a, b in zip(base["linhas"], outra["linhas"]):
        if a["acertou"] != b["acertou"]:
            algum = True
            print(f"{a['id']:<6}{('ok' if a['acertou'] else 'ERR ' + a['motivo'])[:34]:<36}"
                  f"{('ok' if b['acertou'] else 'ERR ' + b['motivo'])[:34]}")
    if not algum:
        print("(as duas acertam e erram nos mesmos casos)")


# ======================================================================= guardar

RESULTADOS = PASTA / "resultados"


def salvar(*rodadas: dict) -> Path:
    """Guarda as rodadas em resultados/ (fora do Git)."""
    RESULTADOS.mkdir(exist_ok=True)
    arquivo = RESULTADOS / f"rodadas-{time.strftime('%Y%m%d-%H%M%S')}.json"
    arquivo.write_text(json.dumps({"modelo": modelo.estado_replay().get("modelo") or modelo.MODELO,
                                   "rodadas": list(rodadas)}, ensure_ascii=False, indent=1), encoding="utf-8")
    return arquivo
