import openpyxl
from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Создает Excel-шаблон для импорта данных приказов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=str(settings.BASE_DIR),
            help='Директория для сохранения шаблона (по умолчанию корень проекта)'
        )

    def handle(self, *args, **kwargs):
        output_dir = kwargs['output_dir']
        output_path = os.path.join(output_dir, 'orders_import_template.xlsx')

        # Заголовки столбцов из load_orders.py
        headers = [
            'Вид документа',
            'Номер документа',
            'Дата издания',
            'Наименование документа',
            'Подписант',
            'Ответственный исполнитель',
            'Передан на исполнение',
            'Передан на хранение',
            'Номер геральдического бланка',
            'Примечание',
        ]

        # Пример данных
        example_data = [
            [
                'Приказ',
                '001-к',
                '15.01.2024',
                'О проведении мероприятия',
                'Иванов И.И.',
                'Петров П.П.',
                'Отдел кадров',
                'Архив',
                'ГБ-000123',
                'Тестовый приказ',
            ],
            [
                'Распоряжение',
                '25-р',
                '01.02.2024',
                'Об утверждении плана',
                'Сидоров С.С.',
                'Васечкин В.В.',
                '',
                '',
                '',
                'Важное распоряжение',
            ],
        ]

        # Создаем новый Excel-файл
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = 'Orders Import Template'

        # Добавляем заголовки
        sheet.append(headers)

        # Добавляем примеры данных
        for row in example_data:
            sheet.append(row)

        # Автоматическая настройка ширины столбцов
        for col in sheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = max_length + 2
            sheet.column_dimensions[column].width = adjusted_width

        # Сохраняем файл
        try:
            os.makedirs(output_dir, exist_ok=True)
            workbook.save(output_path)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Шаблон успешно создан: {output_path}'
                )
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(
                    f'Ошибка при сохранении шаблона: {e}'
                )
            )