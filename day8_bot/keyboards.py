from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from data import PRODUCTS

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
    btns.append([InlineKeyboardButton(text="💳 Оплатить на карту", callback_data="pay_card")])
    btns.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog"), InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
    [InlineKeyboardButton(text="💰 Мой баланс", callback_data="my_balance"), InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
])

admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")],
    [InlineKeyboardButton(text=" Пользователи", callback_data="users_count")],
    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
    [InlineKeyboardButton(text="⭐ Отзывы", callback_data="reviews")]
])
