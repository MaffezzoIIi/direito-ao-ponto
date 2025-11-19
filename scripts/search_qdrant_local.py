#!/usr/bin/env python
"""
Busca vetorial local (SentenceTransformer) com opção de RERANK via cross-encoder.
Uso básico (somente vetorial):
  python -m scripts.search_qdrant_local --query "plano de recuperação judicial" --k 5
Com rerank (recall inicial K=12 e top-N final=5):
  python -m scripts.search_qdrant_local --query "plano de recuperação judicial" --k 12 --n 5 --rerank
Escolher modelo de embeddings:
  EMBED_MODEL=intfloat/multilingual-e5-base python -m scripts.search_qdrant_local --query "..."
Escolher modelo de rerank:
  python -m scripts.search_qdrant_local --query "..." --rerank --rerank-model BAAI/bge-reranker-v2-m3
"""
from __future__ import annotations
import os, argparse
from typing import List, Dict
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from scripts.rerank_local import rerank as rerank_passages

EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")

def format_hit(idx: int, payload: Dict, score_vec: float, score_rerank: float | None = None) -> str:
  lei = payload.get("lei"); art = payload.get("artigo")
  texto = (payload.get("texto", "") or "").replace("\n", " ")[:220]
  parts = [f"{idx:02d}. {lei} art. {art}"]
  parts.append(f"vec={score_vec:.4f}")
  if score_rerank is not None:
    parts.append(f"rerank={score_rerank:.4f}")
  header = "  ".join(parts)
  return f"{header}\n    {texto}...\n"

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--query", required=True, help="Texto da consulta")
  ap.add_argument("--k", type=int, default=8, help="Quantidade inicial de vetores (recall)")
  ap.add_argument("--n", type=int, default=5, help="Top-N final (se usar --rerank)")
  ap.add_argument("--rerank", action="store_true", help="Ativa reranqueamento local (cross-encoder)")
  ap.add_argument("--rerank-model", default=os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"), help="Modelo cross-encoder para rerank")
  ap.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION","leis"))
  ap.add_argument("--host", default=os.getenv("QDRANT_HOST","localhost"))
  ap.add_argument("--port", type=int, default=int(os.getenv("QDRANT_PORT","6333")))
  ap.add_argument("--show-all", action="store_true", help="Mostra todos os K resultados mesmo com rerank")
  args = ap.parse_args()

  if args.n > args.k and args.rerank:
    raise SystemExit("--n não pode ser maior que --k (use K maior para recall)")

  model = SentenceTransformer(EMBED_MODEL)
  qvec = model.encode([args.query], normalize_embeddings=True)[0].tolist()

  client = QdrantClient(host=args.host, port=args.port)
  hits = client.search(collection_name=args.collection, query_vector=qvec, limit=args.k)

  if not hits:
    print("Nenhum resultado.")
    return

  if not args.rerank:
    for i, h in enumerate(hits, start=1):
      payload = h.payload or {}
      print(format_hit(i, payload, h.score))
    return

  # Preparar passagens para rerank
  passages = [
    {
      "texto": (h.payload or {}).get("texto", ""),
      "lei": (h.payload or {}).get("lei"),
      "artigo": (h.payload or {}).get("artigo"),
      "score_vec": h.score,
      "chunk_seq": (h.payload or {}).get("chunk_seq"),
    }
    for h in hits
  ]

  ranked = rerank_passages(args.query, passages, top_n=args.n)

  # Mapear para output formatado
  # Se --show-all, incluir os não selecionados pelo rerank ao final
  selected_ids = {id(p) for p in ranked}
  for i, r in enumerate(ranked, start=1):
    print(format_hit(i, {"lei": r.get("lei"), "artigo": r.get("artigo"), "texto": r.get("texto")}, r.get("score_vec", 0.0), r.get("rerank_score")))
  if args.show_all and len(ranked) < len(passages):
    print("-- Resto (não no top-N rerank) --")
    tail = [p for p in passages if id(p) not in selected_ids]
    for j, p in enumerate(tail, start=len(ranked)+1):
      print(format_hit(j, {"lei": p.get("lei"), "artigo": p.get("artigo"), "texto": p.get("texto")}, p.get("score_vec", 0.0)))

if __name__ == "__main__":
  main()
