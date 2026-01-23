import os
import tempfile

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .rag_engine import create_and_save_index, load_index_and_ask
from .s3_client import upload_file_to_s3

app = FastAPI(title="Smart Doc Assistant")

load_dotenv()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/documents")
async def list_documents():
    base = os.getenv("INDEX_PATH", "indexes")
    if not os.path.isdir(base):
        return {"documents": []}
    docs = [name for name in os.listdir(base) if os.path.isdir(os.path.join(base, name))]
    docs.sort()
    return {"documents": docs}

class QueryRequest(BaseModel):
    filename: str
    question: str

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Por enquanto só aceitamos PDF (.pdf)")

    tmp_path: str | None = None
    try:
        suffix = os.path.splitext(file.filename)[1] or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            tmp.write(await file.read())

        # Mantém uma cópia local (facilita debug e funciona sem S3)
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        local_copy_path = os.path.join(uploads_dir, os.path.basename(file.filename))
        with open(tmp_path, "rb") as src, open(local_copy_path, "wb") as dst:
            dst.write(src.read())

        s3_uploaded = False
        try:
            with open(tmp_path, "rb") as f:
                s3_uploaded = bool(upload_file_to_s3(f, file.filename))
        except Exception:
            # Não trava o app se AWS não estiver configurado/correto
            s3_uploaded = False

        # Indexing can take a while; run off the event loop.
        await run_in_threadpool(create_and_save_index, tmp_path, file.filename)
        return {
            "message": "Arquivo processado e indexado com sucesso",
            "id": file.filename,
            "s3_uploaded": s3_uploaded,
            "local_copy": local_copy_path,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar índice: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/ask")
async def ask_question(request: QueryRequest):
    try:
        # LLM + retrieval are blocking; don't freeze the whole server.
        answer = await run_in_threadpool(load_index_and_ask, request.filename, request.question)
        return {"answer": answer, "source": request.filename}
    except FileNotFoundError:
        base = os.getenv("INDEX_PATH", "indexes")
        docs = []
        if os.path.isdir(base):
            docs = [name for name in os.listdir(base) if os.path.isdir(os.path.join(base, name))]
            docs.sort()
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Documento não encontrado. Faça o upload novamente ou use um id existente.",
                "available": docs[:50],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
