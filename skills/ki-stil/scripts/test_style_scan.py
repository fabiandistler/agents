import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("style_scan.py")
MARKERS = Path(__file__).resolve().parent.parent / "assets" / "marker_lists.json"

_spec = importlib.util.spec_from_file_location("ki_stil_style_scan", SCRIPT)
assert _spec is not None and _spec.loader is not None
style_scan = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = style_scan  # dataclasses resolve annotations via sys.modules
_spec.loader.exec_module(style_scan)

GENERIC_POST = (
    "In der heutigen Zeit ist es wichtiger denn je, dass Data Scientists nicht nur "
    "technisch versiert, sondern auch kommunikativ, neugierig und geschäftsorientiert "
    "sind. Darüber hinaus spielt die Fähigkeit, komplexe Sachverhalte verständlich zu "
    "erklären, eine maßgebliche Rolle. Letztlich entscheidet die Kombination dieser "
    "Faktoren über den Erfolg datengetriebener Organisationen."
)


def run(*args, stdin=""):
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def sentence_texts(text):
    masked, _ = style_scan.mask(text)
    sentences, _, _ = style_scan.split_sentences(masked)
    return [text[s.start : s.end].strip() for s in sentences]


def scan(text, max_positions=10):
    return style_scan.scan(text, style_scan.load_markers(MARKERS), max_positions)


class TestSentenceSplitting(unittest.TestCase):
    def test_abbreviations_do_not_end_sentences(self):
        text = (
            "Wir nutzen z. B. Python, d. h. auch pandas usw. Das Team hat ca. 12 Leute. "
            "Siehe Nr. 4 bzw. Abschnitt 2. Danach kommt z.B. Dr. Meier dran."
        )
        self.assertEqual(
            sentence_texts(text),
            [
                "Wir nutzen z. B. Python, d. h. auch pandas usw.",
                "Das Team hat ca. 12 Leute.",
                "Siehe Nr. 4 bzw. Abschnitt 2.",
                "Danach kommt z.B. Dr. Meier dran.",
            ],
        )

    def test_numbers_dates_and_ordinals(self):
        text = (
            "Am 3. Oktober lief Version 2.0 live. Der 2. Versuch kostete 3,5 Mio. Euro. "
            "Das Ergebnis war 42. Danach haben wir am 25.10.2026 aufgeräumt."
        )
        self.assertEqual(
            sentence_texts(text),
            [
                "Am 3. Oktober lief Version 2.0 live.",
                "Der 2. Versuch kostete 3,5 Mio. Euro.",
                "Das Ergebnis war 42.",
                "Danach haben wir am 25.10.2026 aufgeräumt.",
            ],
        )

    def test_question_exclamation_and_quotes(self):
        text = "Warum? Weil es ging! „Was nun?“, fragte sie. Dann gingen wir."
        self.assertEqual(
            sentence_texts(text),
            ["Warum?", "Weil es ging!", "„Was nun?“, fragte sie.", "Dann gingen wir."],
        )

    def test_list_items_headings_and_code_are_separated(self):
        text = (
            "## Änderung\n\nDrei Punkte:\n- Tests ergänzt\n- Bug behoben\n\n"
            "```python\nx = 1. \ny = 2\n```\n\nSiehe `cfg.load()` und https://example.com/a.b. Fertig."
        )
        self.assertEqual(
            sentence_texts(text),
            [
                "Drei Punkte:",
                "- Tests ergänzt",
                "- Bug behoben",
                "Siehe `cfg.load()` und https://example.com/a.b.",
                "Fertig.",
            ],
        )
        report = scan(text)
        self.assertEqual(report["text"]["words"], 9)
        self.assertEqual(report["text"]["headings_skipped"], 1)
        self.assertEqual(report["text"]["masked"], {"code_blocks": 1, "inline_code": 1, "urls": 1})

    def test_hard_wrapped_lines_stay_one_sentence(self):
        text = "Dieser Satz ist im Editor\numgebrochen und bleibt trotzdem\nein einziger Satz."
        self.assertEqual(len(sentence_texts(text)), 1)


