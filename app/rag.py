from typing import List, Dict

class RAGEngine:
    """
    Stub de um motor RAG.
    Troque por sua implementação com Qdrant/Pgvector/Pinecone + reranking.
    """
    def __init__(self) -> None:
        pass

    def retrieve(self, query: str, k: int = 8) -> List[Dict]:
        # Retorne lista de passagens: [{"text": "...", "source": "Lei 11.101/2005, art. X", "score": 0.78, "meta": {...}}, ...]
        # Aqui, devolvemos dummy para o MVP.
        return [
            {
                "text": "Lei 11.101/2005, art. 53: O plano de recuperação judicial deve conter a discriminação pormenorizada dos meios de recuperação a ser empregados...",
                "source": "Lei 11.101/2005, art. 53",
                "score": 0.85,
                "meta": {"lei": "11.101/2005", "artigo": "53"}
            }
        ]

    def format_citations(self, passages: List[Dict]) -> List[str]:
        # Converta passagens em citações legíveis
        cites = []
        for p in passages:
            cites.append(f"{p.get('source')}")
        return list(dict.fromkeys(cites))  # unique, preserving order
