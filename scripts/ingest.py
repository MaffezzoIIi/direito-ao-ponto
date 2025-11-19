"""Ingestão genérica de textos legais.

Permite baixar (URL) ou ler arquivo local (.html/.txt), normalizar, separar em artigos e
chunkear, produzindo um JSONL pronto para indexação em Qdrant.

Exemplos:
  python -m scripts.ingest --lei "11.101/2005" --input data/raw/lei_11101_2005.txt
  python -m scripts.ingest --lei "11.101/2005" --url "https://www.planalto.gov.br/..." --output data/processed/lei_11101_2005.jsonl

Opções:
  --lei            Código/identificador da lei (ex.: 11.101/2005)
  --lei-nome       Nome descritivo (ex.: "Lei de Recuperação Judicial e Falências")
  --url / --input  Fonte dos dados (um deles obrigatório)
  --output         Caminho de saída .jsonl (default baseado em lei)
  --max-chars      Tamanho máximo aproximado de cada chunk

Formato JSONL gerado por linha:
  {
    "id": "lei-11101-2005-art-47-ch-1",
    "lei": "11.101/2005",
    "lei_nome": "Lei de Recuperação Judicial e Falências",  # opcional se fornecido
    "artigo": "47",
    "texto": "...",
    "url_oficial": "...",
    "data_extracao": "YYYY-MM-DD",
    "chunk_seq": 1,
    "subsections": {"paragrafos": [...], "incisos": [...]}  # conforme detectado
  }
"""
from __future__ import annotations
import argparse, json, os, datetime, pathlib, sys
from typing import Dict, Any
import requests

# Garantir import relativo para executar via "python -m scripts.ingest"
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.ingest_common import html_to_text, normalize_text, split_by_artigos, chunk_text


def fetch_url(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (ingest-legal-assistant)"})
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def read_input(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if path.lower().endswith(".html") or "<html" in raw.lower():
        return html_to_text(raw)
    return normalize_text(raw)


def slugify(text: str) -> str:
    # Converte "11.101/2005" -> "lei_11101_2005"
    only = "".join(ch if ch.isalnum() else "_" for ch in text)
    only = only.strip("_")
    # Normaliza múltiplos underscores
    while "__" in only:
        only = only.replace("__", "_")
    return f"lei_{only.lower()}"


def build_id(lei_slug: str, artigo: str, seq: int) -> str:
    return f"{lei_slug}-art-{artigo}-ch-{seq}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lei", required=True, help="Identificador da lei (ex.: 11.101/2005)")
    ap.add_argument("--lei-nome", default="", help="Nome descritivo da lei")
    ap.add_argument("--url", help="URL oficial para baixar HTML")
    ap.add_argument("--input", help="Arquivo .html ou .txt local")
    ap.add_argument("--output", help="Arquivo .jsonl de saída")
    ap.add_argument("--max-chars", type=int, default=5000, help="Tamanho máximo aproximado por chunk")
    ap.add_argument("--raw-html-out", default="", help="Se usar --url, onde salvar o HTML cru (opcional)")
    ap.add_argument("--source-url", default="", help="URL oficial (override se quiser diferente do --url)")
    args = ap.parse_args()

    if not args.url and not args.input:
        raise SystemExit("Forneça --url ou --input")

    lei_slug = slugify(args.lei)
    output = args.output or f"data/processed/{lei_slug}.jsonl"
    os.makedirs(os.path.dirname(output), exist_ok=True)

    if args.url:
        html = fetch_url(args.url)
        if args.raw_html_out:
            os.makedirs(os.path.dirname(args.raw_html_out), exist_ok=True)
            with open(args.raw_html_out, "w", encoding="utf-8") as fhtml:
                fhtml.write(html)
        text = html_to_text(html)
        source_url = args.source_url or args.url
    else:
        text = read_input(args.input)
        source_url = args.source_url

    artigos = split_by_artigos(text)
    data_extracao = datetime.date.today().isoformat()
    count = 0

    with open(output, "w", encoding="utf-8") as out:
        for art in artigos:
            artigo = art["artigo"].strip()
            bloco = art["texto"].strip()
            if not bloco:
                continue
            chunks = chunk_text(bloco, max_chars=args.max_chars)
            for seq, ch in enumerate(chunks, start=1):
                rec: Dict[str, Any] = {
                    "id": build_id(lei_slug, artigo, seq),
                    "lei": args.lei,
                    "lei_nome": args.lei_nome or None,
                    "artigo": artigo,
                    "texto": ch,
                    "url_oficial": source_url,
                    "data_extracao": data_extracao,
                    "chunk_seq": seq,
                    "subsections": art.get("subsections", {}),
                }
                # remove chave lei_nome se vazio
                if not rec["lei_nome"]:
                    del rec["lei_nome"]
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1

    print(f"OK: {count} chunks escritos em {output}")


if __name__ == "__main__":
    main()