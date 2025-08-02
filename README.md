# Телеграм-бот учета воды (Docker, aiogram, SQLite, RU, MSK)

Легковесный бот с быстрыми кнопками для добавления выпитой воды. Хранение в SQLite, один контейнер, long polling — никаких открытых портов. Русская локаль, время Europe/Moscow.

Функции
- Крупные кнопки: +100, +200, +300, +500, +1000
- Команды: /start, /help, /goal <мл>, /stats, /undo
- /goal — установка дневной цели (по умолчанию 2000 мл)
- “Статистика” — сумма за сегодня, прогресс-бар и последние 3 записи
- “Отменить” — удаляет последнюю запись за сегодняшний день
- Локальное “сегодня” считается по часовому поясу Europe/Moscow

Стек
- Python 3.12 + aiogram 3.x
- SQLite (файл в volume)
- Docker, без публикации портов

Структура
- [Dockerfile](Dockerfile:1)
- [docker-compose.yml](docker-compose.yml:1)
- [.env.example](.env.example:1)
- Код:
  - [app/main.py](app/main.py:1)
  - [app/settings.py](app/settings.py:1)
  - [app/db.py](app/db.py:1)
  - [app/keyboards.py](app/keyboards.py:1)
- Скрипт запуска: [entrypoint.sh](entrypoint.sh:1)
- Данные БД: ./data/water.sqlite3 (создастся автоматически)

Быстрый старт
1) Скопируйте .env.example в .env и вставьте токен бота:
   cp .env.example .env
   # отредактируйте .env и установите BOT_TOKEN

2) Соберите и запустите контейнер:
   docker compose up -d --build

3) Проверьте логи:
   docker logs -f water-bot

4) Откройте ваш бот в Telegram и нажмите /start.

Переменные окружения
- BOT_TOKEN — токен вашего Telegram-бота
- TZ — часовой пояс (по умолчанию Europe/Moscow)
- DAILY_GOAL_DEFAULT — дневная цель по умолчанию, мл (по умолчанию 2000)

Безопасность и надежность
- БД — один SQLite-файл в ./data (volume), сохраняется между перезапусками
- Контейнер не публикует порты — ничего не конфликтует с Caddy, Sing-box, Nightscout
- Рестарт-политика: unless-stopped

Заметки
- Если потребуется webhook под Caddy, можно добавить http-сервис и маршрут в Caddy, но текущая конфигурация этого не требует.
- Для расширений (напоминания, дополнительные срезы статистики) структура уже подготовлена.
