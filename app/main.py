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
from uuid import uuid4
import threading
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

class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant' | 'system'
    content: str

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None  # se não enviado, cria novo
    message: str  # mensagem do usuário neste turno
    k: int = 12               # recall antes do rerank
    use_llm: bool = False     # liga LLM neste request (além do USE_OLLAMA global)
    history: Optional[List[ChatMessage]] = None  # modo stateless alternativo (frontend envia histórico)
    max_history: int = 8      # janela de mensagens a considerar no retrieval

class ChatResponse(BaseModel):
    answer: str
    citations: List[str]
    conversation_id: str
    messages: List[ChatMessage]

class ConversationManager:
    """Gerencia histórico de conversas em memória (pode ser trocado por Redis/DB)."""
    def __init__(self):
        self._store: Dict[str, List[ChatMessage]] = {}
        self._lock = threading.Lock()

    def get(self, cid: str) -> List[ChatMessage]:
        return self._store.get(cid, [])

    def append(self, cid: str, msg: ChatMessage):
        with self._lock:
            if cid not in self._store:
                self._store[cid] = []
            self._store[cid].append(msg)

    def create(self) -> str:
        cid = uuid4().hex
        with self._lock:
            self._store[cid] = []
        return cid

    def truncate(self, cid: str, max_msgs: int):
        with self._lock:
            if cid in self._store and len(self._store[cid]) > max_msgs:
                self._store[cid] = self._store[cid][-max_msgs:]

    def reset(self, cid: str):
        with self._lock:
            self._store[cid] = []

conversation_manager = ConversationManager()

# TODO Futuras melhorias de conversa:
# - Persistir histórico em Redis ou Postgres
# - Implementar janela deslizante com resumo (compression) para conversas longas
# - Suporte a streaming (SSE / WebSocket) para respostas token a token
# - Limite de tokens/contexto mais robusto com cálculo dinamico
# - Mensagens de sistema configuráveis por caso de uso (consulta, documento, etc.)
# - Controle de custo/chaves de API por usuário/autenticação


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Endpoint de conversa multi-turn.
    Estratégia: mantém histórico em memória e usa últimas mensagens do usuário para enriquecer a consulta.
    """
    # 0️⃣ Gerenciar conversation_id
    cid = req.conversation_id or conversation_manager.create()

    # Se veio histórico explicitamente (modo stateless), sobrescreve armazenamento atual
    if req.history is not None and req.conversation_id:
        # Normaliza: não repetimos assistant final (será recalculado)
        msgs = [m for m in req.history if m.role != 'assistant']
        for m in msgs:
            conversation_manager.append(cid, m)

    # Adiciona mensagem atual do usuário
    user_message = ChatMessage(role='user', content=req.message)
    conversation_manager.append(cid, user_message)
    conversation_manager.truncate(cid, max_msgs=50)  # limite duro (configurável)

    # 1️⃣ Construir contexto de histórico (janela)
    history = conversation_manager.get(cid)
    # Seleciona últimas mensagens do usuário para compor consulta
    user_history_texts = [m.content for m in history if m.role == 'user'][-req.max_history:]
    combined_query = " \n".join(user_history_texts)
    question = preprocess_question(combined_query)

    # 2️⃣ Recuperar passagens
    try:
        raw = retriever.search(question, k=max(8, req.k))
    except ConnectionError as ce:
        return ChatResponse(
            answer=f"Erro: Não foi possível acessar o Qdrant. {str(ce)}",
            citations=[],
            conversation_id=cid,
            messages=history + [ChatMessage(role='assistant', content='Falha de conexão com base de vetores.')]
        )

    # 3️⃣ Rerank local
    ranked = rerank(req.message, raw, top_n=5)  # usa mensagem atual para rerank

    if not ranked:
        assistant_answer = "Não encontrei base suficiente nos materiais indexados para responder com segurança."
        assistant_msg = ChatMessage(role='assistant', content=assistant_answer)
        conversation_manager.append(cid, assistant_msg)
        return ChatResponse(
            answer=assistant_answer,
            citations=[],
            conversation_id=cid,
            messages=conversation_manager.get(cid)
        )

    # 4️⃣ Montar contexto formatado
    def fmt_source(p): return f"Lei {p.get('lei')} art. {p.get('artigo')}"
    citations = [fmt_source(p) for p in ranked]

    context = "\n\n".join(
        f"CONTEXTO [{i+1}]: {fmt_source(p)}\n\"{(p.get('texto') or '')}\""
        for i, p in enumerate(ranked)
    )

    # 5️⃣ Resposta
    use_llm_effective = USE_OLLAMA or req.use_llm
    if use_llm_effective:
        try:
            prompt = build_prompt(context, req.message)
            answer = generate_with_ollama(prompt, req.message)
        except Exception as e:
            print(f"[ERRO OLLAMA] {e}")
            answer = (
                "Com base nas fontes recuperadas (após rerank):\n\n"
                f"{context}\n\n"
                "Observação: informação educacional; verifique atualizações legais."
            )
    else:
        answer = (
            "Com base nas fontes recuperadas (após rerank):\n\n"
            f"{context}\n\n"
            "Observação: informação educacional; verifique atualizações legais."
        )

    assistant_msg = ChatMessage(role='assistant', content=answer)
    conversation_manager.append(cid, assistant_msg)

    return ChatResponse(
        answer=answer,
        citations=citations,
        conversation_id=cid,
        messages=conversation_manager.get(cid)
    )

@app.get("/conversation/{cid}", response_model=List[ChatMessage])
def get_conversation(cid: str):
    return conversation_manager.get(cid)

@app.post("/conversation/{cid}/reset")
def reset_conversation(cid: str):
    conversation_manager.reset(cid)
    return {"ok": True, "conversation_id": cid, "messages": []}


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
