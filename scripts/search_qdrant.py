# scripts/search_qdrant.py
#!/usr/bin/env python
"""
Faz uma busca vetorial simples no Qdrant e imprime as top passagens.
Uso:
  python -m scripts.search_qdrant --query "plano de recuperação judicial" --k 5
"""
import os, argparse
from typing import List
from qdrant_client import QdrantClient
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-large"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION","leis"))
    ap.add_argument("--host", default=os.getenv("QDRANT_HOST","localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("QDRANT_PORT","6333")))
    args = ap.parse_args()

    oa = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    emb = oa.embeddings.create(model=EMBED_MODEL, input=[args.query]).data[0].embedding

    client = QdrantClient(host=args.host, port=args.port)
    hits = client.search(collection_name=args.collection, query_vector=emb, limit=args.k)

    for i, h in enumerate(hits, start=1):
        payload = h.payload
        lei = payload.get("lei"); art = payload.get("artigo")
        score = h.score
        texto = payload.get("texto","").strip().replace("\n"," ")[:220]
        print(f"{i:02d}. {lei} art. {art}  score={score:.4f}")
        print(f"    {texto} ...\n")

if __name__ == "__main__":
    main()
