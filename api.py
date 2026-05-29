from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import sqlite3
import random
import string
import os
import json
from datetime import datetime, date, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели
class UserRequest(BaseModel):
    user_id: int

class OpenCaseRequest(BaseModel):
    user_id: int
    case_id: str

class SellItemRequest(BaseModel):
    user_id: int
    item_id: int

class UpgradeItemRequest(BaseModel):
    user_id: int
    item_id: int
    new_price: int = 0
    success: bool = True

class WithdrawRequest(BaseModel):
    user_id: int
    item_id: int
    trade_link: str

class ActivatePromoRequest(BaseModel):
    user_id: int
    code: str

class AdminCoinsRequest(BaseModel):
    admin_id: int
    target_id: int
    coins: int

class AdminSpinsRequest(BaseModel):
    admin_id: int
    target_id: int
    spins: int

class AdminCaseRequest(BaseModel):
    admin_id: int
    target_id: int
    case_name: str

class AdminPromoRequest(BaseModel):
    admin_id: int
    reward: int

class AdminPrimeRequest(BaseModel):
    admin_id: int
    target_id: int

class AdminBanRequest(BaseModel):
    admin_id: int
    target_id: int

class AdminBroadcastRequest(BaseModel):
    admin_id: int
    message: str

# Путь к БД
DB_PATH = os.path.join(os.path.dirname(__file__), 'artdrop.db')

def get_db():
    return sqlite3.connect(DB_PATH)

