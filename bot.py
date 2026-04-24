import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8504103298:AAGfc9eLlj1yLghbeGqVD6v8c876OhyTUYE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("trip.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS participants (
    chat_id INTEGER,
    name TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    chat_id INTEGER,
    payer TEXT,
    amount REAL,
    description TEXT,
    people TEXT
)
""")

# ПАРЫ
cur.execute("""
CREATE TABLE IF NOT EXISTS couples (
    chat_id INTEGER,
    person1 TEXT,
    person2 TEXT
)
""")

conn.commit()


def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить трату")],
            [KeyboardButton(text="👥 Участники"), KeyboardButton(text="📋 Траты")],
            [KeyboardButton(text="📊 Итог"), KeyboardButton(text="❤️ Пары")],
            [KeyboardButton(text="🧹 Очистить")]
        ],
        resize_keyboard=True
    )


def get_people(chat_id):
    cur.execute("SELECT name FROM participants WHERE chat_id = ?", (chat_id,))
    return [row[0] for row in cur.fetchall()]


def add_person(chat_id, name):
    if name not in get_people(chat_id):
        cur.execute("INSERT INTO participants VALUES (?, ?)", (chat_id, name))
        conn.commit()


def get_couples(chat_id):
    cur.execute("SELECT person1, person2 FROM couples WHERE chat_id = ?", (chat_id,))
    return cur.fetchall()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Добавь участников:\n/add Витя Дима Аня Катя\n\n"
        "Добавь трату:\nВитя 2400 кафе\n\n"
        "Создать пару:\n/couple Сережа Полина",
        reply_markup=menu()
    )


@dp.message(Command("add"))
async def add_people(message: types.Message):
    chat_id = message.chat.id
    names = message.text.split()[1:]

    for name in names:
        add_person(chat_id, name)

    await message.answer("Участники добавлены.")


@dp.message(Command("couple"))
async def add_couple(message: types.Message):
    chat_id = message.chat.id
    parts = message.text.split()

    if len(parts) != 3:
        await message.answer("Формат:\n/couple Сережа Полина")
        return

    p1, p2 = parts[1], parts[2]

    add_person(chat_id, p1)
    add_person(chat_id, p2)

    cur.execute("INSERT INTO couples VALUES (?, ?, ?)", (chat_id, p1, p2))
    conn.commit()

    await message.answer(f"❤️ Пара создана: {p1} + {p2}")


@dp.message(Command("total"))
async def total(message: types.Message):
    chat_id = message.chat.id
    people = get_people(chat_id)

    cur.execute(
        "SELECT payer, amount, people FROM expenses WHERE chat_id = ?",
        (chat_id,)
    )
    rows = cur.fetchall()

    balances = {p: 0.0 for p in people}

    # СЧИТАЕМ ПО ЛЮДЯМ (ВАЖНО)
    for payer, amount, people_text in rows:
        selected = people_text.split(",")
        share = amount / len(selected)

        balances[payer] += amount
        for person in selected:
            balances[person] -= share

    # ОБЪЕДИНЯЕМ ПАРЫ
    couples = get_couples(chat_id)

    for p1, p2 in couples:
        total_balance = balances.get(p1, 0) + balances.get(p2, 0)

        balances.pop(p1, None)
        balances.pop(p2, None)

        balances[f"{p1}+{p2}"] = total_balance

    # ДЕЛАЕМ ПЕРЕВОДЫ
    debtors = []
    creditors = []

    for person, balance in balances.items():
        if balance < -0.01:
            debtors.append([person, -balance])
        elif balance > 0.01:
            creditors.append([person, balance])

    transfers = []

    i = j = 0
    while i < len(debtors) and j < len(creditors):
        d_name, d_amt = debtors[i]
        c_name, c_amt = creditors[j]

        pay = min(d_amt, c_amt)

        transfers.append((d_name, c_name, pay))

        debtors[i][1] -= pay
        creditors[j][1] -= pay

        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1

    # ВЫВОД
    text = "📊 Итог:\n\nБалансы:\n"
    for p, b in balances.items():
        sign = "+" if b > 0 else ""
        text += f"{p}: {sign}{b:.2f} ₽\n"

    text += "\n💸 Переводы:\n"
    for d, c, a in transfers:
        text += f"{d} → {c}: {a:.2f} ₽\n"

    await message.answer(text)


@dp.message()
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    text = message.text

    if text == "📊 Итог":
        await total(message)
        return

    # ДОБАВЛЕНИЕ ТРАТЫ
    if "|" in text:
        left, right = text.split("|", 1)
        selected = right.strip().split()
    else:
        left = text
        selected = get_people(chat_id)

    parts = left.strip().split()

    if len(parts) < 3:
        return

    payer = parts[0]
    amount = float(parts[1])
    desc = " ".join(parts[2:])

    add_person(chat_id, payer)

    for p in selected:
        add_person(chat_id, p)

    cur.execute(
        "INSERT INTO expenses VALUES (?, ?, ?, ?, ?)",
        (chat_id, payer, amount, desc, ",".join(selected))
    )
    conn.commit()

    await message.answer("✅ Трата добавлена")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())