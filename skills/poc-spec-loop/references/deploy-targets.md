# Deployment targets — Definition of Done

Each target is three lines. Phase 1 copies them into `SPEC.md ## Definition of Done`; the smoke command becomes the `check` of the final prd item. Language × target picks the framework.

| Target | Smoke command (`check` of last prd item) | Required artefact | Non-goal |
|---|---|---|---|
| `package` | Python: `uv build && uv run python -c "import <name>"` · R: `Rscript -e 'devtools::check(error_on="warning")'` · bash: `bats --recursive test/` | installable package with README usage block | publishing to PyPI/CRAN |
| `http-service` | `docker build -t app:test . && docker run --rm -d -p 8000:8000 --name t app:test && sleep 2 && curl -sf localhost:8000/health && docker rm -f t` | `Dockerfile` (multi-stage, `--target test` runs suite), `/health` endpoint | TLS, auth, horizontal scaling |
| `mcp-server` | Python: `uv run python -m <name> --help` then a `tools/list` round-trip via the MCP inspector CLI · R/bash: n/a → ask, likely `other` | stdio entry point, `tools/list` returns ≥1 tool | HTTP transport unless the goal says so |
| `cli` | `<cmd> --help` exits 0 and one golden-path invocation from SPEC.md `## Users` exits 0 | single entry point, `--help` documents every flag | shell completion, packaging for distros |
| `other:<text>` | Phase 1 asks for a smoke command verbatim; refuse to write prd.json without one | as stated | as stated |

Frameworks by language × target:

| | Python | R | bash |
|---|---|---|---|
| `http-service` | FastAPI | plumber | n/a → ask |
| `mcp-server` | FastMCP (stdio; Streamable HTTP only if the goal says so) | n/a → ask | n/a → ask |
| `cli` | `typer` or stdlib `argparse` | `docopt`/`optparse` via `Rscript` | `getopts` |

Docker: `docker build --check .` (BuildKit) plus `hadolint Dockerfile` as the lint line for any target with a Dockerfile.
