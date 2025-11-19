from typing import Dict, List, Optional
from pathlib import Path
from docxtpl import DocxTemplate
import datetime
import os

# Dependências para geração assistida por IA (stack local)
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from llm_ollama import generate_with_ollama
from app.prompts.legal_prompting import preprocess_question, build_prompt

EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "leis")

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

def generate_peticao_inicial_cobranca(data: Dict) -> str:
    """
    Renderiza o template docx com os dados do JSON.
    Retorna o caminho do arquivo gerado.
    """
    tpl_path = TEMPLATES_DIR / "peticao_inicial_cobranca.docx"
    doc = DocxTemplate(str(tpl_path))

    # Contexto para o template (placeholders)
    ctx = {
        "foro": data.get("foro"),
        "autor_nome": data["autor"]["nome"],
        "autor_cpf": data["autor"].get("cpf", ""),
        "autor_endereco": data["autor"].get("endereco", ""),
        "reu_nome": data["reu"]["nome"],
        "reu_cnpj": data["reu"].get("cnpj", ""),
        "reu_endereco": data["reu"].get("endereco", ""),
        "fatos": data.get("fatos", ""),
        "valor_causa": f"R$ {data.get('valor_causa', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "pedidos": data.get("pedidos", []),
        "provas": data.get("provas", []),
        "hoje": datetime.date.today().strftime("%d/%m/%Y"),
    }

    doc.render(ctx)
    out_path = OUTPUTS_DIR / f"Peticao_Inicial_Cobranca_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(out_path))
    return str(out_path)


# ---------------- IA Assistida -----------------

def _format_currency_br(value: float | int) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_list_sections(raw: str) -> List[str]:
    """Transforma texto do LLM em lista de itens.
    Regras simples: cada linha iniciada por '-', '*', número ou '•' vira item.
    """
    items: List[str] = []
    for line in raw.splitlines():
        ln = line.strip()
        if not ln:
            continue
        if ln[0] in "-*•":
            ln = ln.lstrip("-*• ")
            items.append(ln)
        elif ln[:2].isdigit() or ln[:1].isdigit():  # 1. 2) etc.
            # remove prefix numérico simples
            ln = ln.split(" ", 1)[-1]
            items.append(ln)
    # fallback: se nada detectado e texto único curto -> um item
    if not items and raw.strip():
        items = [raw.strip()]
    return items


def _build_context_from_hits(hits: List) -> str:
    parts = []
    for h in hits:
        p = h.payload or {}
        lei = p.get("lei", "?")
        art = p.get("artigo", "?")
        texto = (p.get("texto", "") or "").strip()
        # Limita cada bloco para não explodir prompt
        if len(texto) > 900:
            texto = texto[:900] + "..."
        parts.append(f"Lei {lei} Art. {art}: {texto}")
    return "\n\n".join(parts)


def _retrieve_legal_context(query: str, k: int, collection: str) -> str:
    model = SentenceTransformer(EMBED_MODEL)
    qvec = model.encode([query], normalize_embeddings=True)[0].tolist()
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    hits = client.search(collection_name=collection, query_vector=qvec, limit=k)
    if not hits:
        return "(Nenhum artigo encontrado para a consulta)"
    return _build_context_from_hits(hits)


def _generate_section(context: str, instrucao: str, pergunta_usuario: str) -> str:
    """Gera uma seção textual usando Ollama com regras jurídicas do prompt."""
    question = (
        f"Elabore a seção: {instrucao}. Baseie-se estritamente no CONTEXTO. "
        f"Caso falte base, diga que não há fundamento suficiente. Pergunta do usuário/caso: {pergunta_usuario}"
    )
    prompt = build_prompt(context, question)
    return generate_with_ollama(context, question) if hasattr(generate_with_ollama, '__call__') else "(LLM não disponível)"


def generate_peticao_inicial_cobranca_ai(
    data: Dict,
    consulta_caso: str,
    k: int = 12,
    n_context: int = 6,
    collection: Optional[str] = None,
    force: bool = False,
) -> str:
    """Gera petição inicial com auxílio de IA.

    Preenche automaticamente campos opcionais (fatos, pedidos, provas) se estiverem
    vazios ou se `force=True`. Usa recuperação de artigos da lei (Qdrant + embeddings locais)
    e gera texto via modelo local (Ollama).

    Parâmetros:
      data: dict de entrada (mesma estrutura já usada).
      consulta_caso: descrição livre do caso fornecida pelo usuário.
      k: quantidade de documentos para recuperar.
      n_context: alias mantido (usado se quiser futura fusão com rerank; aqui não aplicamos).
      collection: nome da collection Qdrant (default ambiente).
      force: sobrescreve seções mesmo se já existir conteúdo.
    """
    collection = collection or QDRANT_COLLECTION

    # Sanitizar/perguntar
    consulta_norm = preprocess_question(consulta_caso)
    contexto = _retrieve_legal_context(consulta_norm, k=k, collection=collection)

    # Seções a gerar
    faltantes = []
    if force or not data.get("fatos"):
        faltantes.append("fatos")
    if force or not data.get("pedidos"):
        faltantes.append("pedidos")
    if force or not data.get("provas"):
        faltantes.append("provas")

    if not faltantes:
        # Nada a gerar; delega à função padrão
        return generate_peticao_inicial_cobranca(data)

    # Geração
    if "fatos" in faltantes:
        texto_fatos = _generate_section(contexto, "exposição clara e cronológica dos fatos relevantes", consulta_caso)
        data["fatos"] = texto_fatos.strip()
    if "pedidos" in faltantes:
        texto_pedidos = _generate_section(contexto, "lista dos pedidos principais (cada item separado)", consulta_caso)
        data["pedidos"] = _parse_list_sections(texto_pedidos)
    if "provas" in faltantes:
        texto_provas = _generate_section(contexto, "lista sucinta dos meios de prova pertinentes", consulta_caso)
        data["provas"] = _parse_list_sections(texto_provas)

    # Garantir formato de valor da causa se numérico
    if isinstance(data.get("valor_causa"), (int, float)):
        # será formatado na função principal
        pass

    return generate_peticao_inicial_cobranca(data)

