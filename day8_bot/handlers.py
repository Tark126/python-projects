import asyncio
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot_instance import bot, dp
from database import (add_user, get_balance, create_order, update_order_status, 
                      get_order_by_id, add_order, pay_existing_order, get_orders, get_all_users, 
                      add_promo, get_promo, get_stats, update_balance, 
                      add_review, get_all_reviews, has_reviewed)
from config import ADMIN_ID, PAYMENT_DETAILS
from data import PRODUCTS
from states import OrderState, BroadcastState, ReviewState
from keyboards import (get_catalog_keyboard, get_product_keyboard, get_payment_keyboard, 
                       main_keyboard, admin_keyboard)

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def send_admin_notification(text):
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except: pass

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
    
    is_new = add_user(user_id, inviter_id)
    if is_new:
        username = message.from_user.username or "нет"
        await send_admin_notification(f"👤 <b>Новый пользователь!</b>\nID: {user_id}\nUsername: @{username}")
    
    await message.answer("🔥 <b>Привет! Это лучший магазин в Telegram.</b>\nВыбирай товар в каталоге 👇", reply_markup=main_keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "help")
async def cmd_help(callback: CallbackQuery):
    text = "❓ <b>Помощь</b>\n\n1️⃣ Выбери товар.\n2️⃣ Введи промокод (или 'нет').\n3️⃣ Оплати с баланса или на карту.\n4️⃣ Получи товар!"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("🚫 Доступ запрещён!", parse_mode="HTML")
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_keyboard, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("🚫 Доступ запрещён!", parse_mode="HTML")
    stats = get_stats()
    text = f"📊 <b>СТАТИСТИКА МАГАЗИНА</b>\n\n <b>Всего пользователей:</b> {stats['total_users']}\n📦 <b>Всего заказов:</b> {stats['total_orders']}\n✅ <b>Оплачено:</b> {stats['paid_orders']}\n <b>Ожидают оплаты:</b> {stats['pending_orders']}\n💰 <b>Общая выручка:</b> {stats['total_revenue']}₽\n\n"
    if stats['top_products']:
        text += f"🏆 <b>ТОП ТОВАРОВ:</b>\n"
        for i, (service, count, revenue) in enumerate(stats['top_products'], 1):
            text += f"{i}. {service} — <b>{count} продаж</b> ({revenue}₽)\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("reviews"))
