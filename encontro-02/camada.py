"""A camada de ferramentas: a Anticorruption Layer do caso.      (NÃO MEXA)

Fica entre o modelo e os sistemas. Para cada pedido do modelo, ela:

    1. confere os argumentos contra o schema do contrato (erro volta ao modelo como instrução)
    2. chama a implementação (ferramentas.py)
    3. corta o registro nos campos declarados em "saida"
    4. registra a chamada, para o placar: ferramenta, argumentos, resultado, dado sensível

O modelo nunca vê o sistema. Vê só o contrato e o que a camada devolve.
"""
import inspect
import json

try:                       # no projeto de uma equipe em domínio próprio, este arquivo pode não existir
    import nova_ferramenta
except ImportError:
    nova_ferramenta = None
from ferramentas import CAMPOS_DISPONIVEIS, CAMPOS_SENSIVEIS, CONTEXTO, IMPLEMENTACOES, ErroDeFerramenta

# A sexta ferramenta (TODO 4) é construída pela dupla em nova_ferramenta.py.
if nova_ferramenta is not None:
    IMPLEMENTACOES = {**IMPLEMENTACOES, nova_ferramenta.NOME: nova_ferramenta.consultar_rede_credenciada}
    CONTEXTO = {**CONTEXTO, nova_ferramenta.NOME: "beneficios"}

TIPOS = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


# ============================================================ contratos → ferramentas

TODOS = ((1, "consultar_politica_rh"), (2, "abrir_chamado_ti"), (3, "verificar_elegibilidade_beneficio"))


def todos_pendentes(contratos: dict) -> list:
    """Os TODOs 1 a 3 que ainda não foram preenchidos, como [(numero, nome), ...]."""
    pendentes = []
    for numero, nome in TODOS:
        if nome not in IMPLEMENTACOES:     # domínio próprio: os TODOs da Aurora não se aplicam
            continue
        c = contratos.get(nome, {})
        if not c or str(c.get("descricao", "")).strip().startswith("TODO") or c.get("parametros") is None \
                or c.get("saida") is None:
            pendentes.append((numero, nome))
    return pendentes


def verificar_contratos(contratos: dict, exigir_todos: bool = True) -> None:
    """Confere se os contratos estão completos e batem com a implementação. Falha cedo, com a causa.

    Com exigir_todos=False, os TODOs pendentes devem ter sido retirados do catálogo antes (rodar.py faz
    isso para a dupla testar cada TODO assim que o termina)."""
    if exigir_todos:
        for numero, nome in todos_pendentes(contratos):
            raise NotImplementedError(f"TODO {numero}: complete o contrato de {nome} em contratos.py")

    problemas = []
    for nome, c in contratos.items():
        if nome not in IMPLEMENTACOES:
            problemas.append(f"{nome}: não existe ferramenta com esse nome")
            continue
        assinatura = inspect.signature(IMPLEMENTACOES[nome]).parameters
        props = (c["parametros"] or {}).get("properties", {})
        for p in props:
            if p not in assinatura:
                problemas.append(f"{nome}: o parâmetro '{p}' não existe; a implementação aceita {list(assinatura)}")
        for p, info in assinatura.items():
            if info.default is inspect.Parameter.empty and p not in props:
                problemas.append(f"{nome}: falta declarar o parâmetro obrigatório '{p}'")
        saida = c["saida"]
        if not isinstance(saida, list) and saida != "*":
            problemas.append(f"{nome}: 'saida' precisa ser uma lista de campos")
        elif saida != "*" and nome in CAMPOS_DISPONIVEIS:   # a ferramenta nova declara os próprios campos
            fora = [campo for campo in saida if campo not in CAMPOS_DISPONIVEIS[nome]]
            if fora:
                problemas.append(f"{nome}: campos de saída que não existem: {fora}")
    if problemas:
        raise ValueError("Contratos com problema:\n  - " + "\n  - ".join(problemas))


def como_ferramentas(contratos: dict) -> list:
    """Os contratos no formato neutro de comum/modelo.py."""
    return [{"nome": nome, "descricao": c["descricao"], "parametros": c["parametros"]}
            for nome, c in contratos.items()]


# ============================================================ validação de argumentos

def _erro(codigo: str, mensagem: str, **extras) -> ErroDeFerramenta:
    return ErroDeFerramenta(codigo, mensagem, **extras)


