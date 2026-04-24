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

conn.commit()


def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить трату")],
            [KeyboardButton(text="👥 Участники"), KeyboardButton(text="📋 Траты")],
            [KeyboardButton(text="📊 Итог"), KeyboardButton(text="🧹 Очистить")]
        ],
        resize_keyboard=True
    )


def get_people(chat_id):
    cur.execute("SELECT name FROM participants WHERE chat_id = ?", (chat_id,))
    return [row[0] for row in cur.fetchall()]


def add_person(chat_id, name):
    people = get_people(chat_id)
    if name not in people:
        cur.execute("INSERT INTO participants VALUES (?, ?)", (chat_id, name))
        conn.commit()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! Я считаю долги в поездке.\n\n"
        "Добавь участников:\n"
        "/add Витя Дима Аня Катя\n\n"
        "Добавь трату:\n"
        "Витя 2400 кафе\n\n"
        "Или только на выбранных людей:\n"
        "Витя 1200 такси | Витя Дима",
        reply_markup=menu()
    )


@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(
        "Команды:\n\n"
        "/add Витя Дима Аня — добавить участников\n"
        "/people — список участников\n"
        "/list — список трат\n"
        "/total — итог\n"
        "/clear — очистить всё\n\n"
        "Быстрый ввод траты:\n"
        "Витя 2400 кафе\n\n"
        "Трата не на всех:\n"
        "Витя 1200 такси | Витя Дима"
    )


@dp.message(Command("add"))
async def add_people(message: types.Message):
    chat_id = message.chat.id
    names = message.text.split()[1:]

    if not names:
        await message.answer("Напиши так:\n/add Витя Дима Аня")
        return

    added = []

    for name in names:
        if name not in get_people(chat_id):
            add_person(chat_id, name)
            added.append(name)

    if added:
        await message.answer("Добавлены: " + ", ".join(added))
    else:
        await message.answer("Все эти участники уже есть.")


@dp.message(Command("people"))
async def people_cmd(message: types.Message):
    await show_people(message)


@dp.message(Command("list"))
async def list_cmd(message: types.Message):
    await show_expenses(message)


@dp.message(Command("total"))
async def total_cmd(message: types.Message):
    await show_total(message)


@dp.message(Command("clear"))
async def clear_cmd(message: types.Message):
    await clear_data(message)


async def show_people(message: types.Message):
    chat_id = message.chat.id
    people = get_people(chat_id)

    if not people:
        await message.answer("Участников пока нет.\nДобавь так:\n/add Витя Дима Аня")
        return

    text = "👥 Участники:\n\n"
    for person in people:
        text += f"• {person}\n"

    await message.answer(text)


async def show_expenses(message: types.Message):
    chat_id = message.chat.id

    cur.execute(
        "SELECT payer, amount, description, people FROM expenses WHERE chat_id = ?",
        (chat_id,)
    )
    rows = cur.fetchall()

    if not rows:
        await message.answer("Трат пока нет.")
        return

    text = "📋 Список трат:\n\n"

    for i, row in enumerate(rows, start=1):
        payer, amount, description, people = row
        text += f"{i}. {payer} — {amount:.2f} ₽\n"
        text += f"   {description}\n"
        text += f"   За: {people}\n\n"

    await message.answer(text)


async def show_total(message: types.Message):
    chat_id = message.chat.id
    people = get_people(chat_id)

    if not people:
        await message.answer("Участников нет.")
        return

    cur.execute(
        "SELECT payer, amount, people FROM expenses WHERE chat_id = ?",
        (chat_id,)
    )
    rows = cur.fetchall()

    if not rows:
        await message.answer("Трат пока нет.")
        return

    balances = {person: 0.0 for person in people}

    for payer, amount, people_text in rows:
        selected_people = people_text.split(",")
        share = amount / len(selected_people)

        balances[payer] += amount

        for person in selected_people:
            balances[person] -= share

    debtors = []
    creditors = []

    for person, balance in balances.items():
        if balance < -0.01:
            debtors.append([person, -balance])
        elif balance > 0.01:
            creditors.append([person, balance])

    transfers = []

    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]

        pay = min(debt, credit)
        transfers.append((debtor, creditor, pay))

        debtors[i][1] -= pay
        creditors[j][1] -= pay

        if debtors[i][1] < 0.01:
            i += 1

        if creditors[j][1] < 0.01:
            j += 1

    text = "📊 Итог поездки:\n\n"

    text += "Балансы:\n"
    for person, balance in balances.items():
        sign = "+" if balance > 0 else ""
        text += f"{person}: {sign}{balance:.2f} ₽\n"

    text += "\n💸 Кто кому переводит:\n"

    if not transfers:
        text += "Никто никому ничего не должен."
    else:
        for debtor, creditor, amount in transfers:
            text += f"{debtor} → {creditor}: {amount:.2f} ₽\n"

    await message.answer(text)


async def clear_data(message: types.Message):
    chat_id = message.chat.id

    cur.execute("DELETE FROM participants WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM expenses WHERE chat_id = ?", (chat_id,))
    conn.commit()

    await message.answer("🧹 Всё очищено.")


async def add_expense_from_text(message: types.Message):
    chat_id = message.chat.id
    text = message.text.strip()

    people = get_people(chat_id)

    if "|" in text:
        left, right = text.split("|", 1)
        selected_people = right.strip().split()
    else:
        left = text
        selected_people = people

    parts = left.strip().split()

    if len(parts) < 3:
        await message.answer(
            "Формат траты:\n"
            "Витя 2400 кафе\n\n"
            "Или:\n"
            "Витя 1200 такси | Витя Дима"
        )
        return

    payer = parts[0]

    try:
        amount = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("Сумма должна быть числом.")
        return

    description = " ".join(parts[2:])

    if payer not in people:
        add_person(chat_id, payer)
        people.append(payer)

    if not selected_people:
        selected_people = people

    for person in selected_people:
        if person not in people:
            add_person(chat_id, person)
            people.append(person)

    cur.execute(
        "INSERT INTO expenses VALUES (?, ?, ?, ?, ?)",
        (
            chat_id,
            payer,
            amount,
            description,
            ",".join(selected_people)
        )
    )

    conn.commit()

    await message.answer(
        f"✅ Трата добавлена:\n\n"
        f"Платил: {payer}\n"
        f"Сумма: {amount:.2f} ₽\n"
        f"Описание: {description}\n"
        f"За кого: {', '.join(selected_people)}"
    )


@dp.message()
async def text_handler(message: types.Message):
    text = message.text

    if text == "➕ Добавить трату":
        await message.answer(
            "Напиши трату так:\n\n"
            "Витя 2400 кафе\n\n"
            "Или не на всех:\n"
            "Витя 1200 такси | Витя Дима"
        )
        return

    if text == "👥 Участники":
        await show_people(message)
        return

    if text == "📋 Траты":
        await show_expenses(message)
        return

    if text == "📊 Итог":
        await show_total(message)
        return

    if text == "🧹 Очистить":
        await clear_data(message)
        return

    await add_expense_from_text(message)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())