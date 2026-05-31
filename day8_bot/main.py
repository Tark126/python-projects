import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Я бот-магазин. Напиши мне что-нибудь.")

# Обработчик любого текста (Эхо)
@dp.message()
async def echo(message: types.Message):
    await message.answer(f"🔹 Ты написал: {message.text}")

# Запуск
async def main():
    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())