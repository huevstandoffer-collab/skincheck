"""
Юзербот на Telethon: поочерёдно отправляет список сообщений в чат с указанным
Telegram-ботом, с задержкой 5-10 сек между ними, и сразу скачивает все
стикеры/фото/файлы из ответов бота на диск в папку site/images/, ведя
site/manifest.json (имя -> файл) для сайта-галереи.

Рассчитан на запуск в облаке БЕЗ постоянного диска (Railway free и т.п.):
сессия хранится в переменной окружения SESSION_STRING (Volume не нужен),
а сама папка site/ (картинки + манифест) периодически архивируется и
присылается тебе в Telegram, в "Сохранённые сообщения", в виде site.zip —
так ты можешь скачать готовые файлы к себе на компьютер прямо из Telegram,
не заходя на сервер.

Установка:
    pip install telethon

Шаг 1 — получи строку сессии (один раз, локально):
    1. Получи api_id и api_hash на https://my.telegram.org (раздел "API development tools")
    2. Запусти рядом лежащий generate_session.py:
           python generate_session.py
       Введи api_id, api_hash, номер телефона и код из Telegram.
       Скрипт выведет длинную строку — это и есть SESSION_STRING.

Шаг 2 — запуск в Railway:
    Задай переменные окружения во вкладке Variables: API_ID, API_HASH,
    TARGET_BOT, SESSION_STRING. Start Command: python skincheck_sender.py

В Telegram, в "Сохранённых сообщениях", будут появляться архивы site.zip
с подписью прогресса (например "42/226") — каждые BACKUP_EVERY скинов и
в самом конце. Скачивай последний архив, распаковывай — внутри уже готовая
папка site/ с картинками и manifest.json, открывай index.html оттуда же.

Прогресс хранится в progress.txt на диске контейнера — переживает временную
работу процесса, но сбрасывается при полном передеплое/рестарте на бесплатном
плане без Volume (если процесс отработает без рестартов до конца, это не
проблема; если прервётся — просто скачай последний присланный архив и
продолжи с того места, на котором остановился, вручную дописав недостающее).
"""

import asyncio
import random
import os
import re
import json
import shutil
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ==== НАСТРОЙКИ ====
API_ID = int(os.environ.get("API_ID", "12345678"))              # <-- свой api_id (число)
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")      # <-- свой api_hash (строка)
TARGET_BOT = os.environ.get("TARGET_BOT", "@ИмяБота")            # <-- username бота-получателя
SESSION_STRING = os.environ.get("SESSION_STRING", "")             # <-- из generate_session.py

PROGRESS_FILE = "progress.txt"
SITE_DIR = "site"
IMAGES_DIR = os.path.join(SITE_DIR, "images")
MANIFEST_FILE = os.path.join(SITE_DIR, "manifest.json")
ARCHIVE_BASENAME = "site_backup"  # -> site_backup.zip

MIN_DELAY = 5   # секунд между сообщениями (после того как получен ответ)
MAX_DELAY = 10  # секунд

# сколько секунд ждать после ПОСЛЕДНЕГО полученного сообщения от бота,
# прежде чем считать, что ответ на этот запрос закончился
RESPONSE_DEBOUNCE = 2.5
# максимум секунд ждать ответа вообще, если бот молчит
MAX_RESPONSE_WAIT = 20

# каждые сколько скачанных картинок присылать архив-бэкап в Saved Messages
BACKUP_EVERY = 20

