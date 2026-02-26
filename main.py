"""
FastAPI backend for the AI-powered code assistant.
Serves the UI, handles file uploads (temp store → index → delete), and runs LLM with semantic retrieval.
"""
import logging
import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import List

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vector_store import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
    build_vector_store_from_paths,
    retrieve_context,
)
from llm_client import run_llm

# --- Config (model is in llm_client.py) ---
INDEX_DIR = Path(__file__).resolve().parent / "data" / "faiss_index"
ALLOWED_EXTENSIONS_STR = ", ".join(sorted(ALLOWED_EXTENSIONS))

app = FastAPI(title="AI Code Assistant")

# In-memory vector store, file list, and contents for preview (replaced on each upload)
_current_vector_store = None
_current_file_names: List[str] = []
_current_file_contents: dict = {}


def _validate_file(name: str, size: int) -> None:
    if size > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File '{name}' exceeds 2 MB limit ({size} bytes).",
        )
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File '{name}' has disallowed extension. Allowed: {ALLOWED_EXTENSIONS_STR}",
        )


class RunRequest(BaseModel):
    instruction: str


class RunResponse(BaseModel):
    result_text: str
    is_diff: bool


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main interface."""
    path = Path(__file__).resolve().parent / "templates" / "index.html"
    if not path.exists():
        raise HTTPException(status_code=500, detail="templates/index.html not found")
    return path.read_text(encoding="utf-8")


@app.get("/preview")
async def preview(name: str = ""):
    """Return in-memory file content for preview. Query param ?name=<filename>."""
    try:
        from urllib.parse import unquote
        global _current_file_names, _current_file_contents
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Missing name parameter.")
        # Use only the basename to avoid path traversal
        raw = unquote(name.strip())
        filename = Path(raw).name
        if not filename or "/" in raw or "\\" in raw:
            raise HTTPException(status_code=404, detail="File not found.")
        if filename not in _current_file_names:
            raise HTTPException(status_code=404, detail="File not found.")
        content = _current_file_contents.get(filename)
        if content is None:
            raise HTTPException(status_code=404, detail="Preview not available.")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        # Ensure JSON-serializable (no lone surrogates)
        content_str = "".join(
            c if ord(c) < 0xD800 or 0xE000 <= ord(c) <= 0x10FFFF else "\ufffd"
            for c in content
        )
        return JSONResponse(content={"content": content_str})
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Preview failed")
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    """
    Accept multiple files, validate size and extension, write to temp dir,
    build FAISS index, then delete temp files. Return list of indexed filenames.
    """
    global _current_vector_store, _current_file_names, _current_file_contents

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    temp_dir = tempfile.mkdtemp(prefix="code_assistant_")
    temp_paths: List[str] = []
    try:
        for u in files:
            if not u.filename or u.filename.startswith("."):
                continue
            content = await u.read()
            _validate_file(u.filename, len(content))
            path = os.path.join(temp_dir, u.filename)
            Path(path).write_bytes(content)
            temp_paths.append(path)

        if not temp_paths:
            raise HTTPException(
                status_code=400,
                detail="No valid files to process. Allowed extensions: " + ALLOWED_EXTENSIONS_STR,
            )

        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _current_vector_store = build_vector_store_from_paths(
            temp_paths,
            persist_dir=str(INDEX_DIR),
        )
        _current_file_names = [Path(p).name for p in temp_paths]
        _current_file_contents = {}
        for p in temp_paths:
            name = Path(p).name
            try:
                _current_file_contents[name] = Path(p).read_text(encoding="utf-8", errors="replace")
            except Exception:
                _current_file_contents[name] = "(binary or unreadable)"

        return JSONResponse(
            status_code=200,
            content={
                "files": _current_file_names,
                "status": "indexed",
                "message": f"Indexed {len(_current_file_names)} file(s).",
            },
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Upload/indexing failed")
        detail = str(e)
        if "OPENAI_API_KEY" in detail or "api_key" in detail.lower() or "authentication" in detail.lower():
            detail = (
                "OpenAI API error. Check that OPENAI_API_KEY is set to a valid key (not the placeholder). "
                "Original: " + detail
            )
        raise HTTPException(status_code=500, detail=f"Indexing failed: {detail}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/run", response_model=RunResponse)
async def run(body: RunRequest):
    """
    Run the assistant: retrieve context from the vector store, call LLM, return result.
    """
    global _current_vector_store

    if not body.instruction.strip():
        raise HTTPException(status_code=400, detail="Instruction cannot be empty.")

    if _current_vector_store is None:
        raise HTTPException(
            status_code=400,
            detail="No project files indexed. Please upload files first.",
        )

    try:
        docs = retrieve_context(_current_vector_store, body.instruction, top_k=8)
        result_text = run_llm(body.instruction, docs)
        return RunResponse(result_text=result_text, is_diff=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant error: {str(e)}")


# Mount static files (CSS, JS)
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
