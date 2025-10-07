#!/usr/bin/env python
"""
Ingestão da Lei 11.101/2005 a partir de HTML (ou TXT).
- Se --url for passado, baixa o HTML e processa
- Caso contrário, lê de --input (.html ou .txt)
- Gera JSONL com metadados por artigo e chunk
"""
from __future__ import annotations
import argparse, json, os, datetime, sys, pathlib
from typing import Dict, Any
import requests

# garante que possamos importar scripts.ingest_common quando rodar "python scripts/..."
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.ingest_common import html_to_text, normalize_text, split_by_artigos, chunk_text

def fetch_url(url: str, timeout: int = 30) -> str:
    r = requests.get(url, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0 (ingest-legal-assistant)"
    })
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text

def read_input(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if path.lower().endswith(".html") or "<html" in raw.lower():
        return html_to_text(raw)
    return normalize_text(raw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="URL oficial do Planalto (ou outra) para baixar HTML")
    ap.add_argument("--input", help="Arquivo de entrada (.html ou .txt). Ignorado se --url for usado.")
    ap.add_argument("--output", required=True, help="Arquivo .jsonl de saída")
    ap.add_argument("--raw-html-out", default="data/raw/lei_11101_2005.html", help="Onde salvar o HTML cru quando usar --url")
    ap.add_argument("--source-url", default="", help="URL oficial a registrar nos metadados (se usar --url, será preenchido automaticamente)")
    ap.add_argument("--max-chars", type=int, default=5000, help="Tamanho max por chunk (aprox.)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    if args.url:
        html = fetch_url(args.url)
        os.makedirs(os.path.dirname(args.raw_html_out), exist_ok=True)
        with open(args.raw_html_out, "w", encoding="utf-8") as f:
            f.write(html)
        text = html_to_text(html)
        source_url = args.url
    elif args.input:
        text = read_input(args.input)
        source_url = args.source_url
    else:
        raise SystemExit("Forneça --url OU --input")

    artigos = split_by_artigos(text)
    count = 0
    data_extracao = datetime.date.today().isoformat()

    with open(args.output, "w", encoding="utf-8") as out:
        for art in artigos:
            artigo = art["artigo"]
            texto = art["texto"].strip()
            if not texto:
                continue
            chunks = chunk_text(texto, max_chars=args.max_chars)
            for seq, ch in enumerate(chunks, start=1):
                rec: Dict[str, Any] = {
                    "id": f"lei-11101-2005-art-{artigo}-ch-{seq}",
                    "lei": "11.101/2005",
                    "artigo": artigo,
                    "texto": ch,
                    "url_oficial": source_url or args.source_url,
                    "data_extracao": data_extracao,
                    "chunk_seq": seq,
                    "subsections": art.get("subsections", {})
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1

    print(f"OK: {count} chunks escritos em {args.output}")

if __name__ == "__main__":
    main()