# Инициализация БД
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        coins INTEGER DEFAULT 500,
        total_deposit INTEGER DEFAULT 0,
        wheel_spins INTEGER DEFAULT 1,
        last_wheel_date TEXT DEFAULT '2000-01-01',
        is_banned INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT 0,
        prime_expires TEXT DEFAULT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_name TEXT,
        item_price INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cases (
        name TEXT PRIMARY KEY,
        price INTEGER,
        max_item_price INTEGER,
        jackpot_chance REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        uses_left INTEGER,
        created_by INTEGER,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        code TEXT,
        reward INTEGER,
        used_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        item_name TEXT,
        item_price INTEGER,
        trade_link TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        created_at TEXT
    )''')
    
    default_cases = [
        ("bomj", 500, 1000, 2.0),
        ("berkut", 1500, 3000, 1.5),
        ("chempion", 5000, 10000, 1.2),
        ("major", 50000, 100000, 1.0),
        ("global", 100000, 200000, 0.8),
        ("s1mple", 500000, 1000000, 0.5),
        ("gabe", 1000000, 2000000, 0.3)
    ]
    for name, price, max_price, chance in default_cases:
        c.execute("INSERT OR IGNORE INTO cases VALUES (?,?,?,?)", (name, price, max_price, chance))
    
    conn.commit()
    conn.close()

init_db()

# Функции
def get_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()

def open_case_logic(case_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT price, max_item_price, jackpot_chance FROM cases WHERE name=?", (case_name,))
    price, max_price, chance = c.fetchone()
    conn.close()
    
    if random.random() * 100 <= chance:
        return ("🔥 ДЖЕКПОТ", max_price)
    
    r = random.random() * 100
    if r <= 30:
        percent = random.uniform(0.5, 0.7)
        item = "🟢 Обычный скин"
    elif r <= 55:
        percent = random.uniform(0.7, 0.9)
        item = "🔵 Средний скин"
    elif r <= 75:
        percent = random.uniform(0.9, 1.2)
        item = "🟣 Хороший скин"
    elif r <= 87:
        percent = random.uniform(1.2, 1.6)
        item = "🟠 Очень хороший"
    else:
        percent = random.uniform(1.6, 2.2)
        item = "🔴 Редкий скин"
    
    return (item, int(price * percent))

# ========== API ЭНДПОИНТЫ ==========

@app.get("/")
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/balance")
async def get_balance(user_id: int):
    user = get_user(user_id)
    if not user:
        create_user(user_id)
        user = get_user(user_id)
    return {"balance": user[2], "wheel_spins": user[4], "ref_count": 0, "prime_active": False}

@app.post("/api/open_case")
async def open_case(req: OpenCaseRequest):
    user = get_user(req.user_id)
    if not user:
        create_user(req.user_id)
        user = get_user(req.user_id)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT price FROM cases WHERE name=?", (req.case_id,))
    case_price = c.fetchone()[0]
    
    if user[2] < case_price:
        conn.close()
        return {"error": "Не хватает монет"}
    
    item_name, item_price = open_case_logic(req.case_id)
    c.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (case_price, req.user_id))
    c.execute("INSERT INTO inventory (user_id, item_name, item_price) VALUES (?,?,?)", (req.user_id, item_name, item_price))
    conn.commit()
    conn.close()
    
    return {"item": item_name, "price": item_price}

@app.get("/api/inventory")
async def get_inventory(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, item_name, item_price FROM inventory WHERE user_id=? ORDER BY id DESC", (user_id,))
    items = [{"id": row[0], "name": row[1], "price": row[2]} for row in c.fetchall()]
    conn.close()
    return {"items": items}

@app.post("/api/sell_item")
async def sell_item(req: SellItemRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT item_price FROM inventory WHERE id=? AND user_id=?", (req.item_id, req.user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return {"error": "Предмет не найден"}
    
    sell_price = int(item[0] * 0.95)
    c.execute("DELETE FROM inventory WHERE id=?", (req.item_id,))
    c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (sell_price, req.user_id))
    conn.commit()
    conn.close()
    return {"price": sell_price}

@app.post("/api/upgrade_item")
async def upgrade_item(req: UpgradeItemRequest):
    conn = get_db()
    c = conn.cursor()
    if req.success and req.new_price > 0:
        c.execute("UPDATE inventory SET item_price=? WHERE id=? AND user_id=?", (req.new_price, req.item_id, req.user_id))
    else:
        c.execute("SELECT item_price FROM inventory WHERE id=? AND user_id=?", (req.item_id, req.user_id))
        item = c.fetchone()
        if item:
            comp = int(item[0] * 0.05)
            c.execute("DELETE FROM inventory WHERE id=?", (req.item_id,))
            c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (comp, req.user_id))
    conn.commit()
    conn.close()
    return {"success": req.success}

@app.post("/api/spin_wheel")
async def spin_wheel(req: UserRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT wheel_spins, last_wheel_date FROM users WHERE user_id=?", (req.user_id,))
    user = c.fetchone()
    if not user:
        create_user(req.user_id)
        user = (0, "2000-01-01")
    
    today = date.today().isoformat()
    if today != user[1]:
        c.execute("UPDATE users SET wheel_spins=wheel_spins+1, last_wheel_date=? WHERE user_id=?", (today, req.user_id))
        conn.commit()
    
    c.execute("SELECT wheel_spins FROM users WHERE user_id=?", (req.user_id,))
    spins = c.fetchone()[0]
    
    if spins <= 0:
        conn.close()
        return {"error": "Нет прокруток"}
    
    prize = random.choice([50, 100, 250, 500, 1000])
    c.execute("UPDATE users SET wheel_spins=wheel_spins-1, coins=coins+? WHERE user_id=?", (prize, req.user_id))
    conn.commit()
    conn.close()
    return {"prize": prize}

@app.post("/api/activate_promo")
async def activate_promo(req: ActivatePromoRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT reward, uses_left FROM promocodes WHERE code=?", (req.code,))
    promo = c.fetchone()
    if not promo:
        conn.close()
        return {"error": "Неверный промокод"}
    if promo[1] <= 0:
        conn.close()
        return {"error": "Промокод использован"}
    
    used = c.execute("SELECT COUNT(*) FROM promo_usage WHERE user_id=? AND code=?", (req.user_id, req.code)).fetchone()[0]
    if used > 0:
        conn.close()
        return {"error": "Вы уже активировали этот промокод"}
    
    c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (promo[0], req.user_id))
    c.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?", (req.code,))
    c.execute("INSERT INTO promo_usage (user_id, code, reward, used_at) VALUES (?,?,?,?)", (req.user_id, req.code, promo[0], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "reward": promo[0]}

@app.post("/api/withdraw")
async def withdraw(req: WithdrawRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT total_deposit FROM users WHERE user_id=?", (req.user_id,))
    deposit = c.fetchone()[0]
    if deposit < 250:
        conn.close()
        return {"error": "Депозит менее 250₽"}
    
    c.execute("SELECT item_name, item_price FROM inventory WHERE id=? AND user_id=?", (req.item_id, req.user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return {"error": "Предмет не найден"}
    
    c.execute("DELETE FROM inventory WHERE id=?", (req.item_id,))
    c.execute("INSERT INTO withdraw_requests (user_id, username, item_name, item_price, trade_link, created_at) VALUES (?,?,?,?,?,?)",
              (req.user_id, "", item[0], item[1], req.trade_link, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/deposit")
async def get_deposit(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT total_deposit FROM users WHERE user_id=?", (user_id,))
    deposit = c.fetchone()
    conn.close()
    return {"total": deposit[0] if deposit else 0}

@app.get("/api/promos")
async def get_promos(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT code, reward FROM promo_usage WHERE user_id=? ORDER BY used_at DESC", (user_id,))
    promos = [{"code": row[0], "reward": row[1]} for row in c.fetchall()]
    conn.close()
    return {"promos": promos}

@app.get("/api/stats")
async def get_stats(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT total_deposit FROM users WHERE user_id=?", (user_id,))
    deposit = c.fetchone()
    conn.close()
    return {"deposit_sum": f"{deposit[0] if deposit else 0} ₽"}

# ========== АДМИН ЭНДПОИНТЫ ==========

ADMIN_PASSWORD = "250734382"
OWNER_ID = 8096023466

def check_admin(uid):
    return uid == OWNER_ID

@app.get("/api/admin_stats")
async def admin_stats():
    conn = get_db()
    c = conn.cursor()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_coins = c.execute("SELECT SUM(coins) FROM users").fetchone()[0] or 0
    total_items = c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    total_deposits = c.execute("SELECT SUM(total_deposit) FROM users").fetchone()[0] or 0
    conn.close()
    return {"users": users, "total_coins": total_coins, "total_items": total_items, "total_deposits": f"{total_deposits} ₽"}

@app.get("/api/admin_users")
async def admin_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, coins, total_deposit FROM users LIMIT 50")
    users = [{"id": row[0], "username": row[1] or str(row[0]), "coins": row[2], "deposit": row[3]} for row in c.fetchall()]
    conn.close()
    return {"users": users}

@app.post("/api/admin_give_coins")
async def admin_give_coins(req: AdminCoinsRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (req.coins, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_give_spins")
async def admin_give_spins(req: AdminSpinsRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET wheel_spins=wheel_spins+? WHERE user_id=?", (req.spins, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_give_case")
async def admin_give_case(req: AdminCaseRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    item_name, item_price = open_case_logic(req.case_name)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, item_name, item_price) VALUES (?,?,?)", (req.target_id, item_name, item_price))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_create_promo")
async def admin_create_promo(req: AdminPromoRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO promocodes (code, reward, uses_left, created_by, created_at) VALUES (?,?,?,?,?)",
              (code, req.reward, 100, req.admin_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"code": code}

@app.post("/api/admin_give_prime")
async def admin_give_prime(req: AdminPrimeRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    expires = (date.today() + timedelta(days=30)).isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET prime_expires=? WHERE user_id=?", (expires, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_ban")
async def admin_ban(req: AdminBanRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    current = c.execute("SELECT is_banned FROM users WHERE user_id=?", (req.target_id,)).fetchone()
    new = 0 if current and current[0] else 1
    c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_broadcast")
async def admin_broadcast(req: AdminBroadcastRequest):
    if not check_admin(req.admin_id):
        return {"error": "Access denied"}
    # Здесь можно добавить отправку через Telegram API
    return {"success": True}

# Статические файлы
@app.get("/images/{filename}")
async def get_image(filename: str):
    path = os.path.join("images", filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404)

@app.get("/sounds/{filename}")
async def get_sound(filename: str):
    path = os.path.join("sounds", filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
