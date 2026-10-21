"""Public wording for bundled sample records; stored evidence stays unchanged.

Only the known seed labels are aliased. Ordinary profile text, job descriptions,
skill names and references to professional projects pass through unchanged.
"""

COMPANY_LABELS = {
    "Demo Studio": "Savanna Studio",
    "Demo Insights": "Nairobi Insights",
    "Demo Digital": "Acacia Digital",
    "Demo Operations": "Savanna Operations",
    "Demo Customer Care": "Acacia Customer Care",
}

PUBLIC_LABELS = {
    **COMPANY_LABELS,
    "Recruiter Demo": "Sarah Mwangi",
    "Amina Demo": "Amina Hassan",
    "Brian Demo": "Brian Otieno",
    "Chloe Demo": "Chloe Wanjiru",
    "David Demo": "David Kamau",
    "Esther Demo": "Esther Achieng",
    "Felix Demo": "Felix Mutua",
    "Demo Learning Institute (fictional)": "Nairobi Learning Institute",
    "Demo Training Centre (fictional)": "Nairobi Training Centre",
    "Demo Previous Employer (fictional)": "Savanna Services",
    "Fictional demonstration vacancy for testing KaziForce. No real recruitment is taking place.": "Review the role requirements and submit your profile to apply.",
    "Fictional demo application to demonstrate profile review and matching.": "Please consider my application. My profile outlines my skills, qualifications and relevant experience.",
}


def public_text(value):
    if not isinstance(value, str):
        return value
    if value.startswith("[Demo] "):
        return value.removeprefix("[Demo] ")
    return PUBLIC_LABELS.get(value, value)


def contact_email(value):
    """Do not present reserved sample logins as usable recruiter contact details."""
    if isinstance(value, str) and value.casefold().endswith("@demo.kaziforce.test"):
        return ""
    return value


def company_search_labels(query):
    """Let job searches find the same company names shown on their cards."""
    return [
        stored
        for stored, displayed in COMPANY_LABELS.items()
        if query.casefold() in displayed.casefold()
    ]
