# Generated by Django 5.1.4 on 2024-12-24 07:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_alter_order_heraldic_blank_number_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='document_title',
            field=models.TextField(db_index=True, verbose_name='Название документа'),
        ),
    ]
