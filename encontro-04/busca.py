"""
busca.py — a busca da Aula 3, já indexada, para rodar em qualquer lugar.

É a configuração final do Encontro 3, a mesma do agente que decide buscar:
corte por estrutura, busca híbrida (vetor + BM25 por Reciprocal Rank Fusion),
só fontes oficiais e só a versão vigente de cada política.

A diferença é onde ela roda. Os vetores dos trechos e das consultas já vêm
calculados em dados/, gerados uma vez pelo professor (preparo/preparar_indice.py).
Por isso este arquivo só precisa de numpy: nada de torch, Chroma ou download
de 470 MB. Se aparecer uma consulta nova, que não está em dados/, o modelo de
embeddings é carregado na hora (precisa de sentence-transformers).

    buscar(pergunta, espacos=None, k=3)   a busca, opcionalmente presa a espaços da wiki
    ESPACOS                               os espaços que existem no índice
    salvar_consultas()                    guarda em dados/ os vetores de consultas novas
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"
ARQ_CHUNKS = DADOS / "indice-aurora.json"
ARQ_VETORES = DADOS / "vetores-aurora.npz"
ARQ_CONSULTAS = DADOS / "consultas-aurora.npz"


# ===================================================================== BM25

# As mesmas palavras vazias e a mesma tokenização do rag_aurora.py, do Encontro 3.
_VAZIAS = set("""
a o as os um uma de do da dos das no na nos nas em para por com que qual quais
quanto quantos quantas como e ou se eu meu minha me ao aos mais nao sim ser ter
tem tenho posso pode isso este essa esse sobre faco preciso pra the
""".split())


def tokenizar(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return [t for t in re.findall(r"[a-z0-9]+", sem_acento) if t not in _VAZIAS]


class BM25:
    """O BM25Okapi do pacote rank-bm25 (k1=1.5, b=0.75, epsilon=0.25), em poucas linhas."""

    def __init__(self, textos: list[str], k1: float = 1.5, b: float = 0.75, epsilon: float = 0.25):
        docs = [Counter(tokenizar(t)) for t in textos]
        self.k1, self.b, self.docs = k1, b, docs
        self.tamanhos = np.array([sum(d.values()) for d in docs], dtype=float)
        self.media = self.tamanhos.mean()
        n = len(docs)
        presenca = Counter(p for d in docs for p in d)
        self.idf = {p: math.log(n - f + 0.5) - math.log(f + 0.5) for p, f in presenca.items()}
        piso = epsilon * (sum(self.idf.values()) / len(self.idf))
        self.idf = {p: (piso if v < 0 else v) for p, v in self.idf.items()}

    def notas(self, pergunta: str) -> np.ndarray:
        notas = np.zeros(len(self.docs))
        norma = self.k1 * (1 - self.b + self.b * self.tamanhos / self.media)
        for termo in tokenizar(pergunta):
            freq = np.array([d.get(termo, 0) for d in self.docs], dtype=float)
            notas += self.idf.get(termo, 0) * (freq * (self.k1 + 1) / (freq + norma))
        return notas


# ===================================================================== índice

class _Indice:
    def __init__(self):
        if not ARQ_CHUNKS.exists() or not ARQ_VETORES.exists():
            raise FileNotFoundError(
                f"Índice não encontrado em {DADOS}. O professor gera uma vez com "
                "`python encontro-04/preparo/preparar_indice.py` e publica a pasta dados/.")
        dados = json.loads(ARQ_CHUNKS.read_text(encoding="utf-8"))
        self.modelo_embeddings = dados["modelo_embeddings"]
        self.chunks = dados["chunks"]
        self.vetores = np.load(ARQ_VETORES)["passagens"].astype(np.float32)
        self.bm25 = BM25([c["texto"] for c in self.chunks])
        self.consultas: dict[str, np.ndarray] = {}
        if ARQ_CONSULTAS.exists():
            z = np.load(ARQ_CONSULTAS, allow_pickle=False)
            for texto, vetor in zip(z["textos"], z["vetores"]):
                self.consultas[str(texto)] = vetor.astype(np.float32)
        self.novas = 0
        self._modelo = None

    def vetor_da_consulta(self, texto: str) -> np.ndarray:
        if texto not in self.consultas:
            self.consultas[texto] = self._embeddings([texto])[0]
            self.novas += 1
        return self.consultas[texto]

    def _embeddings(self, textos: list[str]) -> np.ndarray:
        if self._modelo is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise RuntimeError(
                    "Esta consulta não está no índice gravado e o modelo de embeddings não está instalado.\n"
                    "Isso só acontece fora do menu do notebook. Para buscar algo novo: "
                    "pip install sentence-transformers") from None
            self._modelo = SentenceTransformer(self.modelo_embeddings)
        if "e5" in self.modelo_embeddings.lower():
            textos = [f"query: {t}" for t in textos]
        return self._modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


_indice: _Indice | None = None


def indice() -> _Indice:
    global _indice
    if _indice is None:
        _indice = _Indice()
    return _indice


def espacos() -> list[str]:
    return sorted({c["espaco"] for c in indice().chunks})


# ===================================================================== busca

def _vale(chunk: dict, espacos_permitidos) -> bool:
    if chunk["autoridade"] != "oficial":
        return False
    return espacos_permitidos is None or chunk["espaco"] in espacos_permitidos


def buscar(pergunta: str, espacos: list[str] | str | None = None, k: int = 3,
           profundidade: int = 10, c: int = 60) -> list[dict]:
    """A busca híbrida do Encontro 3, com o filtro de espaço aplicado ANTES da busca.

    espacos=None busca na wiki inteira (o agente único). Uma lista prende a busca àqueles
    espaços: é assim que cada especialista enxerga só a sua parte da wiki.
    Devolve até k registros: id, titulo, secao, espaco, vigencia, autoridade, chunk_id, relevancia, trecho.
    """
    if isinstance(espacos, str):
        espacos = [espacos]
    ind = indice()
    validos = [i for i, ch in enumerate(ind.chunks) if _vale(ch, espacos)]
    if not validos:
        return []

    # vetor: similaridade de cosseno (os vetores já vêm normalizados)
    sims = ind.vetores[validos] @ ind.vetor_da_consulta(pergunta)
    vet = [validos[i] for i in np.argsort(-sims, kind="stable")[:profundidade]]
    # BM25: notas calculadas sobre a wiki inteira, como no Encontro 3, e depois filtradas
    notas = ind.bm25.notas(pergunta)
    permitidos = set(validos)
    lex = [i for i in np.argsort(-notas, kind="stable") if i in permitidos][:profundidade]

    votos: dict[int, float] = {}
    for lista in (vet, lex):
        for pos, i in enumerate(lista, start=1):
            votos[int(i)] = votos.get(int(i), 0) + 1 / (c + pos)
    candidatos = sorted(votos, key=lambda i: -votos[i])[:18]

    # só a versão vigente de cada política
    vigente: dict[str, str] = {}
    for i in candidatos:
        ch = ind.chunks[i]
        vigente[ch["politica"]] = max(vigente.get(ch["politica"], ""), ch["vigencia"])
    candidatos = [i for i in candidatos if ind.chunks[i]["vigencia"] == vigente[ind.chunks[i]["politica"]]]

    saida = []
    for i in candidatos[:k]:
        ch = ind.chunks[i]
        saida.append({"id": ch["id"], "titulo": ch["titulo"], "secao": ch["secao"], "espaco": ch["espaco"],
                      "vigencia": ch["vigencia"], "autoridade": ch["autoridade"], "chunk_id": ch["chunk_id"],
                      "relevancia": round(votos[i], 4), "trecho": ch["texto"]})
    return saida


def salvar_consultas() -> int:
    """Guarda em dados/ os vetores das consultas novas. Devolve quantas consultas há no arquivo."""
    ind = indice()
    if not ind.novas:
        return len(ind.consultas)
    textos = list(ind.consultas)
    np.savez_compressed(ARQ_CONSULTAS, textos=np.array(textos),
                        vetores=np.stack([ind.consultas[t] for t in textos]))
    ind.novas = 0
    return len(textos)


def mostrar(resultados: list[dict], largura: int = 150) -> None:
    for pos, r in enumerate(resultados, start=1):
        texto = " ".join(r["trecho"].split())
        texto = texto[:largura] + ("…" if len(texto) > largura else "")
        print(f"{pos}. {r['chunk_id']} · {r['espaco']} · vigência {r['vigencia']}")
        print(f"   {texto}")
