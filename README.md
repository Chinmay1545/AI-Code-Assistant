# AI Code Assistant

A simple AI powered code assistant that understands uploaded project files and provides explanations or code suggestions using semantic search.

Built using Python, FastAPI, LangChain, and the OpenAI API.

---

## Features

- Upload code files through a web interface  
- Semantic search across uploaded files  
- Context aware explanations  
- Code improvement suggestions  
- Patch generation  

---

## Tech Stack

- Python  
- FastAPI  
- LangChain  
- OpenAI API  

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Chinmay1545/AI-Code-Assistant.git
cd AI-Code-Assistant
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the environment

Mac or Linux:

```bash
source venv/bin/activate
```

Windows:

```bash
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Create a .env file

Create a file named `.env` in the root directory and add:

```
OPENAI_API_KEY=your_api_key_here
```

### 6. Run the server

```bash
uvicorn main:app --reload
```

### 7. Open in browser

```
http://localhost:8000
```

---

## Project Structure

- `main.py` — FastAPI application  
- `vector_store.py` — Semantic search and indexing logic  
- `llm_client.py` — OpenAI API interaction  
- `templates/` — Frontend HTML  
- `static/` — CSS and JavaScript  
