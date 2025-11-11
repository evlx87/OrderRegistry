import os
import shutil
from datetime import datetime

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.db.models import Q

# Предполагаем, что orders.models.py доступен в PYTHONPATH
try:
    from orders.models import Order, order_scan_upload_to
except ImportError:
    # Запасной вариант, если orders.models не импортируется
    class TempOrder:
        DOC_TYPE_ORDER = 'order'
        DOC_TYPE_DECREE = 'decree'


    Order = TempOrder


    def order_scan_upload_to(instance, filename):
        # Если импорт не сработал, используем временный упрощенный путь
        return os.path.join('orders_scan', str(getattr(instance, 'issue_date', datetime.now()).year), filename)

# Маппинг для преобразования текста из Excel в ключи модели
DOC_TYPE_MAP = {
    'Приказ': Order.DOC_TYPE_ORDER,
    'Распоряжение': Order.DOC_TYPE_DECREE,
}

# Маппинг столбцов Excel к полям модели
EXCEL_TO_MODEL_MAP = {
    'Номер документа': 'document_number',
    'Дата издания': 'issue_date',
    'Вид документа': 'doc_type',
    'Наименование документа': 'document_title',
    'Подписант': 'signed_by',
    'Ответственный исполнитель': 'responsible_executor',
    'Передан на исполнение': 'transferred_to_execution',
    'Передан на хранение': 'transferred_for_storage',
    'Номер геральдического бланка': 'heraldic_blank_number',
    'Примечание': 'note',
}


