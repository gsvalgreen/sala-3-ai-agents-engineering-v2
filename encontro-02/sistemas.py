"""Os sistemas da Aurora Tecnologia, simulados.        (NÃO MEXA)

São os "sistemas legados" que ficam atrás das ferramentas do agente.
Fazem o papel do Notion/Confluence, do service desk e do sistema de RH,
sem conta de terceiros e com comportamento controlado para a aula:

    Wiki           as políticas da pasta encontro-01/corpus, com metadados de wiki
    ServiceDesk    cria chamados de TI. Está LENTO hoje: a primeira tentativa de
                   cada atendimento estoura o timeout, mas o chamado é criado.
    SistemaRH      cadastro de colaboradores, com dados sensíveis (CPF, salário)
    PlanilhaGoogle a rede credenciada do plano de saúde, numa planilha do Google Sheets.
                   Devolve as células como texto, linha a linha, como a API real
                   (spreadsheets.values.get). Tem a sujeira de planilha de verdade.

O agente nunca fala com estes sistemas diretamente. Quem fala é a camada de
ferramentas (ferramentas.py + camada.py): a Anticorruption Layer do caso.
"""
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

PASTA_CORPUS = Path(__file__).resolve().parent.parent / "encontro-01" / "corpus"


# ================================================================== Wiki

@dataclass
class Pagina:
    id: str
    titulo: str
    tema: str
    dono: str
    atualizado_em: str
    texto: str


def _ler(caminho: Path) -> Pagina:
    bruto = caminho.read_text(encoding="utf-8")
    _, cabecalho, texto = bruto.split("---", 2)
    campos = dict(linha.split(":", 1) for linha in cabecalho.strip().splitlines())
    campos = {chave.strip(): valor.strip() for chave, valor in campos.items()}
    return Pagina(texto=texto.strip(), **campos)


_PALAVRAS_VAZIAS = set("""
a o as os um uma uns umas de do da dos das no na nos nas em para por com sem
que qual quais quando como onde e ou se eu meu minha meus minhas me mim voce
ao aos ate mais muito ja nao sim ser ter tem tenho posso pode vou vai esta estou
isso este essa esse aqui hoje sobre fazer faco alguma algum coisa preciso pra
""".split())


def radicais(texto: str) -> set:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    palavras = re.findall(r"[a-z0-9]+", sem_acento)
    return {p[:5] for p in palavras if p not in _PALAVRAS_VAZIAS and len(p) > 2}


class Wiki:
    """A wiki interna. Devolve páginas no formato 'cheio' da API da wiki."""

    def __init__(self, pasta: Path = PASTA_CORPUS):
        self.paginas = [_ler(c) for c in sorted(pasta.glob("*.md"))]

    def pagina(self, id_: str) -> Pagina | None:
        return next((p for p in self.paginas if p.id == id_), None)

    def buscar(self, ids: list[str], consulta: str, k: int = 2) -> list[Pagina]:
        """Ranqueia as páginas de 'ids' por palavras em comum com a consulta."""
        alvo = radicais(consulta)
        pontuadas = []
        for p in self.paginas:
            if p.id not in ids:
                continue
            pontos = len(alvo & radicais(p.texto)) + 2 * len(alvo & radicais(p.titulo))
            if pontos > 0:
                pontuadas.append((pontos, p))
        pontuadas.sort(key=lambda par: -par[0])
        return [p for _, p in pontuadas[:k]]

    @staticmethod
    def trecho(pagina: Pagina, consulta: str, paragrafos: int = 2) -> str:
        """Os parágrafos da página mais parecidos com a consulta, na ordem original."""
        partes = [p.strip() for p in pagina.texto.split("\n\n") if p.strip()]
        alvo = radicais(consulta)
        pontos = {i: len(alvo & radicais(partes[i])) for i in range(len(partes))}
        relevantes = [i for i in sorted(pontos, key=lambda i: -pontos[i]) if pontos[i] > 0]
        escolhidos = sorted(relevantes[:paragrafos]) or [0]
        return "\n\n".join(partes[i] for i in escolhidos)

    @staticmethod
    def registro_completo(pagina: Pagina, consulta: str) -> dict:
        """Tudo o que a API da wiki devolve sobre uma página. A ferramenta escolhe o que repassa."""
        return {
            "id": pagina.id,
            "titulo": pagina.titulo,
            "tema": pagina.tema,
            "dono": pagina.dono,
            "atualizado_em": pagina.atualizado_em,
            "trecho": Wiki.trecho(pagina, consulta),
            "texto_completo": pagina.texto,
            "caminho": f"/wiki/aurora/{pagina.tema}/{pagina.id}",
            "permissoes": {"leitura": ["todos-colaboradores"], "edicao": [pagina.dono, "wiki-admins"]},
            "tags": sorted(radicais(pagina.titulo)),
            "revisoes": [
                {"versao": n, "autor": f"{pagina.dono} (editor {n})",
                 "data": str(date.fromisoformat(pagina.atualizado_em) - timedelta(days=45 * (6 - n))),
                 "comentario": f"Revisão {n}: ajuste de redação e atualização de referências internas "
                               f"da página '{pagina.titulo}', conforme solicitação do comitê de políticas."}
                for n in range(1, 7)
            ],
        }


