"""
Utilitários para ingestão de textos legais a partir de HTML/TXT.
- limpeza de HTML do Planalto (e genérico)
- split por artigos (Art. N)
- chunking por tamanho aproximado
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# Art. N (captura número do artigo)
RE_ART = re.compile(r'(?:^|\n)\s*Art\.\s*(\d+[ºo]?)\s*[-–—:]?\s*', flags=re.IGNORECASE)
# § 1º, § 2º ...
RE_PAR = re.compile(r'(?:^|\n)\s*§+\s*(\d+º?)\s*[-–—:]?\s*')
# Incisos romanos (I, II, III...)
RE_INCISO = re.compile(r'(?:^|\n)\s*([IVXLCDM]+)\s*[-–—)]\s+', flags=re.IGNORECASE)

def _normalize_spaces(txt: str) -> str:
    txt = txt.replace('\xa0', ' ')
    txt = txt.replace('\r', '\n')
    txt = re.sub(r'[ \t]+', ' ', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def normalize_text(txt: str) -> str:
    return _normalize_spaces(txt)

def html_to_text(html: str) -> str:
    """
    Limpeza agressiva para páginas do Planalto (e genéricas):
    - remove cabeçalho/rodapé/menu
    - trata <br> e múltiplas quebras
    - remove blocos de 'Vigência', 'Conversão da MP', índice, etc. quando detectáveis
    """
    soup = BeautifulSoup(html, "lxml")

    # remove coisas comuns de navegação
    for tag in soup(["script", "style", "header", "footer", "nav", "iframe"]):
        tag.decompose()

    # heurísticas Planalto: ids/classes frequentes
    for sel in [
        "#barra-brasil", "#topo", "#menu", ".navbar", ".breadcrumb",
        "#rodape", ".rodape", ".footer", "#content-mobile",
        "div#content > p.banner", "div.banner", ".voltar", ".voltarTopo"
    ]:
        for el in soup.select(sel):
            el.decompose()

    # transformar <br> em quebras de linha
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # remover links de índice interno (sumário) se claramente um sumário
    for a in soup.find_all("a"):
        if a.get("href", "").startswith("#"):
            # Se for um índice no topo (heurística: muitos links âncora em sequência)
            pass  # normalmente não precisamos remover individualmente; o get_text já resolve

    text = soup.get_text("\n")
    text = _normalize_spaces(text)

    # Remover linhas claramente de “vigência”/“conversão”/“atualizações” comuns no topo/rodapé
    lines = [ln.strip() for ln in text.split("\n")]
    cleaned: List[str] = []
    for ln in lines:
        low = ln.lower()
        if any(x in low for x in [
            "presidência da república",
            "secretaria-geral",
            "atualizado em",
            "voltar ao topo",
            "sumário",
            "menu"
        ]):
            continue
        cleaned.append(ln)
    return _normalize_spaces("\n".join(cleaned))

def split_by_artigos(txt: str) -> List[Dict]:
    """
    Retorna: [{"artigo": "53", "texto": "...", "subsections": {"paragrafos":[...], "incisos":[...]}}]
    """
    parts: List[Dict] = []
    matches = list(RE_ART.finditer(txt))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i + 1 < len(matches) else len(txt)
        artigo_num = m.group(1).replace('º', '').replace('o', '')
        bloco = txt[start:end].strip()
        paragrafos = [p.group(1) for p in RE_PAR.finditer(bloco)]
        incisos = [i.group(1) for i in RE_INCISO.finditer(bloco)]
        parts.append({
            "artigo": artigo_num,
            "texto": bloco,
            "subsections": {"paragrafos": paragrafos, "incisos": incisos}
        })
    return parts

def chunk_text(text: str, max_chars: int = 5000) -> List[str]:
    """
    Corta preservando parágrafos; se precisar, cai para frases.
    """
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    paragraphs = text.split("\n\n")
    buf = ""
    for p in paragraphs:
        candidate = (buf + "\n\n" + p).strip() if buf else p.strip()
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                chunks.append(buf.strip())
            if len(p) > max_chars:
                sentences = re.split(r'(?<=[\.\!\?])\s+', p)
                sbuf = ""
                for s in sentences:
                    cand = (sbuf + " " + s).strip() if sbuf else s
                    if len(cand) <= max_chars:
                        sbuf = cand
                    else:
                        if sbuf:
                            chunks.append(sbuf.strip())
                        sbuf = s
                if sbuf:
                    chunks.append(sbuf.strip())
                buf = ""
            else:
                buf = p.strip()
    if buf:
        chunks.append(buf.strip())
    return chunks
