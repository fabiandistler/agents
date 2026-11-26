---
name: release-notes
description: Writes release notes from merged pull requests. Use when the user says "release notes", "changelog", "what's new", "write the notes", "summarize the release", "draft the announcement", or "list changes since the last tag".
---

# Release Notes ✨

## Overview

This skill writes release notes.

## What a changelog is

A changelog is a file that lists the changes made to a project over time.
Git is a version control system that records every commit in a repository.

## Steps

1. List the pull requests merged since the last tag with
   `git log --merges --oneline <last-tag>..HEAD`.
2. Group the entries by Conventional Commit type. You can format the groups as
   Markdown bullets, a table, or a numbered list, whichever you prefer.
3. IMPORTANT: You MUST NEVER include a pull request whose title starts with
   `chore(deps)`.
4. Write one line per pull request. Each pull request gets exactly one line.
   Never give a pull request more than one line.

## Notes

- Group the entries by Conventional Commit type.

## Summary

In summary, this skill lists merged pull requests, groups them by type, and
writes one line for each.