# ============================================================ Service desk

class TimeoutDoSistema(Exception):
    """O sistema não respondeu a tempo. A operação pode ou não ter acontecido."""


@dataclass
class ServiceDesk:
    lento: bool = True                       # a primeira tentativa de cada atendimento estoura o timeout
    chamados: list = field(default_factory=list)
    _tentativas: int = 0
    _proximo: int = 4812

    def reiniciar(self) -> None:
        """Começo de um novo atendimento (um caso do rodar.py)."""
        self.chamados.clear()
        self._tentativas = 0

    def criar(self, categoria: str, descricao: str, urgencia: str,
              chave_idempotencia: str | None = None) -> dict:
        if chave_idempotencia:
            existente = next((c for c in self.chamados if c.get("chave_idempotencia") == chave_idempotencia), None)
            if existente:
                return existente

        self._tentativas += 1
        prazo = {"alta": "4 horas úteis", "media": "1 dia útil", "baixa": "3 dias úteis"}.get(urgencia, "3 dias úteis")
        chamado = {
            "id": f"TI-{self._proximo}",
            "status": "aberto",
            "categoria": categoria,
            "urgencia": urgencia,
            "descricao": descricao,
            "prazo_atendimento": prazo,
            "grupo_resolvedor": {"equipamento": "Field Services", "acesso": "Identidade e Acesso",
                                 "software": "Engenharia de Estações", "vpn": "Redes"}.get(categoria, "Service Desk N1"),
            "fila_interna": f"Q-{categoria.upper()}-{urgencia.upper()}",
            "sla_interno_min": {"alta": 240, "media": 480, "baixa": 1440}.get(urgencia, 1440),
            "historico": [{"evento": "criado", "por": "assistente-virtual", "canal": "api"}],
            "chave_idempotencia": chave_idempotencia,
        }
        self._proximo += 1
        self.chamados.append(chamado)          # o chamado É criado...

        if self.lento and self._tentativas == 1:
            raise TimeoutDoSistema("o service desk não respondeu em 10 segundos")  # ...mas a resposta não chega
        return chamado


# ============================================================= Sistema de RH

COLABORADORES = {
    "1043": {"nome": "Marina Albuquerque", "cpf": "000.111.222-43", "salario_base": 9850.00,
             "regime": "CLT", "admissao": "2022-03-14",
             "dependentes": [{"parentesco": "filho", "idade": 3}],
             "beneficios_ativos": ["plano_de_saude", "vale_refeicao"]},
    "1044": {"nome": "Rafael Nogueira", "cpf": "000.111.222-44", "salario_base": 12400.00,
             "regime": "CLT", "admissao": "2019-08-01",
             "dependentes": [{"parentesco": "filha", "idade": 6}],
             "beneficios_ativos": ["plano_de_saude", "vale_refeicao", "auxilio_creche"]},
    "1050": {"nome": "Beatriz Tanaka", "cpf": "000.111.222-50", "salario_base": 15000.00,
             "regime": "PJ", "admissao": "2024-01-10",
             "dependentes": [{"parentesco": "filho", "idade": 2}],
             "beneficios_ativos": []},
}


class ColaboradorNaoEncontrado(Exception):
    pass


class SistemaRH:
    def registro(self, colaborador_id: str) -> dict:
        dados = COLABORADORES.get(str(colaborador_id).strip())
        if dados is None:
            raise ColaboradorNaoEncontrado(colaborador_id)
        return {"colaborador_id": str(colaborador_id).strip(), **dados}

    @staticmethod
    def pre_analise(registro: dict, beneficio: str) -> tuple[str, list]:
        """Checagem automática de critérios. NÃO é decisão: quem decide é o RH."""
        criterios = []
        if registro["regime"] != "CLT":
            criterios.append("regime de contratação não prevê o benefício")
            return "criterios_nao_atendidos", criterios
        if beneficio == "auxilio_creche":
            idades = [d["idade"] for d in registro["dependentes"] if d["parentesco"] in ("filho", "filha")]
            if not idades:
                criterios.append("sem filhos cadastrados")
                return "criterios_nao_atendidos", criterios
            if min(idades) > 5:
                criterios.append("dependente acima de 5 anos e 11 meses")
                return "criterios_nao_atendidos", criterios
            criterios.append("dependente na faixa de idade")
            criterios.append("comprovantes de matrícula e pagamento ainda não analisados")
            return "atende_criterios_basicos", criterios
        criterios.append("benefício sem regra automática de pré-análise")
        return "requer_analise_manual", criterios


