"""SOLUÇÃO DE REFERÊNCIA — desafio opcional do Encontro 2: idempotência em abrir_chamado_ti.

Não é carregada automaticamente pelo rodar.py, de propósito: o --solucao mede os
contratos do professor com a mesma implementação que a turma usa no hands-on,
sem idempotência, para que o placar de referência seja comparável ao das duplas.

Para demonstrar em aula, cole a função abaixo no lugar da original, no fim de
encontro-02/ferramentas.py, e rode de novo os casos que abrem chamado:

    python encontro-02/rodar.py --solucao --casos c11 c13 --detalhe

A coluna "Chamados a mais" deve cair para zero quando o agente repete a chamada.
"""
from sistemas import radicais


def gerar_chave_idempotencia(categoria: str, descricao: str) -> str | None:
    # Mesma categoria + mesmas palavras relevantes = mesmo pedido.
    # A janela de tempo, aqui, é o atendimento: o service desk é reiniciado a cada caso.
    # Limite conhecido: duas descrições bem diferentes do mesmo problema geram chaves
    # diferentes. Idempotência reduz o risco de duplicar, não o elimina.
    return categoria + ":" + " ".join(sorted(radicais(descricao)))
