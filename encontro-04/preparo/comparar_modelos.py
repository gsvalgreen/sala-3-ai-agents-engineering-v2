"""Compara modelos baratos no caso da Aurora antes de escolher o da turma.   (PROFESSOR)

    python encontro-04/preparo/comparar_modelos.py MODELO:PRECO_ENTRADA:PRECO_SAIDA [...]

Exemplo, pelo OpenRouter (BASE_URL e API_KEY no .env, PROVEDOR=openai_compat):

    python encontro-04/preparo/comparar_modelos.py \\
        google/gemini-2.5-flash-lite:0.10:0.40 \\
        deepseek/deepseek-v4-flash:0.09:0.18 \\
        anthropic/claude-haiku-4.5:1.00:5.00

Preços em dólares por milhão de tokens: confira na página de cada modelo em openrouter.ai.
Roda, ao vivo e sem replay, o agente único e o roteador com 3 especialistas nos 19 casos.
Com modelos baratos, uma rodada completa costuma custar centavos.

Na escolha, olhe três colunas, nesta ordem:
    acertos       um modelo que erra demais o contrato de ferramentas estraga a aula inteira
    custo/acerto  é o custo que importa, e não o preço por token
    seg/caso      a turma espera cada demonstração ao vivo
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent.parent))

from comum import medidor, modelo  # noqa: E402


def main() -> None:
    candidatos = sys.argv[1:]
    if not candidatos or any(c.count(":") != 2 for c in candidatos):
        sys.exit(__doc__)
    if not modelo.tem_credencial() or modelo.PROVEDOR == "fake":
        sys.exit("O .env precisa de um provedor real com chave (em geral PROVEDOR=openai_compat, BASE_URL e API_KEY).")

    import multiagente as ma
    ma.preparar(None)
    casos = ma.carregar_casos()
    rodadas = []
    for candidato in candidatos:
        nome, entrada, saida = candidato.split(":")
        modelo.MODELO = nome
        medidor.PRECO_ENTRADA, medidor.PRECO_SAIDA = float(entrada), float(saida)
        print(f"\n=== {nome} (US$ {entrada} / {saida} por milhão)")
        for arq in (ma.monolito(), ma.roteador_especialistas("llm", 3)):
            try:
                rodadas.append(ma.rodar(arq, casos, nome=f"{nome} · {arq.nome[:28]}", mostrar=False))
            except Exception as erro:
                print(f"   {arq.nome}: falhou ({type(erro).__name__}: {str(erro)[:300]})")
                break
        else:
            ma.placar(*rodadas[-2:])

    if rodadas:
        print("\n=== Todos lado a lado\n")
        ma.placar(*rodadas)
        invalidos = {r["nome"]: sum(l["desfecho"] == "invalido" for l in r["linhas"]) for r in rodadas}
        ruins = {k: v for k, v in invalidos.items() if v}
        if ruins:
            print("\nCasos com saída fora do contrato (o modelo não chamou a ferramenta certa):")
            for k, v in ruins.items():
                print(f"   {k}: {v}")
        print(f"\nRodadas salvas em {ma.salvar(*rodadas)}")
        print("Escolhido o modelo, ponha MODELO e os dois preços no .env e rode preparo/gravar_replay.py.")


if __name__ == "__main__":
    main()
