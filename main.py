import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import router

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    # Initialize Bot instance with default properties (e.g. parse_mode="HTML")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    
    # Initialize Dispatcher
    dp = Dispatcher()
    
    # Include the router from handlers.py
    dp.include_router(router)
    
    # Start polling
    print("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")
