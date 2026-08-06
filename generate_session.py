"""
Разовый локальный скрипт: логинится в твой Telegram-аккаунт и выводит
строку сессии (StringSession), которую нужно вставить в Railway
как переменную окружения SESSION_STRING.

Запускать ТОЛЬКО у себя на компьютере, один раз.

Установка:
    pip install telethon

Запуск:
    python generate_session.py
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("Введи свой api_id (число с my.telegram.org): ").strip())
api_hash = input("Введи свой api_hash: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("Готово! Вот твоя строка сессии — сохрани её как переменную")
    print("окружения SESSION_STRING в Railway (Variables).")
    print("НИКОМУ ЕЁ НЕ ПОКАЗЫВАЙ — это равносильно доступу к аккаунту.")
    print("=" * 60 + "\n")
    print(session_string)
    print()
