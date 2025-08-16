import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# TOKEN kiriting
BOT_TOKEN = "8412337873:AAHMHurZCpP7OxLa4fVPuM6bUKzaDO2okHE"

# Bot va Dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

# SQLite bazani ulash
conn = sqlite3.connect("hisob.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL,
    reason TEXT,
    type TEXT,
    date TEXT
)
""")
conn.commit()

# FSM uchun states
class TransactionState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_reason = State()
    transaction_type = State()

# Klaviatura
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Kirim"), KeyboardButton(text="📤 Chiqim")],
        [KeyboardButton(text="📊 Hisobot")]
    ],
    resize_keyboard=True
)

report_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Kunlik"), KeyboardButton(text="🗓 Haftalik")],
        [KeyboardButton(text="📆 Oylik"), KeyboardButton(text="📈 Yillik")],
        [KeyboardButton(text="⬅️ Orqaga")]
    ],
    resize_keyboard=True
)

# --- Yordamchi funksiyalar ---
def parse_amount(text: str) -> int:
    """
    Foydalanuvchi yozgan summani raqamga aylantiradi.
    Masalan: '100ming' -> 100000, '2mln' -> 2000000
    """
    text = text.lower().replace(" ", "")
    if "ming" in text:
        num = int(text.replace("ming", "")) * 1000
    elif "mln" in text:
        num = int(text.replace("mln", "")) * 1_000_000
    else:
        num = int(text)
    return num

def format_amount(amount: int) -> str:
    """
    Summani chiroyli ko‘rinishda qaytaradi.
    Masalan: 100000 -> 100.000 so'm
    """
    return f"{int(amount):,}".replace(",", ".") + " so'm"

# Start komandasi
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("👋 Salom! Men hisobchi botman.\nKirim, chiqim va hisobotlaringizni yuritaman.", reply_markup=main_kb)

# Kirim
@dp.message(F.text == "📥 Kirim")
async def kirim_start(message: Message, state: FSMContext):
    await state.set_state(TransactionState.waiting_for_amount)
    await state.update_data(transaction_type="kirim")
    await message.answer("📥 Kirim summasini kiriting (masalan: 100000, 100 ming, 2 mln):")

# Chiqim
@dp.message(F.text == "📤 Chiqim")
async def chiqim_start(message: Message, state: FSMContext):
    await state.set_state(TransactionState.waiting_for_amount)
    await state.update_data(transaction_type="chiqim")
    await message.answer("📤 Chiqim summasini kiriting (masalan: 50000, 50 ming):")

# Summani qabul qilish
@dp.message(TransactionState.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = parse_amount(message.text)
    except Exception:
        await message.answer("❌ Iltimos, summani to‘g‘ri kiriting (masalan: 100000, 100 ming, 2 mln)!")
        return

    await state.update_data(amount=amount)
    await state.set_state(TransactionState.waiting_for_reason)
    await message.answer("✍️ Nima uchunligini yozing:")

# Sababni qabul qilish
@dp.message(TransactionState.waiting_for_reason)
async def process_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    t_type = data["transaction_type"]
    reason = message.text

    cursor.execute("INSERT INTO transactions (amount, reason, type, date) VALUES (?, ?, ?, ?)",
                   (amount, reason, t_type, datetime.now().isoformat()))
    conn.commit()

    await state.clear()
    await message.answer(
        f"✅ {t_type.upper()} yozildi:\n💰 {format_amount(amount)}\n📝 {reason}",
        reply_markup=main_kb
    )

# Hisobot tugmasi
@dp.message(F.text == "📊 Hisobot")
async def hisobot_menu(message: Message):
    await message.answer("📊 Qaysi hisobotni ko‘rmoqchisiz?", reply_markup=report_kb)

# Orqaga
@dp.message(F.text == "⬅️ Orqaga")
async def back_to_menu(message: Message):
    await message.answer("🏠 Asosiy menyu", reply_markup=main_kb)

# Hisobot funksiyasi
async def generate_report(period: str):
    now = datetime.now()
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = now - timedelta(days=now.weekday())
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "yearly":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return "❌ Xatolik!"

    cursor.execute("SELECT amount, reason, type, date FROM transactions")
    rows = cursor.fetchall()

    kirim_sum = 0
    chiqim_sum = 0
    details = []

    for amount, reason, t_type, date_str in rows:
        date = datetime.fromisoformat(date_str)
        if date >= start:
            # soat va minut formatida chiqarish
            time_str = date.strftime("%H:%M")

            # summani formatlash (masalan: 110000 -> 110.000)
            amount_str = f"{int(amount):,}".replace(",", ".") + " so'm"

            if t_type == "kirim":
                kirim_sum += amount
                details.append(f"➕ {amount_str} — {reason} ({time_str})")
            else:
                chiqim_sum += amount
                details.append(f"➖ {amount_str} — {reason} ({time_str})")

    if not details:
        return "ℹ️ Bu davr uchun yozuvlar topilmadi."

    # jami summalarni ham formatlab chiqaramiz
    report_text = "\n".join(details)
    report_text += (
        f"\n\n💰 Jami kirim: {int(kirim_sum):,}".replace(",", ".") + " so'm"
        f"\n💸 Jami chiqim: {int(chiqim_sum):,}".replace(",", ".") + " so'm"
    )
    return report_text


# Kunlik
@dp.message(F.text == "📅 Kunlik")
async def daily_report(message: Message):
    report = await generate_report("daily")
    await message.answer(f"📅 Kunlik hisobot:\n\n{report}")

# Haftalik
@dp.message(F.text == "🗓 Haftalik")
async def weekly_report(message: Message):
    report = await generate_report("weekly")
    await message.answer(f"🗓 Haftalik hisobot:\n\n{report}")

# Oylik
@dp.message(F.text == "📆 Oylik")
async def monthly_report(message: Message):
    report = await generate_report("monthly")
    await message.answer(f"📆 Oylik hisobot:\n\n{report}")

# Yillik
@dp.message(F.text == "📈 Yillik")
async def yearly_report(message: Message):
    report = await generate_report("yearly")
    await message.answer(f"📈 Yillik hisobot:\n\n{report}")

# Asosiy run
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
