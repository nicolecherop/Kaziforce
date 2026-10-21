"""HTTP workflow evidence using real views and CSRF, in the temporary database."""

from copy import deepcopy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from applications.models import Application
from candidates.models import CandidateDocument, CandidateProfile
from jobs.models import JobPosting
from matching.models import MatchResult
from matching.services import replay_result


def form_payload(response):
    """Read the server-rendered profile/application forms, including row IDs."""
    payload = {}
    forms = [response.context["form"]]
    if "application_form" in response.context:
        forms.append(response.context["application_form"])
    for form in forms:
        for field in form:
            value = field.value()
            if value not in (None, False, ""):
                payload[field.name] = "on" if value is True else value
    for section in response.context["sections"]:
        formset, prefix = section["formset"], section["prefix"]
        payload[f"{prefix}-TOTAL_FORMS"] = str(formset.total_form_count())
        payload[f"{prefix}-INITIAL_FORMS"] = str(formset.initial_form_count())
        for index, form in enumerate(formset):
            for field in form:
                value = field.value()
                if value not in (None, False, ""):
                    payload[f"{prefix}-{index}-{field.name}"] = (
                        "on" if value is True else value
                    )
    return payload


def run_workflows(dataset, checks):
    def check(name, condition, evidence):
        checks.append({"name": name, "passed": bool(condition), "evidence": evidence})
        if not condition:
            raise AssertionError(name)

    def post(client, url, payload):
        token = client.cookies["csrftoken"].value
        return client.post(url, {**payload, "csrfmiddlewaretoken": token})

    def register(role, label):
        client = Client(enforce_csrf_checks=True)
        url = reverse("accounts:create_account")
        client.get(url)
        password = "Fictional-test-only!72-river"
        response = post(
            client,
            url,
            {
                "full_name": f"Evaluation {label}",
                "email": f"{label}@example.test",
                "role": role,
                "password1": password,
                "password2": password,
                "accept_terms": "on",
                "is_staff": "true",
                "is_superuser": "true",
            },
        )
        user = get_user_model().objects.filter(email=f"{label}@example.test").first()
        check(
            f"Register {label} through public form",
            response.status_code == 302
            and user is not None
            and user.role == role
            and not user.is_staff
            and not user.is_superuser,
            "Actual registration view; privilege fields ignored.",
        )
        client.get(reverse("accounts:dashboard"))
        post(client, reverse("accounts:sign_out"), {})
        client.get(reverse("accounts:sign_in"))
        response = post(
            client,
            reverse("accounts:sign_in"),
            {"username": user.email, "password": password},
        )
        check(
            f"Sign in {label} with email",
            response.status_code == 302
            and int(client.session["_auth_user_id"]) == user.pk,
            "Actual login view with CSRF enforcement.",
        )
        return client, user

    candidate_client, candidate = register("candidate", "candidate")
    recruiter_client, recruiter = register("recruiter", "recruiter")
    other_candidate_client, other_candidate = register("candidate", "other-candidate")
    other_recruiter_client, _ = register("recruiter", "other-recruiter")

    job_url = reverse("jobs:create")
    recruiter_client.get(job_url)
    requirements = dataset["jobs"][0]["requirements"]
    job_payload = {
        key: value
        for key, value in requirements.items()
        if key not in ("skills", "education_level_label")
    }
    job_payload["location"] = "Nairobi"
    job_payload["minimum_experience_years"] = "2.0"
    job_payload["skills-TOTAL_FORMS"] = str(len(requirements["skills"]))
    job_payload["skills-INITIAL_FORMS"] = "0"
    for index, skill in enumerate(requirements["skills"]):
        job_payload.update(
            {f"skills-{index}-{key}": value for key, value in skill.items()}
        )
    response = post(recruiter_client, job_url, job_payload)
    job = JobPosting.objects.filter(recruiter=recruiter).first()
    check(
        "Publish a job with structured priorities",
        response.status_code == 302
        and job is not None
        and job.skills.count() == 4
        and job.minimum_experience_years == Decimal("2"),
        "Real job form and skill formset; four requirements saved.",
    )

    profile_url = reverse("candidates:profile_edit")
    candidate_client.get(profile_url)
    snapshot = deepcopy(dataset["profiles"][0]["snapshot"])
    snapshot["profile"]["location"] = "Nairobi"
    snapshot["education"][0]["institution"] = "Fictional College"
    snapshot["certifications"][0]["issuer"] = "Fictional Training Studio"
    snapshot["experience"][0]["company"] = "Fictional Former Employer"
    snapshot["portfolio"] = [
        {"title": "Work samples", "url": "https://example.test/portfolio"}
    ]
    payload = dict(snapshot["profile"])
    for section in ("skills", "education", "certifications", "experience", "portfolio"):
        rows = snapshot[section]
        payload[f"{section}-TOTAL_FORMS"] = str(len(rows))
        payload[f"{section}-INITIAL_FORMS"] = "0"
        for index, row in enumerate(rows):
            for key, value in row.items():
                if value not in (None, False, ""):
                    payload[f"{section}-{index}-{key}"] = (
                        "on" if value is True else value
                    )
    response = post(candidate_client, profile_url, payload)
    profile = CandidateProfile.objects.filter(user=candidate).first()
    check(
        "Save all manual professional profile sections",
        response.status_code == 302
        and profile is not None
        and all(
            getattr(profile, section).exists()
            for section in (
                "skills",
                "education",
                "certifications",
                "experience",
                "portfolio_links",
            )
        ),
        "Skills, education, certification, experience and portfolio entered through HTTP forms.",
    )

    documents_url = reverse("candidates:documents")
    candidate_client.get(documents_url)
    for kind in ("cv", "degree", "certificate"):
        response = post(
            candidate_client,
            documents_url,
            {
                "kind": kind,
                "title": f"Fictional {kind}",
                "file": SimpleUploadedFile(
                    f"{kind}.pdf",
                    b"%PDF-1.7\nSynthetic signature fixture; no real personal data.\n",
                    content_type="application/pdf",
                ),
            },
        )
        check(
            f"Upload private {kind} without extraction",
            response.status_code == 302
            and CandidateDocument.objects.filter(user=candidate, kind=kind).exists(),
            "Signature fixture checks storage/access; not PDF rendering or qualification verification.",
        )
    documents = list(CandidateDocument.objects.filter(user=candidate))
    original_url = reverse("candidates:document_file", args=[documents[0].pk])
    response = candidate_client.get(original_url)
    original_bytes = b"".join(response.streaming_content)
    response.close()
    check(
        "Original document is private",
        other_candidate_client.get(original_url).status_code == 404
        and recruiter_client.get(original_url).status_code == 403
        and bool(original_bytes),
        "Only the candidate can access the original document library.",
    )
    candidate_client.get(reverse("matches:jobs"))
    response = post(candidate_client, reverse("matches:refresh_jobs"), {})
    recommendation = MatchResult.objects.filter(run__owner=candidate, job=job).first()
    check(
        "Candidate requests a saved job recommendation",
        response.status_code == 302
        and recommendation is not None
        and recommendation.score is not None,
        "Actual refresh endpoint, full ESCO reference and persisted explanation.",
    )

    edit_url = reverse("applications:edit", args=[job.pk])
    response = candidate_client.get(edit_url)
    payload = form_payload(response)
    payload.update(
        headline="Tailored backend application",
        cover_letter="Please review my manual profile and attached evidence.",
        documents=[str(document.pk) for document in documents],
        action="draft",
    )
    response = post(candidate_client, edit_url, payload)
    application = Application.objects.filter(candidate=candidate, job=job).first()
    check(
        "Save an independent tailored draft",
        response.status_code == 302
        and application is not None
        and application.status == "draft"
        and application.profile_snapshot["profile"]["headline"]
        == "Tailored backend application"
        and profile.headline != "Tailored backend application",
        "Tailoring leaves the saved professional profile intact.",
    )
    detail_url = reverse("applications:detail", args=[application.pk])
    check(
        "Recruiter cannot read a draft",
        recruiter_client.get(detail_url).status_code == 404,
        "Draft is absent from recruiter-accessible applications.",
    )
    payload = form_payload(candidate_client.get(edit_url))
    payload["action"] = "submit"
    response = post(candidate_client, edit_url, payload)
    application.refresh_from_db()
    frozen_snapshot = deepcopy(application.profile_snapshot)
    check(
        "Submit an application with three independent attachments",
        response.status_code == 302
        and application.status == "submitted"
        and application.attachments.count() == 3
        and application.submitted_at is not None,
        "Submission preserves the tailored profile and document copies.",
    )
    check(
        "Owning recruiter can review; outsiders cannot",
        recruiter_client.get(detail_url).status_code == 200
        and other_recruiter_client.get(detail_url).status_code == 404
        and other_candidate_client.get(detail_url).status_code == 404,
        "Candidate ownership and recruiter job ownership enforced.",
    )

    payload = form_payload(candidate_client.get(profile_url))
    payload["headline"] = "Updated saved profile <script>example</script>"
    response = post(candidate_client, profile_url, payload)
    application.refresh_from_db()
    profile.refresh_from_db()
    check(
        "Editing main profile preserves submitted application",
        response.status_code == 302
        and application.profile_snapshot == frozen_snapshot
        and profile.headline.startswith("Updated saved profile"),
        "All professional sections retained; submitted snapshot unchanged.",
    )
    html = candidate_client.get(reverse("candidates:profile")).content.decode()
    check(
        "Profile text is HTML escaped",
        "&lt;script&gt;example&lt;/script&gt;" in html
        and "<script>example</script>" not in html,
        "Stored free text is rendered as text.",
    )
    response = post(
        candidate_client,
        edit_url,
        {"action": "submit", "headline": "Overwrite attempt"},
    )
    application.refresh_from_db()
    check(
        "Submitted application cannot be overwritten",
        response.status_code == 302 and application.profile_snapshot == frozen_snapshot,
        "Subsequent editing redirects to submitted detail.",
    )

    ranking_url = reverse("matches:applicants", args=[job.pk])
    recruiter_client.get(ranking_url)
    response = post(
        recruiter_client, reverse("matches:refresh_applicants", args=[job.pk]), {}
    )
    result = MatchResult.objects.filter(
        run__owner=recruiter, application=application
    ).first()
    check(
        "Recruiter ranks submitted evidence",
        response.status_code == 302
        and result is not None
        and result.input_snapshot["profile"]["profile"]["headline"]
        == "Tailored backend application",
        "Applicant ranking reads the submitted copy, not the later main profile.",
    )
    check(
        "Stored score replays exactly",
        replay_result(result)["score"] == result.score
        and replay_result(result)["raw_score"] == result.explanation["raw_score"],
        "Saved inputs, configuration, date and public reference reproduce the score.",
    )
    match_url = reverse("matches:detail", args=[result.pk])
    check(
        "Recruiter matching explanation is private",
        recruiter_client.get(match_url).status_code == 200
        and other_recruiter_client.get(match_url).status_code == 404,
        "Saved result is scoped to its requesting owner.",
    )
    attachment = application.attachments.first()
    attachment_url = reverse("applications:attachment_file", args=[attachment.pk])
    response = recruiter_client.get(attachment_url)
    copied_bytes = b"".join(response.streaming_content)
    response.close()
    check(
        "Shared attachment is readable only by application parties",
        copied_bytes == original_bytes
        and other_recruiter_client.get(attachment_url).status_code == 404
        and other_candidate_client.get(attachment_url).status_code == 404,
        "Original and submitted bytes match; outsiders denied.",
    )
    recruiter_client.get(detail_url)
    response = post(
        recruiter_client,
        reverse("applications:status", args=[application.pk]),
        {"status": "shortlisted"},
    )
    application.refresh_from_db()
    html = candidate_client.get(reverse("applications:mine")).content.decode()
    check(
        "Recruiter status update reaches candidate progress",
        response.status_code == 302
        and application.status == "shortlisted"
        and "Shortlisted" in html,
        "Candidate application list reflects recruiter decision.",
    )
    check(
        "CSRF-less state change is rejected",
        recruiter_client.post(
            reverse("applications:status", args=[application.pk]),
            {"status": "unsuccessful"},
        ).status_code
        == 403,
        "CSRF enforcement enabled for all workflow clients.",
    )
    recruiter_client.get(reverse("jobs:manage"))
    response = post(recruiter_client, reverse("jobs:close", args=[job.pk]), {})
    job.refresh_from_db()
    blocked = other_candidate_client.get(edit_url)
    check(
        "Closed job stops new applications",
        response.status_code == 302
        and job.status == "closed"
        and blocked.status_code == 302
        and not Application.objects.filter(candidate=other_candidate, job=job).exists(),
        "Existing submission remains readable; another candidate cannot start an application.",
    )

    # Render the main connected views with a populated workflow, not empty placeholders.
    pages = [
        (candidate_client, "accounts:dashboard", []),
        (candidate_client, "candidates:profile", []),
        (candidate_client, "jobs:opportunities", []),
        (candidate_client, "jobs:detail", [job.pk]),
        (candidate_client, "applications:mine", []),
        (candidate_client, "applications:detail", [application.pk]),
        (candidate_client, "matches:jobs", []),
        (candidate_client, "matches:detail", [recommendation.pk]),
        (recruiter_client, "accounts:dashboard", []),
        (recruiter_client, "jobs:manage", []),
        (recruiter_client, "jobs:edit", [job.pk]),
        (recruiter_client, "applications:inbox", []),
        (recruiter_client, "applications:applicants", [job.pk]),
        (recruiter_client, "matches:workspace", []),
        (recruiter_client, "matches:applicants", [job.pk]),
    ]
    statuses = [
        client.get(reverse(name, args=args), follow=True).status_code
        for client, name, args in pages
    ]
    check(
        "Connected workspace pages render successfully",
        all(code == 200 for code in statuses),
        {"pages": len(pages), "statuses_after_navigation_redirects": statuses},
    )
