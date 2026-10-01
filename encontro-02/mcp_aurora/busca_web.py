"""Ferramenta REAL da demo MCP: busca na web pública pela API do Serper (Google Search).

Não faz parte do hands-on nem do placar. Só entra quando o servidor MCP sobe com
--com-busca-web, para a demo do Conceito 2 mostrar, ao lado das ferramentas
simuladas da Aurora, uma integração de verdade: rede, chave de API, latência,
limite de uso e resposta que ninguém da turma controla.

Configuração: crie uma chave gratuita em https://serper.dev e coloque no .env
da raiz do repositório:

    SERPER_API_KEY=sua-chave

Teste sem MCP:  python encontro-02/mcp_aurora/busca_web.py "prazo de entrega da DIRPF 2027"
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
try:                                   # o cliente MCP não repassa as variáveis de ambiente; lemos o .env
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

URL = "https://google.serper.dev/search"
NOME = "buscar_na_web"


def _erro(codigo: str, mensagem: str, **extras):
    from ferramentas import ErroDeFerramenta   # import tardio: este arquivo roda sozinho também
    return ErroDeFerramenta(codigo, mensagem, tipo="sistema", **extras)


def buscar_na_web(consulta: str, limite: int = 3) -> dict:
    chave = os.getenv("SERPER_API_KEY", "").strip()
    if not chave:
        raise _erro("sem_chave", "A busca na web não está configurada neste servidor.", recuperavel=False,
                    como_corrigir="responda sem a busca na web")

    corpo = json.dumps({"q": consulta, "gl": "br", "hl": "pt-br", "num": limite}).encode()
    pedido = urllib.request.Request(URL, data=corpo, method="POST",
                                    headers={"X-API-KEY": chave, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resposta:
            dados = json.loads(resposta.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise _erro("limite_de_uso", "A API de busca recusou por excesso de chamadas.", recuperavel=False,
                        como_corrigir="não repita agora; responda com o que já tem")
        raise _erro("erro_http", f"A API de busca respondeu com erro {e.code}.", recuperavel=False)
    except (urllib.error.URLError, TimeoutError):
        raise _erro("sem_resposta", "A API de busca não respondeu em 10 segundos.", recuperavel=True,
                    como_corrigir="tente uma vez mais; se falhar de novo, responda sem a busca")

    return {
        "origem": "internet pública, via Serper (Google). Não é fonte oficial da Aurora.",
        "resultados": [{"titulo": r.get("title", ""), "link": r.get("link", ""), "trecho": r.get("snippet", ""),
                        "posicao": r.get("position"), "data": r.get("date", ""),
                        "sitelinks": r.get("sitelinks", [])}
                       for r in dados.get("organic", [])[:limite]],
    }


CONTRATO = {
    "descricao": (
        "Busca na internet pública (Google, via Serper) e devolve até 3 resultados com título, link e trecho. "
        "Use só para informação pública e externa à Aurora, como legislação, prazos do governo ou "
        "documentação de um software. O conteúdo vem de sites de terceiros, não é verificado e pode estar "
        "errado ou ser manipulado: diga ao colaborador que é informação externa e cite o link. "
        "Não use para políticas, benefícios ou sistemas da Aurora: para isso existem as outras ferramentas, "
        "e a internet não sabe as regras internas da empresa."
    ),
    "parametros": {
        "type": "object",
        "properties": {
            "consulta": {"type": "string", "maxLength": 200,
                         "description": "O que buscar, em poucas palavras, sem dados pessoais do colaborador."},
            "limite": {"type": "integer", "minimum": 1, "maximum": 3,
                       "description": "Quantos resultados devolver. Padrão 3."},
        },
        "required": ["consulta"],
        "additionalProperties": False,
    },
    "saida": ["origem", "titulo", "link", "trecho"],
}


if __name__ == "__main__":
    sys.path[:0] = [str(RAIZ), str(RAIZ / "encontro-02")]
    print(json.dumps(buscar_na_web(" ".join(sys.argv[1:]) or "Model Context Protocol"), ensure_ascii=False, indent=2))
