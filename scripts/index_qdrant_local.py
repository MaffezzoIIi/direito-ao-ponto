#!/usr/bin/env python
"""
Indexa JSONL no Qdrant usando embeddings locais (gratuito).
Uso:
  python -m scripts.index_qdrant_local --jsonl data/processed/lei_11101_2005.jsonl --collection leis --recreate
"""
from __future__ import annotations
import os, argparse, json, time
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# Escolha UM modelo:
# - "intfloat/multilingual-e5-base" (768 dims, muito bom em PT-BR)
# - "paraphrase-multilingual-MiniLM-L12-v2" (384 dims, leve)
MODEL_NAME = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")

def batched(it, n=64):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION","leis"))
    ap.add_argument("--host", default=os.getenv("QDRANT_HOST","localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("QDRANT_PORT","6333")))
    ap.add_argument("--recreate", action="store_true")
    args = ap.parse_args()

    # Carrega registros
    recs: List[Dict] = []
    with open(args.jsonl, "r", encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))

    # Embeddings locais
    model = SentenceTransformer(MODEL_NAME)  # CPU ok
    dim = model.get_sentence_embedding_dimension()

    # Qdrant
    client = QdrantClient(host=args.host, port=args.port)
    if args.recreate:
        try: client.delete_collection(args.collection)
        except Exception: pass
    client.recreate_collection(
        collection_name=args.collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )

    pid = 1
    for batch in batched(recs, n=64):
        texts = [r["texto"] for r in batch]
        vecs = model.encode(texts, normalize_embeddings=True).tolist()
        points = [
            PointStruct(id=pid+i, vector=v, payload=batch[i])  # payload = seu JSON
            for i, v in enumerate(vecs)
        ]
        client.upsert(collection_name=args.collection, points=points, wait=True)
        pid += len(batch)
        print(f"Upsert: {pid-1}/{len(recs)}"); time.sleep(0.1)
    print(f"OK: {len(recs)} pontos na collection '{args.collection}' (modelo={MODEL_NAME}, dim={dim})")

if __name__ == "__main__":
    main()
