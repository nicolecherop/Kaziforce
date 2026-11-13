"""Conservative, section-aware CV suggestions, always reviewed before saving.

This is a local parser, not an AI service or a verification of qualifications.
Unclear information remains in source text instead of being invented.
"""

import calendar
import re
from datetime import date

HEADINGS = {
    "summary": (
        "summary",
        "professional summary",
        "profile",
        "personal profile",
        "about me",
        "career objective",
        "objective",
        "professional profile",
    ),
    "skills": (
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "core competencies",
        "competencies",
        "professional skills",
        "skills and competencies",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "employment",
        "career history",
        "work history",
        "internships",
    ),
    "education": (
        "education",
        "academic qualifications",
        "education and qualifications",
        "educational background",
        "academic background",
        "qualifications",
    ),
    "certifications": (
        "certifications",
        "certificates",
        "professional certifications",
        "certifications and training",
        "training and certifications",
        "licenses and certifications",
    ),
    "ignore": (
        "references",
        "referees",
        "interests",
        "hobbies",
        "languages",
        "projects",
        "publications",
        "awards",
        "personal details",
        "declaration",
    ),
}
HEADING_LOOKUP = {name: key for key, names in HEADINGS.items() for name in names}
MONTHS = {
    name.casefold(): index
    for index in range(1, 13)
    for name in (calendar.month_name[index], calendar.month_abbr[index])
}
MONTHS["sept"] = 9
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = rf"(?:\d{{4}}-\d{{2}}-\d{{2}}|{MONTH}\.?\s+\d{{4}}|(?:0?[1-9]|1[0-2])[/.-]\d{{4}}|(?:19|20)\d{{2}})"
PERIOD = re.compile(
    rf"(?<!\d)({DATE})\s*(?:-|–|—|\bto\b)\s*({DATE}|Present|Current|Now|Ongoing)(?!\w)",
    re.I,
)
QUALIFICATION = re.compile(
    r"\b(?:bachelor|master|doctor|diploma|degree|B\.?Sc\.?|M\.?Sc\.?|B\.?A\.?|M\.?A\.?|BCom|MBA|PhD|KCSE|KCPE|certificate)\b",
    re.I,
)
INSTITUTION = re.compile(
    r"\b(?:university|college|institute|school|academy|polytechnic)\b", re.I
)
ROLE = re.compile(
    r"\b(?:developer|engineer|analyst|designer|manager|consultant|assistant|officer|intern|accountant|specialist|coordinator|administrator|teacher|nurse|technician|director|researcher|writer|marketer|architect|receptionist|supervisor|freelancer|lead|chef|cook|driver|plumber|electrician|carpenter|mechanic|hairdresser|stylist|photographer|editor|translator|tutor|cashier|salesperson|cleaner|therapist|lawyer|advocate|doctor)\b",
    re.I,
)


def clean(value):
    return re.sub(r"\s+", " ", value).strip(" \t•●▪·|:-")


def split_sections(text):
    sections = {name: [] for name in ("header", *HEADINGS)}
    current = "header"
    for raw in text.splitlines():
        line = clean(raw)
        label, separator, rest = line.partition(":")
        key = HEADING_LOOKUP.get(label.casefold().replace("&", "and"))
        # "Languages: Python, SQL" is a category inside technical skills,
        # not a switch to the separate spoken-languages section.
        if current == "skills" and separator and label.casefold() == "languages":
            key = None
        if key:
            current = key
            if separator and rest.strip():
                sections[current].append(clean(rest))
        else:
            sections[current].append(line)
    return sections


def parse_date(value):
    value = re.sub(r"(?<=[a-zA-Z])\.", "", value.strip()).casefold()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        match = re.fullmatch(r"([a-z]+)\s+(\d{4})", value)
        if match and match[1] in MONTHS:
            return date(int(match[2]), MONTHS[match[1]], 1).isoformat()
        match = re.fullmatch(r"(\d{1,2})[/.\-](\d{4})", value)
        if match:
            return date(int(match[2]), int(match[1]), 1).isoformat()
    except ValueError:
        pass
    # A year alone does not establish the month or day.
    return ""


def period_values(match, current_field):
    current = match[2].casefold() in {"present", "current", "now", "ongoing"}
    return {
        "start_date": parse_date(match[1]),
        "end_date": "" if current else parse_date(match[2]),
        current_field: current,
    }


def skills_from(lines):
    seen, result = set(), []
    for line in lines:
        # Treat labels such as "Programming languages:" as category headings.
        line = line.split(":", 1)[-1]
        for name in re.split(r"[,;|•●▪\t]+", line):
            name = clean(name)
            if (
                not name
                or len(name) > 80
                or len(name.split()) > 8
                or name.endswith(".")
            ):
                continue
            if name.casefold() not in seen:
                seen.add(name.casefold())
                result.append({"name": name})
    return result[:60]


