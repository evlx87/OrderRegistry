from django.db import models
import os
from django.utils import timezone

# Create your models here.
def order_scan_upload_to(instance, filename):
    # Генерируем имя файла в формате год_месяц_день_номерПриказа
    order_date = timezone.localdate(instance.issue_date)
    year = order_date.year
    month = f"{order_date.month:02}"  # Делаем месяц двузначным
    day = f"{order_date.day:02}"  # Делаем день двузначным

    # Формируем путь для хранения файла
    filename = f"{year}_{month}_{day}_{instance.document_number}.pdf"  # предположим, что файл PDF
    return os.path.join('orders_scan', str(year), filename)  # Задаем директорию по годам

class Order(models.Model):
    document_number = models.CharField(
        max_length=50,
        verbose_name='Номер документа',
        db_index=True)
    issue_date = models.DateField(verbose_name='Дата издания')
    document_title = models.CharField(
        max_length=255,
        verbose_name='Название документа',
        db_index=True)
    signed_by = models.CharField(
        max_length=150,
        verbose_name='Кем подписан документ')
    responsible_executor = models.CharField(
        max_length=150, verbose_name='Ответственный исполнитель')
    transferred_to_execution = models.CharField(
        max_length=150,
        verbose_name='Кому передан (ответственный за исполнение приказа)')
    transferred_for_storage = models.CharField(
        max_length=150, verbose_name='Кому передано на хранение')
    heraldic_blank_number = models.CharField(
        max_length=20, verbose_name='Номер гербового бланка', blank=True)
    note = models.TextField(verbose_name='Примечание', blank=True)
    is_active = models.BooleanField(default=True, verbose_name='Действующий')

    scan = models.FileField(upload_to=order_scan_upload_to, verbose_name='Скан приказа', blank=True, null=True)

    class Meta:
        verbose_name = 'Приказ'
        verbose_name_plural = 'Приказы'

    def __str__(self):
        return f'{self.document_number}'

