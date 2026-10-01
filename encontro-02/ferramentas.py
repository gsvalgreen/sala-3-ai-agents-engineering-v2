"""O que cada ferramenta faz por dentro.           (NÃO MEXA, exceto o DESAFIO no fim)

Aqui está a IMPLEMENTAÇÃO de cinco das seis ferramentas do agente: o código que fala
com os sistemas da Aurora (sistemas.py). O CONTRATO de cada uma, que é o que o
modelo lê, fica em contratos.py. É lá que vocês trabalham.

    Contexto     Ferramenta                           Efeito no mundo
    RH           consultar_politica_rh                leitura
    TI           buscar_base_ti                       leitura
    TI           abrir_chamado_ti                     ESCRITA: cria um chamado
    Benefícios   consultar_regra_beneficio            leitura
    Benefícios   verificar_elegibilidade_beneficio    leitura de dado pessoal
    Benefícios   consultar_rede_credenciada           leitura (TODO 4: vocês constroem,
                                                      em nova_ferramenta.py)

Cada função devolve o registro COMPLETO que o sistema entrega. A camada
(camada.py) corta esse registro nos campos que o contrato declarou em "saida".
Os campos disponíveis de cada ferramenta estão em CAMPOS_DISPONIVEIS.
"""
from sistemas import (ColaboradorNaoEncontrado, ServiceDesk, SistemaRH, TimeoutDoSistema, Wiki,
                      radicais)

WIKI = Wiki()
SERVICE_DESK = ServiceDesk(lento=True)
RH = SistemaRH()


class ErroDeFerramenta(Exception):
    """Erro que volta ao modelo como mensagem. Escrito para ser lido por um modelo."""

    def __init__(self, codigo: str, mensagem: str, *, recebido=None, aceitos=None,
                 como_corrigir: str | None = None, recuperavel: bool = True, tipo: str = "argumento"):
        super().__init__(mensagem)
        self.codigo, self.mensagem, self.tipo = codigo, mensagem, tipo
        self.recebido, self.aceitos = recebido, aceitos
        self.como_corrigir, self.recuperavel = como_corrigir, recuperavel

    def como_dict(self) -> dict:
        dados = {"erro": self.codigo, "mensagem": self.mensagem}
        if self.recebido is not None:
            dados["recebido"] = self.recebido
        if self.aceitos is not None:
            dados["aceitos"] = self.aceitos
        if self.como_corrigir:
            dados["como_corrigir"] = self.como_corrigir
        dados["recuperavel"] = self.recuperavel
        return dados


def reiniciar_atendimento() -> None:
    """Chamado pelo rodar.py antes de cada caso: cada pergunta é um atendimento novo."""
    SERVICE_DESK.reiniciar()


def efeitos_criados() -> list:
    """O que o atendimento mudou no mundo (aqui, os chamados abertos). O rodar.py confere com o gabarito."""
    return SERVICE_DESK.chamados


def _exigir(valor, aceitos: list, nome: str):
    if valor not in aceitos:
        raise ErroDeFerramenta(f"{nome}_invalido", f"'{nome}' não é um valor aceito pelo sistema.",
                               recebido=valor, aceitos=aceitos,
                               como_corrigir=f"repita a chamada com {nome} igual a um dos valores aceitos")


# ================================================================ RH

TEMAS_RH = {
    "ferias": ["rh-ferias"],
    "trabalho_remoto": ["rh-trabalho-remoto"],
    "licencas": ["rh-licencas"],
    "jornada": ["rh-jornada-e-banco-de-horas"],
    "integracao": ["rh-guia-de-integracao"],
    "geral": ["rh-ferias", "rh-trabalho-remoto", "rh-licencas",
              "rh-jornada-e-banco-de-horas", "rh-guia-de-integracao"],
}


def consultar_politica_rh(pergunta: str, tema: str = "geral") -> dict:
    """Busca na wiki as políticas de RH. 'tema' restringe a busca a uma política."""
    _exigir(tema, list(TEMAS_RH), "tema")
    paginas = WIKI.buscar(TEMAS_RH[tema], pergunta)
    return {"resultados": [WIKI.registro_completo(p, pergunta) for p in paginas]}


# ================================================================ TI

PAGINAS_TI = ["ti-equipamentos", "ti-senhas-e-acesso", "ti-vpn-e-acesso-remoto", "ti-instalacao-de-software"]
CATEGORIAS_CHAMADO = ["equipamento", "acesso", "software", "vpn", "outro"]
URGENCIAS = ["baixa", "media", "alta"]


def buscar_base_ti(pergunta: str) -> dict:
    """Busca na base de conhecimento de TI (páginas de TI da wiki)."""
    paginas = WIKI.buscar(PAGINAS_TI, pergunta)
    return {"resultados": [WIKI.registro_completo(p, pergunta) for p in paginas]}


