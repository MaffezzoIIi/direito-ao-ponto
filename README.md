# Legal Assistant MVP (Chat + Documentos)

MVP de um assistente jurídico brasileiro com dois modos:
1) **Consulta** (RAG + citações)
2) **Geração de Documentos** (form → template .docx)

## Como rodar (dev)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # preencha as variáveis
uvicorn app.main:app --reload
```

## Endpoints
- `POST /chat` → body: `{"question":"...", "k":8}`
- `POST /documents/peticao-inicial-cobranca` → body: JSON que atende ao schema em `app/schemas/peticao_inicial_cobranca.schema.json`
  - retorna um arquivo .docx gerado em `outputs/`

## Estrutura
```
app/
  main.py                # FastAPI + rotas
  rag.py                 # stub de RAG (plug de vetores, reranking)
  generators/doc_gen.py  # geração de .docx via docxtpl
  prompts/*.md           # prompts base
  schemas/*.json         # JSON Schemas dos documentos
  templates/*.docx       # templates
scripts/
  ingest_lei_11101_2005.py  # exemplo de ingestão (stub)
```

## Observações
- Este projeto é **esqueleto**: os métodos em `rag.py` estão com stubs para você ligar ao seu índice vetorial (Qdrant/pgvector/Pinecone).
- Para geração de .docx usamos `docxtpl`. Ajuste o template em `app/templates/peticao_inicial_cobranca.docx`.
- LGPD: avalie mascaramento e retenção de logs de acordo com sua política.
