"""SOLUÇÃO DE REFERÊNCIA — Arquitetura B (workflow determinístico).
"""
from comum import modelo
from comum.resultado import Resultado
from ferramentas import buscar, formatar
from politica_de_resposta import FORMATO_JSON, REGRAS

CATEGORIAS = ("rh", "ti", "beneficios", "elegibilidade")

PROMPT_CLASSIFICADOR = """Classifique a pergunta de um colaborador em exatamente uma categoria:

- rh: trabalho remoto, férias, licenças, jornada, ponto, banco de horas
- ti: notebook e equipamentos, senha, bloqueio de conta, VPN, acesso a sistemas, instalação de software
- beneficios: vale-refeição, plano de saúde, auxílio-creche e outros benefícios
- elegibilidade: a pessoa pergunta se ELA tem direito a um benefício

Responda apenas com o nome da categoria, em minúsculas, sem pontuação."""


def classificar(pergunta: str) -> str:
    resposta = modelo.chamar([modelo.mensagem_do_usuario(pergunta)],
                             sistema=PROMPT_CLASSIFICADOR, max_tokens=10)
    categoria = resposta.texto.strip().lower().strip(".")
    # Padrão determinístico: se o modelo sair do contrato, cai em RH.
    return categoria if categoria in CATEGORIAS else "rh"


def resolver(pergunta: str) -> Resultado:
    categoria = classificar(pergunta)

    if categoria == "elegibilidade":
        return Resultado("escalar", [], "Encaminhei sua pergunta ao RH, que analisa a elegibilidade caso a caso.")

    docs = buscar(categoria, pergunta)
    if not docs:
        return Resultado("nao_sei", [], "Não encontrei essa informação nas políticas internas.")

    documentos = "\n\n".join(formatar(doc) for doc in docs)
    sistema = f"{REGRAS}\n\n{FORMATO_JSON}\n\nDocumentos disponíveis:\n\n{documentos}"
    resposta = modelo.chamar([modelo.mensagem_do_usuario(pergunta)], sistema=sistema)
    return Resultado.de_json(resposta.texto)
