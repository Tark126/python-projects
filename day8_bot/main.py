import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 1️⃣ СОСТОЯНИЯ
class OrderState(StatesGroup):
    waiting_for_service = State()
    waiting_for_price = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

# 2️⃣ БАЗА ДАННЫХ
orders_db = {}  # {user_id: {"service": "...", "price": 0}}
users_db = set()  # {user_id1, user_id2, ...} - все кто писал боту

# 3️⃣ INLINE КЛАВИАТУРЫ
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 Оплатить заказ", callback_data="pay_order")],
    [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")]
])

admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="broadcast")],
    [InlineKeyboardButton(text="👥 Пользователей", callback_data="users_count")]
])

# 4️⃣ Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    users_db.add(user_id)  # Сохраняем пользователя
    
    await message.answer("🤖 <b>Привет! Это Магазин 4.0</b>\nТеперь с рассылкой!", reply_markup=main_keyboard, parse_mode="HTML")

# 5️⃣ Команда /admin (для тебя)
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    # Можно добавить проверку на твой ID
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_keyboard, parse_mode="HTML")

# 6️⃣ ОПЛАТА (как в День 11)
@dp.callback_query(F.data == "pay_order")
async def process_pay(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Вводим данные заказа...")
    await callback.message.answer("📝 <b>Шаг 1/2</b>\nНапиши название услуги:")
    await state.set_state(OrderState.waiting_for_service)

@dp.message(OrderState.waiting_for_service)
async def process_service_name(message: Message, state: FSMContext):
    service_name = message.text
    await state.update_data(service=service_name)
    await message.answer(f"✅ Услуга: <b>{service_name}</b>\n\n💰 <b>Шаг 2/2</b>\nВведи сумму оплаты (число):", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_price)

@dp.message(OrderState.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("❌ Ошибка! Введи корректное число (например: 500)")
        return
    
    user_data = await state.get_data()
    service = user_data.get("service", "Неизвестно")
    
    user_id = message.from_user.id
    orders_db[user_id] = {"service": service, "price": price}
    
    receipt = f"""
╔══════════════════════╗
         🧾 <b>ЧЕК ОПЛАТЫ</b>
╚══════════════════════╝

📦 Услуга: <b>{service}</b>
💵 Сумма: <b>{price}₽</b>
👤 ID: <code>{user_id}</code>

✅ <b>Оплата принята!</b>
    """
    
    await message.answer(receipt, parse_mode="HTML")
    await state.clear()

# 7️⃣ МОИ ЗАКАЗЫ
@dp.callback_query(F.data == "my_orders")
async def process_my_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in orders_db:
        order = orders_db[user_id]
        await callback.answer("Ваши заказы:")
        await callback.message.answer(f"""
📋 <b>Ваши заказы:</b>

🔹 Услуга: <b>{order['service']}</b>
🔹 Цена: <b>{order['price']}₽</b>

Статус: <b>Оплачено ✅</b>
        """, parse_mode="HTML")
    else:
        await callback.answer("У вас пока нет заказов")
        await callback.message.answer("📭 У вас пока нет заказов.")

# 8️⃣ РАССЫЛКА (НОВОЕ!)
@dp.callback_query(F.data == "broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Начинаем рассылку...")
    await callback.message.answer("📢 <b>Рассылка</b>\n\nНапиши текст сообщения, которое отправить всем пользователям:")
    await state.set_state(BroadcastState.waiting_for_message)

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    broadcast_text = message.text
    
    await message.answer(f"⏳ <b>Начинаю рассылку...</b>\n\nТекст:\n{broadcast_text}\n\nПользователей: {len(users_db)}")
    
    success_count = 0
    fail_count = 0
    
    # Отправляем всем
    for user_id in users_db:
        try:
            await bot.send_message(user_id, f"📢 <b>Рассылка</b>\n\n{broadcast_text}", parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)  # Пауза чтобы не забанили
        except:
            fail_count += 1
    
    await message.answer(f"✅ <b>Рассылка завершена!</b>\n\n✅ Доставлено: {success_count}\n❌ Не доставлено: {fail_count}")
    await state.clear()

# 9️⃣ СЧЁТЧИК ПОЛЬЗОВАТЕЛЕЙ
@dp.callback_query(F.data == "users_count")
async def process_users_count(callback: CallbackQuery):
    await callback.answer(f"Всего пользователей: {len(users_db)}")
    await callback.message.answer(f"👥 <b>Пользователей:</b> {len(users_db)}")

async def main():
    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
