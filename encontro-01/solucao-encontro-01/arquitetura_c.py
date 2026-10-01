"""SOLUÇÃO DE REFERÊNCIA — Arquitetura C (agente em loop). Não publicar para a turma antes da aula.

O modelo recebe ferramentas e decide sozinho o que fazer a cada passo:
buscar (em qual tema, quantas vezes), escalar ou responder.

    pergunta ──► ┌─► [ modelo decide ] ──► buscar ─┐
                 └──────── resultado ◄─────────────┘
                           │
                           ├──► escalar_para_rh ──► fim
                           └──► responder ────────► fim

Quem decide o próximo passo é o MODELO, em tempo de execução.
"""
from comum import modelo
from comum.resultado import Resultado
from ferramentas import buscar_formatado
from politica_de_resposta import REGRAS

SISTEMA = REGRAS + """

Você tem ferramentas. Busque nos documentos antes de responder; você pode
buscar mais de uma vez e em temas diferentes. Se a pessoa pergunta se ela tem
direito a um benefício, chame escalar_para_rh. Para terminar o atendimento,
chame a ferramenta responder."""

# As ferramentas, no formato neutro do projeto (comum/modelo.py converte).
# A descrição é o contrato que o modelo lê. Esse é o assunto do Encontro 2.
FERRAMENTAS = [
    {
        "nome": "buscar",
        "descricao": ("Busca documentos de política interna da Aurora Tecnologia por palavras-chave. "
                      "Devolve até 3 documentos, com id, dono, data de atualização e texto. "
                      "Use o tema 'todos' quando não souber a área ou quando a pergunta envolver mais de uma."),
        "parametros": {
            "type": "object",
            "properties": {
                "tema": {"type": "string", "enum": ["rh", "ti", "beneficios", "todos"]},
                "consulta": {"type": "string", "description": "Palavras-chave da busca, em português."},
            },
            "required": ["tema", "consulta"],
        },
    },
    {
        "nome": "escalar_para_rh",
        "descricao": ("Encaminha a pergunta para análise humana do RH e encerra o atendimento. "
                      "Use quando a pessoa pergunta se ela tem direito a um benefício."),
        "parametros": {
            "type": "object",
            "properties": {"motivo": {"type": "string"}},
            "required": ["motivo"],
        },
    },
    {
        "nome": "responder",
        "descricao": ("Entrega a resposta final ao colaborador e encerra o atendimento. "
                      "Use 'responder' quando os documentos sustentam a resposta e 'nao_sei' quando "
                      "não há informação ou quando os documentos se contradizem."),
        "parametros": {
            "type": "object",
            "properties": {
                "desfecho": {"type": "string", "enum": ["responder", "nao_sei"]},
                "fontes": {"type": "array", "items": {"type": "string"},
                           "description": "ids dos documentos que sustentam a resposta"},
                "resposta": {"type": "string"},
            },
            "required": ["desfecho", "fontes", "resposta"],
        },
    },
]


MAX_PASSOS = 6


def deve_parar(passos: int) -> bool:
    return passos >= MAX_PASSOS


def executar(chamada: modelo.Chamada) -> str:
    """Executa uma ferramenta que não encerra o atendimento e devolve o resultado em texto."""
    if chamada.nome == "buscar":
        return buscar_formatado(chamada.args.get("tema", "todos"), chamada.args.get("consulta", ""))
    return f"Ferramenta desconhecida: {chamada.nome}"


def resolver(pergunta: str) -> Resultado:
    mensagens = [modelo.mensagem_do_usuario(pergunta)]
    passos = 0

    while not deve_parar(passos):
        resposta = modelo.chamar(mensagens, sistema=SISTEMA, ferramentas=FERRAMENTAS)
        passos += 1

        if not resposta.chamadas:
            # O modelo escreveu texto em vez de usar uma ferramenta.
            return Resultado.de_json(resposta.texto)

        pares = []
        for chamada in resposta.chamadas:
            if chamada.nome == "responder":
                return Resultado.de_dict(chamada.args)
            if chamada.nome == "escalar_para_rh":
                return Resultado("escalar", [], chamada.args.get("motivo", ""))
            pares.append((chamada, executar(chamada)))

        mensagens.append(modelo.mensagem_do_assistente(resposta))
        mensagens.append(modelo.mensagem_de_resultados(pares))

    # Acabaram os passos sem resposta: sair escalando também é um desfecho projetado.
    return Resultado("escalar", [], f"Não consegui concluir em {passos} passos. Encaminhado ao RH.")
