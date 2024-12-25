import json
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Create JSON template for Order model'

    def handle(self, *args, **kwargs):
        # Создаем шаблон данных для модели Order
        order_template = {
            "document_number": "1234567890",  # Номер документа
            "issue_date": "2023-10-01",        # Дата издания в формате YYYY-MM-DD
            "document_title": "Пример документа",  # Название документа
            "signed_by": "Иванов И.И.",        # Кем подписан документ
            "responsible_executor": "Петров П.П.",  # Ответственный исполнитель
            "transferred_to_execution": "",     # Кому передан (ответственный за исполнение приказа)
            "transferred_for_storage": "",       # Кому передано на хранение
            "heraldic_blank_number": "HB12345",  # Номер гербового бланка
            "note": "Примечание к документу",     # Примечание
            "is_active": True,                   # Действующий (True/False)
            "scan": "path/to/scan.pdf"           # Путь к файлу скана
        }

        # Сохраняем шаблон в JSON файл
        with open('order_template.json', 'w', encoding='utf-8') as json_file:
            json.dump(order_template, json_file, ensure_ascii=False, indent=4)

        self.stdout.write(self.style.SUCCESS('JSON template created successfully: order_template.json'))

