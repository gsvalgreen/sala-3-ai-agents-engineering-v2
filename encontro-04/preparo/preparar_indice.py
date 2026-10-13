"""Gera o índice da busca do Encontro 4 a partir da configuração final do Encontro 3.   (PROFESSOR)

    python encontro-04/preparo/preparar_indice.py

Roda uma vez, na máquina do professor, com o ambiente do Encontro 3 (sentence-transformers,
langchain-text-splitters). Não chama a API do modelo: não tem custo.

Escreve em encontro-04/dados/:
    indice-aurora.json     os trechos da wiki (corte por estrutura) com os metadados
    vetores-aurora.npz     o vetor de cada trecho
    consultas-aurora.npz   o vetor de cada pergunta dos casos (o gravar_replay.py acrescenta as
                           consultas que os agentes fizerem)

Com isso a busca do Encontro 4 roda só com numpy, no Colab ou em qualquer máquina.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
E4 = AQUI.parent
E3 = E4.parent / "encontro-03"
sys.path.insert(0, str(E3))
sys.path.insert(0, str(E4))

import rag_aurora as r  # noqa: E402

DADOS = E4 / "dados"


def main() -> None:
    DADOS.mkdir(exist_ok=True)
    docs = r.carregar_corpus()
    chunks = r.chunks_por_estrutura(docs)
    print(f"{len(docs)} páginas · {r.resumo_chunks(chunks)}")

    emb = r.Embeddings()
    inicio = time.perf_counter()
    vetores = np.asarray(emb.passagens([c.page_content for c in chunks]), dtype=np.float32)
    print(f"Embeddings dos trechos: {vetores.shape} em {time.perf_counter() - inicio:.1f}s ({emb.nome})")

    registros = [{
        "chunk_id": c.metadata["chunk_id"], "id": c.metadata["id"], "titulo": c.metadata["titulo"],
        "secao": c.metadata.get("secao", ""), "espaco": c.metadata["espaco"],
        "vigencia": c.metadata["vigencia"], "autoridade": c.metadata["autoridade"],
        "politica": c.metadata["politica"], "texto": c.page_content,
    } for c in chunks]
    (DADOS / "indice-aurora.json").write_text(json.dumps(
        {"modelo_embeddings": emb.nome, "gerado_em": time.strftime("%Y-%m-%d %H:%M"), "chunks": registros},
        ensure_ascii=False, indent=0), encoding="utf-8")
    np.savez_compressed(DADOS / "vetores-aurora.npz", passagens=vetores)

    casos = json.loads((E4 / "casos.json").read_text(encoding="utf-8"))
    perguntas = sorted({c["pergunta"] for c in casos})
    consultas = np.asarray(emb.consultas(perguntas), dtype=np.float32)
    np.savez_compressed(DADOS / "consultas-aurora.npz", textos=np.array(perguntas), vetores=consultas)

    # Conferência: a busca nova devolve a mesma página que a busca do Encontro 3 nos casos?
    import busca
    vet, lex = r.IndiceVetorial(chunks, emb), r.IndiceLexico(chunks)
    diferentes = []
    for caso in casos:
        a = [c.metadata["id"] for c, _ in r.so_a_versao_vigente(
            r.busca_hibrida(vet, lex, caso["pergunta"], k=18, filtro={"autoridade": "oficial"}))[:3]]
        b = [x["id"] for x in busca.buscar(caso["pergunta"])]
        if a != b:
            diferentes.append((caso["id"], a, b))
    print(f"\nConferência com o Encontro 3: {len(casos) - len(diferentes)}/{len(casos)} casos com as mesmas páginas.")
    for id_, a, b in diferentes:
        print(f"  {id_}: Encontro 3 {a} · Encontro 4 {b}")
    print(f"\nPronto. Arquivos em {DADOS}. Próximo passo: preparo/gravar_replay.py")


if __name__ == "__main__":
    main()
