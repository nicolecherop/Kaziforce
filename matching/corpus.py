"""Build and verify a frozen TF-IDF reference from public ESCO text only."""

from django.db import transaction
from .models import MatchingCorpus, SkillCatalogue
from .scoring import MatchingError
from .vectorization import TOKENIZER_VERSION, digest, document_frequencies


def corpus_payload(catalogue, count, frequencies):
    return {
        "catalogue_checksum": catalogue.checksum,
        "catalogue_version": catalogue.version,
        "language": catalogue.language,
        "tokenizer_version": TOKENIZER_VERSION,
        "document_count": count,
        "document_frequencies": frequencies,
    }


def build_corpus():
    catalogue = SkillCatalogue.objects.filter(active=True).first()
    if not catalogue:
        raise MatchingError(
            "Import and activate a skill catalogue before building the matching reference."
        )
    documents = (
        f"{label} {description}"
        for label, description in catalogue.skills.order_by("uri")
        .values_list("preferred_label", "description")
        .iterator(chunk_size=500)
    )
    count, frequencies = document_frequencies(documents)
    if count != catalogue.skill_count or not frequencies:
        raise MatchingError(
            "The skill catalogue is incomplete. The matching reference was not built."
        )
    checksum = digest(corpus_payload(catalogue, count, frequencies))
    with transaction.atomic():
        corpus, created = MatchingCorpus.objects.get_or_create(
            catalogue=catalogue,
            tokenizer_version=TOKENIZER_VERSION,
            source_checksum=catalogue.checksum,
            defaults={
                "checksum": checksum,
                "document_count": count,
                "document_frequencies": frequencies,
            },
        )
        if corpus.checksum != checksum:
            raise MatchingError(
                "This reference version has changed. Preserve it and prepare a new catalogue version."
            )
    return corpus, created


def active_corpus():
    corpus = (
        MatchingCorpus.objects.select_related("catalogue")
        .filter(catalogue__active=True, tokenizer_version=TOKENIZER_VERSION)
        .first()
    )
    if not corpus or corpus.source_checksum != corpus.catalogue.checksum:
        raise MatchingError(
            "Matching is unavailable while the skill reference is being prepared. Please try again later."
        )
    verify_corpus(corpus)
    return corpus


def verify_corpus(corpus):
    if (
        corpus.tokenizer_version != TOKENIZER_VERSION
        or digest(
            corpus_payload(
                corpus.catalogue, corpus.document_count, corpus.document_frequencies
            )
        )
        != corpus.checksum
    ):
        raise MatchingError("The saved matching reference failed its integrity check.")


def reference_for(corpus):
    return {
        "document_count": corpus.document_count,
        "document_frequencies": corpus.document_frequencies,
    }
