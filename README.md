# student-projects

Kijiji iPhone scraper with Telegram bot command control.

## Run

1. Install dependencies:
   `pip install -r requirements.txt`
2. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Start scraper:
   `python /home/runner/work/student-projects/student-projects/kijiji_iphone_scraper.py`

On startup, the bot sends `/start` and `/stop` instructions and waits 30 seconds for input.
