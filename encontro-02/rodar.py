"""Roda o agente sobre os 17 casos com os contratos de vocês, mede e imprime o placar.

Exemplos (a partir da raiz do repositório):

    python encontro-02/rodar.py                          contratos de vocês, 17 casos
    python encontro-02/rodar.py --casos c11 c14 --detalhe   só alguns casos, passo a passo
    python encontro-02/rodar.py --quebra 2               só a versão com a quebra 2
    python encontro-02/rodar.py --comparar 2             contrato bom × quebra 2, lado a lado
    python encontro-02/rodar.py --de-csv encontro-02/resultados/arquivo.csv

Cada execução é salva em encontro-02/resultados/ como CSV.
"""
import argparse
import csv
import importlib
import json
import statistics
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(1, str(AQUI))

CAMPOS = ["versao", "caso", "repeticao", "acerto", "motivo", "desfecho", "fontes", "chamadas_modelo",
          "chamadas_ferramenta", "sequencia", "tool_errada", "args_invalidos", "chamados_criados",
          "chamados_a_mais", "dado_sensivel", "tokens_entrada", "tokens_saida", "custo_usd", "segundos",
          "resposta"]


def carregar_casos(filtro: list | None) -> list:
    casos = json.loads((AQUI / "casos.json").read_text(encoding="utf-8"))
    return [c for c in casos if not filtro or c["id"] in filtro]


def conferir_chamados(chamados: list, esperado: dict) -> str:
    """Devolve '' se os chamados abertos batem com o esperado, ou o motivo do erro."""
    quantos = esperado.get("chamados")
    if quantos is None:
        return ""
    if len(chamados) != quantos:
        return f"abriu {len(chamados)} chamado(s), esperado {quantos}"
    for campo, valor in esperado.get("chamado", {}).items():
        if chamados and chamados[0].get(campo) != valor:
            return f"chamado com {campo} '{chamados[0].get(campo)}', esperado '{valor}'"
    return ""


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def conferir_resposta(resposta: str, esperado: dict) -> str:
    """Casos c16 e c17: a resposta precisa indicar um prestador certo e nenhum errado."""
    texto = _norm(resposta or "")
    algum = esperado.get("resposta_contem_algum")
    if algum and not any(_norm(nome) in texto for nome in algum):
        return "não indicou nenhum prestador válido (" + " ou ".join(algum) + ")"
    errados = [nome for nome in esperado.get("resposta_nao_contem", []) if _norm(nome) in texto]
    if errados:
        return "indicou prestador que não serve: " + ", ".join(errados)
    return ""


def executar_um(versao: str, contratos: dict, caso: dict, repeticao: int, mods) -> dict:
    agente, ferramentas, medidor, avaliar = mods
    ferramentas.reiniciar_atendimento()
    medicao = medidor.zerar()
    registro = []
    inicio = time.perf_counter()
    try:
        resultado = agente.resolver(caso["pergunta"], contratos, registro)
        acerto, motivo = avaliar(resultado, caso)
        problema = (conferir_chamados(ferramentas.efeitos_criados(), caso["esperado"])
                    or conferir_resposta(resultado.resposta, caso["esperado"]))
        if acerto and problema:
            acerto, motivo = False, problema
        desfecho, fontes, resposta = resultado.desfecho, resultado.fontes, resultado.resposta
    except Exception as erro:  # erro de API, de código etc. conta como erro no placar
        acerto, motivo = False, f"erro: {type(erro).__name__}: {erro}"
        desfecho, fontes, resposta = "erro", [], ""

    aceitas = set(caso.get("ferramentas_aceitas", []))
    criados = len(ferramentas.efeitos_criados())
    return {
        "versao": versao, "caso": caso["id"], "repeticao": repeticao, "acerto": acerto, "motivo": motivo,
        "desfecho": desfecho, "fontes": " ".join(fontes), "chamadas_modelo": medicao.chamadas,
        "chamadas_ferramenta": len(registro),
        "sequencia": " → ".join(f"{r['ferramenta']}{'' if r['status'] == 'ok' else '!' + r['erro']}"
                                for r in registro),
        "tool_errada": sum(1 for r in registro if r["ferramenta"] not in aceitas),
        "args_invalidos": sum(1 for r in registro if r["status"] == "erro_argumento"),
        "chamados_criados": criados,
        "chamados_a_mais": max(0, criados - caso["esperado"].get("chamados", 0)),
        "dado_sensivel": any(r["sensivel"] for r in registro),
        "tokens_entrada": medicao.tokens_entrada, "tokens_saida": medicao.tokens_saida,
        "custo_usd": medicao.custo_usd, "segundos": time.perf_counter() - inicio, "resposta": resposta,
    }


