"""TODO 4 — Construir do zero: consultar_rede_credenciada.     (CONTRATO E IMPLEMENTAÇÃO)

Nas ferramentas 1 a 5, a implementação veio pronta e vocês escreveram o contrato.
Aqui não tem nada pronto: vocês escrevem as duas coisas.

O pedido do time de Benefícios
------------------------------
"Todo dia alguém pergunta se tal hospital ou laboratório atende pelo plano. A resposta
está na nossa planilha da rede credenciada, no Google Sheets. Queremos que o assistente
consulte a planilha."

O sistema: a planilha
---------------------
    SHEETS.ler("planilha-rede-credenciada", "prestadores")

devolve o mesmo formato da API do Google Sheets (spreadsheets.values.get):

    {"spreadsheetId": "planilha-rede-credenciada",
     "range": "prestadores!A1:L31",
     "majorDimension": "ROWS",
     "values": [
        ["prestador", "tipo", "especialidades", "cidade", "uf", "bairro", "telefone",
         "atende_24h", "situacao", "codigo_operadora", "valor_negociado_consulta",
         "observacao_interna"],                                            <- cabeçalho
        ["Hospital Jacarandá Paulista", "Hospital", "clínica geral; ...", "São Paulo", ...],
        ...
     ]}

Tudo vem como texto, e a planilha é mantida à mão desde 2021. Olhem os dados antes
de escrever qualquer linha:

    python encontro-02/nova_ferramenta.py          (a partir da raiz: imprime a planilha inteira)

Passo a passo
-------------
  4a. IMPLEMENTAÇÃO: escrevam consultar_rede_credenciada(). Decidam os parâmetros.
      Devolvam um dicionário com a lista de prestadores em "resultados" (um dicionário
      por prestador). Chaves fora de "resultados" também podem voltar ao modelo,
      se o contrato declarar (ex.: a fonte).
  4b. CONTRATO: preencham CONTRATO (descrição, schema, saída), como nos TODOs 1 a 3.
      Os parâmetros do schema precisam bater com os da função.
  4c. TESTE: assim que CONTRATO["parametros"] deixar de ser None, a ferramenta entra
      no catálogo do agente sozinha. Os casos c16 e c17 dependem dela:

          python encontro-02/rodar.py --casos c16 c17 --detalhe

Perguntas para decidir
----------------------
  - Que parâmetros o modelo precisa para chegar ao prestador certo? Quais valores aceitar?
  - "Campinas", "campinas" e "CAMPINAS " são a mesma cidade. Quem resolve isso: o modelo
    ou o código?
  - A planilha tem prestadores descredenciados e em negociação. O modelo deveria vê-los?
  - São Paulo tem mais de dez prestadores. Quantos voltam para o contexto?
  - Quais colunas nunca deveriam entrar no contexto? (O placar tem uma coluna para isso.)
  - Como o agente cita a planilha como fonte?
  - E erros: cidade sem prestador? Tipo que não existe?
"""
import unicodedata

from ferramentas import ErroDeFerramenta   # para devolver erros legíveis ao modelo (veja ferramentas.py)
from sistemas import PlanilhaGoogle

SHEETS = PlanilhaGoogle()
PLANILHA_ID = "planilha-rede-credenciada"
ABA = "prestadores"


def normalizar(texto: str) -> str:
    """'  São Paulo ' -> 'sao paulo'. Minúsculas, sem acento, sem espaço nas pontas."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


# ======================================================================
# TODO 4a — a implementação
#
# Troquem a assinatura pelos parâmetros que vocês decidirem (com tipos e valores
# padrão) e escrevam o corpo. Esqueleto sugerido:
#   1. ler a planilha com SHEETS.ler(PLANILHA_ID, ABA)
#   2. transformar cada linha num dicionário (cabeçalho -> valor)
#   3. filtrar (normalizar() ajuda)
#   4. devolver {"resultados": [...], ...}
# ======================================================================
def consultar_rede_credenciada(cidade: str) -> dict:
    raise NotImplementedError("TODO 4a: implemente consultar_rede_credenciada em nova_ferramenta.py")


# ======================================================================
# TODO 4b — o contrato (mesmo formato de contratos.py)
# ======================================================================
CONTRATO = {
    "descricao": "TODO 4",
    "parametros": None,
    "saida": None,
}


NOME = "consultar_rede_credenciada"


if __name__ == "__main__":   # olhar os dados antes de escrever a ferramenta
    for linha in SHEETS.ler(PLANILHA_ID, ABA)["values"]:
        print(linha)