class Command(BaseCommand):
    help = 'Загружает данные о приказах из Excel-файла и прикрепляет сканы.'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Путь к Excel-файлу')
        parser.add_argument('pdf_dir', type=str, help='Путь к директории с PDF-файлами сканов')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']
        pdf_dir = kwargs['pdf_dir']

        if not os.path.exists(excel_path):
            self.stderr.write(
                self.style.ERROR(f'Файл Excel не найден: {excel_path}'))
            return

        if not os.path.isdir(pdf_dir):
            self.stderr.write(
                self.style.ERROR(f'Директория со сканами не найдена: {pdf_dir}'))
            return

        # Чтение данных из Excel
        try:
            df = pd.read_excel(excel_path)
            # Приводим названия столбцов к нижнему регистру и удаляем пробелы
            df.columns = [col.strip() for col in df.columns]
            orders_data = df.to_dict('records')
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Ошибка при чтении Excel: {e}'))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Загружено {len(orders_data)} записей из файла.'))

        existing_orders = {
            order.document_number: order
            for order in Order.objects.all()
        }

        orders_to_create = []
        orders_to_update = []
        file_errors = 0

        for row in orders_data:
            defaults = {}
            document_number = None
            doc_type_name = None

            # 1. Сбор и преобразование данных из строки Excel
            for excel_col, model_field in EXCEL_TO_MODEL_MAP.items():
                value = row.get(excel_col)

                # 1.1 Преобразование типа документа
                if excel_col == 'Вид документа':
                    doc_type_name = str(value).strip() if value else 'Приказ'
                    defaults[model_field] = DOC_TYPE_MAP.get(doc_type_name, Order.DOC_TYPE_ORDER)
                    continue

                # 1.2 Обработка номера документа
                if model_field == 'document_number':
                    document_number = str(value).strip() if value else None
                    if document_number:
                        defaults[model_field] = document_number
                        continue

                # 1.3 Сохранение остальных полей
                if value is not None:
                    if isinstance(value, str):
                        defaults[model_field] = value.strip()
                    else:
                        defaults[model_field] = value

                # Обеспечиваем, что None будет для пустых строк
                if value is None or (isinstance(value, str) and not value.strip()):
                    if model_field == 'issue_date':
                        defaults[model_field] = None
                    else:
                        defaults[model_field] = ''  # Для CharField

            if not document_number:
                self.stderr.write(
                    self.style.WARNING(f"Пропущена строка без номера документа: {row.get('Наименование документа')}"))
                continue

            # --- КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Преобразование issue_date в datetime.date ---
            raw_issue_date = defaults.get('issue_date')

            if raw_issue_date:
                try:
                    # pd.to_datetime надежно парсит большинство форматов Excel/строк в Pandas Timestamp
                    # errors='coerce' превратит невалидные даты в NaT
                    parsed_date = pd.to_datetime(raw_issue_date, errors='coerce')

                    if pd.notna(parsed_date):
                        # Преобразуем Timestamp в стандартный Python date
                        defaults['issue_date'] = parsed_date.date()
                    else:
                        # Если парсинг не удался
                        self.stderr.write(self.style.WARNING(
                            f"  Не удалось распознать дату '{raw_issue_date}' для документа №{document_number}. Устанавливается NULL."))
                        defaults['issue_date'] = None
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f"  Критическая ошибка парсинга даты {raw_issue_date}: {e}. Устанавливается NULL."))
                    defaults['issue_date'] = None
            else:
                defaults['issue_date'] = None
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            # 2. Логика поиска PDF-файла (и создание temp_order)

            base_file_name = f"{doc_type_name} {document_number}"

            possible_names = [
                f"{base_file_name}.pdf",
                f"{base_file_name}.PDF",
                f"{doc_type_name.lower()} {document_number}.pdf",
                f"{doc_type_name.lower()} {document_number}.PDF",
            ]

            pdf_source_path = None
            for name in possible_names:
                full_path = os.path.join(pdf_dir, name)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    pdf_source_path = full_path
                    break

            # 3. Обработка скана
            if pdf_source_path:

                # 3.1 Создаем временный объект для генерации пути
                # issue_date теперь гарантированно datetime.date или None
                temp_order = Order(
                    issue_date=defaults.get('issue_date'),
                    document_number=document_number,
                    doc_type=defaults.get('doc_type', Order.DOC_TYPE_ORDER)
                )

                # 3.2 Генерируем целевой путь к файлу в MEDIA_ROOT

                target_filename = order_scan_upload_to(temp_order, os.path.basename(pdf_source_path))
                target_full_path = os.path.join(settings.MEDIA_ROOT, target_filename)

                # 3.3 Создаем целевую директорию (включая год/месяц)
                os.makedirs(os.path.dirname(target_full_path), exist_ok=True)

                try:
                    # 3.4 Копируем файл из исходной папки в целевую
                    shutil.copyfile(pdf_source_path, target_full_path)

                    # 3.5 Устанавливаем относительный путь
                    defaults['scan'] = target_filename
                    self.stdout.write(
                        self.style.NOTICE(f"  Файл для {document_number} найден и скопирован: {target_filename}"))

                except Exception as e:
                    file_errors += 1
                    self.stderr.write(self.style.ERROR(f"  Ошибка копирования файла {pdf_source_path}: {e}"))
                    defaults['scan'] = None
            else:
                self.stderr.write(self.style.WARNING(f"  Скан для документа №{document_number} не найден."))
                defaults['scan'] = None

            # 4. Сортировка по созданию или обновлению
            if document_number in existing_orders:
                order_obj = existing_orders[document_number]

                for key, value in defaults.items():
                    setattr(order_obj, key, value)

                orders_to_update.append(order_obj)
            else:
                orders_to_create.append(Order(**defaults))

        # 5. Выполнение bulk-операций
        if orders_to_create:
            Order.objects.bulk_create(orders_to_create)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Успешно создано {len(orders_to_create)} новых приказов.'))

        if orders_to_update:
            fields_to_update = list(EXCEL_TO_MODEL_MAP.values())

            if 'scan' not in fields_to_update:
                fields_to_update.append('scan')

            if 'document_number' in fields_to_update:
                fields_to_update.remove('document_number')

            Order.objects.bulk_update(
                orders_to_update,
                fields_to_update
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Успешно обновлено {len(orders_to_update)} существующих приказов.'))

        if file_errors > 0:
            self.stderr.write(self.style.ERROR(f"Обнаружено {file_errors} ошибок при копировании файлов."))