import re

from langchain_core.tools import tool

from src.config import PROJECT_ROOT, RUNBOOKS_PATH


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
RUNBOOK_ID_PATTERN = re.compile(r"^Runbook ID:\s*(\S+)", re.MULTILINE)
TITLE_PATTERN = re.compile(r"^#\s+(.+)", re.MULTILINE)
STOPWORDS = {"a", "an", "and", "for", "in", "of", "on", "or", "the", "to", "with"}


def tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.casefold())) - STOPWORDS


def extract_runbook_id(content: str) -> str:
    match = RUNBOOK_ID_PATTERN.search(content)

    if not match:
        raise ValueError("Runbook does not contain a Runbook ID.")

    return match.group(1)


def extract_title(content: str) -> str:
    match = TITLE_PATTERN.search(content)

    if not match:
        raise ValueError("Runbook does not contain a title.")

    return match.group(1).strip()


@tool
def search_runbooks(query: str, limit: int = 5) -> list[dict]:
    """Search operational runbooks using keyword matching."""

    if not query.strip():
        raise ValueError("query cannot be empty.")

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    query_terms = tokenize(query)

    if not query_terms:
        raise ValueError("query does not contain searchable terms.")

    results = []

    for runbook_file in RUNBOOKS_PATH.glob("*.md"):
        content = runbook_file.read_text(encoding="utf-8")
        normalized_content = content.casefold()
        score = sum(normalized_content.count(term) for term in query_terms)

        if score == 0:
            continue

        results.append({
            "evidence_id": extract_runbook_id(content),
            "title": extract_title(content),
            "source": str(runbook_file.relative_to(PROJECT_ROOT)),
            "score": score,
            "content": content,
        })

    results.sort(key=lambda result: (-result["score"], result["evidence_id"]))

    return results[:limit]