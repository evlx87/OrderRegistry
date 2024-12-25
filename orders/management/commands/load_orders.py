import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from orders.models import Order
from django.utils import timezone
from datetime import datetime


class Command(BaseCommand):
    help = 'Load orders from orders.json file'

    def handle(self, *args, **kwargs):
        # Открытие файла orders.json
        try:
            with open(os.path.join(settings.JSON_FILES_DIR, 'orders2024.json'), 'r', encoding='utf-8') as file:
                orders_data = json.load(file)

            # Список для пакетного сохранения заказов
            orders_to_create = []
            skipped_orders = []

            # Обработка данных из JSON и сохранение их в базу данных
            for order_data in orders_data:
                fields = order_data.get('fields', {})
                try:
                    document_title = fields.get('document_title', '')[:255]

                    # Проверка поля issue_date
                    issue_date_str = fields.get('issue_date', None)
                    if issue_date_str is None:
                        skipped_orders.append(fields.get("document_number", ""))
                        continue  # Пропустить, если issue_date None

                    # Преобразование issue_date в формат даты
                    try:
                        issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        skipped_orders.append(fields.get("document_number", ""))
                        self.stdout.write(self.style.WARNING(
                            f'Skipped Order with document_number {fields.get("document_number", "")}: '
                            f'issue_date is not in correct format (expected YYYY-MM-DD).'))
                        continue

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

                    # Добавление заказов в список для пакетного сохранения
                    orders_to_create.append(order)

                except Exception as order_exception:
                    self.stdout.write(self.style.ERROR(f'An error occurred while processing order: {order_exception}'))

            # Сохранение всех заказов в базе данных
            if orders_to_create:
                Order.objects.bulk_create(orders_to_create)
                self.stdout.write(self.style.SUCCESS(f'Loaded {len(orders_to_create)} orders successfully'))

            if skipped_orders:
                self.stdout.write(self.style.WARNING(f'Skipped {len(skipped_orders)} orders due to missing or invalid data.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('File orders.json not found'))
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('Error decoding JSON from orders.json'))

