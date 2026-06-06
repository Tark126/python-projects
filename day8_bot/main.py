import asyncio
from bot_instance import dp, bot
import database
import handlers

async def main():
    database.init_db()
    print("✅ Бот запущен в модульном режиме!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