MESSAGES = [
    "Скинчек Химицу",
    "Скинчек Исследователь",
    "Скинчек MuAngel",
    "Скинчек MuDemon",
    "Скинчек СтКлаус",
    "Скинчек Professor",
    "Скинчек Pody",
    "Скинчек Mantro",
    "Скинчек Травка",
    "Скинчек Брауни",
    "Скинчек Милш",
    "Скинчек Угли",
    "Скинчек Карамулька",
    "Скинчек Плюша",
    "Скинчек Хинкали",
    "Скинчек Лули",
    "Скинчек Кукло",
    "Скинчек honey",
    "Скинчек Засоня",
    "Скинчек Coffee",
    "Скинчек Старбакс",
    "Скинчек Тортяшка",
    "Скинчек Шарфя",
    "Скинчек Винни",
    "Скинчек Комочек",
    "Скинчек Винчик",
    "Скинчек Любящяя",
    "Скинчек Грустяшка",
    "Скинчек Сладуська",
    "Скинчек Клубняша",
    "Скинчек Малиняша",
    "Скинчек Eva",
    "Скинчек Fujitobi",
    "Скинчек КуМу",
    "Скинчек Наркотик",
    "Скинчек Мукекс",
    "Скинчек Ножки",
    "Скинчек Holdy",
    "Скинчек Квак",
    "Скинчек Крили",
    "Скинчек Летучи",
    "Скинчек Сырок",
    "Скинчек Акуля",
    "Скинчек Платюшко",
    "Скинчек Вампирюка",
    "Скинчек Минипекарь",
    "Скинчек Мужбик",
    "Скинчек Квакша",
    "Скинчек Беззубик",
    "Скинчек Дневная",
    "Скинчек Буджибу",
    "Скинчек Ачи",
    "Скинчек Звездоловитель",
    "Скинчек Дар",
    "Скинчек Аноним",
    "Скинчек Яйко",
    "Скинчек Лилита",
    "Скинчек Диего",
    "Скинчек RainCow",
    "Скинчек Бэнс",
    "Скинчек Кремовый",
    "Скинчек Бумпи",
    "Скинчек Кукурузная",
    "Скинчек Зум",
    "Скинчек Seashell",
    "Скинчек Flyre",
    "Скинчек jelly",
    "Скинчек Berrymilk",
    "Скинчек Zombu",
    "Скинчек ТрупНевесты",
    "Скинчек Зелёный",
    "Скинчек ВикторГранз",
    "Скинчек Filur",
    "Скинчек Oliver",
    "Скинчек Пикселезированный",
    "Скинчек Чайочек",
    "Скинчек Crepy",
    "Скинчек Olivia",
    "Скинчек Жмыхнуло",
    "Скинчек Куст",
    "Скинчек Китэк",
    "Скинчек GeometryDash",
    "Скинчек Дискордя",
    "Скинчек ъвшвфц",
    "Скинчек Space",
    "Скинчек Мутянчик",
    "Скинчек Уютненькое",
    "Скинчек Пчёлка",
    "Скинчек Нью",
    "Скинчек Инопланетянчик",
    "Скинчек Мутяныч",
    "Скинчек АлмазныйРог",
    "Скинчек Resin",
    "Скинчек Ананасик",
    "Скинчек Бууу",
    "Скинчек Гупи",
    "Скинчек Фриппи",
    "Скинчек Лимонный",
    "Скинчек Глиммер",
    "Скинчек Забодака",
    "Скинчек Pusheen",
    "Скинчек Мут",
    "Скинчек Линукс",
    "Скинчек Жрямкалка",
    "Скинчек Тукс",
    "Скинчек ГлазВырви",
    "Скинчек Манга",
    "Скинчек Watermelon",
    "Скинчек Сладенький",
    "Скинчек Соленый",
    "Скинчек Birthday",
    "Скинчек Нормис",
    "Скинчек Сушняк",
    "Скинчек Сожру",
    "Скинчек МаоМао_Ня",
    "Скинчек ЯдерноКислотный",
    "Скинчек Гирляндыш",
    "Скинчек НовиГод",
    "Скинчек ХоХо",
    "Скинчек NewSocks",
    "Скинчек Сливчэ",
    "Скинчек нфт_змейка",
    "Скинчек Мулан",
    "Скинчек Медузики",
    "Скинчек Звон",
    "Скинчек Фариэлла",
    "Скинчек Игрунья",
    "Скинчек Дарелл",
    "Скинчек Аища",
    "Скинчек Тыквуша",
    "Скинчек RobbeWhite",
    "Скинчек Коть",
    "Скинчек Котён",
    "Скинчек Cry_Cherry",
    "Скинчек Bulbak",
    "Скинчек Сковородыч",
    "Скинчек Флаттер",
    "Скинчек Зеленоглазка",
    "Скинчек CherryBoobs",
    "Скинчек Гарри",
    "Скинчек ПЭПСАААА",
    "Скинчек CursedGift",
    "Скинчек MooTyan",
    "Скинчек Толик",
    "Скинчек ВеланикаБля",
    "Скинчек Веланика",
    "Скинчек Роняша",
    "Скинчек Ронички",
    "Скинчек Вероничка",
    "Скинчек Раскраски",
    "Скинчек Лампчка",
    "Скинчек Роняшка",
    "Скинчек БлеБле",
    "Скинчек Кошелечек",
    "Скинчек РонецкоЭмо",
    "Скинчек Вероняша",
    "Скинчек НаШашлыке",
    "Скинчек Какич",
    "Скинчек Зульза",
    "Скинчек Пульпа",
    "Скинчек Электро фритюрница",
    "Скинчек Темо",
    "Скинчек Пушино",
    "Скинчек Апельсиновая",
    "Скинчек Пушина",
    "Скинчек Фарфор",
    "Скинчек Oreo",
    "Скинчек Слипи",
    "Скинчек Shokette",
    "Скинчек Нямням",
    "Скинчек Писька",
    "Скинчек Mummik",
    "Скинчек Zombik",
    "Скинчек Saymeboo",
    "Скинчек HQD",
    "Скинчек Мегумин",
    "Скинчек Улитыч",
    "Скинчек Harrington",
    "Скинчек Попик",
    "Скинчек Аскет",
    "Скинчек Эстет",
    "Скинчек Отдыхашка",
    "Скинчек Сынок",
    "Скинчек Тин",
    "Скинчек УлетелаНах",
    "Скинчек Manifest",
    "Скинчек antibot",
    "Скинчек Лими",
    "Скинчек Gosick",
    "Скинчек Сисюлики",
    "Скинчек Аблизака",
    "Скинчек Голапопа",
    "Скинчек Кривогенит",
    "Скинчек ьья",
    "Скинчек Галя",
    "Скинчек Симпатюля",
    "Скинчек Хуппи",
    "Скинчек Хаппи",
    "Скинчек Мотылёчкек",
    "Скинчек Интересное Чудо",
    "Скинчек Муботер",
    "Скинчек m&ms",
    "Скинчек Флатраж",
    "Скинчек Витушка",
    "Скинчек Ловешка",
    "Скинчек СКИТЛСЫ",
    "Скинчек Заскитлсился",
    "Скинчек Нэт",
    "Скинчек Яблоня",
    "Скинчек RedBull",
    "Скинчек Меовл",
    "Скинчек Мусяэтоты",
    "Скинчек Оэтомумуся",
    "Скинчек Raistlin",
    "Скинчек Фрутигер",
    "Скинчек Блилик",
    "Скинчек Saska",
    "Скинчек Лёша",
    "Скинчек Blueberrygirl",
    "Скинчек Cookiegirl",
    "Скинчек БОУНТЕ",
    "Скинчек РИБА",
    "Скинчек Мутяшка",
    "Скинчек Garnetpau",
    "Скинчек Мятнаявишня",
    "Скинчек Вишнямятная",
]


