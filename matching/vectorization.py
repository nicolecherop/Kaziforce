"""Small, deterministic TF-IDF implementation over a frozen public corpus."""

from collections import Counter
from hashlib import sha256
import json
import math
import re
import unicodedata

TOKENIZER_VERSION = "technical-tokens-v1"
# Preserve technical tokens such as C++, C#, .NET and node.js.
TOKEN = re.compile(r"\.?[^\W_]+(?:[.+#-][^\W_]+|\+\+|#)*", re.UNICODE)
STOP_WORDS = frozenset(
    "a an and are as at be been being by for from has have in into is it of on or our that the their this to was were will with you your".split()
)


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def tokens(text):
    return [
        term
        for term in TOKEN.findall(unicodedata.normalize("NFKC", text).casefold())
        if term not in STOP_WORDS and not term.isdecimal()
    ]


def document_frequencies(documents):
    frequencies, count = Counter(), 0
    for document in documents:
        frequencies.update(set(tokens(document)))
        count += 1
    return count, dict(sorted(frequencies.items()))


def vector(text, frequencies, document_count):
    """Sublinear TF, smoothed IDF, fixed vocabulary and L2 normalization."""
    values = {
        term: (1 + math.log(count))
        * (math.log((1 + document_count) / (1 + frequencies[term])) + 1)
        for term, count in Counter(tokens(text)).items()
        if term in frequencies
    }
    norm = math.sqrt(math.fsum(value * value for value in values.values()))
    return (
        {term: value / norm for term, value in sorted(values.items())} if norm else {}
    )


def cosine(left, right, frequencies, document_count):
    first, second = vector(left, frequencies, document_count), vector(
        right, frequencies, document_count
    )
    similarity = math.fsum(value * second.get(term, 0) for term, value in first.items())
    return max(0.0, min(1.0, similarity))
