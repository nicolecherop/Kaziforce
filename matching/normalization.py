"""Conservative label normalization; technical punctuation remains significant."""

import unicodedata

NORMALIZATION_VERSION = "labels-v1"


def normalize_skill(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
