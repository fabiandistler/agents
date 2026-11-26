# Packing a claude.ai skill

The delivery of step 8 in `SKILL.md` for a folder outside any git work tree:
pack the rewritten folder for claude.ai with the packager of Anthropic's
`skill-creator`.

1. Ask for the path of the **old ZIP**, the export the folder was unpacked
   from, and record its `sha256sum`.
2. Copy `new_skill/` to `package/<name>/` in the run directory,
   `<name>` being the frontmatter `name`: the packager names the archive
   and its top folder after the folder it packs.
3. Find the installed packager, `<skill-creator>/scripts/package_skill.py`;
   it needs Python with PyYAML. In `<skill-creator>`, run
   `python -m scripts.package_skill <package-dir>/<name> <old-zip-dir>`.
   It validates the frontmatter and writes `<name>.skill`, a ZIP archive.
   If `<old-zip-dir>/<name>.skill` already exists, pass
   `<old-zip-dir>/improve-skill-<timestamp>` as the output directory so
   nothing is overwritten. A validation failure writes no archive: report the
   error as a D-finding and preserve the frontmatter byte for byte.
   If the packager is unavailable, say so. In both fallback cases deliver the
   updated folder for the author to zip by hand.
4. If the author no longer has the old ZIP, pack the snapshot the same way
   (staged as `<name>/`) into `<output-dir>/old/` as the way back.

Done when the new archive exists and the old ZIP's `sha256sum` is
unchanged. Print both archive paths and tell the author: upload the new
archive in claude.ai's skill settings by hand (rename it to `.zip` if the
upload asks for one; the format is the same); to roll back, upload the old
ZIP the same way.
