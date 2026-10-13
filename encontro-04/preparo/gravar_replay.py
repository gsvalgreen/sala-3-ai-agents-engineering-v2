"""Grava as respostas do modelo para a turma reproduzir sem chave e sem custo.   (PROFESSOR)

    python encontro-04/preparo/gravar_replay.py              grava o que falta (pode rodar de novo)
    python encontro-04/preparo/gravar_replay.py --conferir   confere, sem chamar a API, que tudo está gravado

Antes: preparo/preparar_indice.py (uma vez) e o .env com o modelo escolhido
(preparo/comparar_modelos.py ajuda a escolher). Usa o PROVEDOR, o MODELO e os preços do .env.

O que é gravado:
    1. o agente único, as 12 combinações do menu do hands-on e o supervisor com 3 e 4 especialistas,
       nos 19 casos;
    2. todas as células dos notebooks 01 e 02, exatamente como estão (menos as marcadas com
       "# [não gravar]"). Se você editar um notebook, rode este script de novo.

Escreve em encontro-04/dados/: replay.jsonl (as respostas) e consultas-aurora.npz (os vetores
das consultas que os agentes fizeram). Publique a pasta dados/ no repositório da disciplina.

Rodar de novo só chama a API para o que ainda não está gravado. Para gravar do zero (outro
modelo, prompts mudados), apague dados/replay.jsonl antes.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
E4 = AQUI.parent
sys.path.insert(0, str(E4))
sys.path.insert(0, str(E4.parent))

NOTEBOOKS = ["01-dentro-do-multiagente.ipynb", "02-hands-on-multiagente.ipynb"]


def celulas(arquivo: Path) -> list[str]:
    nb = json.loads(arquivo.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def executar_notebook(arquivo: Path) -> None:
    """Roda as células de código em ordem, num namespace próprio, como o Jupyter faria."""
    ns: dict = {"__name__": "__main__"}
    for i, codigo in enumerate(celulas(arquivo), start=1):
        if codigo.lstrip().startswith("# [não gravar]"):
            continue
        try:
            exec(compile(codigo, f"{arquivo.name}[{i}]", "exec"), ns)
        except Exception:
            print(f"\n!! Falhou a célula {i} de {arquivo.name}:\n{codigo}\n")
            raise


def gravar(ma, casos) -> list[dict]:
    from comum import modelo
    rodadas = []
    arquiteturas = [ma.monolito()] + [ma.roteador_especialistas(**c) for c in ma.todas_as_configuracoes()] + \
                   [ma.supervisor(3), ma.supervisor(4)]
    for i, arq in enumerate(arquiteturas, start=1):
        inicio = time.perf_counter()
        rodada = ma.rodar(arq, casos, mostrar=False)
        rodadas.append(rodada)
        estado = modelo.estado_replay()
        print(f"[{i:>2}/{len(arquiteturas)}] {arq.nome:<52} {time.perf_counter() - inicio:5.0f}s · "
              f"{estado['gravadas']} gravadas até aqui")
    for nome in NOTEBOOKS:
        print(f"Notebook {nome}...")
        executar_notebook(E4 / nome)
    return rodadas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--conferir", action="store_true", help="só reproduz; acusa o que faltar, sem chamar a API")
    args = p.parse_args()

    from comum import modelo
    if args.conferir:
        os.environ["AURORA_REPLAY_MODO"] = "usar"
        modelo.PROVEDOR = "sem-chave"             # garante que nada vai à API: o que faltar vira erro
    else:
        if not modelo.tem_credencial() or modelo.PROVEDOR == "fake":
            sys.exit("Para gravar, o .env precisa de um provedor real com chave (PROVEDOR, MODELO e a chave).")
        os.environ["AURORA_REPLAY_MODO"] = "gravar"
        print(f"Gravando com {modelo.PROVEDOR} · {modelo.MODELO}\n")

    import busca
    import multiagente as ma
    ma.preparar("usar" if args.conferir else "gravar")
    casos = ma.carregar_casos()
    inicio = time.perf_counter()
    ja_havia = modelo.estado_replay()["respostas_no_arquivo"]

    if args.conferir:
        try:
            gravar(ma, casos)
        except modelo.RespostaNaoGravada as erro:
            sys.exit(f"\nFALTA GRAVAR: {erro}\nRode o script sem --conferir.")
        if busca.indice().novas:
            sys.exit(f"\nFALTA GRAVAR: {busca.indice().novas} consultas de busca sem vetor em dados/. "
                     "Rode o script sem --conferir.")
        print("\nTudo gravado: os notebooks e o menu do hands-on rodam sem chave, nenhuma chamada faltando.")
        return

    rodadas = gravar(ma, casos)
    total = busca.salvar_consultas()
    estado = modelo.estado_replay()
    print(f"\nPronto em {(time.perf_counter() - inicio) / 60:.1f} min. "
          f"{estado['respostas_no_arquivo'] - ja_havia} respostas novas, "
          f"{estado['respostas_no_arquivo']} no total. {total} consultas com vetor em dados/.")
    print("\nO placar que a turma vai ver (guarde para a aula):\n")
    ma.placar(*rodadas)
    print(f"\nRodadas salvas em {ma.salvar(*rodadas)}")
    print("\nPróximo passo: python encontro-04/preparo/gravar_replay.py --conferir")


if __name__ == "__main__":
    main()