def abrir_chamado_ti(categoria: str, descricao: str, urgencia: str = "media") -> dict:
    """Cria um chamado no service desk. Chamar duas vezes cria dois chamados."""
    _exigir(categoria, CATEGORIAS_CHAMADO, "categoria")
    _exigir(urgencia, URGENCIAS, "urgencia")
    if len(descricao.strip()) < 15:
        raise ErroDeFerramenta("descricao_curta", "A descrição precisa explicar o problema em pelo menos 15 caracteres.",
                               recebido=descricao, como_corrigir="repita com uma descrição do problema relatado")

    chave = gerar_chave_idempotencia(categoria, descricao)   # DESAFIO: veja o fim do arquivo
    try:
        return SERVICE_DESK.criar(categoria, descricao, urgencia, chave_idempotencia=chave)
    except TimeoutDoSistema:
        raise ErroDeFerramenta(
            "timeout", "O service desk não respondeu em 10 segundos. O chamado pode ou não ter sido criado.",
            como_corrigir="tentar de novo pode criar um chamado duplicado", recuperavel=True, tipo="sistema")


# ========================================================== Benefícios

PAGINAS_BENEFICIO = {
    "vale_refeicao": "beneficios-vale-refeicao",
    "plano_de_saude": "beneficios-plano-de-saude",
    "auxilio_creche": "beneficios-auxilio-creche",
}


def consultar_regra_beneficio(beneficio: str, pergunta: str = "") -> dict:
    """Devolve a página de regras de um benefício."""
    _exigir(beneficio, list(PAGINAS_BENEFICIO), "beneficio")
    pagina = WIKI.pagina(PAGINAS_BENEFICIO[beneficio])
    return {"resultados": [WIKI.registro_completo(pagina, pergunta or pagina.titulo)]}


def verificar_elegibilidade_beneficio(colaborador_id: str, beneficio: str) -> dict:
    """Consulta o cadastro no sistema de RH e faz a pré-análise automática de critérios."""
    _exigir(beneficio, list(PAGINAS_BENEFICIO), "beneficio")
    try:
        registro = RH.registro(colaborador_id)
    except ColaboradorNaoEncontrado:
        raise ErroDeFerramenta("colaborador_nao_encontrado", "Não existe colaborador com esse id.",
                               recebido=colaborador_id, recuperavel=False,
                               como_corrigir="não tente adivinhar ids; peça o id ao colaborador ou escale")
    resultado, criterios = RH.pre_analise(registro, beneficio)
    return {
        **registro,
        "beneficio": beneficio,
        "pre_analise": resultado,
        "criterios_verificados": criterios,
        "aviso": "Pré-análise automática. Não é confirmação de elegibilidade: "
                 "somente o RH confirma, depois de analisar a documentação.",
    }


# ============================================================ catálogo

IMPLEMENTACOES = {
    "consultar_politica_rh": consultar_politica_rh,
    "buscar_base_ti": buscar_base_ti,
    "abrir_chamado_ti": abrir_chamado_ti,
    "consultar_regra_beneficio": consultar_regra_beneficio,
    "verificar_elegibilidade_beneficio": verificar_elegibilidade_beneficio,
}

CONTEXTO = {
    "consultar_politica_rh": "rh",
    "buscar_base_ti": "ti",
    "abrir_chamado_ti": "ti",
    "consultar_regra_beneficio": "beneficios",
    "verificar_elegibilidade_beneficio": "beneficios",
}

_CAMPOS_WIKI = ["id", "titulo", "tema", "dono", "atualizado_em", "trecho", "texto_completo",
                "caminho", "permissoes", "tags", "revisoes"]

# Os campos que cada ferramenta PODE devolver. O contrato escolhe quais devolve.
CAMPOS_DISPONIVEIS = {
    "consultar_politica_rh": _CAMPOS_WIKI,
    "buscar_base_ti": _CAMPOS_WIKI,
    "consultar_regra_beneficio": _CAMPOS_WIKI,
    "abrir_chamado_ti": ["id", "status", "categoria", "urgencia", "descricao", "prazo_atendimento",
                         "grupo_resolvedor", "fila_interna", "sla_interno_min", "historico",
                         "chave_idempotencia"],
    "verificar_elegibilidade_beneficio": ["colaborador_id", "nome", "cpf", "salario_base", "regime",
                                          "admissao", "dependentes", "beneficios_ativos", "beneficio",
                                          "pre_analise", "criterios_verificados", "aviso"],
}

# Campos que nunca deveriam chegar ao contexto do modelo: dado pessoal (CPF, salário) e
# dado comercial confidencial (valor negociado com a rede). O rodar.py conta quando chegam.
CAMPOS_SENSIVEIS = {"cpf", "salario_base", "valor_negociado_consulta"}


# ======================================================================
# DESAFIO (depois do Conceito 2), opcional: idempotência
#
# O service desk está lento: a primeira tentativa de cada atendimento estoura
# o timeout, mas o chamado é criado. Se o agente tentar de novo, nasce um
# chamado duplicado (veja a coluna "Chamados a mais" do placar).
#
# Faça esta função devolver uma chave que seja igual para duas tentativas do
# mesmo pedido. Com a chave, o service desk devolve o chamado que já existe
# em vez de criar outro. Dica: normalize a descrição com radicais(), que já
# está importada, e combine com a categoria.
#
# A chave nasce no código, não no modelo: se o modelo gerasse a chave, ele
# geraria uma nova a cada tentativa.
# ======================================================================
def gerar_chave_idempotencia(categoria: str, descricao: str) -> str | None:
    return None   # sem idempotência: cada chamada cria um chamado novo
