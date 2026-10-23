"""Deterministic fictional cases; no scoring engine or personal data dependency."""

from datetime import date, timedelta
from random import Random

SEED = 20261023
AS_OF = "2026-10-23"
# Job wording and professional evidence deliberately use different sentences.
DOMAINS = [
    (
        "backend",
        "Backend developer",
        "Computer Science",
        ["Python", "Django", "SQL", "Docker", "REST APIs", "Git"],
        "Deliver reliable server endpoints and relational storage for customer products.",
        "Maintained order services, investigated slow queries and added regression tests.",
        "Implemented checkout endpoints and improved database migrations for a local retailer.",
    ),
    (
        "frontend",
        "Frontend developer",
        "Computer Science",
        ["JavaScript", "HTML", "CSS", "React", "Git", "accessibility"],
        "Turn interface designs into accessible browser experiences across screen sizes.",
        "Rebuilt navigation, checked keyboard access and reduced layout shifts on mobile.",
        "Created reusable interface components and fixed browser compatibility defects.",
    ),
    (
        "data",
        "Data analyst",
        "Statistics",
        ["SQL", "Python", "Microsoft Excel", "Power BI", "statistics", "data analysis"],
        "Produce dependable business reporting from operational datasets.",
        "Reconciled weekly sales extracts and explained unusual trends to branch managers.",
        "Cleaned survey records, documented quality checks and published regional dashboards.",
    ),
    (
        "support",
        "IT support specialist",
        "Information Technology",
        [
            "technical support",
            "network administration",
            "Windows",
            "Linux",
            "customer service",
            "troubleshooting",
        ],
        "Resolve user incidents and keep office devices and networks operational.",
        "Diagnosed failed connections, maintained device inventories and supported new staff.",
        "Restored workstation access and documented repeat incident resolutions.",
    ),
    (
        "project",
        "Project coordinator",
        "Business Administration",
        [
            "project management",
            "communication",
            "budgeting",
            "risk management",
            "Microsoft Excel",
            "Agile",
        ],
        "Coordinate delivery plans, budgets, stakeholders and project risks.",
        "Tracked milestones, facilitated planning sessions and escalated supplier delays.",
        "Prepared cost forecasts and coordinated field teams against agreed delivery dates.",
    ),
    (
        "accounting",
        "Accounts officer",
        "Accounting",
        [
            "accounting",
            "bookkeeping",
            "Microsoft Excel",
            "payroll",
            "financial reporting",
            "QuickBooks",
        ],
        "Maintain accurate ledgers and support monthly financial close.",
        "Matched bank entries to invoices and reconciled supplier balances each month.",
        "Prepared payroll schedules and checked supporting documents for expense claims.",
    ),
    (
        "marketing",
        "Digital marketing specialist",
        "Marketing",
        [
            "digital marketing",
            "SEO",
            "copywriting",
            "social media marketing",
            "data analysis",
            "communication",
        ],
        "Plan measurable campaigns and improve customer acquisition through digital channels.",
        "Tested campaign messages, reviewed conversion reports and adjusted audience segments.",
        "Wrote landing page copy and managed search campaigns for a small hospitality business.",
    ),
    (
        "design",
        "Graphic designer",
        "Design",
        [
            "graphic design",
            "Adobe Photoshop",
            "Adobe Illustrator",
            "Figma",
            "typography",
            "communication",
        ],
        "Create consistent visual assets for print and digital communication.",
        "Produced publication layouts and prepared brand assets for different print formats.",
        "Refined visual concepts with clients and delivered reusable digital design files.",
    ),
    (
        "hr",
        "Human resources officer",
        "Human Resource Management",
        [
            "recruitment",
            "human resources",
            "payroll",
            "communication",
            "employee relations",
            "Microsoft Excel",
        ],
        "Support fair recruitment, accurate staff records and employee relations.",
        "Coordinated interview schedules, checked onboarding documents and maintained leave records.",
        "Prepared induction materials and helped resolve staff attendance queries.",
    ),
    (
        "operations",
        "Operations coordinator",
        "Supply Chain Management",
        [
            "inventory management",
            "logistics",
            "procurement",
            "Microsoft Excel",
            "communication",
            "budgeting",
        ],
        "Coordinate purchasing, stock control and timely movement of supplies.",
        "Compared supplier quotations, tracked deliveries and reconciled warehouse stock counts.",
        "Planned replenishment schedules and investigated missing delivery documentation.",
    ),
]
ALIASES = {
    "Python": "Python (computer programming)",
    "JavaScript": "JavaScript (computer programming)",
    "Microsoft Excel": "Excel",
}
VARIANTS = [
    "experienced",
    "paraphrased",
    "specialist",
    "junior",
    "partial",
    "career_change",
    "sparse",
    "keyword_decoy",
    "alias",
    "unknown_skill",
]