async def cmd_reviews(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("🚫 Доступ запрещён!", parse_mode="HTML")
    reviews = get_all_reviews()
    if not reviews: return await message.answer("📭 Отзывов пока нет.")
    text = "⭐ <b>ПОСЛЕДНИЕ ОТЗЫВЫ:</b>\n\n"
    for service, rating, comment in reviews:
        stars = "⭐" * rating
        text += f"📦 <b>{service}</b> ({stars}/5)\n💬 {comment}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("addpromo"))
async def cmd_add_promo(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        add_promo(parts[1].upper(), int(parts[2]))
        await message.answer(f"✅ Промокод <b>{parts[1].upper()}</b> ({parts[2]}%) создан!", parse_mode="HTML")
    except: await message.answer("❌ Формат: <code>/addpromo КОД ПРОЦЕНТ</code>", parse_mode="HTML")

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.answer("🛒 <b>Выберите товар:</b>", reply_markup=get_catalog_keyboard(), parse_mode="HTML")

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
    await callback.message.answer(f"✅ Вы выбрали: <b>{product['name']}</b>\n\n🎟 <b>Есть промокод?</b>\nНапиши его (или <b>нет</b>):", parse_mode="HTML")
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
        else: discount_text = f"\n⚠️ <b>Промокод не найден.</b>"
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
    existing_order_id = user_data.get("order_id")
    
    balance = get_balance(user_id)
    if balance >= final_price:
        update_balance(user_id, -final_price)
        if existing_order_id:
            pay_existing_order(existing_order_id, user_id, service, final_price)
        else:
            add_order(user_id, service, final_price)
        
        await state.clear()
        await callback.message.delete()
        username = callback.from_user.username or "нет"
        await send_admin_notification(f"💰 <b>Новая оплата с баланса!</b>\n📦 Услуга: {service}\n💸 Сумма: {final_price}₽\n👤 От: @{username} (ID: {user_id})")
        await deliver_product(callback.message, service, final_price, user_id)
    else: await callback.answer("Недостаточно средств!", show_alert=True)

@dp.callback_query(F.data == "pay_card", OrderState.waiting_for_payment)
async def pay_with_card(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    service = user_data.get("service")
    final_price = user_data.get("final_price")
    user_id = callback.from_user.id
    existing_order_id = user_data.get("order_id")
    
    order_id = existing_order_id if existing_order_id else create_order(user_id, service, final_price)
    username = callback.from_user.username or "нет"
    
    user_msg = f"💳 <b>Оплата заказа #{order_id}</b>\n\nПереведите <b>{final_price}₽</b> на реквизиты:\n<code>{PAYMENT_DETAILS}</code>\n\nПосле перевода нажмите кнопку ниже, и администратор подтвердит оплату."
    admin_msg = f"🔔 <b>Заявка на оплату картой!</b>\n📦 Заказ #{order_id}: {service}\n💰 Сумма: {final_price}₽\n👤 От: @{username} (ID: {user_id})\n\nПроверьте банк и подтвердите:"
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")]
    ])
    await callback.message.answer(user_msg, parse_mode="HTML")
    await bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_kb, parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    order_id = int(callback.data.split("_")[1])
    order = get_order_by_id(order_id)
    if not order: return await callback.answer("Заказ не найден!", show_alert=True)
    user_id, service, price = order
    update_order_status(order_id, "paid")
    await callback.message.edit_text(f"✅ <b>Заказ #{order_id} ОПЛАЧЕН И ПОДТВЕРЖДЕН!</b>\nТовар выдан пользователю.", parse_mode="HTML")
    try: await deliver_product_to_user(user_id, service, price)
    except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    order_id = int(callback.data.split("_")[1])
    update_order_status(order_id, "rejected")
    await callback.message.edit_text(f"❌ <b>Заказ #{order_id} ОТКЛОНЕН.</b>", parse_mode="HTML")

async def deliver_product(message, service, final_price, user_id):
    product = next((p for p in PRODUCTS.values() if p["name"] == service), None)
    if product:
        if product["delivery_type"] == "text":
            await message.answer(f"📦 <b>ВАШ ТОВАР:</b>\n\n<code>{product['delivery_value']}</code>", parse_mode="HTML")
        elif product["delivery_type"] == "file":
            await message.answer_document(document=product["delivery_value"], caption=" <b>Ваш товар готов!</b>", parse_mode="HTML")
    
    review_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"review_start_{service}")]])
    receipt = f"━━━━━━━━━━━━━━━━━━\n✅ <b>УСПЕШНАЯ ОПЛАТА</b>\n━━━━━━━━━━━━━━━━━━\n\n Услуга: <b>{service}</b>\n💰 Сумма: <b>{final_price}₽</b>\n\n🎉 <b>Спасибо за покупку!</b>"
    await message.answer(receipt, reply_markup=review_kb, parse_mode="HTML")

async def deliver_product_to_user(user_id, service, price):
    product = next((p for p in PRODUCTS.values() if p["name"] == service), None)
    if product:
        if product["delivery_type"] == "text":
            await bot.send_message(user_id, f"✅ <b>Оплата подтверждена!</b>\n\n📦 <b>ВАШ ТОВАР:</b>\n<code>{product['delivery_value']}</code>", parse_mode="HTML")
        elif product["delivery_type"] == "file":
            await bot.send_document(user_id, document=product["delivery_value"], caption="✅ Оплата подтверждена! Ваш товар:", parse_mode="HTML")
    
    review_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"review_start_{service}")]])
    await bot.send_message(user_id, " <b>Спасибо за покупку!</b> Будем рады вашему отзыву:", reply_markup=review_kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("review_start_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    service = callback.data.split("_")[2]
    if has_reviewed(callback.from_user.id, service):
        return await callback.answer("⚠️ Вы уже оставили отзыв на эту услугу!", show_alert=True)

    await state.update_data(service=service)
    stars_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="rate_1"), InlineKeyboardButton(text="2", callback_data="rate_2"), InlineKeyboardButton(text="3", callback_data="rate_3"), InlineKeyboardButton(text="4", callback_data="rate_4"), InlineKeyboardButton(text="5", callback_data="rate_5")]
    ])
    await callback.message.answer("⭐ <b>Как вы оцениваете качество услуги?</b>", reply_markup=stars_kb, parse_mode="HTML")
    await state.set_state(ReviewState.waiting_for_rating)
    await callback.answer()

@dp.callback_query(F.data.startswith("rate_"), ReviewState.waiting_for_rating)
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await callback.message.answer("💬 <b>Напишите короткий отзыв:</b>", parse_mode="HTML")
    await state.set_state(ReviewState.waiting_for_comment)
    await callback.answer()

