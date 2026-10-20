"""Read the current candidate's profile with its associated professional records."""

from .models import CandidateProfile


def profile_for(user):
    return (
        CandidateProfile.objects.filter(user=user)
        .prefetch_related(
            "skills", "education", "certifications", "experience", "portfolio_links"
        )
        .first()
    )


def section_status(profile):
    return [
        {
            "label": "Professional summary",
            "anchor": "summary",
            "complete": bool(profile and (profile.headline or profile.summary)),
        },
        {
            "label": "Skills",
            "anchor": "skills",
            "complete": bool(profile and profile.skills.all()),
        },
        {
            "label": "Education",
            "anchor": "education",
            "complete": bool(profile and profile.education.all()),
        },
        {
            "label": "Certifications",
            "anchor": "certifications",
            "complete": bool(profile and profile.certifications.all()),
        },
        {
            "label": "Work experience",
            "anchor": "experience",
            "complete": bool(profile and profile.experience.all()),
        },
        {
            "label": "Portfolio links",
            "anchor": "portfolio",
            "complete": bool(profile and profile.portfolio_links.all()),
        },
    ]
