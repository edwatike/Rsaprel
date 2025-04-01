import feedparser
import logging
from datetime import datetime
import pytz
from telegram import Bot
import asyncio
import json
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_FEEDS = [
    "https://towardsdatascience.com/feed",
    "https://venturebeat.com/feed/",
    "https://rss.app/feeds/PNcbNOcr3uiLMKOm.xml"
]
SENT_POSTS_FILE = "sent_posts.json"
START_DATE = os.getenv("START_DATE", "2025-03-03")
START_DATE = datetime.strptime(START_DATE, "%Y-%m-%d").replace(tzinfo=pytz.UTC)

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
    escaped_text = escape_markdown(text[:4096])
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=escaped_text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
        logger.info(f"Сообщение отправлено: {text[:100]}...")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {str(e)}")

# Функция для проверки RSS-лент
async def check_feeds(bot):
    logger.info("Началась проверка RSS-лент")
    sent_posts = load_sent_posts()

    for feed_url in RSS_FEEDS:
        logger.info(f"Обрабатываю ленту: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        if not hasattr(feed, 'entries'):
            logger.error(f"Не удалось получить записи из {feed_url}")
            continue
            
        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                published_date = datetime(*published[:6], tzinfo=pytz.UTC)
                if published_date < START_DATE:
                    continue

            post_id = entry.get("id") or entry.get("link") or entry.get("title")
            if not post_id or post_id in sent_posts:
                continue

            title = entry.get("title", "Без заголовка")
            link = entry.get("link", "")
            message = f"{title}\n{link}" if link else title

            await send_telegram_message(bot, message)
            save_sent_post(post_id)

    logger.info("Проверка RSS-лент завершена")

# Основная функция
async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Вебхук удалён")
    await check_feeds(bot)

if __name__ == "__main__":
    logger.info("Запуск бота RSS-уведомлений")
    asyncio.run(main())
