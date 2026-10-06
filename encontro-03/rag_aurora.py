"""
rag_aurora.py — as peças do RAG do Encontro 3, pequenas e à vista.

O notebook chama estas funções para que cada etapa caiba numa célula curta.
Nada aqui é mágico: abra o arquivo quando quiser ver como uma peça funciona.

    carregar_corpus        lê as páginas da wiki com os metadados do cabeçalho
    chunks_por_caracteres  corte por tamanho (LangChain RecursiveCharacterTextSplitter)
    chunks_por_estrutura   corte pelas seções do documento (MarkdownHeaderTextSplitter)
    Embeddings             modelo local multilíngue (sentence-transformers)
    IndiceVetorial         Chroma embutido, em memória
    IndiceLexico           BM25, busca por palavra exata
    busca_hibrida          junta as duas listas por Reciprocal Rank Fusion
    so_a_versao_vigente    descarta versões antigas da mesma política
    avaliar / placar       recall@k contra o gabarito (casos.json)
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

PASTA = Path(__file__).resolve().parent
CORPUS = PASTA / "corpus"
CASOS = PASTA / "casos.json"
MODELO_PADRAO = os.environ.get("AURORA_EMBEDDINGS", "intfloat/multilingual-e5-small")


# ======================================================================= corpus

def carregar_corpus(pasta: Path | str = CORPUS) -> list[Document]:
    """Uma página da wiki vira um Document: o texto e os metadados do cabeçalho."""
    docs = []
    for caminho in sorted(Path(pasta).glob("*.md")):
        _, cabecalho, texto = caminho.read_text(encoding="utf-8").split("---", 2)
        meta = {}
        for linha in cabecalho.strip().splitlines():
            chave, valor = linha.split(":", 1)
            meta[chave.strip()] = valor.strip()
        meta["arquivo"] = caminho.name
        # Corpus de outra equipe pode não ter todos os campos. Valores neutros:
        meta.setdefault("id", caminho.stem)
        meta.setdefault("titulo", caminho.stem)
        meta.setdefault("espaco", "-")
        meta.setdefault("politica", meta["id"])
        meta.setdefault("vigencia", "")
        meta.setdefault("autoridade", "oficial")
        docs.append(Document(page_content=texto.strip(), metadata=meta))
    return docs


def pagina(docs: list[Document], id_: str) -> Document:
    return next(d for d in docs if d.metadata["id"] == id_)


# ===================================================================== chunking

def chunks_por_caracteres(docs: list[Document], tamanho: int = 400, sobreposicao: int = 0) -> list[Document]:
    """Corta por contagem de caracteres. Não sabe o que é uma cláusula."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=tamanho, chunk_overlap=sobreposicao)
    chunks = splitter.split_documents(docs)
    return _numerar(chunks)


def chunks_por_estrutura(docs: list[Document], prefixar_titulo: bool = True) -> list[Document]:
    """Corta nas seções (##) do documento. Cada cláusula fica com a sua seção.

    prefixar_titulo=True escreve "Título > Seção" no começo do chunk: sem isso,
    um chunk "5.3 Esse teto não vale..." não diz de que política ele é.
    """
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "titulo_pagina"), ("##", "secao")])
    chunks = []
    for doc in docs:
        for parte in splitter.split_text(doc.page_content):
            meta = {**doc.metadata, **parte.metadata}
            texto = parte.page_content
            if prefixar_titulo:
                caminho = " > ".join(x for x in (doc.metadata["titulo"], meta.get("secao")) if x)
                texto = f"{caminho}\n{texto}"
            chunks.append(Document(page_content=texto, metadata=meta))
    return _numerar(chunks)


def _numerar(chunks: list[Document]) -> list[Document]:
    contagem: dict[str, int] = {}
    for c in chunks:
        n = contagem.get(c.metadata["id"], 0)
        contagem[c.metadata["id"]] = n + 1
        c.metadata["chunk_id"] = f"{c.metadata['id']}#{n}"
    return chunks


