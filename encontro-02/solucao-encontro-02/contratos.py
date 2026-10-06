"""SOLUÇÃO DE REFERÊNCIA — contratos do Encontro 2. Não publicar para a turma antes da aula.

Uma resposta possível, não a única. O que se avalia é a justificativa de cada escolha.

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

    # ------------------------------------------------------------ SOLUÇÃO TODO 1
    "consultar_politica_rh": {
        "descricao": (
            "Consulta as políticas de RH da Aurora na wiki: férias, trabalho remoto e home office, "
            "licenças, jornada e banco de horas, e o guia de integração de novos colaboradores. "
            "Devolve até 2 páginas, com o id da página (para citar como fonte), a data de atualização "
            "e o trecho relevante. Use o tema quando a pergunta for claramente sobre uma política; "
            "use 'geral' quando não tiver certeza ou quando a pergunta envolver mais de uma. "
            "Não use para regras de benefícios (vale-refeição, plano de saúde, auxílio-creche) "
            "nem para problemas de TI."
        ),
        "parametros": {
            "type": "object",
            "properties": {
                "tema": {"type": "string",
                         "enum": ["ferias", "trabalho_remoto", "licencas", "jornada", "integracao", "geral"],
                         "description": "A política consultada. 'integracao' é o guia de boas-vindas; "
                                        "'geral' busca em todas."},
                "pergunta": {"type": "string", "maxLength": 300,
                             "description": "A dúvida do colaborador, com as palavras-chave."},
            },
            "required": ["pergunta"],
            "additionalProperties": False,
        },
        "saida": ["id", "titulo", "atualizado_em", "trecho"],
    },

    # ------------------------------------------------------------ SOLUÇÃO TODO 2
    "abrir_chamado_ti": {
        "descricao": (
            "Abre um chamado no service desk de TI. É uma AÇÃO: cria um registro e notifica a equipe de TI. "
            "Use somente quando o colaborador pedir um chamado, ou quando a base de TI indicar que o "
            "problema exige chamado (equipamento quebrado, perda do segundo fator, programa fora da "
            "Central de Software). Consulte buscar_base_ti antes. Não use quando a base de TI resolve "
            "sem chamado (desbloqueio automático, Central de Software, reiniciar a VPN). "
            "Não repita a chamada depois de um timeout: o chamado pode já ter sido criado; "
            "informe o colaborador e peça que confira no portal de chamados. "
            "Devolve o número do chamado e o prazo de atendimento."
        ),
        "parametros": {
            "type": "object",
            "properties": {
                "categoria": {"type": "string", "enum": ["equipamento", "acesso", "software", "vpn", "outro"],
                              "description": "equipamento: notebook e periféricos; acesso: senha, conta, "
                                             "segundo fator; software: instalação de programas; vpn: acesso remoto."},
                "descricao": {"type": "string", "minLength": 15, "maxLength": 500,
                              "description": "O problema relatado pelo colaborador, em uma ou duas frases."},
                "urgencia": {"type": "string", "enum": ["baixa", "media", "alta"],
                             "description": "alta quando o colaborador está sem acesso a nenhum sistema "
                                            "ou sem equipamento para trabalhar."},
            },
            "required": ["categoria", "descricao", "urgencia"],
            "additionalProperties": False,
        },
        "saida": ["id", "status", "prazo_atendimento"],
    },

    # ------------------------------------------------------------ SOLUÇÃO TODO 3
    "verificar_elegibilidade_beneficio": {
        "descricao": (
            "Faz a pré-análise automática de critérios de um benefício para um colaborador identificado "
            "pelo id, consultando o cadastro no sistema de RH. O resultado NÃO é confirmação de "
            "elegibilidade e nunca deve ser comunicado como tal: depois de chamar, encaminhe ao RH "
            "com escalar_para_rh, informando o resultado da pré-análise no motivo. "
            "Use somente quando o colaborador informar o próprio id e perguntar se tem direito. "
            "Não use para dúvidas gerais sobre um benefício (valor, prazos, como pedir): isso é "
            "consultar_regra_beneficio. Nunca tente adivinhar um id."
        ),
        "parametros": {
            "type": "object",
            "properties": {
                "colaborador_id": {"type": "string", "maxLength": 10,
                                   "description": "O id informado pelo colaborador, ex.: '1043'."},
                "beneficio": {"type": "string", "enum": ["vale_refeicao", "plano_de_saude", "auxilio_creche"]},
            },
            "required": ["colaborador_id", "beneficio"],
            "additionalProperties": False,
        },
        "saida": ["colaborador_id", "beneficio", "pre_analise", "criterios_verificados", "aviso"],
    },
}


# TODO 4 — a sexta ferramenta (contrato e implementação) está em nova_ferramenta.py, nesta pasta.
import nova_ferramenta as _nova   # noqa: E402

if _nova.CONTRATO.get("parametros") is not None:
    CONTRATOS[_nova.NOME] = _nova.CONTRATO
