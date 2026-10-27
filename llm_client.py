"""
OpenAI LLM client for code assistant. Model is configurable at the top of the file.
"""
import os
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

# Configurable model (used for chat/completion)
OPENAI_CHAT_MODEL = "gpt-5.2-2025-12-11"

# Projects whose files total at most this many characters are sent whole instead of as retrieved excerpts
MAX_FULL_CONTEXT_CHARS = 60_000

# Retrieved excerpts separated by at most this many lines are merged into one block
EXCERPT_MERGE_GAP = 3


def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please set it to your OpenAI API key."
        )
    return OpenAI(api_key=api_key)


SYSTEM_PROMPT = """You are a senior software engineer helping a developer understand and improve their code.

Each request contains the developer's instruction and code from their uploaded project. Every line of code is prefixed with its line number (e.g. "  12 | "); the numbers are for reference only and are not part of the source. The context says whether you are seeing complete files or only excerpts found by semantic search. With excerpts, the rest of the project exists but you cannot see it.

Rules:
- Base every claim on the code you were given. Never invent functions, files or behaviour. If the answer depends on code you cannot see, say what is missing instead of guessing.
- Refer to specific code as `file:line` or `file:start-end`.
- Fit the response to the request. Answer questions directly. For explanations, open with a one or two sentence summary, then add only as much detail as is useful.
- When asked to change code, give a unified diff in a ```diff block with `--- a/<file>` / `+++ b/<file>` headers and correct hunk line numbers, then briefly explain the change. Never include the line-number prefixes in diffs or code snippets.
- When reviewing or suggesting improvements, put real bugs and risks before style, and say when something is a judgement call.
- Be concise. Use Markdown headings and lists only when they make the answer easier to read."""


def _split_lines(content: str) -> List[str]:
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _merge_line_ranges(docs: list) -> Dict[str, List[Tuple[int, int]]]:
    """Group retrieved chunks by file (most relevant file first) and merge overlapping or nearby line ranges."""
    ranges: Dict[str, List[Tuple[int, int]]] = {}
    for d in docs:
        ranges.setdefault(d.metadata["source_file"], []).append(
            (d.metadata["start_line"], d.metadata["end_line"])
        )
    for name, spans in ranges.items():
        spans.sort()
        merged = [spans[0]]
        for start, end in spans[1:]:
            if start <= merged[-1][1] + EXCERPT_MERGE_GAP + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        ranges[name] = merged
    return ranges


def _format_file(name: str, content: str, spans: Optional[List[Tuple[int, int]]] = None) -> str:
    """Render a file (or the given line ranges of it) with line numbers."""
    lines = _split_lines(content)
    width = len(str(len(lines)))
    shown = "all"
    if spans is None:
        spans = [(1, len(lines))]
    else:
        shown = ", ".join(f"{start}-{end}" for start, end in spans)
    blocks = [
        "\n".join(f"{n:>{width}} | {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))
        for start, end in spans
    ]
    body = f"\n{' ' * width} | ...\n".join(blocks)
    return f'<file path="{name}" total_lines="{len(lines)}" lines_shown="{shown}">\n{body}\n</file>'


def build_user_message(
    instruction: str,
    file_contents: Dict[str, str],
    context_docs: Optional[list] = None,
) -> str:
    """Build the user message: project file list, code context, then the instruction."""
    project_files = "\n".join(
        f"- {name} ({len(_split_lines(content))} lines)" for name, content in file_contents.items()
    )
    if context_docs is None:
        note = "These are the complete project files."
        files = [_format_file(name, content) for name, content in file_contents.items()]
    else:
        note = "These are excerpts retrieved by semantic search; other code in the project is not shown."
        files = [
            _format_file(name, file_contents[name], spans)
            for name, spans in _merge_line_ranges(context_docs).items()
        ]
    code = "\n\n".join(files)
    return f"""<project_files>
{project_files}
</project_files>

<code_context>
{note}

{code}
</code_context>

<instruction>
{instruction}
</instruction>"""


def run_llm(
    instruction: str,
    file_contents: Dict[str, str],
    context_docs: Optional[list] = None,
) -> str:
    """Run the LLM on the instruction. Sends every file whole when context_docs is None, otherwise only the retrieved excerpts."""
    client = _get_client()
    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(instruction, file_contents, context_docs)},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
