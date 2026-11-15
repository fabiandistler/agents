"""The html-artifacts README links one self-contained example page per layout reference.

Issue #868: human readers get one browser-viewable HTML example per layout page
under skills/html-artifacts/references/. matching-your-style.md is the shared
look every example applies, not a layout, so it has no example. The examples
are illustrations for people; SKILL.md must not point agents at them.
"""

import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "html-artifacts"
README = SKILL_DIR / "README.md"
EXAMPLES = SKILL_DIR / "examples"
STYLE_REFERENCE = "matching-your-style.md"
LAYOUT_REFERENCES = sorted(
    p.name for p in (SKILL_DIR / "references").glob("*.md") if p.name != STYLE_REFERENCE
)
EXAMPLE_PAGES = sorted(EXAMPLES.glob("*.html"))


class _PageScan(HTMLParser):
    """Collect what the self-containment checks need from one page."""

    def __init__(self) -> None:
        super().__init__()
        self.lang = None
        self.has_viewport = False
        self.has_title = False
        self.external_refs: list[str] = []
        self.scripts: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "html":
            self.lang = attr.get("lang")
        if tag == "meta" and attr.get("name") == "viewport":
            self.has_viewport = "width=device-width" in (attr.get("content") or "")
        if tag == "title":
            self.has_title = True
        if tag == "link" and "stylesheet" in (attr.get("rel") or ""):
            self.external_refs.append(f"<link> {attr.get('href')}")
        for name in ("src", "href"):
            value = attr.get(name) or ""
            if re.match(r"(https?:)?//", value):
                self.external_refs.append(f"<{tag} {name}> {value}")
        if tag == "script":
            if attr.get("src"):
                self.external_refs.append(f"<script src> {attr['src']}")
            self._in_script = True
            self.scripts.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.scripts[-1] += data


def _scan(page: Path) -> _PageScan:
    scan = _PageScan()
    scan.feed(page.read_text(encoding="utf-8"))
    return scan


def _readme_example_links() -> dict[str, str]:
    """Map each example page the README table links to the reference on its row."""
    rows = re.findall(
        r"^\| \[[^\]]+\]\(examples/([^)]+\.html)\) \| \[[^\]]+\]\(references/([^)]+\.md)\) \|",
        README.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    return dict(rows)


def test_readme_pairs_every_layout_reference_with_one_existing_example():
    links = _readme_example_links()
    assert sorted(links.values()) == LAYOUT_REFERENCES
    for example in links:
        assert (EXAMPLES / example).is_file(), example
    assert sorted(links) == [p.name for p in EXAMPLE_PAGES]


def test_each_example_is_named_after_its_reference_and_cites_it():
    for example, reference in _readme_example_links().items():
        assert Path(example).stem == Path(reference).stem
        assert f"references/{reference}" in (EXAMPLES / example).read_text(encoding="utf-8")


@pytest.mark.parametrize("page", EXAMPLE_PAGES, ids=lambda p: p.name)
def test_example_is_a_self_contained_responsive_page(page: Path):
    scan = _scan(page)
    assert scan.lang == "en"
    assert scan.has_viewport
    assert scan.has_title
    assert scan.external_refs == []
    assert not re.search(r"@import|url\(\s*['\"]?(https?:)?//", page.read_text(encoding="utf-8"))


@pytest.mark.parametrize("page", EXAMPLE_PAGES, ids=lambda p: p.name)
def test_example_scripts_parse(page: Path, tmp_path: Path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    for index, script in enumerate(_scan(page).scripts):
        source = tmp_path / f"{page.stem}-{index}.js"
        source.write_text(script, encoding="utf-8")
        result = subprocess.run(  # noqa: S603 -- node from PATH, fixed argv.
            [node, "--check", str(source)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr


def test_readme_says_examples_may_drift_from_the_references():
    text = README.read_text(encoding="utf-8")
    assert "not generated from the references" in text
    assert "the reference wins" in text


def test_skill_md_does_not_send_agents_to_the_examples():
    assert "examples/" not in (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