def sanitize_filename(name: str) -> str:
    # убираем недопустимые в именах файлов символы
    name = name.replace("Скинчек ", "").strip()
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def load_progress() -> int:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
    return 0


def save_progress(index: int) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        f.write(str(index))


def load_manifest() -> list:
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_manifest(manifest: list) -> None:
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


async def send_backup(client: TelegramClient, done: int, total: int) -> None:
    archive_path = shutil.make_archive(ARCHIVE_BASENAME, "zip", SITE_DIR)
    caption = f"Прогресс галереи: {done}/{total}"
    await client.send_file("me", archive_path, caption=caption)
    print(f"    архив отправлен в Сохранённые сообщения ({caption})")


async def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    manifest = load_manifest()

    collected = []
    new_msg_event = asyncio.Event()

    @client.on(events.NewMessage(from_users=TARGET_BOT))
    async def handler(event):
        collected.append(event.message)
        new_msg_event.set()

    start_index = load_progress()
    if start_index > 0:
        print(f"Найден прогресс: продолжаю с сообщения #{start_index + 1} из {len(MESSAGES)}")

    for i in range(start_index, len(MESSAGES)):
        text = MESSAGES[i]
        collected.clear()
        new_msg_event.clear()

        await client.send_message(TARGET_BOT, text)
        print(f"[{i + 1}/{len(MESSAGES)}] отправлено: {text}")

        # ждём ответ(ы) бота: продолжаем, пока сообщения не перестанут приходить
        # (RESPONSE_DEBOUNCE сек тишины) или пока не истечёт MAX_RESPONSE_WAIT
        loop = asyncio.get_event_loop()
        deadline = loop.time() + MAX_RESPONSE_WAIT
        while True:
            timeout = min(RESPONSE_DEBOUNCE, max(0, deadline - loop.time()))
            if timeout <= 0:
                break
            try:
                await asyncio.wait_for(new_msg_event.wait(), timeout=timeout)
                new_msg_event.clear()
            except asyncio.TimeoutError:
                break  # тишина RESPONSE_DEBOUNCE сек — считаем, что ответ закончился

        # скачиваем медиа из всех собранных сообщений-ответов прямо на диск
        # и сразу дописываем их в manifest.json для сайта
        base_name = sanitize_filename(text)
        if collected:
            media_count = 0
            for msg in collected:
                if msg.media:
                    media_count += 1
                    label = base_name if media_count == 1 else f"{base_name} ({media_count})"
                    filepath = os.path.join(IMAGES_DIR, sanitize_filename(label))
                    saved_path = await client.download_media(msg, file=filepath)
                    if saved_path:
                        filename = os.path.basename(saved_path)
                        manifest.append({"name": label, "file": filename})
                        save_manifest(manifest)
                        print(f"    скачано: {label} -> {filename}")
            if media_count == 0:
                print("    (ответ получен, но без медиа)")
        else:
            print("    (бот не ответил за отведённое время)")

        save_progress(i + 1)

        if len(manifest) > 0 and len(manifest) % BACKUP_EVERY == 0:
            await send_backup(client, i + 1, len(MESSAGES))

        if i < len(MESSAGES) - 1:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)

    print(f"Готово, все сообщения отправлены. Картинок в манифесте: {len(manifest)}")
    print(f"Папка с картинками: {IMAGES_DIR}")
    print(f"Файл манифеста: {MANIFEST_FILE}")
    await send_backup(client, len(MESSAGES), len(MESSAGES))
    # Прогресс можно удалить/сбросить вручную, если захочешь прогнать список заново:
    # os.remove(PROGRESS_FILE)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
