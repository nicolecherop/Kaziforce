from django.db import migrations, models


def create_rate_limit_cache(apps, schema_editor):
    from django.core.management import call_command

    call_command(
        "createcachetable",
        "security_rate_limits",
        database=schema_editor.connection.alias,
        verbosity=0,
    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_clear_table_names")]
    operations = [
        migrations.AddField(
            model_name="user",
            name="email_two_step_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(create_rate_limit_cache, migrations.RunPython.noop),
    ]
