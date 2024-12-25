from datetime import datetime
from django.utils import timezone
from django.db import models
import os


# Create your models here.
def order_scan_upload_to(instance, filename):
    # Преобразуем дату в объект datetime
    order_datetime = datetime.combine(instance.issue_date, datetime.min.time())
    aware_datetime = timezone.make_aware(order_datetime)
    # Локализуем объект datetime в текущей временной зоне
    localized_datetime = timezone.localtime(aware_datetime)

    # Теперь можем безопасно получать год, месяц и день
    year = localized_datetime.year
    month = f"{localized_datetime.month:02}"
    day = f"{localized_datetime.day:02}"

    # Формируем имя файла
    filename = f"{instance.document_number}_{day}.{month}.{year}.pdf"

    # Возвращаем полный путь для сохранения файла
    return os.path.join('orders_scan', str(year), filename)


class Order(models.Model):
    document_number = models.CharField(
        max_length=10,
        verbose_name='Номер документа',
        db_index=True)
    issue_date = models.DateField(
        verbose_name='Дата издания')
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
