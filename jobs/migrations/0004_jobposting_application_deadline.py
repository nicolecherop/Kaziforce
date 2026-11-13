from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0003_structured_requirements")]
    operations = [
        migrations.AddField(
            model_name="jobposting",
            name="application_deadline",
            field=models.DateField(
                blank=True,
                db_index=True,
                null=True,
                help_text="Optional. Applications close at the end of this date in East Africa Time (EAT).",
            ),
        ),
    ]
