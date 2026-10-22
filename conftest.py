"""Shared pytest setup for every test under scripts/ and skills/."""

import os

pytest_plugins = ["pytester"]

# Git exports these to hooks. From a linked worktree GIT_DIR is absolute, so a
# test's `git init` / `git config` in a tmp dir would act on the real repo
# instead (core.bare=true, a test user.name in the shared .git/config).
GIT_REPO_LOCATING_VARS = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def pytest_configure(config):
    # Process-wide before collection, not a function-scoped fixture, so
    # session fixtures and import-time code are covered too.
    for var in GIT_REPO_LOCATING_VARS:
        os.environ.pop(var, None)
