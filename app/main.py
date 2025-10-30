from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.rag import RAGEngine
from app.documents.generator import generate_peticao_inicial_cobranca
import os
from retrieval_local import RetrieverLocal
from scripts.rerank_local import rerank
from pydantic import BaseModel
from typing import List
from app.prompts.legal_prompting import preprocess_question, build_prompt
from llm_ollama import generate_with_ollama

# (opcional) só se for usar LLM local:
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() in ("1","true","yes")
    
retriever = RetrieverLocal()

app = FastAPI(title="Legal Assistant MVP")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens, ajuste conforme necessário
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

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
    # 1️⃣ Preprocessar a pergunta
    question = preprocess_question(req.question)

    # 2️⃣ Recuperar passagens (embedding + Qdrant)
    raw = retriever.search(question, k=max(8, req.k))

    # 3️⃣ Rerank local (melhora precisão)
    ranked = rerank(question, raw, top_n=5)

    if not ranked:
        return ChatResponse(
            answer="Não encontrei base suficiente nos materiais indexados para responder com segurança.",
            citations=[]
        )

    # 4️⃣ Montar contexto formatado
    def fmt_source(p): return f"Lei {p.get('lei')} art. {p.get('artigo')}"
    citations = [fmt_source(p) for p in ranked]

    context = "\n\n".join(
        f"CONTEXTO [{i+1}]: {fmt_source(p)}\n\"{(p.get('texto') or '').strip()}\""
        for i, p in enumerate(ranked)
    )

    # 5️⃣ Resposta (extrativo ou LLM)
    use_llm_effective = USE_OLLAMA or req.use_llm
    if use_llm_effective:
        try:
            prompt = build_prompt(context, question)
            answer = generate_with_ollama(prompt, question, max_tokens=400)
        except Exception as e:
            print(f"[ERRO OLLAMA] {e}")
            answer = (
                "Com base nas fontes recuperadas (após rerank):\n\n"
                f"{context}\n\n"
                "Observação: informação educacional; verifique atualizações legais."
            )
    else:
        print("LLM desativado, retornando resposta extrativa.")
        # modo extrativo (sem LLM)
        answer = (
            "Com base nas fontes recuperadas (após rerank):\n\n"
            f"{context}\n\n"
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