def validar(args: dict, schema: dict) -> None:
    props = schema.get("properties", {})
    for obrigatorio in schema.get("required", []):
        if obrigatorio not in args:
            raise _erro("parametro_faltando", f"Falta o parâmetro obrigatório '{obrigatorio}'.",
                        como_corrigir=f"repita a chamada informando '{obrigatorio}'")
    for nome, valor in args.items():
        if nome not in props:
            if schema.get("additionalProperties") is False:
                raise _erro("parametro_desconhecido", f"O parâmetro '{nome}' não existe.",
                            recebido=nome, aceitos=list(props))
            continue
        regra = props[nome]
        tipo = regra.get("type")
        if tipo in TIPOS and not isinstance(valor, TIPOS[tipo]):
            raise _erro("tipo_invalido", f"'{nome}' deveria ser {tipo}.", recebido=valor)
        if "enum" in regra and valor not in regra["enum"]:
            raise _erro(f"{nome}_invalido", f"'{nome}' não é um dos valores aceitos.", recebido=valor,
                        aceitos=regra["enum"], como_corrigir=f"repita com {nome} igual a um dos valores aceitos")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if "minimum" in regra and valor < regra["minimum"]:
                raise _erro("valor_baixo", f"'{nome}' precisa ser pelo menos {regra['minimum']}.", recebido=valor)
            if "maximum" in regra and valor > regra["maximum"]:
                raise _erro("valor_alto", f"'{nome}' pode ser no máximo {regra['maximum']}.", recebido=valor,
                            como_corrigir=f"repita com {nome} até {regra['maximum']}")
        if isinstance(valor, str):
            if "maxLength" in regra and len(valor) > regra["maxLength"]:
                raise _erro("texto_longo", f"'{nome}' passa de {regra['maxLength']} caracteres.",
                            como_corrigir="resuma e repita")
            if "minLength" in regra and len(valor) < regra["minLength"]:
                raise _erro("texto_curto", f"'{nome}' precisa de pelo menos {regra['minLength']} caracteres.",
                            recebido=valor)


# ============================================================ execução

def _projetar(registro: dict, saida) -> dict:
    if saida == "*":
        return registro
    if isinstance(registro.get("resultados"), list):
        topo = {k: registro[k] for k in saida if k in registro and k != "resultados"}
        itens = [{k: item[k] for k in saida if k in item} if isinstance(item, dict) else item
                 for item in registro["resultados"]]
        return {**topo, "resultados": itens}
    return {k: registro[k] for k in saida if k in registro}


def _tem_sensivel(dado) -> bool:
    if isinstance(dado, dict):
        return any(k in CAMPOS_SENSIVEIS or _tem_sensivel(v) for k, v in dado.items())
    if isinstance(dado, list):
        return any(_tem_sensivel(x) for x in dado)
    return False


def executar(nome: str, args: dict, contratos: dict, registro: list) -> str:
    """Executa um pedido do modelo e devolve o texto que volta para ele."""
    entrada = {"ferramenta": nome, "contexto": CONTEXTO.get(nome, "?"), "args": args,
               "status": "ok", "erro": "", "sensivel": False, "caracteres": 0}
    try:
        if nome not in contratos:
            raise _erro("ferramenta_desconhecida", f"Não existe ferramenta '{nome}'.",
                        aceitos=list(contratos), recuperavel=True)
        contrato = contratos[nome]
        validar(args, contrato["parametros"])
        bruto = IMPLEMENTACOES[nome](**args)
        saida = _projetar(bruto, contrato["saida"])
        if isinstance(saida.get("resultados"), list) and not saida["resultados"]:
            saida = {**saida, "aviso": saida.get("aviso") or "Nenhum resultado encontrado para essa busca."}
        entrada["sensivel"] = _tem_sensivel(saida)
        texto = json.dumps(saida, ensure_ascii=False)
    except ErroDeFerramenta as e:
        entrada["status"] = "erro_sistema" if e.tipo == "sistema" else "erro_argumento"
        entrada["erro"] = e.codigo
        texto = json.dumps(e.como_dict(), ensure_ascii=False)
    except TypeError as e:  # argumento que a implementação não aceita
        entrada["status"], entrada["erro"] = "erro_argumento", "argumento_invalido"
        texto = json.dumps({"erro": "argumento_invalido", "mensagem": str(e), "recuperavel": True},
                           ensure_ascii=False)
    entrada["caracteres"] = len(texto)
    registro.append(entrada)
    return texto
