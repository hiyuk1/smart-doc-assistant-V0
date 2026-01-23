# Smart Doc Assistant

FastAPI API that ingests PDFs and answers questions using RAG (retrieval + LLM).

## Local run (Windows)

1) Create `.env` (optional): copy `.env.example` → `.env`.
2) Start Ollama and pull models:
   - `ollama pull llama3.2:1b`
   - `ollama pull nomic-embed-text`
3) Run the API:
   - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
4) Open:
   - `http://127.0.0.1:8000/docs`

## Docker

Build and run the API container:
- `docker build -t smart-doc-assistant .`
- `docker run --rm -p 8000:8000 --env-file .env smart-doc-assistant`

## Docker Compose (recommended)

This starts both services: the API + Ollama.

1) Create `.env`: copy `.env.example` → `.env`
2) Start everything:
   - `docker compose up -d --build`
3) Pull models inside the Ollama container (first time only):
   - `docker exec -it ollama ollama pull llama3.2:1b`
   - `docker exec -it ollama ollama pull nomic-embed-text`
4) Open:
   - `http://localhost:8000/docs`

Notes:
- `indexes/` and `uploads/` are mounted as volumes to persist data.
- Ollama models are stored in a Docker named volume (`ollama`).

## GitHub safety

- Never commit `.env` or SSH keys (`*.pem`).
- Local folders `indexes/` and `uploads/` are ignored by `.gitignore`.
