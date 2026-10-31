"""Build the GitHub Pages homepage from the validated skill manifest. Stdlib only."""

from __future__ import annotations

import argparse
import shutil
from html import escape
from pathlib import Path
from string import Template

from catalogue import REPO_ROOT, SkillEntry, load_catalogue, routed_categories

LABELS = {
    "architecture": "Architecture",
    "refactoring": "Refactoring",
    "ai-ml": "AI & ML",
    "workflow": "Workflow",
    "communication": "Communication",
    "personal": "Personal",
}


def build_site(output: Path, *, dry_run: bool = False) -> None:
    """Write only public website assets, with catalogue text escaped as HTML."""
    skills = load_catalogue()
    routers = routed_categories(skills)
    counts = {category: sum(skill.category == category for skill in skills) for category in LABELS}
    filters = [
        f'<button type="button" data-category-filter="all" aria-pressed="true">All skills <span>{len(skills)}</span></button>'
    ]
    filters.extend(
        f'<button type="button" data-category-filter="{category}" aria-pressed="false">{escape(label)} <span>{counts[category]}</span></button>'
        for category, label in LABELS.items()
        if counts[category]
    )
    source = REPO_ROOT / "site"
    page = Template((source / "index.html").read_text(encoding="utf-8")).substitute(
        skill_count=len(skills),
        category_count=sum(count > 0 for count in counts.values()),
        filters="\n".join(filters),
        cards="\n".join(_skill_card(skill, routers) for skill in skills),
    )
    if dry_run:
        return
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    for asset in ("style.css", "app.js", "favicon.svg"):
        shutil.copyfile(source / asset, output / asset)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Examples: python3 scripts/build_site.py --output _site --dry-run; "
        "python3 scripts/build_site.py --output _site. Exit: 0 success, 1 build failure, 2 usage.",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="directory to write the public site"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate and render without writing"
    )
    args = parser.parse_args()
    build_site(args.output, dry_run=args.dry_run)
    print(f"{'Validated' if args.dry_run else 'Built'} homepage: {args.output}")


def _skill_card(skill: SkillEntry, routers: set[str]) -> str:
    kind = skill.activation.title()
    if skill.activation == "auto" and skill.category in routers:
        kind = f"Via {skill.category}"
    summary = skill.summary.split(" - ")[0]
    return (
        f'<a class="skill-card" data-category="{skill.category}" '
        f'href="https://github.com/fabiandistler/agents/blob/main/{escape(skill.path)}">'
        f'<div class="card-top"><span class="skill-mark" aria-hidden="true">{skill.category[:2].upper()}</span>'
        f'<span class="skill-kind">{escape(kind)}</span></div>'
        f"<h3>{escape(skill.name)}</h3><p>{escape(summary)}</p>"
        f"<footer>{escape(LABELS[skill.category])}<span>Read skill ↗</span></footer></a>"
    )


if __name__ == "__main__":
    main()