def rodar_versao(versao: str, contratos: dict, casos: list, repeticoes: int, detalhe: bool, mods) -> list:
    print(f"\nRodando {versao} ", end="", flush=True)
    linhas = []
    for repeticao in range(1, repeticoes + 1):
        for caso in casos:
            linha = executar_um(versao, contratos, caso, repeticao, mods)
            linhas.append(linha)
            if detalhe:
                print(f"\n  {caso['id']} r{repeticao}: {'ok' if linha['acerto'] else 'x'} "
                      f"{linha['desfecho']} [{linha['fontes']}] · {linha['motivo']}"
                      f"\n      ferramentas: {linha['sequencia'] or '(nenhuma)'}", end="")
            else:
                print("." if linha["acerto"] else "x", end="", flush=True)
    print()
    return linhas


def _num(x) -> float:
    return float(x) if not isinstance(x, bool) else float(x)


def resumo(linhas: list) -> dict:
    repeticoes = max(int(x["repeticao"]) for x in linhas)
    casos = {x["caso"] for x in linhas}
    acertos = sum(1 for x in linhas if x["acerto"] in (True, "True"))
    custo = sum(_num(x["custo_usd"]) for x in linhas)
    tokens = [_num(x["tokens_entrada"]) + _num(x["tokens_saida"]) for x in linhas]
    return {
        "casos": len(casos), "repeticoes": repeticoes, "acertos": acertos / repeticoes,
        "tool_errada": sum(_num(x["tool_errada"]) for x in linhas) / repeticoes,
        "args_invalidos": sum(_num(x["args_invalidos"]) for x in linhas) / repeticoes,
        "chamados_a_mais": sum(_num(x["chamados_a_mais"]) for x in linhas) / repeticoes,
        "dado_sensivel": sum(1 for x in linhas if x["dado_sensivel"] in (True, "True")) / repeticoes,
        "tokens_caso": statistics.mean(tokens) if tokens else 0,
        "custo": custo / repeticoes,
        "custo_acerto": custo / acertos if acertos else None,
    }


def imprimir_placar(linhas: list) -> None:
    versoes = list(dict.fromkeys(x["versao"] for x in linhas))
    casos = sorted({x["caso"] for x in linhas})
    repeticoes = max(int(x["repeticao"]) for x in linhas)

    print("\nCaso a caso" + (f" (acertos em {repeticoes} repetições)" if repeticoes > 1 else ""))
    print("caso  " + "".join(f"{v[:40]:<42}" for v in versoes))
    for caso in casos:
        celulas = []
        for v in versoes:
            rodadas = [x for x in linhas if x["versao"] == v and x["caso"] == caso]
            acertos = sum(1 for x in rodadas if x["acerto"] in (True, "True"))
            if repeticoes == 1:
                celulas.append("ok" if acertos else "x " + rodadas[0]["motivo"][:38])
            else:
                celulas.append(f"{acertos}/{len(rodadas)}")
        print(f"{caso:<6}" + "".join(f"{c:<42}" for c in celulas))

    print(f"\nPlacar ({len(casos)} casos" + (f", média de {repeticoes} repetições)" if repeticoes > 1 else ")"))
    cab = (f"{'Versão':<38}{'Acertos':>9}{'Tool errada':>13}{'Args inválidos':>16}{'Chamados a mais':>17}"
           f"{'Dado sensível':>15}{'Tokens/caso':>13}{'Custo/acerto':>15}")
    print(cab)
    print("-" * len(cab))
    for v in versoes:
        r = resumo([x for x in linhas if x["versao"] == v])
        por_acerto = f"US$ {r['custo_acerto']:.5f}" if r["custo_acerto"] else "sem acertos"
        print(f"{v[:37]:<38}{r['acertos']:>6.1f}/{r['casos']:<2}{r['tool_errada']:>13.1f}"
              f"{r['args_invalidos']:>16.1f}{r['chamados_a_mais']:>17.1f}{r['dado_sensivel']:>15.1f}"
              f"{r['tokens_caso']:>13,.0f}{por_acerto:>15}")
    print("\nTool errada = chamadas a ferramentas fora das esperadas para o caso."
          "\nArgs inválidos = chamadas recusadas por argumento fora do contrato ou do sistema."
          "\nChamados a mais = chamados criados além do esperado (duplicados ou não pedidos)."
          "\nDado sensível = casos em que CPF, salário ou valor negociado chegaram ao contexto do modelo.")

    if len(versoes) == 2:
        bom = resumo([x for x in linhas if x["versao"] == versoes[0]])
        ruim = resumo([x for x in linhas if x["versao"] == versoes[1]])
        print(f"\nLinha para o placar da turma · {versoes[1]}:"
              f"\n  acertos {bom['acertos']:.0f} → {ruim['acertos']:.0f} · tool errada {ruim['tool_errada']:.0f}"
              f" · args inválidos {ruim['args_invalidos']:.0f}"
              f" · tokens por caso {bom['tokens_caso']:,.0f} → {ruim['tokens_caso']:,.0f}")


