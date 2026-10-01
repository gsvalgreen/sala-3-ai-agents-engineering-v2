"""O agente do Encontro 2: o loop do Encontro 1, com as ferramentas do caso.   (NÃO MEXA)

O prompt de sistema é fixo e não fala de nenhuma ferramenta específica.
Tudo o que o modelo sabe sobre cada ferramenta vem do contrato (contratos.py).
Assim, a diferença no placar vem do contrato, e não de um prompt caprichado.
"""
import importlib.util
from pathlib import Path

from camada import como_ferramentas, executar
from comum import modelo
from comum.resultado import Resultado

# As mesmas regras de resposta do Encontro 1, lidas do arquivo de lá.
_arquivo = Path(__file__).resolve().parent.parent / "encontro-01" / "politica_de_resposta.py"
_spec = importlib.util.spec_from_file_location("politica_de_resposta_e1", _arquivo)
_politica = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_politica)

SISTEMA = _politica.REGRAS + """

Você tem ferramentas para consultar as fontes da Aurora e para agir nos sistemas dela.
Consulte as fontes antes de responder. Para encerrar o atendimento, chame a ferramenta
responder ou a ferramenta escalar_para_rh."""

MAX_PASSOS = 8

# Ferramentas de encerramento: fazem parte do executor, não do catálogo do caso.
ENCERRAMENTO = [
    {
        "nome": "responder",
        "descricao": ("Entrega a resposta final ao colaborador e encerra o atendimento. "
                      "Use 'responder' quando as fontes sustentam a resposta e 'nao_sei' quando "
                      "não há informação ou quando as fontes se contradizem."),
        "parametros": {
            "type": "object",
            "properties": {
                "desfecho": {"type": "string", "enum": ["responder", "nao_sei"]},
                "fontes": {"type": "array", "items": {"type": "string"},
                           "description": "ids das páginas que sustentam a resposta"},
                "resposta": {"type": "string"},
            },
            "required": ["desfecho", "fontes", "resposta"],
        },
    },
    {
        "nome": "escalar_para_rh",
        "descricao": ("Encaminha o atendimento para análise humana do RH e encerra. "
                      "Use quando a pessoa pergunta se ela tem direito a um benefício."),
        "parametros": {
            "type": "object",
            "properties": {"motivo": {"type": "string"}},
            "required": ["motivo"],
        },
    },
]


def resolver(pergunta: str, contratos: dict, registro: list) -> Resultado:
    ferramentas = como_ferramentas(contratos) + ENCERRAMENTO
    mensagens = [modelo.mensagem_do_usuario(pergunta)]

    for _ in range(MAX_PASSOS):
        resposta = modelo.chamar(mensagens, sistema=SISTEMA, ferramentas=ferramentas)
        if not resposta.chamadas:
            return Resultado.de_json(resposta.texto)

        pares = []
        for chamada in resposta.chamadas:
            if chamada.nome == "responder":
                return Resultado.de_dict(chamada.args)
            if chamada.nome == "escalar_para_rh":
                return Resultado("escalar", [], chamada.args.get("motivo", ""))
            pares.append((chamada, executar(chamada.nome, chamada.args, contratos, registro)))

        mensagens.append(modelo.mensagem_do_assistente(resposta))
        mensagens.append(modelo.mensagem_de_resultados(pares))

    return Resultado("escalar", [], f"Não consegui concluir em {MAX_PASSOS} passos. Encaminhado ao RH.")
