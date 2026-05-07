# student-projects

Kijiji iPhone scraper with Telegram bot command control.

## Run

1. Install dependencies:
   `pip install -r requirements.txt`
2. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `SCRAPER_HEADLESS` (`true`/`false`, optional)
3. Start scraper:
   `python kijiji_iphone_scraper.py`

On startup, the bot sends `/start` and `/stop` instructions and waits 30 seconds for input.