def resumo_chunks(chunks: list[Document]) -> str:
    tamanhos = sorted(len(c.page_content) for c in chunks)
    return (f"{len(chunks)} chunks · tamanho mínimo {tamanhos[0]}, "
            f"mediano {tamanhos[len(tamanhos) // 2]}, máximo {tamanhos[-1]} caracteres")


# =================================================================== embeddings

class Embeddings:
    """Modelo local, roda em CPU. Na primeira vez baixa ~470 MB do Hugging Face.

    A família E5 foi treinada com prefixos: "query: " na pergunta e "passage: "
    no trecho. Esquecer os prefixos piora a busca sem dar erro nenhum.
    """

    _carregados: dict = {}

    def __init__(self, modelo: str = MODELO_PADRAO):
        from sentence_transformers import SentenceTransformer
        self.nome = modelo
        if modelo not in Embeddings._carregados:      # carrega uma vez só por sessão
            Embeddings._carregados[modelo] = SentenceTransformer(modelo)
        self.modelo = Embeddings._carregados[modelo]
        self._prefixos = "e5" in modelo.lower()

    def passagens(self, textos: list[str]):
        if self._prefixos:
            textos = [f"passage: {t}" for t in textos]
        return self.modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False)

    def consultas(self, textos: list[str]):
        if self._prefixos:
            textos = [f"query: {t}" for t in textos]
        return self.modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False)


def similaridade(a, b) -> float:
    """Cosseno. Os vetores já vêm normalizados, então é só o produto interno."""
    return float((a * b).sum())


# ================================================================ índice vetorial

class IndiceVetorial:
    """Chroma embutido, em memória. Nós calculamos os embeddings e entregamos prontos."""

    _contador = 0

    def __init__(self, chunks: list[Document], emb: Embeddings, nome: str | None = None):
        import chromadb
        IndiceVetorial._contador += 1
        self.emb = emb
        self.chunks = {c.metadata["chunk_id"]: c for c in chunks}
        self.colecao = chromadb.EphemeralClient().create_collection(
            name=nome or f"aurora-{IndiceVetorial._contador}", embedding_function=None)
        vetores = emb.passagens([c.page_content for c in chunks])
        self.colecao.add(
            ids=[c.metadata["chunk_id"] for c in chunks],
            documents=[c.page_content for c in chunks],
            metadatas=[_meta_simples(c.metadata) for c in chunks],
            embeddings=[v.tolist() for v in vetores],
        )

    def buscar(self, pergunta: str, k: int = 3, filtro: dict | None = None) -> list[tuple[Document, float]]:
        """Devolve [(chunk, similaridade)], do mais parecido para o menos.

        O Chroma usa distância L2 ao quadrado por padrão. Com vetores
        normalizados, similaridade de cosseno = 1 - distância / 2.
        """
        r = self.colecao.query(query_embeddings=[self.emb.consultas([pergunta])[0].tolist()],
                               n_results=k, where=filtro)
        return [(self.chunks[i], round(1 - d / 2, 3)) for i, d in zip(r["ids"][0], r["distances"][0])]


def _meta_simples(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}


# ================================================================== índice léxico

_VAZIAS = set("""
a o as os um uma de do da dos das no na nos nas em para por com que qual quais
quanto quantos quantas como e ou se eu meu minha me ao aos mais nao sim ser ter
tem tenho posso pode isso este essa esse sobre faco preciso pra the
""".split())


def tokenizar(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return [t for t in re.findall(r"[a-z0-9]+", sem_acento) if t not in _VAZIAS]


class IndiceLexico:
    """BM25: pontua por palavra em comum, dando mais peso às palavras raras."""

    def __init__(self, chunks: list[Document]):
        from rank_bm25 import BM25Okapi
        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenizar(c.page_content) for c in chunks])

    def buscar(self, pergunta: str, k: int = 3, filtro: dict | None = None) -> list[tuple[Document, float]]:
        """filtro aceita só igualdade simples, por exemplo {"autoridade": "oficial"}."""
        notas = self.bm25.get_scores(tokenizar(pergunta))
        ordem = sorted(range(len(notas)), key=lambda i: -notas[i])
        if filtro:
            ordem = [i for i in ordem if all(self.chunks[i].metadata.get(c) == v for c, v in filtro.items())]
        return [(self.chunks[i], round(float(notas[i]), 2)) for i in ordem[:k]]


