# Реестр приказов и распоряжений

Веб-приложение на Django 5.2 для ведения реестра приказов и распоряжений организации с возможностью:
- добавления/редактирования/удаления документов
- загрузки сканов (PDF)
- поиска и фильтрации
- экспорта в Excel
- авторизации пользователей
- логирования действий

## Технологии

- Python 3.11+
- Django 5.2.8
- PostgreSQL (рекомендуется) / SQLite (для тестов)
- Bootstrap 5 + jQuery
- openpyxl (экспорт в Excel)
- pandas (импорт из Excel)

## Системные требования

- Python ≥ 3.11
- PostgreSQL 13+ (или SQLite для быстрого старта)
- Git
- virtualenv или poetry (по желанию)

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/OrderRegistry.git
cd OrderRegistry
```

### 2. Создание и активация виртуального окружения
```bash
python -m venv venv
```

#### Windows
```bash
venv\Scripts\activate
```
#### Linux / macOS
```bash
source venv/bin/activate
```
### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```
### 4. Настройка переменных окружения
Скопируйте файл-пример и отредактируйте его под свои данные:
```bash
cp env.sample .env
```
Откройте .env и заполните:
```Python
envSECRET_KEY="очень-длинный-случайный-ключ-генерируйте-новый!"
DEBUG=True

# Разрешённые хосты (через запятую без пробелов)
ALLOWED_HOSTS="127.0.0.1,localhost"

# PostgreSQL (рекомендуется)
DB_ENGINE="django.db.backends.postgresql"
DB_NAME="order_registry_db"
DB_USER="your_postgres_user"
DB_PASSWORD="your_postgres_password"
DB_HOST="localhost"
DB_PORT=5432

# Название вашей организации (отображается в шапке)
ORGANIZATION_NAME="ООО «Ромашка»"
```

Для быстрого старта можно использовать SQLite — просто закомментируйте строки с DB_* в .env или оставьте их пустыми.

### 5. Применение миграций
```Bash
python manage.py migrate
```

### 6. ВАЖНО! Создание таблицы для кэша (обязательно!)
Проект использует кэширование в базе данных. Таблица не создаётся автоматически.
```Bash
python manage.py createcachetable
```
Без этой команды будет ошибка relation "orders_cache_table" does not exist.

### 7. Создание суперпользователя
```Bash
python manage.py createsuperuser
```
Следуйте подсказкам — это будет администратор системы.

### 8. Запуск сервера разработки
```Bash
python manage.py runserver
```
Откройте в браузере: ```http://127.0.0.1:8000```

### Начальные данные (по желанию)
Загрузка приказов из Excel + копирование сканов
Если у вас есть Excel-файл со старыми приказами и папка со сканами:
```Bash
python manage.py load_orders путь/к/файлу.xlsx путь/к/папке_со_сканами/
```
Пример:
```Bash
python manage.py load_orders data/orders_2024.xlsx scans/2024/
```

#### Другие полезные команды
```Bash
# Создать JSON-шаблон для fixtures
python manage.py make_json

# Преобразовать старый JSON в формат fixtures (если нужно)
python manage.py create_json путь/к/папке_со_сканами/
```

## Функционал

Возможность
Как пользоваться
Вход/выход
Кнопка «Войти» в правом верхнем углу
Добавить приказ
Кнопка «Добавить» → модальное окноРедактировать
Иконка карандаша в таблице
Удалить
Иконка корзины в таблице
Поиск по названию
Поле «Введите название документа...»
Фильтр по номеру, году, виду
Форма над таблицей
Экспорт в Excel
Кнопка «Экспорт в Excel» → выбор полей
Просмотр скана
Клик по номеру документа → карточка → ссылка

## Логирование
Все действия пользователей и ошибки записываются в папку logs/:

logs/orders_logs.log — ежедневные логи с ротацией (хранятся 30 дней)

## Деплой в продакшн (кратко)

DEBUG=False
Настроить ALLOWED_HOSTS
Использовать ASGI-сервер (uvicorn + gunicorn, Daphne, Hypercorn)
Настроить статику: python manage.py collectstatic
Обслуживать медиа-файлы через nginx или whitenoise
Рекомендуется использовать Redis вместо DatabaseCache

## Лицензия
Проект распространяется как открытое ПО. Лицензия — на усмотрение владельца репозитория.