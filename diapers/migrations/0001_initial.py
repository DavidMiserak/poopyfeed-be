import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("children", "0002_diaperchange"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="DiaperChange",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "change_type",
                            models.CharField(
                                choices=[
                                    ("wet", "Wet"),
                                    ("dirty", "Dirty"),
                                    ("both", "Wet + Dirty"),
                                ],
                                max_length=10,
                            ),
                        ),
                        ("changed_at", models.DateTimeField()),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "child",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="diaper_changes",
                                to="children.child",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "children_diaperchange",
                        "ordering": ["-changed_at"],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
