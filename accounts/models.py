"""Identity and roles, kept separate from candidate and recruiter profile data."""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        RECRUITER = "recruiter", "Recruiter"
        ADMINISTRATOR = "administrator", "Administrator"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CANDIDATE)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_user_email_case_insensitive")]
