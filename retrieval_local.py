# app/retrieval_local.py
from __future__ import annotations
import os
import unicodedata
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")  # 768 dims
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "leis")
DEFAULT_HOST = os.getenv("QDRANT_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Carregamento lazy (evita custar no import)
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(DEFAULT_MODEL)  # CPU ok
    return _model


def _normalize(text: str) -> str:
    """
    Normaliza minimamente a consulta (opcional).
    Não removemos acentos nos documentos, só limpamos a query para maior robustez.
    """
    if not text:
        return text
    # NFKC + strip espaços extras
    t = unicodedata.normalize("NFKC", text).strip()
    # colapse espaços
    while "  " in t:
        t = t.replace("  ", " ")
    return t


class RetrieverLocal:
    """
    Busca vetorial com embeddings locais (SentenceTransformers) + Qdrant.
    Retorna passagens em um formato pronto para o rerank e para o /chat.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        collection: str = DEFAULT_COLLECTION,
        model_name: str = DEFAULT_MODEL,
        include_scores: bool = True,
    ) -> None:
        self.client = QdrantClient(host=host, port=port)
        self.collection = collection
        self.model_name = model_name
        self.include_scores = include_scores

    def embed(self, text: str) -> List[float]:
        model = _get_model()
        vec = model.encode([_normalize(text)], normalize_embeddings=True)[0]
        return vec.tolist()

    def search(self, query: str, k: int = 12) -> List[Dict[str, Any]]:
        """
        Executa busca vetorial simples no Qdrant.
        Saída: lista de dicts no padrão que os próximos passos esperam:
        {
          "texto": "...",
          "lei": "11.101/2005",
          "artigo": "53",
          "score_vec": 0.83,
          "url": "https://...",
          "chunk_seq": 1
        }
        """
        if not query or not query.strip():
            return []

        qvec = self.embed(query)
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=qvec,
            limit=int(k),
        )

        results: List[Dict[str, Any]] = []
        for h in hits:
            p = h.payload or {}
            item = {
                "texto": p.get("texto", ""),
                "lei": p.get("lei"),
                "artigo": p.get("artigo"),
                "url": p.get("url_oficial"),
                "chunk_seq": p.get("chunk_seq"),
            }
            if self.include_scores:
                item["score_vec"] = float(h.score)
            results.append(item)
        return results

    def search_with_filter(
        self,
        query: str,
        k: int = 12,
        lei: Optional[str] = None,
        artigo: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Versão com filtros simples (por metadados). Útil quando você já sabe a lei/alvo.
        """
        if not query or not query.strip():
            return []

        qvec = self.embed(query)

        # Monta filtro simples por payload (Qdrant filter)
        from qdrant_client.http import models as qm
        must: List[Any] = []
        if lei:
            must.append(qm.FieldCondition(key="lei", match=qm.MatchValue(value=lei)))
        if artigo:
            must.append(qm.FieldCondition(key="artigo", match=qm.MatchValue(value=artigo)))

        flt = qm.Filter(must=must) if must else None

        hits = self.client.search(
            collection_name=self.collection,
            query_vector=qvec,
            query_filter=flt,
            limit=int(k),
        )

        results: List[Dict[str, Any]] = []
        for h in hits:
            p = h.payload or {}
            item = {
                "texto": p.get("texto", ""),
                "lei": p.get("lei"),
                "artigo": p.get("artigo"),
                "url": p.get("url_oficial"),
                "chunk_seq": p.get("chunk_seq"),
            }
            if self.include_scores:
                item["score_vec"] = float(h.score)
            results.append(item)
        return results
