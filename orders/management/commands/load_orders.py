import json
from django.core.management.base import BaseCommand
from orders.models import Order
from django.utils import timezone


class Command(BaseCommand):
    help = 'Load orders from orders.json file'

    def handle(self, *args, **kwargs):
        # Открытие файла orders.json
        try:
            with open('orders.json', 'r', encoding='utf-8') as file:
                orders_data = json.load(file)

            # Обработка данных из JSON и сохранение их в базу данных
            for order_data in orders_data:
                fields = order_data.get('fields', {})
                try:
                    document_title = fields.get('document_title', '')[:255]

                    # Проверка поля issue_date
                    issue_date_str = fields.get('issue_date', None)
                    if issue_date_str is None:
                        self.stdout.write(self.style.WARNING(
                            f'Skipped Order with document_number {fields.get("document_number", "")}: '
                            f'issue_date is None'))
                        continue

                    # Преобразование issue_date в формат даты
                    issue_date = timezone.datetime.strptime(issue_date_str, '%Y-%m-%d').date()

                    # Создание объекта Order
                    order = Order(
                        document_number=fields.get('document_number', ''),
                        issue_date=issue_date,
                        document_title=document_title,
                        signed_by=fields.get('signed_by', ''),
                        responsible_executor=fields.get('responsible_executor', ''),
                        transferred_to_execution=fields.get('transferred_to_execution', ''),
                        transferred_for_storage=fields.get('transferred_for_storage', ''),
                        heraldic_blank_number=fields.get('heraldic_blank_number', ''),
                        note=fields.get('note', ''),
                        is_active=fields.get('is_active', True),
                    )

                    # Сохранение объекта в базе данных
                    order.save()
                    self.stdout.write(self.style.SUCCESS(f'Order {order.document_number} saved successfully'))

                except Exception as order_exception:
                    self.stdout.write(self.style.ERROR(f'An error occurred while saving order: {order_exception}'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('File orders.json not found'))
