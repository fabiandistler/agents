# German Headings in the Release PR Body

`release-pr` writes its pull request body in English — the `## Release`
heading, `**Bump:**`, `### Changes`, `### Checks run`, `### Not verified here`
and `### After merge` — even though `pr-description` writes every other PR body
in German. This project keeps it that way.

## Why this is out of scope

**The body is built around an English changelog.** `### Changes` is the
NEWS.md or CHANGELOG.md section pasted verbatim, and those files are English.
German headings around it would make one body in two languages, and translating
the changelog itself is out of the question: it is the package's public record.

**The release body travels with English artifacts.** The `tag` step publishes
the release notes from the same changelog section, and the PR title is
`<package> X.Y.Z`. An English body reads as one piece with both.

**Release PRs face a wider audience than review PRs.** `pr-description`
serves internal review, where German fits the readers. A release PR is where a
package meets its users — CRAN, r-universe, PyPI — who are not assumed to read
German.

The split is deliberate, not an oversight: ADR-0009 kept `release-pr` unchanged
when `pr-description` went German, and `pr-description` routes release PRs to
`release-pr`.

## Prior requests

- #519: "release-pr: write the release PR body headings in German"
