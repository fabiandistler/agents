# Forge-Specific Rules in `pr-description`

`pr-description` writes the same German title and body on every forge —
GitHub, Azure DevOps, GitLab or any other. It never inspects the remote URL and
carries no forge-conditional rule: no length cap or shortening order, no
work-item syntax, no Mermaid subset per forge, no printed `az` or other CLI
line. This project keeps it that way.

## Why this is out of scope

**Every rule the agent loads costs context and invites mistakes.** The Azure
DevOps branch was loaded on every run but applied on few, and an agent that
classifies the forge can take the wrong branch or print a remote URL that
carries a token.

**The removed rules rested on unverified facts.** Microsoft does not document
the 4,000-character description cap the skill enforced, and Mermaid rendering
on Azure DevOps Server was never confirmed. Rules built on guesses are worse
than none.

**The neutral body already works everywhere.** `Closes #<n>` is harmless text
where the forge does not act on it, and Mermaid written as `graph TD` /
`graph LR` without HTML in labels renders on GitHub and Azure DevOps alike. On
Azure DevOps the user links work items when opening the PR; the skill only
writes a file and never opens the PR anyway.

The removal is recorded as an amendment to ADR-0009, which first added the
forge rules. `release-pr` keeps its own forge handling: it opens and tags
releases, so the forge is part of its job.

## What would reopen it

A documented, recurring failure on a specific forge: the same neutral body
demonstrably breaking or being rejected there, more than once, with the
evidence linked in the request.

## Prior requests

- #528: "pr-description: forge-agnostic and leaner" (removal)
