# Generated by Django 5.1.4 on 2024-12-23 07:40

import orders.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_scanorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='scan',
            field=models.FileField(blank=True, null=True, upload_to=orders.models.order_scan_upload_to, verbose_name='Скан приказа'),
        ),
        migrations.DeleteModel(
            name='ScanOrder',
        ),
    ]
