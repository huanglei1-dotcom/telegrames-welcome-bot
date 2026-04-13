from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

USERNAME_PATTERN = re.compile(r"@([A-Za-z0-9_]{5,32})")
HASHTAG_PATTERN = re.compile(r"#insta360recomendado\b", re.IGNORECASE)


@dataclass
class ParsedSubmission:
    inviter_username: Optional[str]
    hashtag_present: bool
    parse_valid: bool


def parse_submission_text(text: str) -> ParsedSubmission:
    username_match = USERNAME_PATTERN.search(text)
    hashtag_present = HASHTAG_PATTERN.search(text) is not None
    inviter_username = username_match.group(1).lower() if username_match else None
    parse_valid = inviter_username is not None and hashtag_present
    return ParsedSubmission(
        inviter_username=inviter_username,
        hashtag_present=hashtag_present,
        parse_valid=parse_valid,
    )