# ====================================================== Planilha (Google Sheets)

class PlanilhaNaoEncontrada(Exception):
    pass


_CABECALHO_REDE = ["prestador", "tipo", "especialidades", "cidade", "uf", "bairro", "telefone",
                   "atende_24h", "situacao", "codigo_operadora", "valor_negociado_consulta",
                   "observacao_interna"]

# Mantida à mão pelo time de Benefícios desde 2021. Por isso a grafia varia.
_LINHAS_REDE = [
    ["Hospital Jacarandá Paulista", "Hospital", "clínica geral; cardiologia; ortopedia; pediatria", "São Paulo", "SP", "Bela Vista", "(11) 3000-1101", "SIM", "ativo", "OP-11-0457", "R$ 182,00", "Contrato renovado em 03/2026 com reajuste de 6,2%. Falar com Débora (comercial) antes de qualquer renegociação."],
    ["Hospital Ipê Roxo", "hospital", "clínica geral; oncologia; neurologia", "Sao Paulo", "SP", "Vila Mariana", "(11) 3000-1102", "SIM", "ativo", "OP-11-0512", "R$ 210,00", "Rede premium: coparticipação diferenciada em internação eletiva. Ver aditivo 2025-14."],
    ["Pronto Atendimento Paineira", "Pronto-socorro", "urgência e emergência adulto e infantil", "São Paulo", "SP", "Santana", "(11) 3000-1103", "sim", "ativo", "OP-11-0619", "R$ 150,00", "Unidade com fila longa aos domingos; várias reclamações registradas no RH em 2025."],
    ["Laboratório Cerejeira Análises", "Laboratório", "análises clínicas; coleta domiciliar", "São Paulo", "SP", "Pinheiros", "(11) 3000-1104", "Não", "ativo", "OP-11-0733", "R$ 38,00", "Coleta domiciliar só com pedido médico digitalizado."],
    ["Diagnósticos Manacá", "laboratório", "análises clínicas; imagem; ultrassom", "São Paulo", "SP", "Moema", "(11) 3000-1105", "NÃO", "ativo", "OP-11-0788", "R$ 41,50", ""],
    ["Clínica Sibipiruna", "Clínica", "dermatologia; ginecologia; clínica geral", "São Paulo", "SP", "Tatuapé", "(11) 3000-1106", "", "ativo", "OP-11-0801", "R$ 120,00", "Agenda de dermatologia com espera média de 30 dias."],
    ["Clínica Flamboyant Kids", "Clínica", "pediatria; alergologia", "Sao Paulo ", "SP", "Perdizes", "(11) 3000-1107", "não", "ativo", "OP-11-0845", "R$ 135,00", ""],
    ["Hospital Tipuana Sul", "Hospital", "clínica geral; obstetrícia; maternidade", "São Paulo", "SP", "Santo Amaro", "(11) 3000-1108", "SIM", "descredenciado", "OP-11-0290", "R$ 175,00", "DESCREDENCIADO em 08/2026 por pendência contratual. Não indicar."],
    ["Laboratório Aroeira", "Laboratório", "análises clínicas", "São Paulo", "SP", "Lapa", "(11) 3000-1109", "Não", "em negociação", "OP-11-0902", "R$ 36,00", "Proposta enviada em 09/2026; ainda não atende pelo plano."],
    ["Clínica Resedá Ortopedia", "clinica", "ortopedia; fisioterapia", "São Paulo", "SP", "Brooklin", "(11) 3000-1110", "Não", "ativo", "OP-11-0915", "R$ 128,00", ""],
    ["Pronto Atendimento Figueira 24h", "Pronto-socorro", "urgência e emergência adulto", "São Paulo", "SP", "Butantã", "(11) 3000-1111", "SIM", "ativo", "OP-11-0934", "R$ 155,00", ""],
    ["Hospital Pau-Brasil", "Hospital", "clínica geral; cardiologia; cirurgia geral", "São Paulo", "SP", "Mooca", "(11) 3000-1112", "SIM", "ativo", "OP-11-0967", "R$ 190,00", "Negociação de pacote de cirurgia bariátrica em andamento; valores não divulgar."],
    ["Laboratório Quintal Análises Clínicas", "Laboratório", "análises clínicas; exames de sangue; coleta domiciliar", "Campinas", "SP", "Cambuí", "(19) 3000-2201", "Não", "ativo", "OP-19-0103", "R$ 35,00", ""],
    ["Diagnósticos Ipê Campinas", "laboratório", "análises clínicas; exames de sangue; imagem", "campinas", "SP", "Centro", "(19) 3000-2202", "não", "ativo", "OP-19-0118", "R$ 39,00", "Unidade Centro fecha para reforma em 12/2026."],
    ["Laboratório Taquaral Exames", "Laboratório", "análises clínicas; exames de sangue", "Campinas ", "SP", "Taquaral", "(19) 3000-2203", "Não", "descredenciado", "OP-19-0087", "R$ 33,00", "Descredenciado em 07/2026. Colaboradores ainda ligam perguntando."],
    ["Hospital Sapucaia Campinas", "Hospital", "clínica geral; pediatria; ortopedia", "CAMPINAS", "SP", "Barão Geraldo", "(19) 3000-2204", "SIM", "ativo", "OP-19-0131", "R$ 170,00", ""],
    ["Clínica Guapuruvu", "Clínica", "clínica geral; psicologia", "Campinas", "SP", "Nova Campinas", "(19) 3000-2205", "", "ativo", "OP-19-0144", "R$ 110,00", ""],
    ["Hospital Araucária Norte", "Hospital", "clínica geral; cardiologia; pronto-socorro", "Curitiba", "PR", "Cabral", "(41) 3000-3301", "SIM", "ativo", "OP-41-0201", "R$ 165,00", ""],
    ["Pronto Atendimento Pinhão 24h", "Pronto-socorro", "urgência e emergência adulto e infantil", "Curitiba", "PR", "Água Verde", "(41) 3000-3302", "sim", "ativo", "OP-41-0214", "R$ 140,00", "Credenciado recente (06/2026)."],
    ["Clínica Tingui", "Clínica", "clínica geral; pediatria", "curitiba", "PR", "Mercês", "(41) 3000-3303", "Não", "ativo", "OP-41-0227", "R$ 105,00", ""],
    ["Hospital Barigui Sul", "Hospital", "clínica geral; pronto-socorro; maternidade", "Curitiba", "PR", "Portão", "(41) 3000-3304", "SIM", "descredenciado", "OP-41-0159", "R$ 160,00", "Descredenciado em 05/2026. Migrar pacientes em tratamento para o Araucária Norte."],
    ["Laboratório Erva-Mate", "Laboratório", "análises clínicas; exames de sangue", "Curitiba", "PR", "Batel", "(41) 3000-3305", "Não", "ativo", "OP-41-0233", "R$ 37,00", ""],
    ["Hospital Palmeira Imperial", "Hospital", "clínica geral; ortopedia; cardiologia", "Rio de Janeiro", "RJ", "Botafogo", "(21) 3000-4401", "SIM", "ativo", "OP-21-0301", "R$ 205,00", ""],
    ["Laboratório Restinga", "Laboratório", "análises clínicas; imagem", "Rio de Janeiro", "RJ", "Tijuca", "(21) 3000-4402", "Não", "ativo", "OP-21-0315", "R$ 42,00", ""],
    ["Clínica Pitangueira", "Clínica", "ginecologia; obstetrícia; pediatria", "Rio de janeiro", "RJ", "Barra da Tijuca", "(21) 3000-4403", "", "ativo", "OP-21-0328", "R$ 130,00", ""],
    ["Hospital Buriti Mineiro", "Hospital", "clínica geral; neurologia; pronto-socorro", "Belo Horizonte", "MG", "Funcionários", "(31) 3000-5501", "SIM", "ativo", "OP-31-0401", "R$ 172,00", ""],
    ["Laboratório Canela de Ema", "Laboratório", "análises clínicas; exames de sangue", "Belo Horizonte", "MG", "Savassi", "(31) 3000-5502", "Não", "ativo", "OP-31-0414", "R$ 36,50", ""],
    ["Clínica Ingá Recife", "Clínica", "clínica geral; dermatologia", "Recife", "PE", "Boa Viagem", "(81) 3000-6601", "Não", "ativo", "OP-81-0501", "R$ 115,00", ""],
    ["Hospital Mangaba", "Hospital", "clínica geral; pediatria; pronto-socorro", "Recife", "PE", "Derby", "(81) 3000-6602", "SIM", "em negociação", "OP-81-0514", "R$ 168,00", "Ainda não atende. Previsão de credenciamento: 01/2027."],
    ["Hospital Timbaúva", "Hospital", "clínica geral; cardiologia; ortopedia", "Porto Alegre", "RS", "Moinhos de Vento", "(51) 3000-7701", "SIM", "ativo", "OP-51-0601", "R$ 178,00", ""],
]

