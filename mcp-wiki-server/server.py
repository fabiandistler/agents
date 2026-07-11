#!/usr/bin/env python3
"""MCP server that exposes a wiki/knowledge base, one tool per topic folder.

Each top-level directory under the wiki root becomes its own tool, e.g.
``wiki/sql/`` -> tool ``wiki_sql``. Tools accept optional ``query`` (substring
search) and ``page`` (filename) arguments. With no arguments, a topic tool
returns a table of contents for that topic.

Configuration via environment variables:
    WIKI_PATH       Local directory containing topic folders (default: ./wiki)
    WIKI_GIT_URL    Remote git repo URL; cloned on startup (overrides WIKI_PATH)
    WIKI_GIT_BRANCH Branch to clone (default: main)
    WIKI_CACHE_DIR  Where to clone WIKI_GIT_URL (default: tempdir)
"""

from mcp.server.fastmcp import FastMCP
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

MAX_PAGE_CHARS = 8000
MAX_QUERY_HITS = 20

mcp = FastMCP("wiki")


def resolve_wiki_root() -> Path:
    if url := os.getenv("WIKI_GIT_URL"):
        branch = os.getenv("WIKI_GIT_BRANCH", "main")
        cache = Path(os.getenv("WIKI_CACHE_DIR", tempfile.gettempdir())) / "mcp-wiki-cache"
        if not cache.exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", "-b", branch, url, str(cache)],
                check=True,
            )
        return cache
    return Path(os.getenv("WIKI_PATH", Path(__file__).parent / "wiki")).resolve()


def sanitize(name: str) -> str:
    return "wiki_" + re.sub(r"[^a-z0-9_]", "_", name.lower())


def render(topic: Path, query: str | None, page: str | None) -> str:
    if page:
        base = topic.resolve()  # topic may be a symlink; compare against its real path
        target = (base / page).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            return f"Page not found: {page}"
        text = target.read_text(encoding="utf-8")
        if len(text) > MAX_PAGE_CHARS:
            return text[:MAX_PAGE_CHARS] + "\n\n... [truncated]"
        return text

    files = sorted(topic.rglob("*.md"))

    if query:
        ql = query.lower()
        hits: list[str] = []
        for f in files:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
                if ql in line.lower():
                    rel = f.relative_to(topic)
                    hits.append(f"**{rel}:{i}** — {line.strip()}")
                    if len(hits) >= MAX_QUERY_HITS:
                        break
            if len(hits) >= MAX_QUERY_HITS:
                break
        return "\n".join(hits) if hits else f"No matches for '{query}' in {topic.name}"

    lines = [f"# {topic.name} pages", ""]
    for f in files:
        first = next(
            (ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()),
            "",
        )
        lines.append(f"- `{f.relative_to(topic)}` — {first[:100]}")
    return "\n".join(lines)


def make_handler(topic: Path):
    def handler(query: str | None = None, page: str | None = None) -> str:
        return render(topic, query, page)

    handler.__doc__ = (
        f"Search or read the '{topic.name}' wiki topic. "
        f"No args: list pages. query=<term>: find matches. page=<filename.md>: full page."
    )
    return handler


def register_topics(root: Path) -> None:
    if not root.exists():
        print(f"[wiki] root not found: {root}", file=sys.stderr)
        return
    topics = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not topics:
        print(f"[wiki] no topic folders in {root}", file=sys.stderr)
        return
    for d in topics:
        mcp.tool(name=sanitize(d.name))(make_handler(d))
    print(f"[wiki] registered {len(topics)} topic tool(s) from {root}", file=sys.stderr)


register_topics(resolve_wiki_root())


if __name__ == "__main__":
    mcp.run()
