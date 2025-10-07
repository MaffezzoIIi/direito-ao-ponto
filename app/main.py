from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.rag import RAGEngine
from app.generators.doc_gen import generate_peticao_inicial_cobranca
import os
from retrieval_local import RetrieverLocal
from scripts.rerank_local import rerank
from pydantic import BaseModel
from typing import List

# (opcional) só se for usar LLM local:
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() in ("1","true","yes")
if USE_OLLAMA:
    from llm_ollama import generate_with_ollama
    
retriever = RetrieverLocal()

app = FastAPI(title="Legal Assistant MVP")

rag = RAGEngine()

class ChatRequest(BaseModel):
    question: str
    k: int = 12              # recall maior antes do rerank
    use_llm: bool = False   # permite ligar LLM por request (além do USE_OLLAMA global)

class ChatResponse(BaseModel):
    answer: str
    citations: List[str]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 1) Recupera passagens (embeddings locais + Qdrant)
    raw = retriever.search(req.question, k=max(8, req.k))

    # 2) Rerank local (cross-encoder) para precisão
    ranked = rerank(req.question, raw, top_n=5)

    if not ranked:
        return ChatResponse(
            answer="Não encontrei base suficiente nos materiais indexados para responder com segurança.",
            citations=[]
        )

    # 3) Monta contexto e citações
    def fmt_source(p): return f"Lei {p.get('lei')} art. {p.get('artigo')}"
    citations = [fmt_source(p) for p in ranked]

    contexto = "\n\n".join(
        f"[{i+1}] {fmt_source(p)}\n{(p.get('texto') or '').strip()}"
        for i, p in enumerate(ranked)
    )

    # 4) Resposta
    answer: str
    use_llm_effective = USE_OLLAMA or req.use_llm
    if use_llm_effective:
        try:
            answer = generate_with_ollama(contexto, req.question, max_tokens=400)
            if not answer.strip():
                # Fallback extrativo
                raise RuntimeError("Resposta vazia do LLM")
        except Exception:
            answer = (
                "Com base nas fontes recuperadas (após rerank):\n\n"
                f"{contexto}\n\n"
                "Observação: informação educacional; verifique atualizações legais."
            )
    else:
        # Modo extrativo (sem LLM) — ótimo para TCC e para máquinas fracas
        answer = (
            "Com base nas fontes recuperadas (após rerank):\n\n"
            f"{contexto}\n\n"
            "Observação: informação educacional; verifique atualizações legais."
        )

    return ChatResponse(answer=answer, citations=citations)

# ===== Documentos =====

class Parte(BaseModel):
    nome: str
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    estado_civil: Optional[str] = None

class PeticaoInicialCobranca(BaseModel):
    autor: Parte
    reu: Parte
    foro: str
    fatos: str
    pedidos: List[str]
    valor_causa: float
    provas: Optional[List[str]] = Field(default_factory=list)

@app.post("/documents/peticao-inicial-cobranca")
def gerar_peticao_inicial_cobranca(payload: PeticaoInicialCobranca):
    try:
        path = generate_peticao_inicial_cobranca(payload.model_dump())
        return {"ok": True, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
