"""
LangChain-based document loading, chunking, embeddings, and FAISS vector store.
Files are loaded from temp paths, indexed, then temp files are not retained (caller deletes).
"""
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Configurable at module level
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".md", ".txt"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB


def _get_embeddings() -> OpenAIEmbeddings:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please set it to your OpenAI API key."
        )
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=api_key)


def load_documents_from_paths(file_paths: List[str]) -> List[Document]:
    """Load text documents from file paths using LangChain TextLoader."""
    documents: List[Document] = []
    for path in file_paths:
        p = Path(path)
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        try:
            loader = TextLoader(path, encoding="utf-8", autodetect_encoding=True)
            docs = loader.load()
            for d in docs:
                d.metadata["source_file"] = p.name
                d.metadata["file_path"] = path
            documents.extend(docs)
        except Exception as e:
            raise RuntimeError(f"Failed to load file {path}: {e}") from e
    return documents


def build_vector_store_from_paths(
    file_paths: List[str],
    persist_dir: Optional[str] = None,
) -> FAISS:
    """
    Load documents from paths, split into chunks, embed with OpenAI, store in FAISS.
    If persist_dir is given, FAISS index is saved there for reuse.
    """
    if not file_paths:
        raise ValueError("No file paths provided")

    documents = load_documents_from_paths(file_paths)
    if not documents:
        raise ValueError("No documents could be loaded from the given paths")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    embeddings = _get_embeddings()
    vector_store = FAISS.from_documents(chunks, embeddings)

    if persist_dir:
        os.makedirs(persist_dir, exist_ok=True)
        vector_store.save_local(persist_dir)

    return vector_store


def load_vector_store_from_disk(persist_dir: str) -> FAISS:
    """Load an existing FAISS index from disk."""
    embeddings = _get_embeddings()
    return FAISS.load_local(
        persist_dir,
        embeddings,
        allow_dangerous_deserialization=True,
    )


def retrieve_context(
    vector_store: FAISS,
    query: str,
    top_k: int = 8,
) -> List[Document]:
    """Retrieve top_k most relevant chunks for the query."""
    return vector_store.similarity_search(query, k=top_k)
