"""Os contratos das ferramentas: o que o modelo lê.      (COMPLETE OS TODOs 1, 2 e 3)

O TODO 4 (a sexta ferramenta, construída do zero) fica em nova_ferramenta.py.

Cada contrato tem três partes:

    "descricao"   o que a ferramenta faz, QUANDO usar e QUANDO NÃO usar
    "parametros"  o schema da entrada (JSON Schema): tipos, enums, obrigatórios, limites
    "saida"       os campos do registro que voltam ao modelo. Tudo o que volta entra
                  no contexto, a cada passo seguinte do loop

O NOME de cada ferramenta já vem definido (o placar depende dele), assim como
os nomes dos parâmetros, que são os da implementação em ferramentas.py.

Duas ferramentas já vêm com contrato pronto, como exemplo: buscar_base_ti e
consultar_regra_beneficio. Leiam as duas antes de escrever as suas.

Para testar:  python encontro-02/rodar.py --casos c01 c11 c14 --detalhe
"""

CONTRATOS = {

    # ------------------------------------------------------------ PRONTO (exemplo)
    "buscar_base_ti": {
        "descricao": (
            "Busca na base de conhecimento de TI da Aurora: notebook e equipamentos, senha e "
            "bloqueio de conta, VPN e acesso remoto, instalação de programas. Devolve até 2 páginas, "
            "com o id da página (para citar como fonte) e o trecho relevante. "
            "Use antes de responder qualquer dúvida de TI e antes de decidir abrir um chamado. "
            "Não use para políticas de RH nem para benefícios, mesmo quando a pergunta menciona "
            "seguro, trabalho remoto ou ponto: essas palavras aparecem em páginas de TI também."
        ),
        "parametros": {
            "type": "object",
            "properties": {
                "pergunta": {"type": "string", "maxLength": 300,
                             "description": "A dúvida do colaborador, em português, com as palavras-chave do problema."},
            },
            "required": ["pergunta"],
            "additionalProperties": False,
        },
        "saida": ["id", "titulo", "atualizado_em", "trecho"],
    },

    # ------------------------------------------------------------ PRONTO (exemplo)
    "consultar_regra_beneficio": {
        "descricao": (
            "Consulta a regra vigente de um benefício da Aurora: valor, prazos, documentos e como pedir. "
            "Use para dúvidas gerais sobre um benefício. Devolve a página do benefício com o id para citar. "
            "Não use para saber se um colaborador específico tem direito ao benefício: isso é "
            "verificar_elegibilidade_beneficio."
        ),
        "parametros": {
            "type": "object",
            "properties": {
                "beneficio": {"type": "string", "enum": ["vale_refeicao", "plano_de_saude", "auxilio_creche"],
                              "description": "O benefício consultado."},
                "pergunta": {"type": "string", "maxLength": 300,
                             "description": "A dúvida do colaborador, para destacar o trecho relevante."},
            },
            "required": ["beneficio"],
            "additionalProperties": False,
        },
        "saida": ["id", "titulo", "atualizado_em", "trecho"],
    },

    # ==================================================================
    # TODO 1 — consultar_politica_rh
    #
    # Busca nas políticas de RH da wiki. Parâmetros da implementação:
    #   pergunta  (texto, obrigatório)
    #   tema      (opcional). Valores que o sistema aceita:
    #             "ferias", "trabalho_remoto", "licencas", "jornada", "integracao", "geral"
    #             ("integracao" é o guia de boas-vindas; "geral" busca em todas as políticas)
    # Campos disponíveis na saída (por página encontrada):
    #   id, titulo, tema, dono, atualizado_em, trecho, texto_completo, caminho,
    #   permissoes, tags, revisoes
    # Perguntas para decidir: quando o modelo NÃO deve usar esta ferramenta?
    # Sem o id na saída, o agente consegue citar a fonte?
    # ==================================================================
    "consultar_politica_rh": {
        "descricao": ("Busca nas políticas de RH na wiki da Aurora. "
                      "Use para dúvidas sobre férias, licenças, trabalho remoto, jornada, integração e políticas gerais. "
                      "Devolve até 2 páginas com o `id` das páginas (para citar como fonte) e o `trecho` relevante. "
                      "Somente cite informações que encontrar nas páginas de documentos."
                      "(\"integracao\" é o guia de boas-vindas; \"geral\" busca em todas as políticas)"),
        "parametros": {  # JSON Schema da entrada
            "type": "object",
            "properties": {
                "pergunta": {"type": "string", "maxLength": 300, "description": "..."},
                "tema": {"type": "string",
                         "enum": ["ferias", "trabalho_remoto", "licencas", "jornada", "integracao", "geral"],
                         "description": "..."}},
            "required": ["pergunta"],
            "additionalProperties": False,
        },
        "saida": ["id", "titulo", "tema", "dono", "atualizado_em", "trecho", "texto_completo", "caminho", "permissoes",
                  "tags", "revisoes"],
    },

    # ==================================================================
    # TODO 2 — abrir_chamado_ti
    #
    # ESCRITA: cria um chamado no service desk. Parâmetros da implementação:
    #   categoria  (obrigatório). Valores aceitos: "equipamento", "acesso", "software", "vpn", "outro"
    #   descricao  (obrigatório). Pelo menos 15 caracteres
    #   urgencia   (opcional). Valores aceitos: "baixa", "media", "alta"
    # Campos disponíveis na saída:
    #   id, status, categoria, urgencia, descricao, prazo_atendimento, grupo_resolvedor,
    #   fila_interna, sla_interno_min, historico, chave_idempotencia
    # Perguntas para decidir: em que situações o agente deve abrir chamado, e em quais
    # NÃO deve (a base de TI já resolve? o colaborador pediu?). O que o colaborador
    # precisa saber do chamado aberto?
    # ==================================================================
    "abrir_chamado_ti": {
        "descricao": ("Cria um chamado no service desk de TI. "
                      "Use quando a dúvida do colaborador não puder ser resolvida com a base de conhecimento de TI ou quando o colaborador solicitar ajuda. "
                      "Devolve o id do chamado, status, prazo de atendimento, grupo_resolvedor e prazo_atendimento."),
        "parametros": {
            "type": "object",
            "properties": {
                "categoria": {"type": "string", "enum": ["equipamento", "acesso", "software", "vpn", "outro"],
                              "description": "..."},
                "descricao": {"type": "string", "minLength": 15, "maxLength": 500,
                              "description": "..."},
                "urgencia": {"type": "string", "enum": ["baixa", "media", "alta"], "default": "media",
                             "description": "..."},
            },
            "required": ["categoria", "descricao"],
            "additionalProperties": False,
        },
        "saida": ["id", "status", "categoria", "urgencia", "descricao", "prazo_atendimento", "grupo_resolvedor",
                  "fila_interna", "sla_interno_min", "historico", "chave_idempotencia"],
    },

    # ==================================================================
    # TODO 3 — verificar_elegibilidade_beneficio
    #
    # Lê o cadastro do colaborador no sistema de RH e faz uma PRÉ-ANÁLISE automática.
    # Só o RH confirma elegibilidade. Parâmetros da implementação:
    #   colaborador_id  (obrigatório). Ex.: "1043"
    #   beneficio       (obrigatório). Valores aceitos: "vale_refeicao", "plano_de_saude", "auxilio_creche"
    # Campos disponíveis na saída:
    #   colaborador_id, nome, cpf, salario_base, regime, admissao, dependentes,
    #   beneficios_ativos, beneficio, pre_analise, criterios_verificados, aviso
    # Perguntas para decidir: quais desses campos o modelo precisa ver, e quais nunca
    # deveriam entrar no contexto? O que o agente faz com a pré-análise?
    # Em que se diferencia de consultar_regra_beneficio?
    # ==================================================================
    "verificar_elegibilidade_beneficio": {
        "descricao": ("Lê o cadastro do colaborador no sistema de RH e faz uma PRÉ-ANÁLISE automática. "
                      "Use para saber se um colaborador específico tem direito a um dos benefícios disponíveis."
                      "Devolve o resultado da pré-análise, com os critérios verificados e um aviso de que só o RH confirma a elegibilidade."),
        "parametros": {
            "type": "object",
            "properties": {
                "colaborador_id": {"type": "string", "pattern": "^[0-9]+$", "description": "..."},
                "beneficio": {"type": "string", "enum": ["vale_refeicao", "plano_de_saude", "auxilio_creche"],
                              "description": "..."},
            },
            "required": ["colaborador_id", "beneficio"],
            "additionalProperties": False,
        },
        "saida": ["colaborador_id", "nome", "regime", "admissao", "dependentes", "beneficios_ativos",
                  "beneficio", "pre_analise", "criterios_verificados", "aviso"],
    },
}

# ======================================================================
# TODO 4 — a sexta ferramenta é construída do zero em nova_ferramenta.py
# (contrato E implementação). Quando o contrato de lá estiver preenchido,
# ela entra neste catálogo sozinha. Não precisa mexer aqui.
# ======================================================================
import nova_ferramenta as _nova  # noqa: E402

if _nova.CONTRATO.get("parametros") is not None:
    CONTRATOS[_nova.NOME] = _nova.CONTRATO
