"""Homepage build contracts: complete catalogue, safe rendering, portable assets."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from build_site import build_site
from catalogue import load_catalogue


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name) / "public"

    def test_catalogue_is_complete_and_build_is_repeatable(self):
        build_site(self.output)
        page = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertEqual(page.count('class="skill-card"'), len(load_catalogue()))
        for skill in load_catalogue():
            self.assertIn(f"/blob/main/{skill.path}", page)
        self.assertIn("Via architecture", page)
        self.assertIn('href="./style.css"', page)
        self.assertEqual(
            {asset.name for asset in self.output.iterdir()},
            {"index.html", "style.css", "app.js", "favicon.svg"},
        )
        build_site(self.output)
        self.assertEqual(page, (self.output / "index.html").read_text(encoding="utf-8"))

    def test_manifest_text_cannot_become_markup_or_template_source(self):
        skill = replace(load_catalogue()[0], summary='<script>alert("x")</script> $skill_count')
        with patch("build_site.load_catalogue", return_value=[skill]):
            build_site(self.output)
        page = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("$skill_count", page)

    def test_dry_run_creates_no_output(self):
        build_site(self.output, dry_run=True)
        self.assertFalse(self.output.exists())
