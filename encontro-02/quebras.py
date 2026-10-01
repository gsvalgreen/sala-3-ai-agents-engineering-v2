"""As quatro quebras de contrato da Parte 2.          (NÃO MEXA)

Cada quebra parte dos contratos de vocês e estraga UMA coisa, sempre igual
para a turma toda. O prompt de sistema e a implementação não mudam.

    1  Descrição ambígua        as ferramentas de Benefícios ganham descrições quase iguais
    2  Texto livre no lugar     todo enum vira texto livre, e os parâmetros perdem a descrição
       de enum
    3  Restrição removida       somem as frases de "quando não usar" e os campos obrigatórios
    4  Saída verbosa            toda ferramenta devolve o registro inteiro do sistema

Uso: python encontro-02/rodar.py --comparar 2
"""
import copy
import re

NOMES = {
    1: "Descrição ambígua",
    2: "Texto livre no lugar de enum",
    3: "Restrição removida",
    4: "Saída verbosa",
}

_DESCRICAO_AMBIGUA = ("Consulta informações de benefícios do colaborador na base da Aurora, "
                      "como auxílio-creche, plano de saúde e vale-refeição.")

_FRASE_RESTRITIVA = re.compile(r"[^.]*\b(não use|nunca|somente|apenas|só)\b[^.]*\.", re.IGNORECASE)


def aplicar(contratos: dict, numero: int) -> tuple[dict, list]:
    """Devolve (contratos quebrados, lista do que mudou)."""
    c = copy.deepcopy(contratos)
    mudancas = []

    if numero == 1:
        for nome in ("consultar_regra_beneficio", "verificar_elegibilidade_beneficio",
                     "consultar_rede_credenciada"):
            if nome not in c:                      # a sexta só existe depois do TODO 4
                continue
            c[nome]["descricao"] = _DESCRICAO_AMBIGUA
            mudancas.append(f"{nome}: descrição trocada por \"{_DESCRICAO_AMBIGUA}\"")

    elif numero == 2:
        for nome, contrato in c.items():
            for param, regra in contrato["parametros"].get("properties", {}).items():
                if "enum" in regra:
                    regra.pop("enum")
                    regra.pop("description", None)
                    regra["type"] = "string"
                    mudancas.append(f"{nome}.{param}: enum virou texto livre, sem descrição")
                elif "description" in regra:
                    regra.pop("description")
                    mudancas.append(f"{nome}.{param}: perdeu a descrição")

    elif numero == 3:
        for nome, contrato in c.items():
            antes = contrato["descricao"]
            depois = re.sub(r"\s+", " ", _FRASE_RESTRITIVA.sub("", antes)).strip()
            if depois != antes:
                contrato["descricao"] = depois
                mudancas.append(f"{nome}: removidas as frases de restrição da descrição")
            schema = contrato["parametros"]
            if schema.get("required"):
                mudancas.append(f"{nome}: nenhum parâmetro obrigatório (antes: {schema['required']})")
                schema["required"] = []
            for regra in schema.get("properties", {}).values():
                for limite in ("maxLength", "minLength", "minimum", "maximum"):
                    regra.pop(limite, None)

    elif numero == 4:
        for nome, contrato in c.items():
            if contrato["saida"] != "*":
                contrato["saida"] = "*"
                mudancas.append(f"{nome}: devolve o registro inteiro do sistema")

    else:
        raise ValueError(f"Quebra {numero} não existe. Use de 1 a 4.")

    return c, mudancas