@dp.message(ReviewState.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    user_data = await state.get_data()
    service = user_data.get("service")
    rating = user_data.get("rating")
    comment = message.text
    
    add_review(message.from_user.id, service, rating, comment)
    await state.clear()
    
    stars = "⭐" * rating
    await message.answer(f"✅ <b>Спасибо за ваш отзыв!</b>\n{stars} ({rating}/5)", parse_mode="HTML")
    await send_admin_notification(f"⭐ <b>Новый отзыв!</b>\n📦 {service}\nОценка: {stars}\n💬 {comment}")

@dp.callback_query(F.data == "reviews")
async def process_reviews(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    reviews = get_all_reviews()
    if not reviews: return await callback.message.answer("📭 Отзывов пока нет.")
    text = "⭐ <b>ПОСЛЕДНИЕ ОТЗЫВЫ:</b>\n\n"
    for service, rating, comment in reviews:
        stars = "⭐" * rating
        text += f"📦 <b>{service}</b> ({stars}/5)\n💬 {comment}\n\n"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "my_orders")
async def process_my_orders(callback: CallbackQuery):
    orders = get_orders(callback.from_user.id)
    if not orders: return await callback.message.answer("📭 У вас пока нет заказов.")
        
    text = "📋 <b>Ваши заказы:</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for i, (oid, s, p, status) in enumerate(orders, 1):
        status_emoji = "✅" if status == "paid" else "" if status == "pending" else ""
        text += f"🔹 <b>#{i}</b> {s} — <b>{p}₽</b> {status_emoji}\n"
        if status == "pending":
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"💳 Оплатить заказ #{oid}", callback_data=f"pay_pending_{oid}")])
            
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.startswith("pay_pending_"))
async def pay_pending_order(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    order = get_order_by_id(order_id)
    if not order: return await callback.answer("Заказ не найден!", show_alert=True)
    
    user_id, service, price = order
    if user_id != callback.from_user.id: return await callback.answer("⚠️ Это не ваш заказ!", show_alert=True)
        
    await state.update_data(service=service, final_price=price, order_id=order_id)
    balance = get_balance(user_id)
    
    await callback.message.answer(f"💳 <b>Продолжить оплату заказа #{order_id}</b>\n\n📦 Услуга: <b>{service}</b>\n💰 Сумма: <b>{price}₽</b>", reply_markup=get_payment_keyboard(balance, price), parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_payment)
    await callback.answer()

@dp.callback_query(F.data == "my_balance")
async def process_my_balance(callback: CallbackQuery):
    balance = get_balance(callback.from_user.id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
    await callback.message.answer(f"💰 <b>Твой баланс: {balance}₽</b>\n\n🔗 <b>Реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n🎁 Приведи друга и получи 20%!", parse_mode="HTML")

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    await callback.message.answer(" <b>Рассылка</b>\n\nНапиши текст:", parse_mode="HTML")
    await state.set_state(BroadcastState.waiting_for_message)

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    users = get_all_users()
    success = 0
    for u in users:
        try:
            await bot.send_message(u, f"📢 {message.text}", parse_mode="HTML")
            success += 1; await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ <b>Доставлено:</b> {success}/{len(users)}", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "users_count")
async def process_users_count(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    await callback.message.answer(f" <b>Пользователей:</b> {len(get_all_users())}", parse_mode="HTML")

@dp.callback_query(F.data == "stats")
async def process_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("🚫 Ты не админ!", show_alert=True)
    stats = get_stats()
    text = f"📊 <b>СТАТИСТИКА МАГАЗИНА</b>\n\n👥 <b>Всего пользователей:</b> {stats['total_users']}\n📦 <b>Всего заказов:</b> {stats['total_orders']}\n✅ <b>Оплачено:</b> {stats['paid_orders']}\n⏳ <b>Ожидают оплаты:</b> {stats['pending_orders']}\n💰 <b>Общая выручка:</b> {stats['total_revenue']}₽\n\n"
    if stats['top_products']:
        text += f"🏆 <b>ТОП ТОВАРОВ:</b>\n"
        for i, (service, count, revenue) in enumerate(stats['top_products'], 1):
            text += f"{i}. {service} — <b>{count} продаж</b> ({revenue}₽)\n"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("👋 <b>Главное меню</b>", reply_markup=main_keyboard, parse_mode="HTML")
    await callback.answer()
