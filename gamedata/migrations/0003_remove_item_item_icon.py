
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gamedata', '0002_item_patchitem'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='item',
            name='item_icon',
        ),
    ]
