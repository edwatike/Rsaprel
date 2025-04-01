import feedparser
import logging
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import asyncio
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = "7914883717:AAGRHrHXN_ZakbgMwNRDCs4nZob3mavLojw"
CHAT_ID = "@grokkkk"  # ID канала оставлен как указали
RSS_FEEDS = [
    "https://towardsdatascience.com/feed",
    "https://venturebeat.com/feed/",
    "https://rss.app/feeds/PNcbNOcr3uiLMKOm.xml"
]
CHECK_INTERVAL = 300  # 5 минут
SENT_POSTS_FILE = "sent_posts.json"

# Функция для получения даты от пользователя
def get_start_date_from_user():
    while True:
        try:
            date_str = input("Введите дату начала проверки (ММ-ДД или ГГГГ-ММ-ДД): ")
            if len(date_str.split('-')) == 2:
                month, day = map(int, date_str.split('-'))
                return datetime(2025, month, day, tzinfo=pytz.UTC)
            else:
                return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
        except ValueError:
            print("Неверный формат даты. Используйте ММ-ДД (например, 03-31) или ГГГГ-ММ-ДД (например, 2025-03-31)")

# Функция для загрузки отправленных записей
def load_sent_posts():
    try:
        with open(SENT_POSTS_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        logger.info("Файл sent_posts.json не найден, создаю новый")
        return set()

# Функция для сохранения отправленных записей
def save_sent_post(post_id):
    sent_posts = load_sent_posts()
    sent_posts.add(post_id)
    with open(SENT_POSTS_FILE, "w") as f:
        json.dump(list(sent_posts), f)

# Функция для экранирования специальных символов в MarkdownV2
def escape_markdown(text):
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Функция для отправки сообщения в Telegram
async def send_telegram_message(bot, text):
    escaped_text = escape_markdown(text[:4096])  # Ограничение Telegram на длину сообщения
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=escaped_text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True  # Отключаем превью ссылок для чистоты
        )
        logger.info(f"Сообщение отправлено: {text[:100]}...")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {str(e)}")

# Функция для проверки RSS-лент
async def check_feeds(bot, start_date):
    logger.info("Началась проверка RSS-лент")
    sent_posts = load_sent_posts()

    for feed_url in RSS_FEEDS:
        logger.info(f"Обрабатываю ленту: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        if not hasattr(feed, 'entries'):
            logger.error(f"Не удалось получить записи из {feed_url}")
            continue
            
        for entry in feed.entries:
            # Получаем дату публикации
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                published_date = datetime(*published[:6], tzinfo=pytz.UTC)
                if published_date < start_date:
                    continue

            # Уникальный идентификатор поста
            post_id = entry.get("id") or entry.get("link") or entry.get("title")
            if not post_id or post_id in sent_posts:
                continue

            # Формируем сообщение
            title = entry.get("title", "Без заголовка")
            link = entry.get("link", "")
            message = f"{title}\n{link}" if link else title

            await send_telegram_message(bot, message)
            save_sent_post(post_id)

    logger.info("Проверка RSS-лент завершена")

# Основная функция
async def main():
    START_DATE = get_start_date_from_user()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Удаляем вебхук если он есть
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Вебхук удалён")

    # Первоначальная проверка
    logger.info("Выполняю первоначальную проверку RSS-лент")
    await check_feeds(bot, START_DATE)

    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_feeds, "interval", seconds=CHECK_INTERVAL, args=(bot, START_DATE))
    scheduler.start()
    logger.info("Планировщик запущен")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    logger.info("Запуск бота RSS-уведомлений")
    asyncio.run(main())
