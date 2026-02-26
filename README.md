# AI-Powered Code Assistant

A local web application that performs **context-aware code recommendations** using semantic search and an OpenAI LLM. Upload multiple project files, then ask questions or request code improvements; the assistant uses retrieval over your codebase to give relevant answers.

## Features

- **Semantic search**: Files are chunked, embedded with OpenAI, and stored in a FAISS vector index. Queries retrieve the most relevant snippets.
- **Prompt-driven**: You talk to the agent via a single instruction field; the model follows your request (explain, improve, generate a patch, etc.).
- **Clean UI**: Drag-and-drop upload, two-panel layout (file list + preview on the left, assistant output on the right), loading states, and optional download of the response.

## Requirements

- **Python 3.11+**
- **OpenAI API key** (for embeddings and chat model)

## Before pushing to GitHub

- **Never commit `.env`** — it’s in `.gitignore`; keep your API key there and only use `.env.example` as a template.
- The repo is set up to ignore: `.env`, `venv/`, `data/`, `__pycache__/`, IDE/OS junk, and other generated files. See `.gitignore` for the full list.

## Setup

1. **Clone or download** this project and open a terminal in its root.

2. **Create a virtual environment** (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set your OpenAI API key** (the app loads it from a `.env` file):

   Copy the example env file and add your key:

   ```bash
   cp .env.example .env
   # Edit .env and set OPENAI_API_KEY=sk-your-actual-key
   ```

   You can also set it in the shell if you prefer:

   ```bash
   export OPENAI_API_KEY="sk-your-actual-key"
   ```

5. **Run the application**:

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

   Or:

   ```bash
   python main.py
   ```

6. Open **http://localhost:8000** in your browser.

## Usage

1. **Upload files**: Drag and drop or use the browse button. Allowed extensions: `py`, `js`, `ts`, `java`, `c`, `cpp`, `go`, `rs`, `md`, `txt`. Max **2 MB per file**. Files are indexed and then removed from disk (contents kept in memory for preview).
2. **Enter an instruction** (e.g. “Explain the main function”, “Suggest improvements”, or “Generate a unified diff for …”).
3. **Run**: The app retrieves relevant chunks, calls the LLM with that context, and shows the result. Use **Download Patch** to save the response as a file.

## Project structure

| Path | Description |
|------|-------------|
| `main.py` | FastAPI app: routes, upload, run, preview. |
| `vector_store.py` | LangChain document loading, chunking, OpenAI embeddings, FAISS index. |
| `llm_client.py` | OpenAI chat calls; model and behavior per mode. |
| `templates/index.html` | Single-page UI. |
| `static/style.css` | Styles. |
| `static/app.js` | Frontend logic (upload, run, preview, download patch). |
| `requirements.txt` | Python dependencies. |
| `data/faiss_index/` | Created at runtime; FAISS index persisted here. |

## Configuration

- **LLM model**: Edit `OPENAI_CHAT_MODEL` at the top of `llm_client.py` (default: `gpt-5.2-2025-12-11`).
- **Embeddings**: Edit `EMBEDDING_MODEL` in `vector_store.py` (e.g. `text-embedding-3-small`).
- **Chunking**: Adjust `CHUNK_SIZE` and `CHUNK_OVERLAP` in `vector_store.py` if needed.

## Error handling

- Missing `OPENAI_API_KEY`: The app will return a clear error when you upload or run.
- File too large or wrong extension: Upload endpoint returns 400 with a message.
- No files indexed: Running without uploading first returns a “Please upload files first” message.

## License

Use and modify as you like.
