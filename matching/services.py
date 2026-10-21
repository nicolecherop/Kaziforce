"""Persist complete owner-scoped matching runs and reproducible result inputs."""

from django.db import transaction
from django.utils import timezone
from .corpus import active_corpus, reference_for, verify_corpus
from .inputs import collect_inputs, standardize_pairs
from .models import MatchResult, MatchRun
from .scoring import MatchingError, configuration, has_evidence, score_pair
from .vectorization import digest


def generate_matches(user, job=None):
    if (job is None and user.role != "candidate") or (
        job is not None and (user.role != "recruiter" or job.recruiter_id != user.pk)
    ):
        raise MatchingError("You cannot request matches for this workspace.")
    corpus = active_corpus()
    pairs, checksum, source = collect_inputs(user, job)
    if job is None and not has_evidence(source["profile"]):
        raise MatchingError(
            "Add professional information to your profile before requesting matches."
        )
    if not pairs:
        raise MatchingError(
            "No submitted applicants are available to rank."
            if job
            else "No new open jobs are available to match."
        )
    standardize_pairs(pairs, corpus.catalogue)
    as_of, config = timezone.localdate(), configuration()
    scored, unscored = [], []
    reference = reference_for(corpus)
    for pair in pairs:
        try:
            output = score_pair(pair["profile"], pair["job"], reference, as_of, config)
        except MatchingError as error:
            unscored.append((pair, {"unavailable": str(error)}))
        else:
            scored.append((pair, output))
    scored.sort(
        key=lambda item: (
            -item[1]["raw_score"],
            item[0]["application_id"] or item[0]["job_id"],
        )
    )
    with transaction.atomic():
        run = MatchRun.objects.create(
            owner=user,
            kind=MatchRun.Kind.APPLICANTS if job else MatchRun.Kind.JOBS,
            job=job,
            corpus=corpus,
            configuration=config,
            input_checksum=checksum,
            as_of=as_of,
        )
        results = [
            MatchResult(
                run=run,
                job_id=pair["job_id"],
                candidate_id=pair["candidate_id"],
                application_id=pair["application_id"],
                rank=rank,
                score=output["score"],
                input_snapshot=pair,
                input_checksum=digest(pair),
                components=output["components"],
                explanation=dict(output["explanation"], raw_score=output["raw_score"]),
            )
            for rank, (pair, output) in enumerate(scored, start=1)
        ]
        results.extend(
            MatchResult(
                run=run,
                job_id=pair["job_id"],
                candidate_id=pair["candidate_id"],
                application_id=pair["application_id"],
                input_snapshot=pair,
                input_checksum=digest(pair),
                explanation=reason,
            )
            for pair, reason in unscored
        )
        MatchResult.objects.bulk_create(results)
    return run


def run_is_current(run, user, job=None):
    if not run:
        return False
    try:
        corpus = active_corpus()
        _, checksum, _ = collect_inputs(user, job)
    except MatchingError:
        return False
    return (
        run.corpus_id == corpus.pk
        and run.input_checksum == checksum
        and run.as_of == timezone.localdate()
        and run.configuration == configuration()
    )


def replay_result(result):
    """Recalculate solely from stored inputs, corpus, date and configuration."""
    verify_corpus(result.run.corpus)
    if digest(result.input_snapshot) != result.input_checksum:
        raise MatchingError("The saved matching inputs failed their integrity check.")
    return score_pair(
        result.input_snapshot["profile"],
        result.input_snapshot["job"],
        reference_for(result.run.corpus),
        result.run.as_of,
        result.run.configuration,
    )
