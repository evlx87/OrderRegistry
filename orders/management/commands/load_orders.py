import os

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from orders.models import Order


class Command(BaseCommand):
    help = 'Загружает данные о приказах из Excel-файла'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Путь к Excel-файлу')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        excel_path = kwargs['path']
        if not os.path.exists(excel_path):
            self.stderr.write(
                self.style.ERROR(
                    f'Файл не найден: {excel_path}'))
            return

        # Чтение данных из Excel
        try:
            df = pd.read_excel(excel_path)
            orders_data = df.to_dict('records')
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(
                    f'Ошибка при чтении Excel: {e}'))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Загружено {
                    len(orders_data)} записей из файла.'))

        existing_document_numbers = set(
            Order.objects.values_list('document_number', flat=True)
        )

        orders_to_create = []
        orders_to_update = []

        for item in orders_data:
            # 1. Очистка и подготовка номера документа
            document_number = str(item.get('document_number', '')).strip()

            if not document_number:
                self.stderr.write(
                    self.style.WARNING(
                        f'Пропуск записи без номера документа: {item}'))
                continue

            # 2. Формирование словаря обновляемых/создаваемых полей
            defaults = {
                # Примечание: предполагается, что 'document_date' из Excel
                # соответствует issue_date в модели
                'issue_date': item.get('document_date'),
                'document_title': item.get('document_title'),
                'signed_by': item.get('signed_by'),
                'responsible_executor': item.get('responsible_executor'),
                'transferred_to_execution': item.get('transferred_to_execution'),
                'transferred_for_storage': item.get('transferred_for_storage'),
                'heraldic_blank_number': item.get('heraldic_blank_number'),
                'note': item.get('note'),
                'is_active': item.get('is_active', True),
                'scan': item.get('scan'),
            }

            # 3. Приведение значений None/NaN к пустым строкам для
            # CharField/TextField
            for key in defaults:
                if isinstance(defaults[key], str):
                    defaults[key] = defaults[key].strip()
                # Только для полей, где в модели не разрешен null (для
                # CharField/TextField)
                if key != 'issue_date' and defaults[key] is None:
                    defaults[key] = ''

            # 4. Сортировка по созданию или обновлению
            if document_number in existing_document_numbers:
                # Добавляем в список для bulk_update
                orders_to_update.append(
                    Order(document_number=document_number, **defaults)
                )
            else:
                # Добавляем в список для bulk_create
                orders_to_create.append(
                    Order(document_number=document_number, **defaults)
                )

        # 5. Выполнение bulk-операций
        if orders_to_create:
            Order.objects.bulk_create(orders_to_create)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Успешно создано {
                        len(orders_to_create)} новых приказов.'))

        if orders_to_update:
            # --- КОРРЕКТИРОВКА: Динамическое получение списка полей ---
            # Для bulk_update нужны только те поля, которые мы передаем в defaults.
            # 'document_number' не включаем, т.к. это поле для поиска/сопоставления.
            fields_to_update = list(defaults.keys())

            Order.objects.bulk_update(
                orders_to_update,
                fields_to_update
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Успешно обновлено {
                        len(orders_to_update)} существующих приказов.'))
