"""SOLUÇÃO DE REFERÊNCIA — TODO 4 do Encontro 2: consultar_rede_credenciada.
Não publicar para a turma antes da aula.

Uma resposta possível, não a única. Pontos que a solução quer mostrar:

  - A limpeza é do código, não do modelo: cidade e tipo são normalizados aqui.
    O modelo não precisa adivinhar que "CAMPINAS " e "campinas" são a mesma coisa.
  - O código filtra o que o modelo não deve ver: descredenciados e em negociação
    nunca saem da ferramenta. Não adianta pedir no prompt "não indique descredenciados".
  - A saída é curta e sem colunas internas: nada de código da operadora, observação
    interna ou valor negociado (confidencial). O contrato declara só o que o modelo usa.
  - "limite" tem teto no schema (maximum): São Paulo tem mais de dez prestadores.
  - A fonte volta como chave de topo, para o agente citar a planilha.
  - Erro que ensina: cidade fora da rede volta com as cidades atendidas.
"""
import unicodedata
from collections import Counter

from ferramentas import ErroDeFerramenta
from sistemas import PlanilhaGoogle

SHEETS = PlanilhaGoogle()
PLANILHA_ID = "planilha-rede-credenciada"
ABA = "prestadores"

TIPOS = ["hospital", "laboratorio", "clinica", "pronto_socorro", "qualquer"]


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _tipo(celula: str) -> str:
    return normalizar(celula).replace("-", "_").replace(" ", "_")


def consultar_rede_credenciada(cidade: str, tipo: str = "qualquer", somente_24h: bool = False,
                               limite: int = 5) -> dict:
    if tipo not in TIPOS:
        raise ErroDeFerramenta("tipo_invalido", "'tipo' não é um valor aceito.", recebido=tipo, aceitos=TIPOS,
                               como_corrigir="repita com um dos valores aceitos")

    dados = SHEETS.ler(PLANILHA_ID, ABA)
    cabecalho, *linhas = dados["values"]
    prestadores = [dict(zip(cabecalho, linha)) for linha in linhas]

    ativos = [p for p in prestadores if normalizar(p["situacao"]) == "ativo"]
    grafias = {}                                    # a grafia mais comum de cada cidade
    for p in ativos:
        grafias.setdefault(normalizar(p["cidade"]), Counter())[p["cidade"].strip()] += 1
    cidades_atendidas = sorted((c.most_common(1)[0][0] for c in grafias.values()), key=normalizar)

    na_cidade = [p for p in ativos if normalizar(p["cidade"]) == normalizar(cidade)]
    if not na_cidade:
        raise ErroDeFerramenta(
            "cidade_sem_rede", "Não há prestador credenciado ativo nessa cidade.", recebido=cidade,
            aceitos=cidades_atendidas, recuperavel=False,
            como_corrigir="se a cidade estiver escrita de outro jeito, repita; senão, responda que a rede "
                          "não cobre a cidade e oriente a consultar a operadora")

    filtrados = [p for p in na_cidade
                 if (tipo == "qualquer" or _tipo(p["tipo"]) == tipo)
                 and (not somente_24h or normalizar(p["atende_24h"]) == "sim")]

    return {
        "fonte": PLANILHA_ID,
        "total_encontrado": len(filtrados),
        "resultados": [
            {**p, "tipo": _tipo(p["tipo"]), "cidade": p["cidade"].strip(),
             "atende_24h": normalizar(p["atende_24h"]) == "sim"}
            for p in filtrados[:limite]
        ],
    }


CONTRATO = {
    "descricao": (
        "Consulta a rede credenciada do plano de saúde da Aurora (planilha mantida pelo time de Benefícios): "
        "hospitais, laboratórios, clínicas e prontos-socorros que atendem pelo plano, por cidade. "
        "Devolve só prestadores ATIVOS, com endereço (bairro), telefone e se atende 24h. "
        "Use quando a pessoa quer saber onde ser atendida ou se um prestador atende pelo plano. "
        "Cite 'planilha-rede-credenciada' (campo fonte) como fonte da resposta. "
        "Não use para regras do plano (carência, inclusão de dependente, coparticipação): isso é "
        "consultar_regra_beneficio. Se a cidade não tiver rede, a ferramenta devolve erro com as "
        "cidades atendidas: não invente prestador."
    ),
    "parametros": {
        "type": "object",
        "properties": {
            "cidade": {"type": "string", "maxLength": 60,
                       "description": "Cidade onde a pessoa quer atendimento, ex.: 'Campinas'."},
            "tipo": {"type": "string", "enum": TIPOS,
                     "description": "Tipo de prestador. 'qualquer' quando a pergunta não especifica."},
            "somente_24h": {"type": "boolean",
                            "description": "true quando a pessoa precisa de atendimento 24 horas."},
            "limite": {"type": "integer", "minimum": 1, "maximum": 5,
                       "description": "Quantos prestadores devolver. Padrão 5."},
        },
        "required": ["cidade"],
        "additionalProperties": False,
    },
    "saida": ["fonte", "total_encontrado", "prestador", "tipo", "especialidades", "bairro", "telefone",
              "atende_24h"],
}

NOME = "consultar_rede_credenciada"