def build_dataset():
    rng = Random(SEED)
    jobs, profiles = [], []
    for domain, title, field, skills, job_text, evidence_a, evidence_b in DOMAINS:
        for level, years in enumerate((0, 2, 4, 1)):
            selected = skills[:3] + [skills[3 + level % 3]]
            jobs.append(
                {
                    "id": f"{domain}-job-{level + 1}",
                    "domain": domain,
                    "level": level,
                    "split": "holdout" if level == 2 else "development",
                    "requirements": {
                        "title": f"{('Junior ', '', 'Senior ', 'Associate ')[level]}{title}",
                        "company": f"Evaluation Organisation {len(jobs) + 1:02d}",
                        "description": job_text,
                        "requirements": (
                            "Support supervised delivery and document your work."
                            if years == 0
                            else "Own assigned deliverables and explain decisions to colleagues."
                        ),
                        "education_level": "any" if level in (0, 3) else "bachelors",
                        "education_level_label": (
                            "Any qualification"
                            if level in (0, 3)
                            else "Bachelor's degree"
                        ),
                        "education_field": "" if level in (0, 3) else field,
                        "education_priority": 1,
                        "minimum_experience_years": str(years),
                        "experience_details": job_text,
                        "experience_priority": 1 + level % 2,
                        "skills": [
                            {
                                "name": skill,
                                "requirement": "required" if n < 3 else "preferred",
                                "priority": 3 if n == level % 3 else 2,
                            }
                            for n, skill in enumerate(selected)
                        ],
                    },
                }
            )
        for index in range(20):
            variant = VARIANTS[index % len(VARIANTS)]
            years = (5, 3, 7, 0, 1, 4, 0, 6, 3, 2)[index % 10] + index // 10
            selection = rng.sample(skills, (6, 5, 4, 3, 2, 2, 1, 6, 5, 3)[index % 10])
            if variant == "alias":
                selection = [ALIASES.get(skill, skill) for skill in selection]
            if variant == "unknown_skill":
                selection.append(f"Regional {domain} toolkit")
            text = evidence_a if index < 10 else evidence_b
            if variant == "career_change":
                text = "Moving from shop administration into this field; completed introductory exercises."
            if variant == "keyword_decoy":
                text = "Sold training subscriptions about these subjects; did not perform the technical or professional work."
            if variant == "junior":
                text = "Completed supervised coursework and a small personal practice assignment."
            snapshot = {
                "profile": {
                    "headline": title,
                    "summary": "" if variant == "sparse" else text,
                },
                "skills": [{"name": skill} for skill in selection],
                "education": (
                    []
                    if variant in ("sparse", "career_change")
                    else [
                        {
                            "qualification": (
                                "Diploma"
                                if variant == "junior"
                                else "Bachelor's degree"
                            ),
                            "field_of_study": field,
                        }
                    ]
                ),
                "certifications": (
                    [{"name": f"Practical {field} training"}] if index % 4 == 0 else []
                ),
                "experience": (
                    []
                    if years == 0 or variant == "sparse"
                    else [
                        {
                            "job_title": (
                                "Sales representative"
                                if variant == "keyword_decoy"
                                else title
                            ),
                            "description": text,
                            "start_date": f"{2026 - years}-01-01",
                            "end_date": "2026-01-01",
                            "currently_working": False,
                        }
                    ]
                ),
            }
            profiles.append(
                {
                    "id": f"{domain}-profile-{index + 1:02d}",
                    "domain": domain,
                    "variant": variant,
                    "years": years,
                    "split": "holdout" if index >= 14 else "development",
                    "location": ("Nairobi", "Mombasa", "Kisumu")[index % 3],
                    "snapshot": snapshot,
                }
            )

    labels = []
    for job in jobs:
        for profile in profiles:
            same = job["domain"] == profile["domain"]
            if not same:
                shared = {s["name"] for s in job["requirements"]["skills"]} & {
                    s["name"] for s in profile["snapshot"]["skills"]
                }
                grade = 1 if shared else 0
                reason = (
                    "Different professional field; some transferable skills."
                    if shared
                    else "Different professional field with insufficient supporting evidence."
                )
            elif profile["variant"] in ("keyword_decoy", "sparse", "career_change"):
                grade, reason = (
                    1,
                    "Relevant terms but limited or unrelated evidence of performing the work.",
                )
            elif profile["variant"] in ("partial", "junior", "unknown_skill"):
                grade = 2 if job["level"] in (0, 3) else 1
                reason = "Developing evidence; plausible for supervised work, gaps for more demanding roles."
            else:
                grade = (
                    3
                    if profile["years"]
                    >= int(job["requirements"]["minimum_experience_years"])
                    else 2
                )
                reason = "Relevant professional evidence; compare experience and specialisation manually."
            labels.append(
                {
                    "job_id": job["id"],
                    "profile_id": profile["id"],
                    "grade": grade,
                    "rationale": reason,
                }
            )

    freelancers = []
    for domain_index, domain in enumerate(DOMAINS):
        domain_profiles = [p for p in profiles if p["domain"] == domain[0]]
        for index, profile in enumerate(
            domain_profiles[n] for n in (0, 1, 2, 3, 8, 15)
        ):
            freelancers.append(
                {
                    "id": f"worker-{domain_index + 1:02d}-{index + 1}",
                    "profile_id": profile["id"],
                    "domain": domain[0],
                    "title": domain[1],
                    "location": profile["location"],
                    "work_mode": ("flexible", "remote", "on_site")[index % 3],
                    "rate": str((800, 1500, 3000, 500, 25000, 2000)[index]),
                    "rate_unit": ("day", "day", "project", "hour", "project", "day")[
                        index
                    ],
                    "accepting_bookings": index != 4,
                    "share_professional_profile": True,
                    "available_from": (
                        date.fromisoformat(AS_OF)
                        + timedelta(days=40 if index == 5 else 0)
                    ).isoformat(),
                    "busy": index == 2,
                    "ratings": ([], [5], [4, 4, 5], [2, 3, 2, 4], [5, 5], [4] * 8)[
                        index
                    ],
                    "hidden_rating": 1 if index == 0 else None,
                }
            )
    projects = []
    for domain_index, domain in enumerate(DOMAINS):
        for index in range(2):
            projects.append(
                {
                    "id": f"{domain[0]}-project-{index + 1}",
                    "domain": domain[0],
                    "title": f"{domain[1]} assignment {index + 1}",
                    "description": domain[4],
                    "skills": domain[3][:3] if index == 0 else domain[3][2:5],
                    "location": "Nairobi",
                    "work_mode": "flexible" if index == 0 else "on_site",
                    "budget": "10000" if index == 0 else "5000",
                    "start_date": "2026-11-02",
                    "end_date": "2026-11-06",
                }
            )
    freelance_labels = []
    for project in projects:
        for worker in freelancers:
            profile = next(p for p in profiles if p["id"] == worker["profile_id"])
            reasons = []
            if not worker["accepting_bookings"]:
                reasons.append("not accepting bookings")
            if worker["available_from"] > project["start_date"] or worker["busy"]:
                reasons.append("unavailable for the dates")
            if project["work_mode"] == "on_site" and (
                worker["work_mode"] == "remote"
                or worker["location"] != project["location"]
            ):
                reasons.append("on-site arrangement incompatible")
            if worker["rate_unit"] == "project" and int(worker["rate"]) > int(
                project["budget"]
            ):
                reasons.append("project rate exceeds budget")
            if worker["rate_unit"] == "day" and int(worker["rate"]) * 5 > int(
                project["budget"]
            ):
                reasons.append("daily cost exceeds budget")
            if reasons:
                grade, reason = 0, "; ".join(reasons)
            elif project["domain"] != worker["domain"]:
                grade, reason = (
                    0,
                    "Different professional specialisation despite possible shared generic skills.",
                )
            else:
                grade = (
                    3
                    if profile["variant"]
                    in ("experienced", "paraphrased", "specialist", "alias")
                    else 2
                )
                reason = (
                    "Relevant service; review evidence and agree scope. Hourly total needs an agreed hour estimate."
                    if worker["rate_unit"] == "hour"
                    else "Relevant service and compatible logistics; review scope and evidence."
                )
            freelance_labels.append(
                {
                    "job_id": project["id"],
                    "profile_id": worker["id"],
                    "grade": grade,
                    "rationale": reason,
                }
            )
    return {
        "version": "synthetic-v2",
        "seed": SEED,
        "as_of": AS_OF,
        "purpose": "Expanded synthetic engineering evaluation; not hiring accuracy or independent human judgement.",
        "label_status": "Designed expectations frozen before scoring; independent review pending.",
        "rubric": {
            "0": "Unrelated or ineligible",
            "1": "Weak/transferable evidence",
            "2": "Plausible with gaps",
            "3": "Strong supporting evidence",
        },
        "jobs": jobs,
        "profiles": profiles,
        "labels": labels,
        "freelancers": freelancers,
        "projects": projects,
        "freelance_labels": freelance_labels,
    }
