# scripts/index_qdrant.py
#!/usr/bin/env python
"""
Lê um JSONL de chunks (texto legal) e indexa no Qdrant com embeddings OpenAI.
Uso:
  python -m scripts.index_qdrant --jsonl data/processed/lei_11101_2005.jsonl --collection leis
"""
from __future__ import annotations
import os, argparse, json, math, time
from typing import List, Dict

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from openai import OpenAI

EMBED_MODEL = "text-embedding-3-large"  # 3072 dims

def batched(iterable, n=64):
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION","leis"))
    ap.add_argument("--host", default=os.getenv("QDRANT_HOST","localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("QDRANT_PORT","6333")))
    ap.add_argument("--recreate", action="store_true", help="apaga e recria a collection")
    args = ap.parse_args()

    # Carregar registros
    records: List[Dict] = []
    with open(args.jsonl, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    # Clientes
    client = QdrantClient(host=args.host, port=args.port)
    oa = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Coleção
    if args.recreate:
        try:
            client.delete_collection(args.collection)
        except Exception:
            pass
    client.recreate_collection(
        collection_name=args.collection,
        vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
    )

    # Embeddings em batch
    point_id = 1
    total = len(records)
    for batch in batched(records, n=64):
        texts = [r["texto"] for r in batch]
        # chamada única para vários inputs
        emb = oa.embeddings.create(model=EMBED_MODEL, input=texts)
        vectors = [e.embedding for e in emb.data]

        points = []
        for rec, vec in zip(batch, vectors):
            points.append(PointStruct(
                id=point_id,
                vector=vec,
                payload=rec
            ))
            point_id += 1

        client.upsert(collection_name=args.collection, points=points, wait=True)
        print(f"Upsert: {point_id-1}/{total}")
        time.sleep(0.2)  # educativo: respeitar rate limit

    print(f"OK: {total} registros indexados na collection '{args.collection}'")

if __name__ == "__main__":
    main()
