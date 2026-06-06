
import sqlite3
import asyncio
from bot_instance import bot

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, inviter_id INTEGER DEFAULT 0, balance INTEGER DEFAULT 0)''')
    try: cursor.execute('ALTER TABLE users ADD COLUMN inviter_id INTEGER DEFAULT 0')
    except: pass
    try: cursor.execute('ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0')
    except: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT, price INTEGER, status TEXT DEFAULT 'pending')''')
    try: cursor.execute('ALTER TABLE orders ADD COLUMN status TEXT DEFAULT "pending"')
    except: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, discount_percent INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT, rating INTEGER, comment TEXT)''')
    
    conn.commit()
    conn.close()

def add_user(user_id, inviter_id=0):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone() is not None
    cursor.execute('''INSERT INTO users (user_id, inviter_id) VALUES (?, ?) 
                      ON CONFLICT(user_id) DO UPDATE SET inviter_id = CASE WHEN inviter_id = 0 THEN excluded.inviter_id ELSE inviter_id END''', (user_id, inviter_id))
    conn.commit()
    conn.close()
    return not exists

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

def create_order(user_id, service, price):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, service, price, status) VALUES (?, ?, ?, "pending")', (user_id, service, price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id, status):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_order_by_id(order_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, service, price FROM orders WHERE id = ?', (order_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def add_order(user_id, service, price):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, service, price, status) VALUES (?, ?, ?, "paid")', (user_id, service, price))
    cursor.execute('SELECT inviter_id FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0] > 0:
        inviter_id = res[0]
        bonus = price // 5
        update_balance(inviter_id, bonus)
        conn.close()
        asyncio.create_task(notify_inviter(inviter_id, bonus))
        return
    conn.commit()
    conn.close()

def pay_existing_order(order_id, user_id, service, price):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = "paid" WHERE id = ?', (order_id,))
    cursor.execute('SELECT inviter_id FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0] > 0:
        inviter_id = res[0]
        bonus = price // 5
        update_balance(inviter_id, bonus)
        conn.close()
        asyncio.create_task(notify_inviter(inviter_id, bonus))
        return
    conn.commit()
    conn.close()

async def notify_inviter(inviter_id, bonus):
    try:
        await bot.send_message(inviter_id, f"🎉 <b>Твой друг сделал заказ!</b>\n💰 Ты получил <b>{bonus}₽</b> на баланс!", parse_mode="HTML")
    except: pass

def get_orders(user_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, service, price, status FROM orders WHERE user_id = ?', (user_id,))
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

def get_stats():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM orders')
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'paid'")
    paid_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'paid'")
    total_revenue = cursor.fetchone()[0]
    cursor.execute("SELECT service, COUNT(*) as count, SUM(price) as revenue FROM orders WHERE status = 'paid' GROUP BY service ORDER BY count DESC LIMIT 5")
    top_products = cursor.fetchall()
    conn.close()
    return {
        'total_users': total_users, 'total_orders': total_orders,
        'paid_orders': paid_orders, 'pending_orders': pending_orders,
        'total_revenue': total_revenue, 'top_products': top_products
    }

def add_review(user_id, service, rating, comment):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reviews (user_id, service, rating, comment) VALUES (?, ?, ?, ?)', (user_id, service, rating, comment))
    conn.commit()
    conn.close()

def has_reviewed(user_id, service):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM reviews WHERE user_id = ? AND service = ?', (user_id, service))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_all_reviews():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT service, rating, comment FROM reviews ORDER BY id DESC LIMIT 20')
    reviews = cursor.fetchall()
    conn.close()
    return reviews
