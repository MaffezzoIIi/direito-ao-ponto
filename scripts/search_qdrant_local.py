#!/usr/bin/env python
"""
Busca vetorial grátis (CPU) usando embeddings locais.
Uso:
  python -m scripts.search_qdrant_local --query "plano de recuperação judicial" --k 5
"""
import os, argparse
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION","leis"))
    ap.add_argument("--host", default=os.getenv("QDRANT_HOST","localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("QDRANT_PORT","6333")))
    args = ap.parse_args()

    model = SentenceTransformer(MODEL_NAME)
    qvec = model.encode([args.query], normalize_embeddings=True)[0].tolist()

    client = QdrantClient(host=args.host, port=args.port)
    hits = client.search(collection_name=args.collection, query_vector=qvec, limit=args.k)

    for i, h in enumerate(hits, start=1):
        p = h.payload
        lei = p.get("lei"); art = p.get("artigo"); score = h.score
        texto = p.get("texto","").replace("\n"," ")[:220]
        print(f"{i:02d}. {lei} art. {art}  score={score:.4f}\n    {texto} ...\n")

if __name__ == "__main__":
    main()
