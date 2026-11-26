"""Server-side checks for the signup form."""

import re

USERNAME_MAX = 32
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


def username_error(username: str) -> str | None:
    if len(username) > USERNAME_MAX:
        return "too long"
    if not USERNAME_PATTERN.match(username):
        return "only lowercase letters, digits and _"
    return None
