"""Servidor MCP da Aurora: os contratos de vocês, servidos pelo protocolo MCP.

As mesmas ferramentas do hands-on (cinco, ou seis depois do TODO 4), com a mesma camada (validação, projeção
da saída, erros escritos para o modelo). A diferença é o transporte: em vez de
o agente importar o código, qualquer cliente MCP descobre as ferramentas em
tempo de execução e as chama pelo protocolo.

    python encontro-02/mcp_aurora/servidor.py              contratos de vocês (contratos.py)
    python encontro-02/mcp_aurora/servidor.py --solucao    contratos do professor
    python encontro-02/mcp_aurora/servidor.py --solucao --quebra 4   com uma das quebras da Parte 2
    python encontro-02/mcp_aurora/servidor.py --solucao --com-busca-web
                                                            + uma ferramenta REAL: busca na web (Serper)
    python encontro-02/mcp_aurora/servidor.py --solucao --planilha-real
                                                            a rede credenciada vem do Google Sheets de verdade

Normalmente quem inicia o servidor é o cliente (listar_ferramentas.py, ou um
aplicativo como o Claude Desktop), e não vocês. Ele conversa por stdin/stdout.
Precisa do SDK oficial: pip install "mcp<2"   (a versão 2.0 mudou a API do servidor)
"""
import asyncio
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ENCONTRO = AQUI.parent
RAIZ = ENCONTRO.parent
sys.path[:0] = [str(RAIZ), str(ENCONTRO), str(AQUI)]
if "--solucao" in sys.argv:
    sys.path.insert(0, str(RAIZ / "professor" / "solucao-encontro-02"))

if "--planilha-real" in sys.argv:          # demo: a rede credenciada vem do Google Sheets de verdade
    import os
    os.environ["PLANILHA_REAL"] = "1"

try:                                       # o kit foi escrito para a 1.x; a 2.0 mudou a API do servidor
    from importlib.metadata import version as _versao
    if int(_versao("mcp").split(".")[0]) >= 2:
        sys.exit(f"\n→ o servidor MCP não subiu: você tem o pacote mcp {_versao('mcp')}, e o kit usa a versão 1.x.\n"
                 '  Corrija com: pip install "mcp<2"')
except ImportError:
    pass

import mcp.types as types  # noqa: E402
from mcp.server.lowlevel import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

import camada  # noqa: E402
from camada import executar, verificar_contratos  # noqa: E402
from contratos import CONTRATOS  # noqa: E402

try:
    verificar_contratos(CONTRATOS)
except (NotImplementedError, ValueError) as problema:   # o cliente mostra esta mensagem no terminal
    sys.exit(f"\n→ o servidor MCP não subiu: {problema}\n  (para a demo com tudo pronto, use --solucao)")
if "--com-busca-web" in sys.argv:          # demo: uma ferramenta real ao lado das simuladas
    import busca_web  # noqa: E402
    camada.IMPLEMENTACOES[busca_web.NOME] = busca_web.buscar_na_web
    camada.CONTEXTO[busca_web.NOME] = "web"
    CONTRATOS = {**CONTRATOS, busca_web.NOME: busca_web.CONTRATO}
if "--quebra" in sys.argv:
    import quebras  # noqa: E402
    CONTRATOS, _ = quebras.aplicar(CONTRATOS, int(sys.argv[sys.argv.index("--quebra") + 1]))
servidor = Server("aurora-tecnologia")
registro: list = []   # log das chamadas, como no hands-on


@servidor.list_tools()
async def listar() -> list[types.Tool]:
    return [types.Tool(name=nome, description=c["descricao"], inputSchema=c["parametros"])
            for nome, c in CONTRATOS.items()]


@servidor.call_tool()
async def chamar(nome: str, argumentos: dict) -> list[types.TextContent]:
    texto = executar(nome, argumentos or {}, CONTRATOS, registro)
    return [types.TextContent(type="text", text=texto)]


async def main() -> None:
    async with stdio_server() as (leitura, escrita):
        await servidor.run(leitura, escrita, servidor.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
