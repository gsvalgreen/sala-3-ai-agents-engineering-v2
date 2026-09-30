"""Arquitetura B — workflow determinístico.   (COMPLETE OS TODOs 1 e 2)

O fluxo está escrito no código. O modelo só faz duas tarefas pequenas:
classificar a pergunta e redigir a resposta.

    pergunta ──► classificar ──► tema?
                                   ├── "elegibilidade" ──► escalar (sem chamar o modelo)
                                   └── "rh" | "ti" | "beneficios"
                                          ──► buscar(tema, pergunta) ──► [ modelo + 3 documentos ] ──► resposta

Quem decide o próximo passo é o CÓDIGO, não o modelo.
"""
from comum import modelo
from comum.resultado import Resultado
from ferramentas import buscar, formatar
from politica_de_resposta import FORMATO_JSON, REGRAS

CATEGORIAS = ("rh", "ti", "beneficios", "elegibilidade")


# --------------------------------------------------------------------------
# TODO 1 — o classificador
#
# Escreva o prompt de sistema que faz o modelo responder com UMA das
# CATEGORIAS acima, e nada mais. Dicas:
#   - diga o que entra em cada categoria (ex.: "ti: notebook, senha, VPN...");
#   - "elegibilidade" é quando a pessoa pergunta se ELA tem direito a algo;
#   - peça a resposta em minúsculas, sem pontuação.
# --------------------------------------------------------------------------
PROMPT_CLASSIFICADOR = """
Você classifica dúvidas internas de colaboradores da Aurora Tecnologia.

Regras:
1. Classifique a pergunta em uma das categorias: "rh", "ti", "beneficios" ou "elegibilidade" conforme definições abaixo:
    - "rh": perguntas sobre férias, guia de integracao, jornada de trabalho e banco de horas, licencas e trabalho remoto.
    - "ti": perguntas sobre equipamentos, instalacao de software, senhas e acesso, vpn e acesso remoto e configuração de maquinas.
    - "beneficios": perguntas sobre vale refeicao, auxilio creche, plano de saude e inclusão de dependentes no plano de saúde (filhos e recem-nascidos).
    - "elegibilidade": perguntas sobre se o colaborador tem direito a um benefício.
Classifique somente com uma das categorias, em minúsculas e sem pontuação. 
"""


def classificar(pergunta: str) -> str:
    resposta = modelo.chamar([modelo.mensagem_do_usuario(pergunta)],
                             sistema=PROMPT_CLASSIFICADOR, max_tokens=10)
    categoria = resposta.texto.strip().lower()

    # TODO 1 (continuação): e se o modelo responder algo fora de CATEGORIAS?
    # Decida um comportamento padrão e devolva sempre uma categoria válida.
    if categoria not in CATEGORIAS:
        return "invalida"
    else:
        return categoria

def resolver(pergunta: str) -> Resultado:
    categoria = classificar(pergunta)
    if categoria == "invalida":
        return Resultado("nao_sei", [], "Não foi possível classificar a pergunta. Por favor, reformule.")
    # ----------------------------------------------------------------------
    # TODO 2 — o roteamento
    #
    # a) Se a categoria for "elegibilidade", devolva direto:
    #        Resultado("escalar", [], "texto explicando que o RH vai analisar")
    #    (repare: esse caminho nem chama o modelo)
    #
    if categoria == "elegibilidade":
        return Resultado("escalar", [], "Sua pergunta será analisada pelo RH para verificar a elegibilidade do benefício.")
    # b) Senão, busque os documentos do tema:   docs = buscar(categoria, pergunta)
    #    Se não vier nenhum documento, devolva Resultado("nao_sei", [], "...").
    #
    docs = buscar(categoria, pergunta)
    if not docs:
        return Resultado("nao_sei", [], "Não foram encontrados documentos relacionados à sua pergunta.")
    # c) Monte o prompt de sistema com REGRAS, FORMATO_JSON e os documentos
    #    (veja como a arquitetura_a.py faz com formatar), chame o modelo
    #    e devolva Resultado.de_json(resposta.texto).
    # ----------------------------------------------------------------------
    documentos = "\n\n".join(formatar(doc) for doc in docs)
    sistema = f"{REGRAS}\n\n{FORMATO_JSON}\n\nDocumentos disponíveis:\n\n{documentos}"
    resposta = modelo.chamar([modelo.mensagem_do_usuario(pergunta)], sistema=sistema)
    return Resultado.de_json(resposta.texto)
