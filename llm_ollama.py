# app/llm_ollama.py
import os, requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SEC", "120"))

SYSTEM = (
    "Você é um assistente jurídico brasileiro. Responda APENAS com base no CONTEXTO fornecido. "
    "Se faltar base, diga que não encontrou. Sempre cite a lei e o artigo, quando possível."
)

def generate_with_ollama(context: str, question: str, max_tokens: int = 400) -> str:
    prompt = f"SISTEMA:\n{SYSTEM}\n\nCONTEXTO:\n{context}\n\nPERGUNTA:\n{question}\n\nRESPOSTA:"
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"num_predict": max_tokens}},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("response") or "").strip()
