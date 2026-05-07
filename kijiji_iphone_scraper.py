import asyncio
import json
import os
from threading import Event, Lock

from seleniumbase import Driver
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


URL = "https://www.kijiji.ca/b-cell-phone/canada/iphone/k0c760l0?sort=dateDesc&view=list"
JSON_FILE = "kijiji_data.json"
SCRAPE_INTERVAL_HOURS = 12
SECONDS_PER_HOUR = 60 * 60
SCRAPE_INTERVAL_SECONDS = SCRAPE_INTERVAL_HOURS * SECONDS_PER_HOUR
IDLE_CHECK_SECONDS = 2
INITIAL_WAIT_SECONDS = 30
SKIP_INITIAL_LISTINGS = 6

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
HEADLESS = os.getenv("SCRAPER_HEADLESS", "false").lower() == "true"


scraper_running = False
scraper_state_lock = Lock()
initial_command_received = Event()


async def safe_send_telegram(bot, message: str) -> None:
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except TelegramError as exc:
        print(f"Telegram API error: {exc}")


def set_scraper_running(value: bool) -> None:
    global scraper_running
    with scraper_state_lock:
        scraper_running = value


def is_scraper_running() -> bool:
    with scraper_state_lock:
        return scraper_running


def scrape_data():
    driver = Driver(uc=True, headless=HEADLESS)
    driver.get(URL)

    listings = WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "section[data-testid='listing-card']")
        )
    )

    # Skip top featured/sponsored cards that are often repeated noise.
    listings = listings[SKIP_INITIAL_LISTINGS:]
    scraped_data = []

    for index, listing in enumerate(listings):
        try:
            product_url = listing.find_element(
                By.CSS_SELECTOR,
                "a[data-testid='listing-link']",
            ).get_attribute("href")

            title = listing.find_element(
                By.CSS_SELECTOR,
                "h3[data-testid='listing-title']",
            ).text

            price = listing.find_element(
                By.CSS_SELECTOR,
                "p[data-testid='listing-price']",
            ).text

            time_data = listing.find_element(
                By.CSS_SELECTOR,
                "p[data-testid='listing-date']",
            ).text.strip()

            scraped_data.append(
                {
                    "product_url": product_url,
                    "title": title,
                    "price": price,
                    "time": time_data,
                }
            )

        except Exception as exc:
            print(f"Failed to parse listing data at index {index}: {exc}")

    driver.quit()
    return scraped_data


def run_scraper_cycle():
    print("\nRunning scraper...\n")
    new_data = scrape_data()

    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            old_data = json.load(file)
    else:
        old_data = []

    old_urls = {item["product_url"] for item in old_data}
    new_items = [item for item in new_data if item["product_url"] not in old_urls]

    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(new_data, file, ensure_ascii=False, indent=4)

    return new_items


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != CHAT_ID:
        return

    set_scraper_running(True)
    initial_command_received.set()

    try:
        await update.message.reply_text("✅ Scraper started. Send /stop anytime to pause.")
    except TelegramError as exc:
        print(f"Telegram API error: {exc}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != CHAT_ID:
        return

    set_scraper_running(False)
    initial_command_received.set()

    try:
        await update.message.reply_text("⏸️ Scraper paused. Send /start anytime to resume.")
    except TelegramError as exc:
        print(f"Telegram API error: {exc}")


async def wait_with_pause(seconds: int) -> None:
    for _ in range(seconds):
        if not is_scraper_running():
            print("Scraper paused during wait interval.")
            return
        await asyncio.sleep(1)


async def wait_for_initial_command(bot) -> None:
    await safe_send_telegram(
        bot,
        "🤖 Kijiji iPhone scraper control is ready.\n"
        "Use /start to run scraping or /stop to keep it paused.\n"
        f"Waiting {INITIAL_WAIT_SECONDS} seconds for your command...",
    )

    for _ in range(INITIAL_WAIT_SECONDS):
        if initial_command_received.is_set():
            return
        await asyncio.sleep(1)

    set_scraper_running(False)
    await safe_send_telegram(
        bot,
        f"⏱️ No command received in {INITIAL_WAIT_SECONDS} seconds. "
        "Scraper is paused. Send /start to begin.",
    )


async def scraper_controller(bot) -> None:
    while True:
        if not is_scraper_running():
            await asyncio.sleep(IDLE_CHECK_SECONDS)
            continue

        new_items = await asyncio.to_thread(run_scraper_cycle)

        if new_items:
            print(f"\n{len(new_items)} NEW ITEMS FOUND!\n")
            for item in new_items:
                message = (
                    "🔥 New Product Found!\n\n"
                    f"📌 Title: {item['title']}\n"
                    f"💰 Price: {item['price']}\n"
                    f"⏰ Time: {item['time']}\n"
                    f"🔗 Link: {item['product_url']}"
                )
                print(message)
                await safe_send_telegram(bot, message)
        else:
            print("No new items found.")

        print(f"\nWaiting {SCRAPE_INTERVAL_HOURS} hours...\n")
        await wait_with_pause(SCRAPE_INTERVAL_SECONDS)


async def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables before running.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))

    await app.initialize()
    await app.start()

    if app.updater is None:
        print(
            "Telegram updater could not be started. "
            "Check TELEGRAM_BOT_TOKEN and your network connection."
        )
        await app.stop()
        await app.shutdown()
        return

    await app.updater.start_polling(drop_pending_updates=True)

    await wait_for_initial_command(app.bot)
    await scraper_controller(app.bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down scraper.")
