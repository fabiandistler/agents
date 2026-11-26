# Slop signals

The fixed list of patterns that mark filler in a skill. Every signal has a
stable ID; a candidate cites it, and the skill audit checklist cites the same
IDs, so an audit finding and a cleanup candidate name one thing the same way.

The signals describe structure, not vocabulary: each one applies to a skill in
any language. The marker words in the examples are illustrations, not a word
list to search for.

## SL1 Explaining known things

Checklist: B2.

- **Shape:** a sentence or paragraph that defines a general concept the model
  already knows: what a file format, a tool, a protocol or a common practice
  is.
- **Test:** delete it in your head. If a capable model would act the same
  without it, it is slop. A definition specific to this skill's domain or
  project (a local term, a house convention) is not.
- **Action:** remove.

## SL2 Several wordings of one case

Checklist: B8.

- **Shape:** two or more adjacent sentences or examples that state the same
  constraint in different words, often a positive form followed by its
  negation.
- **Test:** does each wording add a condition, a limit or an exception the
  others lack? If not, all but one are slop.
- **Action:** keep the sharpest wording, remove the rest.

## SL3 Menu without a default

Checklist: B4.

- **Shape:** a list of equivalent options ("A, B or C", "whichever you
  prefer", "any of the following") with no option marked as the default.
- **Test:** does the choice change the outcome in a way the author cares
  about? If it does, the menu hides a decision; if not, it is noise.
- **Action:** name one default and, only where a real case needs it, the
  condition for the alternative.

## SL4 Shouting instead of a reason

Checklist: B9.

- **Shape:** capitals, stacked emphasis or alarm markers ("IMPORTANT",
  "CRITICAL", "MUST NEVER", bold warnings) carrying a rule without saying why
  it exists.
- **Test:** the rule under the shouting is usually load-bearing; the emphasis
  is the slop. Ask whether the author can name the failure the rule prevents.
- **Action:** keep the rule, state it plainly, and add its reason. Remove the
  rule only when the author confirms it is obsolete.

## SL5 Repeated rule

Checklist: B8 (within one skill); X3 covers the same rule in two skills.

- **Shape:** one rule stated in two sections of the skill, for example once
  in the steps and again under a notes or tips heading.
- **Test:** do both places say the same thing for the same case? If one adds
  a case, that addition is not a repeat.
- **Action:** keep the rule where the agent needs it while acting (usually
  the step), remove the other statement.

## SL6 Trigger list in the description

Checklist: D3.

- **Shape:** the frontmatter description enumerates phrases, synonyms or
  features ("use when the user says X, Y, Z, W…") instead of naming the
  distinct situations once.
- **Test:** does each item name a distinct branch the skill handles, or a
  synonym of another item?
- **Action:** report only. Descriptions are not rewritten here; the fix
  belongs to `skill-creator`'s description optimisation, which measures
  triggering.

## SL7 Decoration

Checklist: B10.

- **Shape:** headings that carry no content of their own (an "Overview" or
  "Introduction" that restates the title), emojis in headings or rules, and
  closing sections that summarise what the body already said.
- **Test:** remove the element. If no rule, step or pointer is lost, it is
  slop.
- **Action:** remove; merge a heading's one useful sentence into its
  neighbour.
