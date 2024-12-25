import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from datetime import datetime

class Command(BaseCommand):
    help = 'Создает JSON файл на основе данных приказов'

    def handle(self, *args, **kwargs):
        # Укажите директорию, где находятся сканы приказов
        scans_directory = 'C:\\Users\\evlx.OKK\\Desktop\\scan2024'
        file_path = os.path.join(settings.JSON_FILES_DIR, 'output2024.json')

        # Чтение исходных данных из JSON-файла
        with open(file_path, 'r', encoding="utf-8") as file:
            data = json.load(file)

        # Преобразование данных
        transformed_data = []
        for item in data:
            # Извлечение необходимых полей с обеспечением наличия значений
            document_number = item.get("Номердокумента")  # используйте правильный ключ
            if not document_number:
                self.stdout.write(self.style.WARNING(f"Warning: 'Номердокумента' is missing in item: {item}"))
                continue  # Пропустить этот элемент, если 'Номердокумента' отсутствует

            # Преобразование даты
            issue_date_str = item.get("Датаиздания")
            if issue_date_str:
                try:
                    # Предполагается, что дата может быть в формате 'DD.MM.YYYY'
                    issue_date = datetime.strptime(issue_date_str, '%d.%m.%Y').strftime('%Y-%m-%d')
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"Warning: Invalid date format in item: {item}"))
                    issue_date = None  # Если формат неверный, устанавливаем значение None
            else:
                issue_date = None  # Если дата отсутствует

            document_title = item.get("Названиедокумента,кемподписандокумент")
            responsible_executor = item.get("Ответственныйисполнитель", "")
            signed_by = item.get("Подписавшийдокумент", "")
            transferred_to_execution = item.get("Комупередан(ответственныйзаисполнениеприказа)", "")
            transferred_for_storage = item.get("Комупереданонахранение", "")
            heraldic_blank_number = item.get("Номергербовогобланка/Примечание", "")
            note = ""

            # Путь к файлу скана
            scan_filename = f"{document_number}.pdf"  # предполагаем, что сканы имеют имя вида <номер документа>.pdf
            scan_file_path = os.path.join(scans_directory, scan_filename)

            # Проверяем, существует ли файл скана
            if os.path.isfile(scan_file_path):
                scan_file_relative_path = os.path.relpath(scan_file_path, start=scans_directory)
                # Записываем относительный путь в поле scan
                transformed_item = {
                    "model": "orders_order",
                    "fields": {
                        "document_number": document_number,
                        "issue_date": issue_date,
                        "document_title": document_title,
                        "signed_by": signed_by,
                        "responsible_executor": responsible_executor,
                        "transferred_to_execution": transferred_to_execution,
                        "transferred_for_storage": transferred_for_storage,
                        "heraldic_blank_number": heraldic_blank_number,
                        "note": note,
                        "is_active": True,
                        "scan": scan_file_relative_path  # сохраняем относительный путь
                    }
                }
            else:
                transformed_item = {
                    "model": "orders_order",
                    "fields": {
                        "document_number": document_number,
                        "issue_date": issue_date,
                        "document_title": document_title,
                        "signed_by": signed_by,
                        "responsible_executor": responsible_executor,
                        "transferred_to_execution": transferred_to_execution,
                        "transferred_for_storage": transferred_for_storage,
                        "heraldic_blank_number": heraldic_blank_number,
                        "note": note,
                        "is_active": True,
                        "scan": None  # если скан отсутствует, записываем None
                    }
                }

            transformed_data.append(transformed_item)

        # Запись преобразованных данных в новый JSON-файл
        output_file_path = os.path.join(settings.JSON_FILES_DIR, 'orders2024.json')
        with open(output_file_path, 'w', encoding="utf-8") as file:
            json.dump(transformed_data, file, indent=4, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS("Преобразование завершено. Результат сохранен в orders.json"))

