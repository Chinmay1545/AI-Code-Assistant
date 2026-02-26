"""
OpenAI LLM client for code assistant. Model is configurable at the top of the file.
"""
import os
from openai import OpenAI

# Configurable model (used for chat/completion)
OPENAI_CHAT_MODEL = "gpt-5.2-2025-12-11"


def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please set it to your OpenAI API key."
        )
    return OpenAI(api_key=api_key)


SYSTEM_PROMPT = (
    "You are a senior software engineer providing concise, actionable recommendations. "
    "Answer the user's question or follow their instruction using the provided code context. "
    "Respond in whatever format best fits the request (explanation, code snippets, unified diff, etc.)."
)


def _format_context(docs: list) -> str:
    """Format retrieved chunks and file names for the user message."""
    parts = []
    seen_files = set()
    for d in docs:
        name = d.metadata.get("source_file", "unknown")
        if name not in seen_files:
            seen_files.add(name)
        parts.append(f"--- {name} ---\n{d.page_content}")
    return "\n\n".join(parts)


def run_llm(instruction: str, context_docs: list) -> str:
    """Run the LLM with user instruction and retrieved context. Prompt alone drives the response."""
    client = _get_client()
    context_block = _format_context(context_docs)
    file_names = sorted({d.metadata.get("source_file", "unknown") for d in context_docs})

    user_content = f"""User instruction: {instruction}

Relevant code context (file names: {', '.join(file_names)}):

{context_block}"""

    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
