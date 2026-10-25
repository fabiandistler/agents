# Marker catalogue

What the counted signals mean, how strong the evidence behind each is, and how
to read and maintain the list in `assets/marker_lists.json`.

## Contents

- [Provenance of the list](#provenance-of-the-list)
- [Evidence behind the tiers](#evidence-behind-the-tiers)
- [Reading the script output](#reading-the-script-output)
- [Orientation values](#orientation-values)
- [List categories](#list-categories)
- [Deliberately not measured](#deliberately-not-measured)
- [Re-curating the list](#re-curating-the-list)

## Provenance of the list

The German phrase lists are **eigene Beobachtung, keine Studie**. No
peer-reviewed German excess-vocabulary study exists; the lists combine
journalism lists (GIGA, t3n), Wikipedia's "Signs of AI writing" advice page,
and German translations of English style words documented for English text
(Kobak et al. 2025; Juzek & Ward 2025). Say so whenever a user asks where a
marker comes from.

As of 2026-10 the list reflects the models in common use at that point.
Markers shift within months: after em dashes became a known tell in 2025,
several models dropped them and other phrasings rose in their place. Re-check
the list by 2027-01 (the `naechste_pruefung` key in the JSON), and earlier
whenever a new model generation becomes the default. The rhetorical patterns
(contrastive framing, significance inflation, missing specifics) last longer
than single words; the authenticity stage does not age at all.

## Evidence behind the tiers

- **Strong**
  - *Missing own substance:* German ChatGPT reading texts held fewer concrete
    examples than benchmark texts (Drackert et al. 2025).
  - *Low sentence-length dispersion:* human prose has more scattered sentence
    lengths than LLM output (Muñoz-Ortiz et al. 2024; Kutyła et al. 2026).
    No study supports a fixed band such as "15–22 words"; that rule is
    folklore, so the script measures spread instead.
  - *Nominal style and textbook vocabulary:* more nominalisations, higher
    lexical density and more technical vocabulary in German LLM text
    (Drackert et al. 2025); noun-heavy, dense style even in informal
    registers (Reinhart et al. 2025).
  - *English calques:* non-idiomatic expressions translated from English
    (Drackert et al. 2025); English-like linear word order in German AI news
    (Valentinelli 2026).
- **Medium:** triads, „nicht X, sondern Y“, connector floskeln, significance
  inflation. Documented by Wikipedia's advice page and journalism, not by
  controlled German studies. Plausible, not validated.
- **Weak:** dashes. The German Gedankenstrich is a spaced en dash („ – “) and
  correct punctuation. The unspaced em dash („—“) is English typography;
  population-level em-dash use rose sharply in 2024–25, but newer models
  suppress it, so absence proves nothing.

Detectors and judges: OpenAI's own classifier reached 26 % true positives and
was withdrawn; 14 tools tested by Weber-Wulff et al. (2023) were "neither
accurate nor reliable"; 289 German teachers could not tell ChatGPT essays from
student essays and were overconfident (Fleckenstein et al. 2024); detectors
flagged 61 % of non-native TOEFL essays as AI (Liang et al. 2023). Only
holistic judgement by heavy LLM users reached high accuracy (Russell et al.
2025), which is why this skill combines counts with a judgement pass and
never issues an authorship verdict.

## Reading the script output

- `text`: words, sentences, paragraphs, skipped Markdown headings, and how many
  code blocks, inline code spans and URLs were masked before counting.
- `short_text`, `dispersion_reliable`, `notes`: when to switch to the reduced
  check. Dispersion needs at least 80 words and 5 sentences.
- `sentence_length`: `mean`, `sd`, `cv` (SD divided by mean, comparable across
  texts), `median`, `min`, `max`, `share_under_8`, `share_over_30`.
- `lexical.<category>`: `tier`, `hits`, `per_100_words`, and `positions`
  (matched words, sentence and paragraph number, character offset). Positions
  are capped by `--max-positions`; `truncated: true` means more exist.
- `nominal_style`: capitalised words with a nominal suffix (-ung, -heit,
  -keit, -ion, -ität, -ismus, -nis), per 100 words, with the ten most frequent.
- `figures`: candidates for triads (also bare three-item fragments),
  „nicht X, sondern Y“ (also split across sentences: „Es geht nicht um X. Es
  geht um Y.“, „Wir bauen keine X. Wir bauen Y.“) and „nicht nur … sondern
  auch“. Candidates only: read each one in context.
- `openings`: paragraph openings that repeat, and sentence-initial words that
  open at least a quarter of all sentences.
- `dashes.counts`: `spaced_en_dash` (standard, ignore), `unspaced_en_dash`,
  `number_range` (10–20, ignore), `spaced_em_dash`, `unspaced_em_dash` (the
  weak hint), `spaced_hyphen` (typewriter substitute, ignore).
- `clusters`: windows of three consecutive sentences with at least 3 hits
  from at least 2 categories, merged where they overlap. This is the field
  that most directly answers "is there a pile-up, and where?".
- `tier_hits_per_100_words`: all hits summed by tier.
- `substance_hints`: digit tokens and first-person pronouns. Prompts for the
  own-substance question, never a score.

## Orientation values

These are own rules of thumb, not validated thresholds. Use them to phrase a
finding, never as a cut-off that decides the Ampel by itself.

- Sentence-length CV under about 0.30, with at least 5 sentences and no
  sentence under 8 or over 30 words: gleichförmig, a strong signal. Above
  about 0.45: variabel. In between: unremarkable.
- Medium-tier list hits above about 3 per 100 words, or strong-tier list hits
  (Lehrbuchvokabular plus Lehnmuster) above about 2 per 100 words: dense.
- Nominal style above about 8 per 100 words is heavy for a post, mail or
  application; academic and legal German often runs higher by nature.
- One unspaced em dash means nothing; several per paragraph together with
  other clusters are a weak hint.

## List categories

- `floskeln` (medium): connectors and filler whose removal changes nothing
  („darüber hinaus“, „zudem“, „letztlich“, „in der heutigen Zeit“,
  „zusammenfassend lässt sich sagen“). Test: does the sentence say the same
  without it?
- `lehrbuchvokabular` (strong): elevated all-purpose adjectives („fundiert“,
  „ganzheitlich“, „maßgeblich“, „vielschichtig“, „zukunftsweisend“). Not
  wrong, just conspicuously frequent; replace with an everyday word or cut.
- `abstrakte_substantive` (medium): „Ansätze“, „Möglichkeiten“, „Aspekte“,
  „Faktoren“, „Lösungen“, „Herausforderungen“, „Mehrwert“. Ask „Welche denn
  konkret?“. Exempt in scientific, legal and theoretical texts.
- `signifikanz` (medium): asserted rather than shown importance („wichtiger
  denn je“, „eine zentrale Rolle“, „Meilenstein“, „Gamechanger“,
  „unterstreicht“).
- `lehnmuster` (strong): calques and translated English style words („macht
  Sinn“, „am Ende des Tages“, „einen Unterschied machen“, „eintauchen in“,
  „nahtlos“, „-landschaft“, „auf dieser Reise“, „in 2025“, „Das Beste
  daran?“).

False positives to expect: „Bereich“ and „Lösung“ inside compounds,
„Landschaft“ in a text about landscapes, „Reise“ in a travel post, „zudem“ in
a legal brief. That is why hits are candidates and only clusters count.

## Deliberately not measured

- **Lexical variety** (type-token ratio and the like). Low variety is exactly
  what makes detectors flag non-native writers (Liang et al. 2023); measuring
  it would punish plain language.
- **Typos.** "No typos means AI" is folklore; spell-checkers have existed for
  decades.
- **A target sentence length.** Only dispersion is evidence-backed.

## Re-curating the list

1. Edit `assets/marker_lists.json`. Its `format` key states the syntax: an
   entry matches a whole word or phrase case-insensitively; `*` at the end
   allows word endings, `*` at the start allows prefixes; `re:` starts a
   Python regex.
2. Keep each entry in exactly one category, and prefer durable patterns over
   single fashionable words.
3. Update `stand` and `naechste_pruefung` in the JSON and the as-of paragraph
   above.
4. Run the tests next to the script (`python3 -m pytest scripts/`); one test
   rejects an entry listed in two categories.
