from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("children", "0004_feeding"),
        ("diapers", "0001_initial"),
        ("naps", "0001_initial"),
        ("feedings", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="DiaperChange"),
                migrations.DeleteModel(name="Nap"),
                migrations.DeleteModel(name="Feeding"),
            ],
            database_operations=[],
        ),
    ]
