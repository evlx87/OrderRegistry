# Generated by Django 5.1.4 on 2024-12-19 13:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_remove_order_number'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='order',
            options={'verbose_name': 'Приказ', 'verbose_name_plural': 'Приказы'},
        ),
        migrations.AlterField(
            model_name='order',
            name='document_number',
            field=models.CharField(db_index=True, max_length=50, verbose_name='Номер документа'),
        ),
        migrations.AlterField(
            model_name='order',
            name='document_title',
            field=models.CharField(db_index=True, max_length=255, verbose_name='Название документа'),
        ),
    ]
