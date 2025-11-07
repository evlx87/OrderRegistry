import openpyxl
from django.core.management.base import BaseCommand
from django.db.models import CharField, TextField

from orders.models import Order


class Command(BaseCommand):
    help = 'Загружает данные из файла Excel в модель Order, используя массовые операции.'

    def add_arguments(self, parser):
        parser.add_argument(
            'excel_file_path',
            type=str,
            help='Путь к файлу Excel для загрузки.')

    def handle(self, *args, **options):
        excel_file_path = options['excel_file_path']
        self.stdout.write(
            self.style.NOTICE(
                f'Начинаем загрузку данных из: {excel_file_path}'))

        try:
            workbook = openpyxl.load_workbook(excel_file_path)
            sheet = workbook.active
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    f'Ошибка: Файл не найден по пути {excel_file_path}'))
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Ошибка при чтении Excel-файла: {e}'))
            return

        # 1. Получаем заголовки (первая строка)
        headers = [cell.value for cell in sheet[1]]
        data = []

        # 2. Читаем данные из файла
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if any(row):  # Пропускаем пустые строки
                data.append(dict(zip(headers, row)))

        if not data:
            self.stdout.write(self.style.NOTICE(
                'В файле нет данных для обработки.'))
            return

        # 3. Разделение данных на создание и обновление

        # Получаем список document_number для всех записей в базе
        existing_document_numbers = set(
            Order.objects.values_list('document_number', flat=True)
        )

        orders_to_create = []
        orders_to_update = []

        # Список полей, которые нужно обновить с помощью bulk_update
        # Исключаем document_number, так как он используется для поиска
        fields_to_update = [
            'document_date', 'document_title', 'transferred_for_execution',
            'transferred_to_execution', 'responsible_executor', 'recipient',
            'heraldic_blank_number', 'is_active', 'scan',
        ]

        for item in data:
            document_number = str(item.get('document_number')).strip()

            # Подготовка словаря с данными для Order
            defaults = {
                'document_date': item.get('document_date'),
                'document_title': item.get('document_title'),
                'transferred_for_execution': item.get('transferred_for_execution'),
                'transferred_to_execution': item.get('transferred_to_execution'),
                'responsible_executor': item.get('responsible_executor'),
                'recipient': item.get('recipient'),
                'heraldic_blank_number': item.get('heraldic_blank_number'),
                # Устанавливаем is_active в True по умолчанию, если поле не
                # указано
                'is_active': item.get('is_active', True),
                'scan': item.get('scan'),
            }

            # Очистка пустых значений None (чтобы поля blank=True корректно
            # обрабатывались)
            for key, value in defaults.items():
                if value is None:
                    defaults[key] = '' if isinstance(Order._meta.get_field(
                        key), (CharField, TextField)) else None

            if document_number in existing_document_numbers:
                # Обновление
                orders_to_update.append(
                    Order(document_number=document_number, **defaults)
                )
            else:
                # Создание
                orders_to_create.append(
                    Order(document_number=document_number, **defaults)
                )

        # 4. Выполнение массовых операций

        # Массовое создание
        if orders_to_create:
            Order.objects.bulk_create(orders_to_create)
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Создано {
                        len(orders_to_create)} новых заказов.'))

        # Массовое обновление (используется bulk_update)
        if orders_to_update:
            # Важно: bulk_update требует явного указания списка полей для
            # обновления
            Order.objects.bulk_update(
                orders_to_update,
                fields_to_update
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'🔄 Обновлено {
                        len(orders_to_update)} существующих заказов.'))

        self.stdout.write(self.style.SUCCESS('✨ Загрузка данных завершена.'))
