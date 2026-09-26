# Deployment targets — Definition of Done

Each target is three lines. Phase 1 copies them into `SPEC.md ## Definition of Done`; the smoke command becomes the `check` of the final prd item. Language × target picks the framework.

| Target | Smoke command (`check` of last prd item) | Required artefact | Non-goal |
|---|---|---|---|
| `package` | Python: `uv build && uv run python -c "import <name>"` · R: `Rscript -e 'devtools::check(error_on="warning")'` · bash: `bats --recursive test/` | installable package with README usage block | publishing to PyPI/CRAN |
| `http-service` | `docker rm -f t >/dev/null 2>&1; docker build -t app:test . && docker run --rm -d -p 8000:8000 --name t app:test && curl -sf --retry 10 --retry-connrefused --retry-delay 1 localhost:8000/health; rc=$?; docker rm -f t >/dev/null 2>&1; exit $rc` — the container is removed on every path, so a failed attempt never blocks the next one on the name `t` | `Dockerfile` (multi-stage, `--target test` runs suite), `/health` endpoint | TLS, auth, horizontal scaling |
| `mcp-server` | Python: `npx -y @modelcontextprotocol/inspector@2.8.0 --cli uv run python -m <name> --method tools/list --format json \| jq -e '.result.tools \| length > 0'` (needs Node; a stdio server ignores `--help` and would wait on stdin) · R/bash: n/a → ask, likely `other` | stdio entry point, `tools/list` returns ≥1 tool | HTTP transport unless the goal says so |
| `cli` | `<cmd> --help` exits 0 and one golden-path invocation from SPEC.md `## Users` exits 0 | single entry point, `--help` documents every flag | shell completion, packaging for distros |
| `other:<text>` | Phase 1 asks for a smoke command verbatim; refuse to write prd.json without one | as stated | as stated |

Frameworks by language × target:

| | Python | R | bash |
|---|---|---|---|
| `http-service` | FastAPI | plumber | n/a → ask |
| `mcp-server` | FastMCP (stdio; Streamable HTTP only if the goal says so) | n/a → ask | n/a → ask |
| `cli` | `typer` or stdlib `argparse` | `docopt`/`optparse` via `Rscript` | `getopts` |

Docker: `docker build --check .` (BuildKit) plus `hadolint Dockerfile` as the lint line for any target with a Dockerfile.