def experience_from(lines):
    lines = [line for line in lines if line]
    dated = [
        (index, PERIOD.search(line))
        for index, line in enumerate(lines)
        if PERIOD.search(line)
    ]
    result = []
    for number, (index, match) in enumerate(dated):
        previous = dated[number - 1][0] + 1 if number else 0
        prefix = clean(lines[index][: match.start()])
        suffix = clean(lines[index][match.end() :])
        inline = prefix or suffix
        headers = [inline] if inline else lines[max(previous, index - 2) : index]
        parts = [
            clean(part)
            for line in headers
            for part in re.split(r"\s*[|]\s*|\s+at\s+|\s+[-–—]\s+", line, flags=re.I)
            if clean(part)
        ]
        role_index = next(
            (
                i
                for i, part in enumerate(parts)
                if ROLE.search(part) and len(part) <= 160 and not part.endswith(".")
            ),
            None,
        )
        # A clearly delimited role/company header also supports professions
        # outside our common title vocabulary without inventing a title.
        if (
            role_index is None
            and len(headers) == 1
            and len(parts) == 2
            and all(len(part) <= 160 for part in parts)
        ):
            role_index = 0
        if role_index is None:
            continue
        title = parts[role_index]
        neighbours = parts[role_index + 1 :] or parts[:role_index]
        company = (
            neighbours[0]
            if neighbours
            and len(neighbours[0]) <= 160
            and not neighbours[0].endswith(".")
            else ""
        )
        end = dated[number + 1][0] if number + 1 < len(dated) else len(lines)
        description_lines = lines[index + 1 : end]
        # Do not absorb the next role's header into this role's responsibilities.
        if number + 1 < len(dated):
            for offset, line in enumerate(description_lines):
                if ROLE.search(line) and len(line) <= 160 and not line.endswith("."):
                    description_lines = description_lines[:offset]
                    break
        result.append(
            {
                "job_title": title,
                "company": company,
                "description": "\n".join(description_lines)[:2000],
                **period_values(match, "currently_working"),
            }
        )
    return result[:30]


def education_from(lines):
    lines = [line for line in lines if line]
    result = []
    used = set()
    for index, line in enumerate(lines):
        if not QUALIFICATION.search(line) or index in used:
            continue
        period = PERIOD.search(line)
        title_line = clean(PERIOD.sub("", line))
        parts = [
            clean(part)
            for part in re.split(r"\s*\|\s*|\s+at\s+|\s+[–—]\s+", title_line)
            if clean(part)
        ]
        qualification = next((part for part in parts if QUALIFICATION.search(part)), "")
        institution = next(
            (
                part
                for part in parts
                if part != qualification and INSTITUTION.search(part)
            ),
            "",
        )
        nearby = lines[max(0, index - 1) : index] + lines[index + 1 : index + 3]
        if not institution:
            institution = next(
                (
                    clean(PERIOD.sub("", item))
                    for item in nearby
                    if INSTITUTION.search(item) and not QUALIFICATION.search(item)
                ),
                "",
            )
        if not period:
            period = next(
                (
                    PERIOD.search(item)
                    for item in lines[index + 1 : index + 3]
                    if PERIOD.search(item)
                ),
                None,
            )
        result.append(
            {
                "qualification": qualification[:160],
                "institution": institution[:160],
                **(period_values(period, "currently_studying") if period else {}),
            }
        )
        used.add(index)
    return result[:30]


def certifications_from(lines):
    result = []
    pending = None
    for line in lines:
        if not line:
            continue
        if re.fullmatch(DATE, line, re.I):
            if pending:
                pending["issue_date"] = parse_date(line)
            continue
        if line.lower().startswith(("issuer:", "issued by:")) and pending:
            pending["issuer"] = clean(line.split(":", 1)[1])[:160]
            continue
        if line.lower().startswith(("issued:", "issue date:")) and pending:
            pending["issue_date"] = parse_date(line.split(":", 1)[1])
            continue
        if line.lower().startswith(("expires:", "expiry date:")) and pending:
            pending["expiry_date"] = parse_date(line.split(":", 1)[1])
            continue
        parts = re.split(r"\s*\|\s*|\s+[-–—]\s+|\s+issued by\s+", line, flags=re.I)
        if len(line) > 250 or line.endswith("."):
            continue
        pending = {
            "name": clean(parts[0])[:160],
            "issuer": clean(parts[1])[:160] if len(parts) > 1 else "",
        }
        result.append(pending)
    return result[:30]


def parse_cv(text):
    sections = split_sections(text)
    header = "\n".join(sections["header"])
    basic = {}
    email = re.search(
        r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", header, re.I
    )
    if email:
        basic["contact_email"] = email[0].rstrip(".")
    for line in sections["header"]:
        label, _, value = line.partition(":")
        if label.lower() in {"location", "city", "based in"} and value.strip():
            basic["location"] = clean(value)[:120]
        if (
            label.lower() in {"headline", "professional title", "job title"}
            and value.strip()
        ):
            basic["headline"] = clean(value)[:160]
    if "headline" not in basic:
        title = next(
            (
                line
                for line in sections["header"][:6]
                if ROLE.search(line)
                and len(line) <= 100
                and not re.search(r"[@:|\d]", line)
                and not line.endswith(".")
            ),
            "",
        )
        if title:
            basic["headline"] = title
    for match in re.finditer(
        r"(?<![\w])(?:\+\d[\d ()-]{7,24}\d|0\d[\d ()-]{7,15}\d)(?![\w])", header
    ):
        phone = match[0].strip()
        if 9 <= len(re.sub(r"\D", "", phone)) <= 15 and not PERIOD.search(phone):
            basic["phone_number"] = phone
            break
    summary = "\n".join(line for line in sections["summary"] if line)
    if summary:
        basic["summary"] = summary[:3000]
    portfolio = []
    for value in re.findall(r"https?://[^\s<>]+", header):
        value = value.rstrip(".,;)|")
        if len(value) <= 500:
            portfolio.append({"title": "Professional link", "url": value})
    notes = [
        "Check every suggestion before saving. Missing details can be filled in here or later."
    ]
    if PERIOD.search(text):
        notes.append(
            "Month-only dates use the first day of that month. Year-only dates are left blank; enter the correct dates before including those entries."
        )
    return {
        "basic": basic,
        "skills": skills_from(sections["skills"]),
        "education": education_from(sections["education"]),
        "experience": experience_from(sections["experience"]),
        "certifications": certifications_from(sections["certifications"]),
        "portfolio": portfolio[:10],
        "notes": notes,
    }
