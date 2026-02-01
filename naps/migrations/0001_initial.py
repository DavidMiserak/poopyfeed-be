import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("children", "0003_nap"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Nap",
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
                        ("napped_at", models.DateTimeField()),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "child",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="naps",
                                to="children.child",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "children_nap",
                        "ordering": ["-napped_at"],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
