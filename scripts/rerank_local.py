# scripts/rerank_local.py
#!/usr/bin/env python
"""
Rerank local (cross-encoder) usando BAAI/bge-reranker-v2-m3 (grátis, CPU).
Entrada: query (str) + passagens (list[dict] com chave 'texto')
Saída: mesmas passagens, ordenadas por 'rerank_score' desc.
"""
from __future__ import annotations
from typing import List, Dict
from sentence_transformers import CrossEncoder

# modelo recomendado (bom em PT-BR, rápido em CPU)
MODEL_RERANK = "BAAI/bge-reranker-v2-m3"

# carregamento lazy (evita custo se não for usar em todos os requests)
_ce_model: CrossEncoder | None = None

def _get_model() -> CrossEncoder:
    global _ce_model
    if _ce_model is None:
        _ce_model = CrossEncoder(MODEL_RERANK)
    return _ce_model

def rerank(query: str, passages: List[Dict], top_n: int | None = None) -> List[Dict]:
    """
    passages: [{"texto": "...", ...}, ...]
    retorna: lista ordenada desc por 'rerank_score' e (opcionalmente) truncada para top_n
    """
    if not passages:
        return []
    model = _get_model()
    pairs = [(query, p.get("texto", "") or p.get("text", "")) for p in passages]
    scores = model.predict(pairs).tolist()
    ranked = sorted(
        (dict(p, rerank_score=float(s)) for p, s in zip(passages, scores)),
        key=lambda d: d["rerank_score"],
        reverse=True
    )
    return ranked[:top_n] if top_n else ranked
