import requests
from typing import List, Optional
from pydantic import BaseModel
from uuid import uuid4
import logging

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

class Conversation(BaseModel):
    id: int
    user_id: int
    cid: str
    messages: Optional[List[ChatMessage]] = []
    created_at: str
    updated_at: str


API_URL = "http://localhost:8080/api"

class ConversationManagerAPI:
    """Gerencia histórico de conversas via API Go/Postgres."""
    def __init__(self):
        pass
    
    def get_all_conversations(self) -> List[Conversation]:
        resp = requests.get(f"{API_URL}/conversations")
        resp.raise_for_status()
        data = resp.json()
        return [Conversation(**conv) for conv in data]

    def get(self, cid: str) -> List[ChatMessage]:
        resp = requests.get(f"{API_URL}/conversations/{cid}")
        resp.raise_for_status()
        data = resp.json()
        return [ChatMessage(**msg) for msg in data]
    
    def get_messages(self, cid: str) -> List[ChatMessage]:
        resp = requests.get(f"{API_URL}/conversations/{cid}/messages")
        resp.raise_for_status()
        data = resp.json()
        return [ChatMessage(**msg) for msg in data]

    def append(self, cid: str, msg: ChatMessage):
        payload = {"cid": cid, "content": msg.content, "user_id": 1}
        resp = requests.post(f"{API_URL}/conversations/{cid}/messages", json=payload)
        resp.raise_for_status()

    def create(self) -> str:
        cid = uuid4().hex
        print(f"[INFO] Creating conversation ...")
        payload = {"cid": cid, "user_id": 1}
        
        try:
            headers = {"Content-Type": "application/json"}
            resp = requests.post(
                "http://localhost:8080/api/conversations/create",
                json=payload,
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

            logging.info(f"[INFO] Conversation created successfully")
            return data.get("cid", cid)
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao criar conversa: {e} | Response: {getattr(e.response, 'text', None)}")
            return ""

    def truncate(self, cid: str, max_msgs: int):
        # Implementação depende da API Go
        pass

    def reset(self, cid: str):
        resp = requests.post(f"{API_URL}/{cid}/reset")
        resp.raise_for_status()
