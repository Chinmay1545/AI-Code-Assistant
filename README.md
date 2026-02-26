# AI Code Assistant

A simple AI powered code assistant that understands uploaded project files and provides explanations or code suggestions using semantic search.

Built using Python, FastAPI, LangChain, and the OpenAI API.

## Features

- Upload code files through a web interface
- Semantic search across uploaded files
- Context aware explanations
- Code improvement suggestions
- Patch generation

## Tech Stack

Python  
FastAPI  
LangChain  
OpenAI API  

## Setup

Clone the repository:

git clone https://github.com/Chinmay1545/AI-Code-Assistant.git

cd AI-Code-Assistant

Create a virtual environment:

python -m venv venv

Activate environment:

Mac/Linux:
source venv/bin/activate

Windows:
venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Create a .env file:

OPENAI_API_KEY=your_api_key_here

Run the server:

uvicorn main:app --reload

Open in browser:

http://localhost:8000

## Project Structure

main.py : FastAPI app

vector_store.py : semantic search logic

llm_client.py : OpenAI API calls

templates/ : frontend HTML

static/ : CSS and JavaScript
