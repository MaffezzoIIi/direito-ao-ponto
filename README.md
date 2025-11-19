# Legal Assistant (Chat + Documentos)

MVP de um assistente jurídico brasileiro com dois modos:

1. **Consulta** (RAG + citações)
2. **Geração de Documentos** (form → template .docx)

## 🚀 Modo de Conversa Multi-turn

O endpoint `/chat` agora suporta conversas persistentes em memória. Cada requisição pode conter um `conversation_id` para continuar o histórico.

### Request

```bash
POST /chat
{
  "conversation_id": "<opcional>",
  "message": "Qual é o objetivo da recuperação judicial?",
  "use_llm": true,
  "k": 12,
  "max_history": 8
}
```

Se `conversation_id` não for enviado, o backend cria um novo e retorna no payload.

### Response

```json
{
  "answer": "...",
  "citations": ["Lei 11.101 art. 47", "Lei 11.101 art. 51"],
  "conversation_id": "b2f1e7c8d8e94b7a9d4c1e0d4c2f8a7b",
  "messages": [
    {"role": "user", "content": "Qual é o objetivo da recuperação judicial?"},
    {"role": "assistant", "content": "..."}
  ]
}
```

### Endpoints auxiliares

```bash
GET /conversation/{conversation_id}
POST /conversation/{conversation_id}/reset
```

### Estratégia de Histórico

O motor de busca considera as últimas `max_history` mensagens do usuário para criar uma consulta combinada. O histórico completo é mantido até 50 mensagens (limite configurado em memória).

Para produzir uma conversa de verdade no frontend, basta reutilizar o `conversation_id` retornado e exibir o array `messages` em formato de chat.

### Futuras Melhorias

- Persistência em Redis ou banco (atualmente somente memória local)
- Resumo automático (message windowing) para conversas longas
- Streaming de tokens via Server-Sent Events ou WebSocket
- Controles de custo/token

## Como rodar (dev)

```bash
python -m venv .venv
".venv\\Scripts\\activate"  # PowerShell Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints Principais

```text
POST /chat
POST /documents/peticao-inicial-cobranca
GET  /conversation/{conversation_id}
POST /conversation/{conversation_id}/reset
```

## Estrutura

```text
app/
  main.py                # FastAPI + rotas
  rag.py                 # stub de RAG
  prompts/               # prompts base e processamento
  documents/             # geração de documentos
scripts/                 # ingestão e indexação
data/                    # dados legais (raw/processed)
```

## Observações

- Este projeto é **esqueleto**: os métodos em `rag.py` estão com stubs para você ligar ao seu índice vetorial (Qdrant / pgvector / Pinecone). Agora o fluxo local usa SentenceTransformers + Qdrant.
- Para geração de documentos personalize templates em `app/documents/templates/`.
- Ajuste variáveis de ambiente (ex: `USE_OLLAMA=true`).
- Avalie requisitos de LGPD para armazenamento de histórico.

## 📦 Stack Local (Embeddings + Rerank)

Fluxo típico para adicionar uma nova lei usando somente recursos locais:

```bash
# 1. Ingestão (gera JSONL processado de artigos/chunks)
python -m scripts.ingest --lei "11.101/2005" --input data/raw/lei_11101_2005.txt

# (Opcional) baixar via URL oficial:
python -m scripts.ingest --lei "11.101/2005" --url "https://www.planalto.gov.br/..." --output data/processed/lei_11101_2005.jsonl --raw-html-out data/raw/lei_11101_2005.html

# 2. Indexação local (embeddings CPU)
python -m scripts.index_qdrant_local --jsonl data/processed/lei_11101_2005.jsonl --collection leis --recreate

# 3. Busca vetorial simples
python -m scripts.search_qdrant_local --query "plano de recuperação judicial" --k 8

# 4. Busca + rerank (melhor precisão)
python -m scripts.search_qdrant_local --query "plano de recuperação judicial" --k 12 --n 5 --rerank
```

Variáveis úteis:

```text
EMBED_MODEL=intfloat/multilingual-e5-base   # mudar modelo de embeddings
RERANK_MODEL=BAAI/bge-reranker-v2-m3        # mudar modelo cross-encoder
QDRANT_COLLECTION=leis                      # nome da collection
QDRANT_HOST=localhost QDRANT_PORT=6333      # endpoint Qdrant
```

Para ver todos os resultados antes do rerank final: `--show-all`.
