import os
from datetime import datetime

from django.db import models
from django.utils import timezone


# Create your models here.
def order_scan_upload_to(instance, filename):
    if not instance.issue_date:
        year = 'unknown_date'
        month = '00' # Добавляем заглушку для месяца
        day = 'dd'
    else:
        order_datetime = datetime.combine(instance.issue_date, datetime.min.time())
        aware_datetime = timezone.make_aware(order_datetime)
        localized_datetime = timezone.localtime(aware_datetime)
        year = localized_datetime.year
        month = f"{localized_datetime.month:02}"
        day = f"{localized_datetime.day:02}"

    doc_type_prefix = getattr(instance, 'doc_type', 'doc')
    filename = f"{doc_type_prefix}_{instance.document_number}_{day}.{month}.{year}.pdf"

    return os.path.join('orders_scan', str(year), str(month), filename)


class Order(models.Model):
    DOC_TYPE_ORDER = 'order'
    DOC_TYPE_DECREE = 'decree'

    DOC_TYPE_CHOICES = [
        (DOC_TYPE_ORDER, 'Приказ'),
        (DOC_TYPE_DECREE, 'Распоряжение'),
    ]

    doc_type = models.CharField(
        max_length=10,
        choices=DOC_TYPE_CHOICES,
        default=DOC_TYPE_ORDER,  # По умолчанию все существующие/новые документы будут 'Приказами'
        verbose_name="Вид документа",
        db_index=True  # Добавляем индекс, так как по нему точно будет фильтрация
    )

    document_number = models.CharField(
        max_length=10,
        verbose_name='Номер документа',
        db_index=True)
    issue_date = models.DateField(
        verbose_name='Дата издания',
        null=True,
        blank=True)
    document_title = models.CharField(
        max_length=800,
        verbose_name='Название документа',
        db_index=True)
    signed_by = models.CharField(
        max_length=255,
        verbose_name='Кем подписан документ')
    responsible_executor = models.CharField(
        max_length=255,
        verbose_name='Ответственный исполнитель',
        null=True)
    transferred_to_execution = models.CharField(
        max_length=255,
        verbose_name='Кому передан (ответственный за исполнение приказа)',
        null=True,
        blank=True)
    transferred_for_storage = models.CharField(
        max_length=255,
        verbose_name='Кому передано на хранение',
        null=True,
        blank=True)
    heraldic_blank_number = models.CharField(
        max_length=20,
        null=True,
        verbose_name='Номер гербового бланка')
    note = models.TextField(
        verbose_name='Примечание',
        blank=True)
    is_active = models.BooleanField(
        default=True,
        verbose_name='Действующий')

    scan = models.FileField(
        upload_to=order_scan_upload_to,
        verbose_name='Скан приказа',
        blank=True,
        null=True)

    class Meta:
        verbose_name = 'Приказ'
        verbose_name_plural = 'Приказы'

    def __str__(self):
        return f'{self.document_number}'
