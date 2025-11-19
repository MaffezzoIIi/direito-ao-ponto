"""Teste rápido (manual) do pipeline local: ingest -> index -> search.

Uso:
  python -m scripts.test_local_stack --lei "11.101/2005" \
      --input data/raw/lei_11101_2005.txt \
      --collection leis_test --query "recuperação judicial" \
      --workdir .tmp_test_local

Este script NÃO substitui testes automatizados formais; serve como checagem
rápida de que as etapas principais estão funcionando no ambiente local.
"""
from __future__ import annotations
import argparse, os, shutil, subprocess, sys, pathlib
import json

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(f"Falha: {' '.join(cmd)}")
    return proc.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lei", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--collection", default="leis_test")
    ap.add_argument("--query", default="recuperação judicial")
    ap.add_argument("--workdir", default=".tmp_test_local")
    ap.add_argument("--max-chars", type=int, default=2000)
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--rerank", action="store_true")
    args = ap.parse_args()

    work = ROOT / args.workdir
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    jsonl = work / "ingest.jsonl"

    # 1. Ingest
    out_ingest = run([
        sys.executable, "-m", "scripts.ingest",
        "--lei", args.lei,
        "--input", args.input,
        "--output", str(jsonl),
        "--max-chars", str(args.max_chars),
    ])
    print(out_ingest)

    # Verificar JSONL básico
    with open(jsonl, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    try:
        sample = json.loads(first_line)
    except json.JSONDecodeError:
        raise SystemExit("JSONL inválido na primeira linha")
    assert "texto" in sample and "artigo" in sample, "Campos essenciais ausentes"
    print("Ingestão OK; primeiro registro:", sample["id"])

    # 2. Index
    out_index = run([
        sys.executable, "-m", "scripts.index_qdrant_local",
        "--jsonl", str(jsonl),
        "--collection", args.collection,
        "--recreate",
    ])
    print(out_index)

    # 3. Search
    search_cmd = [
        sys.executable, "-m", "scripts.search_qdrant_local",
        "--query", args.query,
        "--k", str(args.k),
        "--collection", args.collection,
    ]
    if args.rerank:
        search_cmd += ["--rerank", "--n", str(args.n)]
    out_search = run(search_cmd)
    print(out_search)
    print("Pipeline concluído.")


if __name__ == "__main__":
    main()