"""
LangChain-based document loading, chunking, embeddings, and FAISS vector store.
Files are loaded from temp paths, indexed, then temp files are not retained (caller deletes).
"""
import os
from pathlib import Path
from typing import List

from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Configurable at module level
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".md", ".txt"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB

# Language-aware splitters cut at class/function boundaries before falling back to blank lines.
# Extensions not listed here (.txt) use plain paragraph/line splitting.
LANGUAGE_BY_EXTENSION = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".java": Language.JAVA,
    ".c": Language.C,
    ".cpp": Language.CPP,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".md": Language.MARKDOWN,
}


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


def _get_splitter(extension: str) -> RecursiveCharacterTextSplitter:
    kwargs = dict(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, add_start_index=True)
    language = LANGUAGE_BY_EXTENSION.get(extension)
    if language:
        return RecursiveCharacterTextSplitter.from_language(language, **kwargs)
    return RecursiveCharacterTextSplitter(separators=["\n\n", "\n", " ", ""], **kwargs)


def split_documents(documents: List[Document]) -> List[Document]:
    """Split each file with a splitter for its language and record each chunk's line range."""
    chunks: List[Document] = []
    for doc in documents:
        text = doc.page_content
        splitter = _get_splitter(Path(doc.metadata["source_file"]).suffix.lower())
        for chunk in splitter.split_documents([doc]):
            start_line = text.count("\n", 0, chunk.metadata["start_index"]) + 1
            chunk.metadata["start_line"] = start_line
            chunk.metadata["end_line"] = start_line + chunk.page_content.count("\n")
            chunks.append(chunk)
    return chunks


def build_vector_store_from_paths(file_paths: List[str]) -> FAISS:
    """Load documents from paths, split into chunks, embed with OpenAI, store in an in-memory FAISS index."""
    if not file_paths:
        raise ValueError("No file paths provided")

    documents = load_documents_from_paths(file_paths)
    if not documents:
        raise ValueError("No documents could be loaded from the given paths")

    chunks = split_documents(documents)

    # Embed each chunk with its file name prepended so queries that mention a file find its chunks;
    # the stored text stays the raw code.
    embeddings = _get_embeddings()
    vectors = embeddings.embed_documents(
        [f"File: {c.metadata['source_file']}\n\n{c.page_content}" for c in chunks]
    )
    return FAISS.from_embeddings(
        text_embeddings=list(zip([c.page_content for c in chunks], vectors)),
        embedding=embeddings,
        metadatas=[c.metadata for c in chunks],
    )


def retrieve_context(
    vector_store: FAISS,
    query: str,
    top_k: int = 8,
) -> List[Document]:
    """Retrieve top_k most relevant chunks for the query."""
    return vector_store.similarity_search(query, k=top_k)