def busca_hibrida(vetorial: IndiceVetorial, lexico: IndiceLexico, pergunta: str, k: int = 3,
                  filtro: dict | None = None, profundidade: int = 10, c: int = 60) -> list[tuple[Document, float]]:
    """Reciprocal Rank Fusion: cada lista vota com 1/(c + posição).

    Não tenta comparar a nota do BM25 com a do vetor, que estão em escalas
    diferentes. Só a posição de cada chunk em cada lista importa.
    """
    votos: dict[str, float] = {}
    chunks: dict[str, Document] = {}
    for lista in (vetorial.buscar(pergunta, profundidade, filtro), lexico.buscar(pergunta, profundidade, filtro)):
        for pos, (chunk, _) in enumerate(lista, start=1):
            cid = chunk.metadata["chunk_id"]
            votos[cid] = votos.get(cid, 0) + 1 / (c + pos)
            chunks[cid] = chunk
    melhores = sorted(votos, key=lambda cid: -votos[cid])[:k]
    return [(chunks[cid], round(votos[cid], 4)) for cid in melhores]


# ============================================================ conflito de versões

def so_a_versao_vigente(resultados: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
    """Para cada política, mantém só os chunks da página com a vigência mais recente."""
    vigente: dict[str, str] = {}
    for chunk, _ in resultados:
        pol, vig = chunk.metadata["politica"], chunk.metadata["vigencia"]
        vigente[pol] = max(vigente.get(pol, ""), vig)
    return [(c, s) for c, s in resultados if c.metadata["vigencia"] == vigente[c.metadata["politica"]]]


# ===================================================================== exibição

def mostrar(resultados: list[tuple[Document, float]], largura: int = 160) -> None:
    for pos, (chunk, nota) in enumerate(resultados, start=1):
        m = chunk.metadata
        texto = " ".join(chunk.page_content.split())
        if len(texto) > largura:
            texto = texto[:largura] + "…"
        print(f"{pos}. [{nota}] {m['chunk_id']}  ·  {m.get('espaco', '-')} · "
              f"vigência {m.get('vigencia') or '-'} · {m.get('autoridade', '-')}")
        print(f"   {texto}")


def mostrar_chunks(chunks: list[Document], id_pagina: str) -> None:
    for c in chunks:
        if c.metadata["id"] == id_pagina:
            print(f"── {c.metadata['chunk_id']} ({len(c.page_content)} caracteres) " + "─" * 30)
            print(c.page_content)
            print()


# ==================================================================== avaliação

def carregar_casos(caminho: Path | str = CASOS) -> list[dict]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def _contem(chunk: Document, trecho: str) -> bool:
    return " ".join(trecho.split()) in " ".join(chunk.page_content.split())


def avaliar(buscar, casos: list[dict], k: int = 3) -> list[dict]:
    """Roda cada caso no buscador e marca:

    achou        o trecho esperado está em algum dos k chunks
    contaminou   um trecho errado (versão velha, FAQ informal, regra sem a exceção)
                 aparece ANTES do trecho certo, ou aparece e o certo não
    """
    linhas = []
    for caso in casos:
        if caso["categoria"] == "sem-resposta":
            continue
        resultados = buscar(caso["pergunta"], k)
        pos_ok = next((i for i, (c, _) in enumerate(resultados) if _contem(c, caso["trecho_esperado"])), None)
        enganosos = caso.get("trechos_enganosos", [])
        pos_ruim = next((i for i, (c, _) in enumerate(resultados)
                         if any(_contem(c, t) for t in enganosos)), None)
        contaminou = pos_ruim is not None and (pos_ok is None or pos_ruim < pos_ok)
        linhas.append({"id": caso["id"], "categoria": caso["categoria"],
                       "achou": pos_ok is not None, "contaminou": contaminou})
    return linhas


def placar(linhas: list[dict], titulo: str = "") -> dict:
    """Imprime o resultado por categoria e devolve os totais."""
    cats: dict[str, list[dict]] = {}
    for l in linhas:
        cats.setdefault(l["categoria"], []).append(l)
    if titulo:
        print(titulo)
    print(f"  {'categoria':<14}{'achou':>8}{'contaminou':>13}")
    for cat, ls in cats.items():
        print(f"  {cat:<14}{sum(l['achou'] for l in ls):>4}/{len(ls):<3}{sum(l['contaminou'] for l in ls):>9}/{len(ls)}")
    total = {"achou": sum(l["achou"] for l in linhas), "contaminou": sum(l["contaminou"] for l in linhas),
             "casos": len(linhas)}
    print(f"  {'TOTAL':<14}{total['achou']:>4}/{total['casos']:<3}{total['contaminou']:>9}/{total['casos']}")
    return total


def falhas(linhas: list[dict]) -> list[str]:
    return [l["id"] for l in linhas if not l["achou"] or l["contaminou"]]


# ============================================================ experimentos

def registrar(experimentos: list[dict], nome: str, linhas: list[dict]) -> None:
    """Guarda o resultado de uma configuração para comparar depois com comparar()."""
    experimentos[:] = [e for e in experimentos if e["nome"] != nome]
    experimentos.append({"nome": nome, "linhas": linhas})


def comparar(experimentos: list[dict]) -> None:
    """Uma linha por configuração, uma coluna por categoria: achou (contaminou)."""
    cats = []
    for e in experimentos:
        for l in e["linhas"]:
            if l["categoria"] not in cats:
                cats.append(l["categoria"])
    larg = max([len(e["nome"]) for e in experimentos] + [13]) + 2
    print("configuração".ljust(larg) + "".join(c[:11].rjust(13) for c in cats) + "TOTAL".rjust(12))
    for e in experimentos:
        celulas = []
        for c in cats + ["*"]:
            ls = [l for l in e["linhas"] if c == "*" or l["categoria"] == c]
            celulas.append(f"{sum(l['achou'] for l in ls)}/{len(ls)} ({sum(l['contaminou'] for l in ls)})")
        print(e["nome"].ljust(larg) + "".join(x.rjust(13) for x in celulas[:-1]) + celulas[-1].rjust(12))
    print("\nformato: achou/casos (contaminados). Melhor = achou alto e contaminados zero.")


# ============================================================== checkpoint

def checkpoint(corpus: Path | str = CORPUS, modelo: str = MODELO_PADRAO) -> dict:
    """Monta do zero tudo o que as etapas usam. Para quem se perdeu no caminho."""
    docs = carregar_corpus(corpus)
    emb = Embeddings(modelo)
    chunks_c = chunks_por_caracteres(docs)
    chunks_e = chunks_por_estrutura(docs)
    return {
        "docs": docs, "emb": emb, "chunks_c": chunks_c, "chunks_e": chunks_e,
        "vet_c": IndiceVetorial(chunks_c, emb), "vet_e": IndiceVetorial(chunks_e, emb),
        "lex_e": IndiceLexico(chunks_e),
    }


def tabela_markdown(experimentos: list[dict]) -> str:
    """A mesma comparação de comparar(), em markdown, para colar na nota de chunking."""
    cats = []
    for e in experimentos:
        for l in e["linhas"]:
            if l["categoria"] not in cats:
                cats.append(l["categoria"])
    linhas = ["| configuração | " + " | ".join(cats) + " | total |",
              "|---|" + "---|" * (len(cats) + 1)]
    for e in experimentos:
        cel = []
        for c in cats + ["*"]:
            ls = [l for l in e["linhas"] if c == "*" or l["categoria"] == c]
            cel.append(f"{sum(l['achou'] for l in ls)}/{len(ls)} ({sum(l['contaminou'] for l in ls)})")
        linhas.append(f"| {e['nome']} | " + " | ".join(cel) + " |")
    return "\n".join(linhas)


# ============================================================ montar buscador

def montar_buscador(docs: list[Document], emb: Embeddings, estrategia: str = "estrutura",
                    tamanho: int = 400, sobreposicao: int = 0, prefixar_titulo: bool = True,
                    busca: str = "vetor", so_vigente: bool = False, so_oficial: bool = False):
    """Monta um buscador(pergunta, k) a partir das decisões de projeto.

    estrategia   "tamanho" ou "estrutura"
    busca        "vetor", "bm25" ou "hibrida"
    so_vigente   para cada politica, só a página de vigência mais recente
    so_oficial   descarta páginas com autoridade diferente de "oficial"
    """
    if estrategia == "tamanho":
        chunks = chunks_por_caracteres(docs, tamanho, sobreposicao)
    elif estrategia == "estrutura":
        chunks = chunks_por_estrutura(docs, prefixar_titulo)
    else:
        raise ValueError('estrategia deve ser "tamanho" ou "estrutura"')
    if busca not in ("vetor", "bm25", "hibrida"):
        raise ValueError('busca deve ser "vetor", "bm25" ou "hibrida"')
    vet = IndiceVetorial(chunks, emb) if busca in ("vetor", "hibrida") else None
    lex = IndiceLexico(chunks) if busca in ("bm25", "hibrida") else None
    filtro = {"autoridade": "oficial"} if so_oficial else None

    def buscar(pergunta: str, k: int = 3):
        n = k * 3 if so_vigente else k
        if busca == "vetor":
            res = vet.buscar(pergunta, n, filtro)
        elif busca == "bm25":
            res = lex.buscar(pergunta, n, filtro)
        else:
            res = busca_hibrida(vet, lex, pergunta, n, filtro)
        if so_vigente:
            res = so_a_versao_vigente(res)
        return res[:k]

    buscar.chunks = chunks
    return buscar


# ============================================================== busca na web

def buscar_na_web(consulta: str, limite: int = 3) -> list[dict]:
    """A mesma ferramenta real do Encontro 2 (encontro-02/mcp_aurora/busca_web.py), pela API do Serper.

    Só para a demonstração do professor: precisa de SERPER_API_KEY no .env da raiz.
    Sem chave ou sem rede, avisa e devolve uma lista vazia, sem quebrar o notebook.
    """
    import importlib.util
    import sys
    arquivo = next((d / "encontro-02" / "mcp_aurora" / "busca_web.py" for d in (PASTA, *PASTA.parents)
                    if (d / "encontro-02" / "mcp_aurora" / "busca_web.py").exists()), None)
    if arquivo is None:
        print(f"Busca na web indisponível: não achei encontro-02/mcp_aurora/busca_web.py acima de {PASTA}. "
              "A pasta encontro-03 precisa estar dentro do repositório, ao lado de encontro-02. "
              "Pode seguir para a Etapa 8.")
        return []
    pasta_e2 = arquivo.parent.parent
    if str(pasta_e2) not in sys.path:          # busca_web usa ferramentas.py do Encontro 2 para os erros
        sys.path.append(str(pasta_e2))
    try:
        spec = importlib.util.spec_from_file_location("busca_web", arquivo)
        busca_web = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(busca_web)
        return busca_web.buscar_na_web(consulta, limite)["resultados"]
    except Exception as erro:
        motivo = getattr(erro, "mensagem", None) or f"{type(erro).__name__}: {erro}"
        print(f"Busca na web indisponível ({motivo}). Pode seguir para a Etapa 8.")
        return []


def mostrar_web(resultados: list[dict], largura: int = 160) -> None:
    for pos, r in enumerate(resultados, start=1):
        trecho = " ".join(r.get("trecho", "").split())
        if len(trecho) > largura:
            trecho = trecho[:largura] + "…"
        print(f"{pos}. {r.get('titulo', '')}")
        print(f"   {r.get('link', '')}")
        print(f"   {trecho}")
