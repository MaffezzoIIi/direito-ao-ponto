# scripts/search_qdrant_reranked_local.py
#!/usr/bin/env python
"""
Busca vetorial (embeddings locais) + RERANK local (cross-encoder).
Uso:
  python -m scripts.search_qdrant_reranked_local --query "plano de recuperação judicial" --k 12 --n 5
"""
import os, argparse
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from scripts.rerank_local import rerank

EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=12, help="quantidade inicial do Qdrant (recall)")
    ap.add_argument("--n", type=int, default=5, help="top-N após rerank (precisão)")
    ap.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION","leis"))
    ap.add_argument("--host", default=os.getenv("QDRANT_HOST","localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("QDRANT_PORT","6333")))
    args = ap.parse_args()

    model = SentenceTransformer(EMBED_MODEL)
    qvec = model.encode([args.query], normalize_embeddings=True)[0].tolist()

    client = QdrantClient(host=args.host, port=args.port)
    hits = client.search(collection_name=args.collection, query_vector=qvec, limit=args.k)

    # normaliza passagens para o rerank
    passages = []
    for h in hits:
        p = h.payload
        passages.append({
            "texto": p.get("texto",""),
            "lei": p.get("lei"),
            "artigo": p.get("artigo"),
            "score_vec": h.score,  # score do vetor (para debug)
            "url": p.get("url_oficial"),
            "chunk_seq": p.get("chunk_seq"),
        })

    ranked = rerank(args.query, passages, top_n=args.n)

    # printa resultado final
    for i, r in enumerate(ranked, start=1):
        prefix = f"{i:02d}. Lei {r['lei']} art. {r['artigo']}"
        print(f"{prefix}  vec={r['score_vec']:.4f}  rerank={r['rerank_score']:.4f}")
        txt = (r["texto"] or "").replace("\n", " ")
        print(f"    {txt[:220]}...\n")

if __name__ == "__main__":
    main()
