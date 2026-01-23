import os
import json
from pathlib import Path


INDEX_PATH = Path(os.getenv("INDEX_PATH", "indexes"))


def _safe_file_id(file_id: str) -> str:
    file_id = os.path.basename(file_id)
    file_id = file_id.replace("/", "_").replace("\\", "_")
    return file_id or "doc"


def _index_dir(file_id: str) -> Path:
    return INDEX_PATH / _safe_file_id(file_id)


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def _embeddings():
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        base_url=_ollama_base_url(),
        sync_client_kwargs={"timeout": float(os.getenv("OLLAMA_TIMEOUT", "60"))},
        async_client_kwargs={"timeout": float(os.getenv("OLLAMA_TIMEOUT", "60"))},
    )


def _llm():
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b"),
        base_url=_ollama_base_url(),
        temperature=0,
        # Keep generations bounded so Swagger doesn't sit loading forever.
        num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "256")),
        num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "2048")),
        keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "5m"),
        sync_client_kwargs={"timeout": float(os.getenv("OLLAMA_TIMEOUT", "120"))},
        async_client_kwargs={"timeout": float(os.getenv("OLLAMA_TIMEOUT", "120"))},
    )


def create_and_save_index(local_pdf_path: str, file_id: str) -> bool:
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    loader = PyPDFLoader(local_pdf_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(documents)

    index_dir = _index_dir(file_id)
    index_dir.mkdir(parents=True, exist_ok=True)

    # Always persist chunks as plain text (fallback retrieval).
    chunks_path = index_dir / "chunks.json"
    chunks_payload = [
        {
            "page_content": d.page_content,
            "metadata": d.metadata or {},
        }
        for d in chunks
    ]
    chunks_path.write_text(json.dumps(chunks_payload, ensure_ascii=False), encoding="utf-8")

    # Best-effort semantic vector index (requires Ollama embedding model).
    try:
        from langchain_community.vectorstores import Chroma

        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=_embeddings(),
            persist_directory=str(index_dir),
            collection_name="docs",
        )
        # Chroma persists automatically when persist_directory is set.
    except Exception:
        # If embeddings aren't available, TF-IDF fallback will be used at query time.
        pass
    return True


def load_index_and_ask(file_id: str, query: str) -> str:
    index_dir = _index_dir(file_id)
    if not index_dir.exists():
        raise FileNotFoundError("Índice não encontrado.")

    # Try semantic retrieval first.
    context = ""
    try:
        from langchain_community.vectorstores import Chroma

        vectorstore = Chroma(
            persist_directory=str(index_dir),
            embedding_function=_embeddings(),
            collection_name="docs",
        )
        docs = vectorstore.similarity_search(query, k=4)
        context = "\n\n---\n\n".join(d.page_content for d in docs)
    except Exception:
        # Fallback: TF-IDF over persisted chunks (no embeddings needed).
        chunks_path = index_dir / "chunks.json"
        if not chunks_path.exists():
            raise FileNotFoundError("Índice não encontrado.")

        payload = json.loads(chunks_path.read_text(encoding="utf-8"))
        texts = [item.get("page_content", "") for item in payload]

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(stop_words=None)
        tfidf = vectorizer.fit_transform(texts + [query])
        sims = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()
        top_idx = sims.argsort()[-4:][::-1]
        context = "\n\n---\n\n".join(texts[i] for i in top_idx if texts[i])

    prompt = (
        "Você é um assistente que responde perguntas usando APENAS o contexto fornecido. "
        "Se o contexto não for suficiente, diga que não encontrou a informação no documento.\n\n"
        f"Pergunta: {query}\n\n"
        f"Contexto:\n{context}"
    )

    response = _llm().invoke(prompt)
    return getattr(response, "content", str(response))