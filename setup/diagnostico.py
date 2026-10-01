"""Diagnóstico do repositório: estrutura, dependências e imports.

    python setup/diagnostico.py

Rode a partir de qualquer pasta. Não chama o modelo e não gasta nada.
Cada problema vem com a correção.
"""
import importlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
problemas = []


def ok(texto):
    print("  [ok]    " + texto)


def falha(texto, correcao):
    print("  [FALHA] " + texto + "\n          → " + correcao)
    problemas.append(texto)


ESPERADOS = {
    "raiz": [".env.example", "requirements.txt", "README.md"],
    "comum": ["__init__.py", "modelo.py", "medidor.py", "resultado.py", "avaliar.py"],
    "encontro-01": ["politica_de_resposta.py", "ferramentas.py", "casos.json", "rodar.py"],
    "encontro-02": ["sistemas.py", "ferramentas.py", "nova_ferramenta.py", "contratos.py", "camada.py",
                    "agente.py", "quebras.py", "casos.json", "rodar.py", "mcp_aurora/servidor.py"],
    "professor/solucao-encontro-02": ["contratos.py", "nova_ferramenta.py", "idempotencia.py"],
}

print(f"Raiz do repositório: {RAIZ}\n")

print("1. Estrutura")
for aninhada in RAIZ.glob("*/encontro-02/rodar.py"):     # uma cópia do repositório dentro do repositório
    pasta = aninhada.parent.parent
    falha(f"há uma pasta a mais: {pasta.name}/encontro-02",
          f"o zip foi extraído dentro do repositório. Mova o conteúdo de '{pasta.name}/' "
          "para a raiz (sobrescrevendo) e apague a pasta que sobrou")
for pasta, arquivos in ESPERADOS.items():
    base = RAIZ if pasta == "raiz" else RAIZ / pasta
    faltando = [a for a in arquivos if not (base / a).exists()]
    if faltando:
        falha(f"{pasta}/: faltam {', '.join(faltando)}",
              "use o pacote completo do repositório (ai-agents-engineering-completo.zip)")
    else:
        ok(f"{pasta}/")
corpus = list((RAIZ / "encontro-01" / "corpus").glob("*.md"))
if len(corpus) < 12:
    falha(f"encontro-01/corpus/: {len(corpus)} políticas, esperado 12",
          "o Encontro 2 lê as políticas do Encontro 1; use o pacote completo")
else:
    ok("encontro-01/corpus/ (12 políticas)")
if not (RAIZ / ".env").exists():
    falha(".env não encontrado na raiz", "copie .env.example para .env e preencha a chave")
else:
    ok(".env")

print("\n2. Python e dependências")
if sys.version_info < (3, 10):
    falha(f"Python {sys.version.split()[0]}", "o kit precisa de Python 3.10 ou mais novo")
else:
    ok(f"Python {sys.version.split()[0]}")
try:
    from dotenv import dotenv_values
    modo_teste = dotenv_values(RAIZ / ".env").get("PROVEDOR", "").strip().lower() == "fake"
except ImportError:
    modo_teste = False
for modulo, pacote, obrigatorio in (("dotenv", "python-dotenv", True), ("anthropic", "anthropic", not modo_teste),
                                    ("mcp", "mcp", False)):
    try:
        importlib.import_module(modulo)
        ok(pacote)
    except ImportError:
        if obrigatorio:
            falha(f"falta o pacote {pacote}", "pip install -r requirements.txt")
        else:
            print(f"  [aviso] falta {pacote}" + (" (o .env está com PROVEDOR=fake)" if pacote == "anthropic"
                                                 else ": só a demo de MCP precisa") + " → pip install -r requirements.txt")

print("\n3. Imports do Encontro 2, com a solução do professor")
if problemas:
    print("  (pulado: corrija os itens acima primeiro)")
else:
    sys.path[:0] = [str(RAIZ / "professor" / "solucao-encontro-02"), str(RAIZ), str(RAIZ / "encontro-02")]
    try:
        import camada
        import contratos
        camada.verificar_contratos(contratos.CONTRATOS)
        ok(f"contratos do professor: {len(contratos.CONTRATOS)} ferramentas ({', '.join(contratos.CONTRATOS)})")
        import agente  # noqa: F401
        ok("agente.py (lê as regras do encontro-01)")
    except Exception as erro:
        falha(f"{type(erro).__name__}: {erro}", "cole esta mensagem na conversa com o Claude")

print("\n" + ("Tudo certo. Teste: python encontro-02/rodar.py --solucao --casos c01 c16 --detalhe"
              if not problemas else f"{len(problemas)} problema(s). Corrija de cima para baixo e rode de novo."))
