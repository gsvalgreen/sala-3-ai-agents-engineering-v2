"""Cliente MCP mínimo: inicia o servidor da Aurora, descobre as ferramentas e mostra
os contratos como um revisor de code review veria.

    python encontro-02/mcp_aurora/listar_ferramentas.py
    python encontro-02/mcp_aurora/listar_ferramentas.py --solucao
    python encontro-02/mcp_aurora/listar_ferramentas.py --solucao --quebra 4
    python encontro-02/mcp_aurora/listar_ferramentas.py --solucao --com-busca-web
    python encontro-02/mcp_aurora/listar_ferramentas.py --solucao --planilha-real --chamar consultar_rede_credenciada '{"cidade": "Campinas"}'
    python encontro-02/mcp_aurora/listar_ferramentas.py --com-busca-web --chamar buscar_na_web '{"consulta": "prazo DIRPF 2027"}'
    python encontro-02/mcp_aurora/listar_ferramentas.py --chamar buscar_base_ti '{"pergunta": "vpn não conecta"}'

É o que um agente faz ao se conectar a um servidor MCP: pergunta "que ferramentas
você tem?" e recebe nome, descrição e schema de cada uma. Esse texto entra no
contexto do modelo.
Precisa do SDK oficial: pip install "mcp<2"   (a versão 2.0 mudou a API do servidor)
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVIDOR = Path(__file__).resolve().parent / "servidor.py"

CHECKLIST = [
    "O nome diz o que a ferramenta faz?",
    "A descrição diz quando NÃO usar?",
    "O schema restringe a entrada (enums, limites, obrigatórios)?",
    "A saída cabe no contexto?",
    "Ela escreve no mundo? Dá para desfazer?",
]


async def main(args) -> None:
    parametros = StdioServerParameters(command=sys.executable,
                                       args=[str(SERVIDOR)] + (["--solucao"] if args.solucao else [])
                                       + (["--quebra", str(args.quebra)] if args.quebra else [])
                                       + (["--com-busca-web"] if args.com_busca_web else [])
                                       + (["--planilha-real"] if args.planilha_real else []),
                                       env=dict(os.environ))   # repassa o ambiente (chaves, modo planilha real)
    async with stdio_client(parametros) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()

            if args.chamar:
                nome, argumentos = args.chamar
                resultado = await sessao.call_tool(nome, json.loads(argumentos))
                for bloco in resultado.content:
                    print(bloco.text)
                return

            ferramentas = (await sessao.list_tools()).tools
            print(f"O servidor oferece {len(ferramentas)} ferramentas.\n")
            for f in ferramentas:
                print("=" * 78)
                print(f.name)
                print("-" * 78)
                print(f.description)
                print("\nschema:", json.dumps(f.inputSchema, ensure_ascii=False, indent=2))
            print("=" * 78)
            print("\nPara cada ferramenta, o revisor pergunta:")
            for item in CHECKLIST:
                print("  [ ] " + item)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--solucao", action="store_true", help="usa os contratos do professor")
    parser.add_argument("--quebra", type=int, choices=[1, 2, 3, 4], help="serve os contratos com uma quebra")
    parser.add_argument("--com-busca-web", action="store_true",
                        help="inclui a ferramenta real de busca na web (precisa de SERPER_API_KEY no .env)")
    parser.add_argument("--planilha-real", action="store_true",
                        help="a rede credenciada vem do Google Sheets de verdade (demo do professor)")
    parser.add_argument("--chamar", nargs=2, metavar=("FERRAMENTA", "ARGS_JSON"))
    try:
        asyncio.run(main(parser.parse_args()))
    except Exception as erro:
        import traceback
        # o SDK embrulha o erro real em grupos de exceção; mostramos a causa mais interna
        while isinstance(erro, BaseExceptionGroup) and erro.exceptions:
            erro = erro.exceptions[0]
        print("\n--- detalhe técnico ---", file=sys.stderr)
        traceback.print_exception(erro, file=sys.stderr)
        sys.exit(f"\nO cliente MCP falhou: {type(erro).__name__}: {erro}\n"
                 "Se houver uma mensagem do servidor acima (começando com →), ela é a causa.\n"
                 "Para ver o servidor sozinho: python encontro-02/mcp_aurora/servidor.py --solucao "
                 "(se subir, fica parado esperando; saia com Ctrl+C)")