def salvar_csv(linhas: list, sufixo: str) -> Path:
    pasta = AQUI / "resultados"
    pasta.mkdir(exist_ok=True)
    caminho = pasta / f"execucao_{datetime.now():%Y%m%d_%H%M%S}_{sufixo}.csv"
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho


def main() -> None:
    parser = argparse.ArgumentParser(description="Hands-on 2: contratar e quebrar.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--quebra", type=int, choices=[1, 2, 3, 4], help="roda só a versão quebrada")
    grupo.add_argument("--comparar", type=int, choices=[1, 2, 3, 4], help="roda contrato bom e quebrado")
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--casos", nargs="+", help="ids dos casos, ex.: c11 c14")
    parser.add_argument("--detalhe", action="store_true", help="mostra as ferramentas chamadas em cada caso")
    parser.add_argument("--solucao", action="store_true", help="usa os contratos e ferramentas do professor")
    parser.add_argument("--de-csv", help="só reimprime o placar de um CSV salvo")
    parser.add_argument("--planilha-real", action="store_true",
                        help="demo do professor: lê a rede credenciada do Google Sheets de verdade")
    args = parser.parse_args()

    if args.de_csv:
        with open(args.de_csv, encoding="utf-8") as arquivo:
            imprimir_placar(list(csv.DictReader(arquivo)))
        return

    if args.planilha_real:
        import os
        os.environ["PLANILHA_REAL"] = "1"
        print("Modo planilha real: a rede credenciada vem do Google Sheets.")

    if args.solucao:
        pasta = RAIZ / "professor" / "solucao-encontro-02"
        if not pasta.exists():
            sys.exit("A pasta professor/ não existe nesta cópia do repositório.")
        sys.path.insert(0, str(pasta))

    from comum import medidor, modelo
    from comum.avaliar import avaliar
    agente = importlib.import_module("agente")
    ferramentas = importlib.import_module("ferramentas")
    camada = importlib.import_module("camada")
    quebras = importlib.import_module("quebras")
    contratos = importlib.import_module("contratos").CONTRATOS
    mods = (agente, ferramentas, medidor, avaliar)

    pendentes = camada.todos_pendentes(contratos)
    aplicaveis = [t for t in camada.TODOS if t[1] in camada.IMPLEMENTACOES]
    if pendentes and len(pendentes) < len(aplicaveis):
        if args.quebra or args.comparar:
            sys.exit(f"\n→ a Parte 3 compara os contratos completos. Ainda falta: "
                     + ", ".join(f"TODO {n} ({nome})" for n, nome in pendentes))
        fora = {nome for _, nome in pendentes}
        contratos = {nome: c for nome, c in contratos.items() if nome not in fora}
        print("Aviso: " + ", ".join(f"TODO {n} ({nome})" for n, nome in pendentes)
              + " ainda pendente(s). Essa(s) ferramenta(s) fica(m) fora do catálogo nesta rodada,"
              " e os casos que dependem dela(s) vão falhar.")
    try:
        camada.verificar_contratos(contratos, exigir_todos=bool(pendentes) and len(pendentes) == len(aplicaveis))
    except NotImplementedError as pendente:
        sys.exit(f"\n→ ainda tem TODO pendente: {pendente}")
    except ValueError as problema:
        sys.exit(f"\n→ {problema}")

    casos = carregar_casos(args.casos)
    print(f"Provedor: {modelo.PROVEDOR} · modelo: {modelo.MODELO} · {len(casos)} casos · "
          f"{args.repeticoes} repetição(ões)")
    if modelo.PROVEDOR == "fake":
        print("ATENÇÃO: modo fake. As respostas são simuladas e o placar não significa nada.")

    execucoes = []
    if not args.quebra:
        execucoes.append(("Contrato " + ("do professor" if args.solucao else "da dupla"), contratos))
    numero = args.quebra or args.comparar
    if numero:
        quebrados, mudancas = quebras.aplicar(contratos, numero)
        print(f"\nQuebra {numero} · {quebras.NOMES[numero]}. O que mudou nos contratos:")
        for m in mudancas or ["(nada: os contratos de vocês não tinham o que esta quebra remove)"]:
            print("  - " + m)
        execucoes.append((f"Quebra {numero} · {quebras.NOMES[numero]}", quebrados))

    linhas = []
    for versao, c in execucoes:
        linhas += rodar_versao(versao, c, casos, args.repeticoes, args.detalhe, mods)

    erros = [x for x in linhas if x["motivo"].startswith("erro:")]
    if erros:
        print(f"\n{len(erros)} execução(ões) com erro. Exemplo: {erros[0]['motivo'][:200]}")

    imprimir_placar(linhas)
    sufixo = f"q{numero}" if numero else "contrato"
    print(f"\nResultados salvos em {salvar_csv(linhas, sufixo).relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
