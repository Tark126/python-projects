import asyncio
import sqlite3
import random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN, ADMIN_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, inviter_id INTEGER DEFAULT 0, balance INTEGER DEFAULT 0)''')
    try: cursor.execute('ALTER TABLE users ADD COLUMN inviter_id INTEGER DEFAULT 0')
    except: pass
    try: cursor.execute('ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0')
    except: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT, price INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, discount_percent INTEGER)''')
    conn.commit()
    conn.close()

def add_user(user_id, inviter_id=0):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO users (user_id, inviter_id) VALUES (?, ?) 
                      ON CONFLICT(user_id) DO UPDATE SET inviter_id = CASE WHEN inviter_id = 0 THEN excluded.inviter_id ELSE inviter_id END''', (user_id, inviter_id))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def add_order(user_id, service, price):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, service, price) VALUES (?, ?, ?)', (user_id, service, price))
    
    cursor.execute('SELECT inviter_id FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0] > 0:
        inviter_id = res[0]
        bonus = price // 5  # 🔥 ТВОЕ ИЗМЕНЕНИЕ: 20% бонуса (деление на 5)
        update_balance(inviter_id, bonus)
        conn.close()
        asyncio.create_task(notify_inviter(inviter_id, bonus))
        return
    conn.commit()
    conn.close()

async def notify_inviter(inviter_id, bonus):
    try:
        await bot.send_message(inviter_id, f"🎉 <b>Твой друг сделал заказ!</b>\n💰 Ты получил <b>{bonus}₽</b> на свой баланс!", parse_mode="HTML")
    except: pass

def get_orders(user_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT service, price FROM orders WHERE user_id = ?', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_all_users():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    return [u[0] for u in users]

def add_promo(code, percent):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO promos (code, discount_percent) VALUES (?, ?)', (code.upper(), percent))
    conn.commit()
    conn.close()

def get_promo(code):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT discount_percent FROM promos WHERE code = ?', (code.upper(),))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

init_db()
# =================================================

PRODUCTS = {
    "smm": {"name": "SMM Продвижение", "price": 1500, "desc": "Накрутка 1000 живых подписчиков за 24 часа.", "img": "https://picsum.photos/seed/smm/800/600", "delivery_type": "text", "delivery_value": "🔑 Ваш промокод: SUPER_SMM_2024"},
    "design": {"name": "Разработка Логотипа", "price": 2500, "desc": "Уникальный логотип для твоего бренда.", "img": "https://picsum.photos/seed/design/800/600", "delivery_type": "file", "delivery_value": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
    "site": {"name": "Сайт-визитка", "price": 5000, "desc": "Современный одностраничный сайт.", "img": "https://picsum.photos/seed/site/800/600", "delivery_type": "text", "delivery_value": "🔗 Ссылка: https://example.com/mysite\nЛогин: admin | Пароль: 12345"},
    # 👇 ЗДЕСЬ МОЖЕТ БЫТЬ ТВОЙ ТОВАР, КОТОРЫЙ ТЫ ДОБАВИЛ ВЧЕРА! 👇
    "my_product": {"name": "Мой крутой товар", "price": 3000, "desc": "Сделано мной лично!", "img": "https://picsum.photos/seed/myproduct/800/600", "delivery_type": "text", "delivery_value": "Секретный код: 1423"}
}

class OrderState(StatesGroup):
    waiting_for_promo = State()
    waiting_for_payment = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

def get_catalog_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for prod_id, prod_data in PRODUCTS.items():
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"🛒 {prod_data['name']} — {prod_data['price']}₽", callback_data=f"view_{prod_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return keyboard

def get_product_keyboard(prod_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить этот товар", callback_data=f"buy_{prod_id}")],
        [InlineKeyboardButton(text="🔙 Вернуться в каталог", callback_data="catalog")]
    ])

def get_payment_keyboard(balance, price):
    btns = []
    if balance >= price:
        btns.append([InlineKeyboardButton(text=f"💰 Оплатить с баланса ({balance}₽)", callback_data="pay_balance")])
    else:
        btns.append([InlineKeyboardButton(text=f"💳 На балансе мало ({balance}₽)", callback_data="pay_balance_low")])
    
    btns.append([InlineKeyboardButton(text="💳 Оплатить картой", callback_data="pay_card")])
    btns.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog"), InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
    [InlineKeyboardButton(text="💰 Мой баланс", callback_data="my_balance"), InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
])

admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="broadcast")],
    [InlineKeyboardButton(text="👥 Пользователей", callback_data="users_count")]
])

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    inviter_id = 0
    parts = message.text.split()
    if len(parts) > 1 and parts[1].startswith('ref_'):
        try:
            inviter_id = int(parts[1].split('_')[1])
            if inviter_id == user_id: inviter_id = 0
        except ValueError: inviter_id = 0
    add_user(user_id, inviter_id)
    
    if inviter_id > 0:
        await message.answer("👋 <b>Добро пожаловать!</b>\nТы зарегистрировался по приглашению.\nТвой друг получит бонус после твоего первого заказа! 🎁", reply_markup=main_keyboard, parse_mode="HTML")
    else:
        await message.answer("🔥 <b>Привет! Это лучший магазин в Telegram.</b>\nЯ сделал этого бота сам!\n\nВыбирай товар в каталоге 👇", reply_markup=main_keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "help")
async def cmd_help(callback: CallbackQuery):
    text = "❓ <b>Помощь и FAQ</b>\n\n" \
           "1️⃣ <b>Как купить?</b> Зайди в 'Каталог', выбери товар и нажми 'Купить'.\n" \
           "2️⃣ <b>Как получить скидку?</b> При покупке введи промокод (или напиши 'нет').\n" \
           "3️⃣ <b>Как заработать?</b> Нажми 'Мой баланс', скопируй ссылку и отправь другу. За его покупку ты получишь 20%!\n\n" \
           "Если есть вопросы, пиши админу: @ТВОЙ_НИК"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 <b>Доступ запрещён!</b>", parse_mode="HTML")
        return
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_keyboard, parse_mode="HTML")

@dp.message(Command("addpromo"))
async def cmd_add_promo(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        add_promo(parts[1].upper(), int(parts[2]))
        await message.answer(f"✅ Промокод <b>{parts[1].upper()}</b> ({parts[2]}%) успешно создан!", parse_mode="HTML")
    except:
        await message.answer("❌ Ошибка! Формат: <code>/addpromo КОД ПРОЦЕНТ</code>", parse_mode="HTML")

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.answer("🛒 <b>Выберите товар из нашего каталога:</b>", reply_markup=get_catalog_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("view_"))
async def show_product(callback: CallbackQuery):
    prod_id = callback.data.split("_")[1]
    product = PRODUCTS.get(prod_id)
    if not product: return await callback.answer("Товар не найден!", show_alert=True)
    
    text = f"🖼 <b>{product['name']}</b>\n\n{product['desc']}\n\n💰 <b>Цена: {product['price']}₽</b>"
    await callback.message.answer_photo(photo=product['img'], caption=text, reply_markup=get_product_keyboard(prod_id), parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery, state: FSMContext):
    prod_id = callback.data.split("_")[1]
    product = PRODUCTS.get(prod_id)
    if not product: return
    await state.update_data(service=product['name'], price=product['price'])
    await callback.message.answer(f"✅ Вы выбрали: <b>{product['name']}</b>\n\n🎟 <b>Есть промокод?</b>\nНапиши его (или напиши <b>нет</b>):", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_promo)

@dp.message(OrderState.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    user_data = await state.get_data()
    service = user_data.get("service")
    original_price = user_data.get("price")
    promo_input = message.text.strip().upper()
    final_price = original_price
    discount_text = ""

    if promo_input != "НЕТ":
        discount_percent = get_promo(promo_input)
        if discount_percent:
            final_price = original_price - (original_price * discount_percent // 100)
            discount_text = f"\n🎉 <b>Промокод применён! Скидка: {discount_percent}%</b>"
        else:
            discount_text = f"\n⚠️ <b>Промокод не найден. Оплата по полной цене.</b>"

    await state.update_data(final_price=final_price, discount_text=discount_text)
    balance = get_balance(message.from_user.id)
    
    await message.answer(f"━━━━━━━━━━━━━━━━━━\n🧾 <b>ИТОГ К ОПЛАТЕ</b>\n━━━━━━━━━━━━━━━━━━\n\n📦 Услуга: <b>{service}</b>\n💰 Сумма: <b>{final_price}₽</b>{discount_text}\n\n💳 <b>Выберите способ оплаты:</b>", reply_markup=get_payment_keyboard(balance, final_price), parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_payment)

@dp.callback_query(F.data == "pay_balance", OrderState.waiting_for_payment)
async def pay_with_balance(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    service = user_data.get("service")
    final_price = user_data.get("final_price")
    user_id = callback.from_user.id
    
    balance = get_balance(user_id)
    if balance >= final_price:
        update_balance(user_id, -final_price)
        add_order(user_id, service, final_price)
        await state.clear()
        await callback.message.delete() # Удаляем меню оплаты для чистоты
        await deliver_product(callback.message, service, final_price, user_id)
    else:
        await callback.answer("Недостаточно средств на балансе!", show_alert=True)

@dp.callback_query(F.data == "pay_balance_low", OrderState.waiting_for_payment)
async def pay_balance_low(callback: CallbackQuery):
    await callback.answer("Недостаточно средств! Пополните баланс или выберите карту.", show_alert=True)

@dp.callback_query(F.data == "pay_card", OrderState.waiting_for_payment)
async def pay_with_card(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    final_price = user_data.get("final_price")
    mock_link = f"https://yookassa.ru/mock_payment_{random.randint(10000, 99999)}"
    
    await callback.message.answer(f"🔗 <b>Ссылка на безопасную оплату:</b>\n<code>{mock_link}</code>\n\n<i>(Это симуляция. В реальности здесь была бы страница банка)</i>\n\nНажми кнопку ниже, когда 'оплатишь':", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я оплатил", callback_data="confirm_mock_payment")]]), parse_mode="HTML")

@dp.callback_query(F.data == "confirm_mock_payment", OrderState.waiting_for_payment)
async def confirm_mock_payment(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    service = user_data.get("service")
    final_price = user_data.get("final_price")
    user_id = callback.from_user.id
    
    add_order(user_id, service, final_price)
    await state.clear()
    await callback.message.delete()
    await deliver_product(callback.message, service, final_price, user_id)

async def deliver_product(message, service, final_price, user_id):
    product = next((p for p in PRODUCTS.values() if p["name"] == service), None)
    if product:
        if product["delivery_type"] == "text":
            await message.answer(f"📦 <b>ВАШ ТОВАР:</b>\n\n<code>{product['delivery_value']}</code>\n\n<i>⚠️ Скопируйте и сохраните эту информацию!</i>", parse_mode="HTML")
        elif product["delivery_type"] == "file":
            await message.answer_document(document=product["delivery_value"], caption="📦 <b>Ваш товар готов! Скачивайте файл.</b>", parse_mode="HTML")
    
    receipt = f"━━━━━━━━━━━━━━━━━━\n✅ <b>УСПЕШНАЯ ОПЛАТА</b>\n━━━━━━━━━━━━━━━━━━\n\n📦 Услуга: <b>{service}</b>\n💰 Сумма: <b>{final_price}₽</b>\n👤 ID: <code>{user_id}</code>\n\n🎉 <b>Спасибо за покупку!</b>"
    await message.answer(receipt, parse_mode="HTML", reply_markup=main_keyboard)

@dp.callback_query(F.data == "my_orders")
async def process_my_orders(callback: CallbackQuery):
    orders = get_orders(callback.from_user.id)
    if orders:
        text = "📋 <b>Ваши заказы:</b>\n\n" + "".join([f"🔹 <b>#{i}</b> {s} — <b>{p}₽</b>\n" for i, (s, p) in enumerate(orders, 1)])
        await callback.message.answer(text + "\n✅ Статус: <b>Оплачено и выдано</b>", parse_mode="HTML")
    else:
        await callback.message.answer("📭 У вас пока нет заказов.\nЗагляните в 🛒 Каталог!")

@dp.callback_query(F.data == "my_balance")
async def process_my_balance(callback: CallbackQuery):
    balance = get_balance(callback.from_user.id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
    await callback.message.answer(f"💰 <b>Твой баланс: {balance}₽</b>\n\n🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n🎁 Отправь её другу! За его первую покупку ты получишь 20% на баланс.", parse_mode="HTML")

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    await callback.message.answer("📢 <b>Рассылка</b>\n\nНапиши текст сообщения:", parse_mode="HTML")
    await state.set_state(BroadcastState.waiting_for_message)

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    users = get_all_users()
    await message.answer(f"⏳ <b>Начинаю рассылку...</b>\n\nПользователей: {len(users)}", parse_mode="HTML")
    success = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 <b>Важное обновление!</b>\n\n{message.text}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05) # Защита от спам-блока Telegram
        except: pass
    await message.answer(f"✅ <b>Рассылка завершена!</b>\n\nУспешно доставлено: {success}", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "users_count")
async def process_users_count(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    await callback.message.answer(f"👥 <b>Пользователей в базе:</b> {len(get_all_users())}", parse_mode="HTML")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("👋 <b>Главное меню</b>", reply_markup=main_keyboard, parse_mode="HTML")
    await callback.answer()

async def main():
    print("✅ Бот запущен в премиальном режиме!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