class TestDensityAndMarkers(unittest.TestCase):
    def test_generic_post_hits_and_density(self):
        report = scan(GENERIC_POST)
        self.assertEqual(report["text"]["words"], 47)
        floskeln = report["lexical"]["floskeln"]
        self.assertEqual(floskeln["hits"], 3)
        self.assertEqual(floskeln["per_100_words"], round(300 / 47, 2))
        self.assertEqual(floskeln["positions"][1]["match"], "Darüber hinaus")
        self.assertEqual(floskeln["positions"][1]["sentence"], 2)
        self.assertEqual(report["lexical"]["lehrbuchvokabular"]["hits"], 1)
        self.assertEqual(report["figures"]["nicht_nur_sondern_auch"]["candidates"], 1)
        self.assertEqual(report["figures"]["triad"]["candidates"], 1)
        self.assertEqual(report["clusters_total"], 1)

    def test_longest_phrase_wins_without_double_count(self):
        report = scan("Es ist wichtig zu beachten, dass wir testen. " * 3)
        self.assertEqual(report["lexical"]["floskeln"]["hits"], 3)

    def test_plain_language_raises_no_counter(self):
        text = (
            "Ich habe das Modell gestern getestet. Es war zu langsam. Ich habe den Cache "
            "eingebaut. Jetzt braucht eine Anfrage 80 Millisekunden statt 900. Morgen "
            "zeige ich das im Team. Wir entscheiden dann, ob es live geht. Mein Kollege "
            "Jonas prüft vorher die Logs. Er findet oft Fehler, die ich übersehe. Das ist "
            "gut so. Danach schreibe ich die Doku. Sie wird kurz. Fragen gerne an mich."
        )
        report = scan(text)
        for name, block in report["lexical"].items():
            self.assertEqual(block["hits"], 0, name)
        self.assertEqual(report["clusters_total"], 0)
        self.assertGreater(report["substance_hints"]["digit_tokens"], 0)
        self.assertGreater(report["substance_hints"]["first_person"], 0)

    def test_not_x_but_y_variants(self):
        report = scan(
            "Das ist kein Bug, sondern ein Feature. Es geht nicht um Tools. Es geht um Daten. "
            "Wir bauen keine Software. Wir bauen Vertrauen."
        )
        self.assertEqual(report["figures"]["nicht_x_sondern_y"]["candidates"], 3)
        self.assertEqual(report["figures"]["nicht_nur_sondern_auch"]["candidates"], 0)

    def test_triad_fragment(self):
        report = scan("Wir bauen Vertrauen. Schnell, sicher, skalierbar.")
        self.assertEqual(report["figures"]["triad"]["candidates"], 1)
        self.assertEqual(report["figures"]["triad"]["positions"][0]["sentence"], 2)

    def test_dispersion_uniform_vs_varied(self):
        uniform = " ".join(["Wir haben das Modell heute erneut gründlich getestet."] * 12)
        varied = (
            "Kurz. Das Modell lief heute zum ersten Mal auf echten Daten aus dem Lager, "
            "und die Fehlerquote lag deutlich unter dem, was wir im Frühjahr gesehen hatten, "
            "obwohl die Daten schmutziger waren. Gut. Trotzdem bleibt ein Rest. "
        ) * 4
        self.assertEqual(scan(uniform)["sentence_length"]["cv"], 0.0)
        varied_stats = scan(varied)["sentence_length"]
        self.assertGreater(varied_stats["cv"], 0.8)
        self.assertGreater(varied_stats["share_under_8"], 0.4)
        self.assertGreater(varied_stats["share_over_30"], 0.2)

    def test_positions_are_bounded(self):
        report = scan("Darüber hinaus gilt das. " * 30, max_positions=5)
        floskeln = report["lexical"]["floskeln"]
        self.assertEqual(floskeln["hits"], 30)
        self.assertEqual(len(floskeln["positions"]), 5)
        self.assertTrue(floskeln["truncated"])


class TestDashes(unittest.TestCase):
    def test_classification(self):
        text = (
            "Daten – nicht Modelle – zählen. Das gilt—leider—oft. Seite 10–20 und "
            "10 – 20 lesen. Ein Wort - so. Ein Halbgeviert–ohne Leerzeichen.\n"
            "- Listenpunkt\n– Listenpunkt\n— Listenpunkt"
        )
        counts = {k: len(v) for k, v in style_scan.classify_dashes(text).items()}
        self.assertEqual(
            counts,
            {
                "spaced_en_dash": 2,
                "unspaced_en_dash": 1,
                "number_range": 2,
                "spaced_em_dash": 0,
                "unspaced_em_dash": 2,
                "spaced_hyphen": 1,
            },
        )

    def test_spaced_en_dash_is_not_weighted(self):
        report = scan("Daten – nicht Modelle – zählen. " * 5)
        self.assertEqual(report["tier_hits_per_100_words"]["weak"], 0.0)
        self.assertEqual(report["dashes"]["counts"]["spaced_en_dash"], 10)


class TestShortText(unittest.TestCase):
    def test_short_text_is_flagged(self):
        report = scan("Wir bauen keine Software. Wir bauen Vertrauen. Schnell, sicher, skalierbar.")
        self.assertTrue(report["short_text"])
        self.assertFalse(report["dispersion_reliable"])
        self.assertTrue(report["notes"])

    def test_single_sentence_has_no_sd(self):
        stats = scan("Ein einziger Satz.")["sentence_length"]
        self.assertIsNone(stats["sd"])
        self.assertIsNone(stats["cv"])


class TestMarkerList(unittest.TestCase):
    def test_entries_belong_to_exactly_one_category(self):
        spec = json.loads(MARKERS.read_text(encoding="utf-8"))
        seen = {}
        for name, body in spec["kategorien"].items():
            for entry in body["eintraege"]:
                key = entry.lower()
                self.assertNotIn(key, seen, f"{entry!r} in {name} and {seen.get(key)}")
                seen[key] = name

    def test_malformed_list_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp, "m.json")
            bad.write_text('{"kategorien": {"x": {"stufe": "huge", "eintraege": []}}}')
            with self.assertRaises(style_scan.MarkerListError):
                style_scan.load_markers(bad)


class TestCli(unittest.TestCase):
    def test_stdin_json(self):
        proc = run("-", stdin=GENERIC_POST)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["marker_lists"]["source"], "eigene Beobachtung, keine Studie")
        self.assertNotIn(GENERIC_POST[:60], proc.stdout)

    def test_file_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "draft.md")
            src.write_text(GENERIC_POST, encoding="utf-8")
            out = Path(tmp, "scan.json")
            proc = run(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(json.loads(out.read_text())["text"]["words"], 47)

    def test_exit_codes(self):
        self.assertEqual(run("/nope/missing.txt").returncode, 1)
        self.assertEqual(run("-", "--max-positions", "-1").returncode, 2)
        self.assertEqual(run("-", stdin="  ...  \n").returncode, 3)

    def test_help_is_short(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 25)
        self.assertIn("exit codes", proc.stdout)


if __name__ == "__main__":
    unittest.main()
