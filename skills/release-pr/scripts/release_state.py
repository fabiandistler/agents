#!/usr/bin/env python3
"""Report the release state of an R or Python package as JSON.

Answers the questions a release needs answered before anything is edited:
which version the package declares, which version the top changelog heading
names and whether it has entries, which tag was released last, what the
commits since that tag suggest as the next bump, and where else the current
version string appears in tracked files.

The package is detected from `DESCRIPTION` (R, changelog `NEWS.md`) or
`pyproject.toml` with a `[project]` table (Python, changelog `CHANGELOG.md`).
Versions are compared on their leading numeric components; a fourth component
of 9000 or more (R) or a `(development version)` / `[Unreleased]` heading marks
a development state.

STATE is one of:

  consistent    version == top heading, the heading has entries, and no tag
                carries this version yet: ready to tag.
  released      the declared version already has a tag: the next change must
                bump before it can be released.
  open-heading  version == top heading but the heading is empty: a bump that
                ran ahead of its entries. Fill it, or re-set the version.
  development   a dev suffix or an Unreleased/development heading: the
                release step replaces it with the concrete version.
  mismatch      version and top heading disagree, or no changelog exists.

Exit codes: 0 state is consistent, released or development; 1 usage error;
2 not an R or Python package (or ambiguous without --language); 3 state is
open-heading or mismatch, details in the JSON; 4 git unavailable or no commits.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11: regex fallback below
    tomllib = None

DEV_R = 9000
MAX_MENTIONS = 20
CONVENTIONAL = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?:\s")


def usage_error(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("error: git not found", file=sys.stderr)
        sys.exit(4)
    except subprocess.CalledProcessError as exc:
        print(f"error: git {' '.join(args)}: {exc.stderr.strip()}", file=sys.stderr)
        sys.exit(4)
    return out.stdout


# --- package detection -------------------------------------------------------


def read_description(repo: Path) -> dict | None:
    path = repo / "DESCRIPTION"
    if not path.is_file():
        return None
    fields: dict[str, str] = {}
    key = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:1].isspace() and key:
            fields[key] += " " + line.strip()
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
    if "Package" not in fields or "Version" not in fields:
        return None
    return {
        "language": "r",
        "package": fields["Package"],
        "version": fields["Version"],
        "source": "DESCRIPTION",
        "changelog": "NEWS.md",
    }


def read_pyproject(repo: Path) -> dict | None:
    path = repo / "pyproject.toml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    project = None
    if tomllib is not None:
        try:
            project = tomllib.loads(text).get("project")
        except tomllib.TOMLDecodeError:
            project = None
    if project is None:
        block = re.search(r"^\[project\]\n(.*?)(?=^\[|\Z)", text, re.DOTALL | re.MULTILINE)
        if not block:
            return None
        name = re.search(r'^name\s*=\s*"([^"]+)"', block.group(1), re.MULTILINE)
        version = re.search(r'^version\s*=\s*"([^"]+)"', block.group(1), re.MULTILINE)
        dynamic = re.search(r"^dynamic\s*=\s*\[[^\]]*\bversion\b", block.group(1), re.MULTILINE)
        project = {
            "name": name.group(1) if name else None,
            "version": version.group(1) if version else None,
            "dynamic": ["version"] if dynamic else [],
        }
    if not project or not project.get("name"):
        return None
    return {
        "language": "python",
        "package": project["name"],
        "version": project.get("version"),
        "dynamic_version": "version" in (project.get("dynamic") or []),
        "source": "pyproject.toml",
        "changelog": "CHANGELOG.md",
    }


def detect(repo: Path, language: str | None) -> dict:
    found = [p for p in (read_description(repo), read_pyproject(repo)) if p]
    if language:
        found = [p for p in found if p["language"] == language]
    if not found:
        print("error: no DESCRIPTION or pyproject.toml [project] found", file=sys.stderr)
        sys.exit(2)
    if len(found) > 1:
        print("error: both R and Python packages found; pass --language", file=sys.stderr)
        sys.exit(2)
    return found[0]


# --- versions ----------------------------------------------------------------


def numeric(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    m = re.match(r"v?(\d+(?:[.-]\d+)*)", version)
    return tuple(int(x) for x in re.split(r"[.-]", m.group(1))) if m else ()


def is_dev_version(language: str, version: str | None) -> bool:
    if not version:
        return False
    parts = numeric(version)
    if language == "r":
        return len(parts) >= 4 and parts[3] >= DEV_R
    return bool(re.search(r"\.dev\d*$", version))


def has_prerelease(language: str, version: str | None) -> bool:
    if not version or language != "python":
        return False
    return bool(re.search(r"(a|b|rc)\d+", version))


def bump(parts: tuple[int, ...], which: str) -> str:
    major, minor, patch = (list(parts) + [0, 0, 0])[:3]
    if which == "major":
        return f"{major + 1}.0.0"
    if which == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


# --- changelog ---------------------------------------------------------------


def read_changelog(repo: Path, language: str, package: str) -> dict | None:
    path = repo / ("NEWS.md" if language == "r" else "CHANGELOG.md")
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    level = "# " if language == "r" else "## "
    headings = [i for i, line in enumerate(lines) if line.startswith(level)]
    if not headings:
        return {"file": path.name, "version": None, "entries": 0, "line": None}
    first = headings[0]
    end = headings[1] if len(headings) > 1 else len(lines)
    body = [line for line in lines[first + 1 : end] if line.strip()]
    entries = sum(1 for line in body if re.match(r"^\s*[-*+]\s", line))
    text = lines[first][len(level) :].strip()
    version = None
    development = False
    if language == "r":
        m = re.match(re.escape(package) + r"\s+(.+)$", text, re.IGNORECASE)
        rest = m.group(1) if m else text
        if "development version" in rest:
            development = True
        else:
            version = rest.split()[0] if rest else None
    else:
        m = re.match(r"\[?([^\]\s]+)\]?", text)
        rest = m.group(1) if m else text
        if rest.lower() == "unreleased":
            development = True
        else:
            version = rest
    return {
        "file": path.name,
        "version": version,
        "development_heading": development,
        "entries": entries,
        "line": first + 1,
    }


def section(repo: Path, language: str, version: str) -> str | None:
    path = repo / ("NEWS.md" if language == "r" else "CHANGELOG.md")
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    level = "# " if language == "r" else "## "
    start = None
    for i, line in enumerate(lines):
        if line.startswith(level):
            if start is not None:
                return "\n".join(lines[start + 1 : i]).strip() + "\n"
            if re.search(r"(?<![\w.])" + re.escape(version) + r"(?![\w.])", line):
                start = i
    if start is None:
        return None
    return "\n".join(lines[start + 1 :]).strip() + "\n"


# --- git ---------------------------------------------------------------------


def last_tag(repo: Path) -> tuple[str | None, str]:
    tags = git(repo, "tag", "--list", "--sort=-v:refname").split()
    for tag in tags:
        if re.match(r"^v?\d+(\.\d+)+", tag):
            return tag, ("v" if tag.startswith("v") else "")
    return None, "v"


def commits_since(repo: Path, tag: str | None) -> dict:
    rev = f"{tag}..HEAD" if tag else "HEAD"
    raw = git(repo, "log", "--no-merges", "--format=%s%x00%b%x1e", rev)
    counts = {"count": 0, "breaking": 0, "feat": 0, "fix": 0, "other": 0, "unconventional": 0}
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        subject, _, body = record.strip("\n").partition("\x00")
        counts["count"] += 1
        m = CONVENTIONAL.match(subject)
        if not m:
            counts["unconventional"] += 1
            continue
        if m.group("bang") or "BREAKING CHANGE:" in body or "BREAKING-CHANGE:" in body:
            counts["breaking"] += 1
        elif m.group("type") == "feat":
            counts["feat"] += 1
        elif m.group("type") == "fix":
            counts["fix"] += 1
        else:
            counts["other"] += 1
    return counts


def removed_exports(repo: Path, tag: str | None) -> list[str]:
    if not tag or not (repo / "NAMESPACE").is_file():
        return []
    diff = git(repo, "diff", f"{tag}..HEAD", "--", "NAMESPACE")
    return [line[1:].strip() for line in diff.splitlines() if line.startswith("-export")]


def version_mentions(repo: Path, version: str | None, skip: set[str]) -> list[dict]:
    if not version:
        return []
    out = subprocess.run(
        ["git", "-C", str(repo), "grep", "-n", "-F", "-e", version, "--", "."],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    hits = []
    for line in out.splitlines():
        path, _, rest = line.partition(":")
        if path in skip or path.endswith((".lock", "renv.lock", "uv.lock")):
            continue
        lineno, _, text = rest.partition(":")
        hits.append({"file": path, "line": int(lineno), "text": text.strip()[:120]})
        if len(hits) >= MAX_MENTIONS:
            break
    return hits


# --- main --------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="release_state.py",
        description="Report the release state of an R or Python package as JSON.",
        epilog=(
            "examples:\n"
            "  release_state.py\n"
            "  release_state.py --repo ~/pkg --section 1.2.0 > notes.md\n"
            "exit: 0 ok | 1 usage | 2 not a package | 3 inconsistent | 4 git"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", default=".", help="package root (default: cwd)")
    parser.add_argument("--language", choices=["r", "python"], help="pick when both exist")
    parser.add_argument(
        "--section", metavar="VERSION", help="print that changelog section as Markdown and exit"
    )
    parser.add_argument("--output", metavar="FILE", help="write the JSON here instead of stdout")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        usage_error(f"not a directory: {repo}")
    git(repo, "rev-parse", "--verify", "HEAD")

    pkg = detect(repo, args.language)
    language, package, version = pkg["language"], pkg["package"], pkg["version"]

    if args.section:
        text = section(repo, language, args.section)
        if text is None:
            print(f"error: no {pkg['changelog']} section for {args.section}", file=sys.stderr)
            sys.exit(3)
        sys.stdout.write(text)
        return

    changelog = read_changelog(repo, language, package)
    tag, prefix = last_tag(repo)
    tag_version = tag.lstrip("v") if tag else None
    head_tags = git(repo, "tag", "--points-at", "HEAD").split()
    counts = commits_since(repo, tag)
    exports_gone = removed_exports(repo, tag)

    problems: list[str] = []
    dynamic = bool(pkg.get("dynamic_version"))
    if dynamic:
        problems.append(
            "version is dynamic in pyproject.toml: the tag is the version source, "
            "uv version cannot bump it; the changelog heading stands in for the declared version"
        )
        if changelog and changelog.get("version"):
            version = changelog["version"]
    dev = is_dev_version(language, version) or bool(
        changelog and changelog.get("development_heading")
    )
    if changelog is None:
        problems.append(f"{pkg['changelog']} not found")
        state = "mismatch"
    elif dev:
        state = "development"
    elif changelog["version"] is None or numeric(changelog["version"]) != numeric(version):
        problems.append(
            f"{pkg['source']} says {version} but the top {pkg['changelog']} heading says {changelog['version']}"
        )
        state = "mismatch"
    elif tag_version and numeric(tag_version) == numeric(version):
        state = "released"
        if not head_tags:
            problems.append(
                f"{version} is already tagged as {tag} and HEAD is not that commit: bump before releasing"
            )
    elif changelog["entries"] == 0:
        problems.append(f"top {pkg['changelog']} heading {changelog['version']} has no entries")
        state = "open-heading"
    else:
        state = "consistent"

    base = numeric(version)
    if counts["breaking"] or exports_gone:
        which = "minor" if base and base[0] == 0 else "major"
    elif counts["feat"]:
        which = "minor"
    elif counts["count"]:
        which = "patch"
    else:
        which = None
    if state == "development" and which is None:
        which = "patch"
    suggested = bump(base, which) if which else None
    if state in ("consistent", "open-heading") and which and numeric(suggested) <= base:
        suggested = version
    if has_prerelease(language, version):
        problems.append(f"{version} is a pre-release; a final release drops the suffix")

    report = {
        "language": language,
        "package": package,
        "version": version,
        "version_source": "changelog heading (dynamic version)" if dynamic else pkg["source"],
        "state": state,
        "changelog": changelog,
        "last_tag": tag,
        "last_tag_version": tag_version,
        "tag_prefix": prefix,
        "head_tags": head_tags,
        "commits_since_tag": counts,
        "removed_exports": exports_gone,
        "suggested_bump": which,
        "suggested_version": suggested,
        "version_mentions": version_mentions(
            repo, version, {pkg["source"], pkg["changelog"], "NEWS.md", "CHANGELOG.md"}
        ),
        "problems": problems,
    }
    text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(text)
    sys.exit(3 if state in ("open-heading", "mismatch") else 0)


if __name__ == "__main__":
    main()