PLANILHAS = {
    "planilha-rede-credenciada": {
        "titulo": "Rede credenciada — plano de saúde Aurora (mantida por Benefícios)",
        "abas": {"prestadores": [_CABECALHO_REDE] + _LINHAS_REDE},
    },
}


class PlanilhaGoogle:
    """Simula a leitura de uma planilha pela API do Google Sheets (spreadsheets.values.get).

    Como na API real: devolve uma lista de linhas, cada linha uma lista de células,
    todas como TEXTO. A primeira linha é o cabeçalho. Nenhum filtro, nenhum tipo,
    nenhuma limpeza: quem lê é que interpreta.
    """

    def __init__(self):
        self._real = None

    def ler(self, planilha_id: str, aba: str) -> dict:
        if os.getenv("PLANILHA_REAL", "").strip() == "1":
            if self._real is None:
                self._real = SheetsReal.do_ambiente()
            return self._real.ler(planilha_id, aba)
        planilha = PLANILHAS.get(planilha_id)
        if planilha is None or aba not in planilha["abas"]:
            raise PlanilhaNaoEncontrada(f"{planilha_id}/{aba}")
        valores = planilha["abas"][aba]
        ultima_coluna = chr(ord("A") + len(valores[0]) - 1)
        return {
            "spreadsheetId": planilha_id,
            "range": f"{aba}!A1:{ultima_coluna}{len(valores)}",
            "majorDimension": "ROWS",
            "values": [list(linha) for linha in valores],
        }


