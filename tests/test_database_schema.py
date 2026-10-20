"""Explicit application table names remain readable and stable."""

from django.db import connection
from django.test import TestCase


class DatabaseSchemaTests(TestCase):
    def test_agreed_table_names_exist_and_legacy_names_are_gone(self):
        tables = set(connection.introspection.table_names())
        expected = {
            "users",
            "candidate_profiles",
            "candidate_skills",
            "candidate_education",
            "candidate_certifications",
            "candidate_experience",
            "candidate_portfolio_links",
            "candidate_documents",
            "jobs",
            "job_skills",
            "applications",
            "application_draft_documents",
            "application_attachments",
        }
        self.assertTrue(expected.issubset(tables), expected - tables)
        self.assertFalse(
            {
                "accounts_user",
                "candidates_candidateprofile",
                "jobs_jobposting",
                "applications_application",
            }
            & tables
        )
