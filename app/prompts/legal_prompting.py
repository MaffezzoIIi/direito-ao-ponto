# app/prompts/legal_prompting.py
import re
import unicodedata

# ---------- PREPROCESSAMENTO ----------

def preprocess_question(text: str) -> str:
    """
    Limpa e melhora a pergunta do usuário antes de buscar.
    """
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"[!?]+$", "", text)
    text = unicodedata.normalize("NFKC", text)

    # padroniza algumas expressões jurídicas
    replacements = {
        "falência": "processo de falência",
        "recuperação judicial": "plano de recuperação judicial",
        "recuperação extrajudicial": "processo de recuperação extrajudicial",
        "cobrança": "ação de cobrança",
        "contrato": "contrato civil",
    }
    for k, v in replacements.items():
        if k.lower() in text.lower():
            text = re.sub(k, v, text, flags=re.IGNORECASE)

    # se a pergunta for muito curta, dá contexto
    if len(text.split()) <= 3:
        text = f"explicação sobre {text}"

    return text


# ---------- PROMPT JURÍDICO ----------

SYSTEM_PROMPT = """
Você é um assistente jurídico especializado em Direito Brasileiro.
Seu papel é RESPONDER SOMENTE com base no CONTEXTO fornecido.
Se a informação não estiver no contexto, diga:
"Não encontrei informações suficientes na base indexada para responder com segurança."

Regras:
- Cite o número da lei e do artigo sempre que possível.
- Use linguagem formal, objetiva e respeitosa.
- Organize a resposta em tópicos quando for pertinente.
- Nunca invente dispositivos legais.
- Sempre finalize com uma observação: "Verifique a legislação atualizada."
"""

def build_prompt(context: str, question: str) -> str:
    """Monta o prompt completo para envio ao LLM."""
    return f"{SYSTEM_PROMPT}\n\nCONTEXTO:\n{context}\n\nPERGUNTA:\n{question}\n\nRESPOSTA:"