class SheetsReal:
    """A leitura de verdade, pela API do Google Sheets, com uma conta de serviço.

    Configuração no .env (só o professor precisa):
        GOOGLE_CREDENCIAIS=caminho/para/a-chave-da-conta-de-servico.json   (FORA do repositório)
        GOOGLE_PLANILHA_ID=o id da planilha, o trecho da URL entre /d/ e /edit
    Precisa de: pip install google-auth requests
    """
    ESCOPO_LEITURA = "https://www.googleapis.com/auth/spreadsheets.readonly"
    URL = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, sessao, ids: dict):
        self.sessao = sessao          # qualquer objeto com .get(url, params=..., timeout=...)
        self.ids = ids                # id lógico do caso -> id real da planilha no Google

    @classmethod
    def do_ambiente(cls, escopo: str = ESCOPO_LEITURA) -> "SheetsReal":
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        except ImportError:
            pass
        credenciais, planilha = os.getenv("GOOGLE_CREDENCIAIS", "").strip(), os.getenv("GOOGLE_PLANILHA_ID", "").strip()
        if not credenciais or not planilha:
            raise RuntimeError("Modo planilha real: defina GOOGLE_CREDENCIAIS e GOOGLE_PLANILHA_ID no .env")
        try:
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
        except ImportError:
            raise RuntimeError("Modo planilha real: falta instalar as bibliotecas (pip install google-auth requests)")
        chave = service_account.Credentials.from_service_account_file(credenciais, scopes=[escopo])
        return cls(AuthorizedSession(chave), {"planilha-rede-credenciada": planilha})

    def ler(self, planilha_id: str, aba: str) -> dict:
        real = self.ids.get(planilha_id)
        if real is None:
            raise PlanilhaNaoEncontrada(f"{planilha_id}/{aba}")
        resposta = self.sessao.get(f"{self.URL}/{real}/values/{aba}", timeout=10)
        if resposta.status_code in (403, 404):
            raise PlanilhaNaoEncontrada(
                f"{planilha_id}/{aba}: o Google respondeu {resposta.status_code}. Confira se a planilha foi "
                "compartilhada com o e-mail da conta de serviço, se a aba existe e se a API do Sheets está ativa")
        resposta.raise_for_status()
        dados = resposta.json()
        # Mesmo formato do simulador. Diferença real que fica de propósito: a API do Google
        # corta as células vazias no FIM de cada linha, então as linhas podem ter tamanhos diferentes.
        return {"spreadsheetId": planilha_id, "range": dados.get("range", aba),
                "majorDimension": dados.get("majorDimension", "ROWS"), "values": dados.get("values", [])}
