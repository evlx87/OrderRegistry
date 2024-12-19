from django.db import models

# Create your models here.
class Order(models.Model):
    document_number = models.CharField(max_length=50, verbose_name='Номер документа')
    issue_date = models.DateField(verbose_name='Дата издания')
    document_title = models.CharField(max_length=255, verbose_name='Название документа')
    signed_by = models.CharField(max_length=150, verbose_name='Кем подписан документ')
    responsible_executor = models.CharField(max_length=150, verbose_name='Ответственный исполнитель')
    transferred_to_execution = models.CharField(max_length=150, verbose_name='Кому передан (ответственный за исполнение приказа)')
    transferred_for_storage = models.CharField(max_length=150, verbose_name='Кому передано на хранение')
    heraldic_blank_number = models.CharField(max_length=20, verbose_name='Номер гербового бланка', blank=True)
    note = models.TextField(verbose_name='Примечание', blank=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f'{self.number}. {self.document_number}'