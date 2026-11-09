"""Ishxona xodimlarining tug'ilgan kunlarini eslatuvchi Telegram bot."""
import html
import logging
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import assistant
import db
from birthdays import (
    age_on, days_until, format_date, next_birthday, parse_employee_line,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bdbot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Tashkent"))
NOTIFY_TIME = os.getenv("NOTIFY_TIME", "09:00")
REMIND_DAYS = sorted(
    {int(x) for x in os.getenv("REMIND_DAYS", "3,1").split(",") if x.strip().isdigit() and int(x) > 0},
    reverse=True,
)
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}
ENV_CHAT_IDS = {int(x) for x in os.getenv("CHAT_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}


def today():
    return datetime.now(TZ).date()


def is_admin(update: Update) -> bool:
    # ADMIN_IDS bo'sh bo'lsa, hamma boshqara oladi (faqat sinov uchun tavsiya etiladi)
    return not ADMIN_IDS or (update.effective_user and update.effective_user.id in ADMIN_IDS)


async def deny(update: Update) -> None:
    await update.effective_message.reply_text("⛔ Bu buyruq faqat adminlar uchun.")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


# ---------- Buyruqlar ----------

HELP = (
    "🎂 <b>Tug'ilgan kun eslatuvchi bot</b>\n\n"
    "<b>Hamma uchun:</b>\n"
    "/today — bugungi tug'ilgan kunlar\n"
    "/upcoming [kun] — yaqin kunlardagilar (standart 30 kun)\n"
    "/list — barcha xodimlar\n"
    "/myid — Telegram ID va chat ID\n\n"
    "<b>Adminlar uchun:</b>\n"
    "/add Ism Familiya 15.03.1990 — xodim qo'shish (yil ixtiyoriy: 15.03)\n"
    "/import — bir nechta xodimni qo'shish (har qatorda bittadan)\n"
    "/del ID — xodimni o'chirish\n"
    "/subscribe — shu guruhga tabriklar yuborish\n"
    "/unsubscribe — shu guruhni o'chirish\n"
    "/check — tekshiruvni hozir ishga tushirish\n\n"
    "<b>🎙 Ovozli yordamchi:</b>\n"
    "Shaxsiy chatda istalgan savolni ovozli yoki matnli xabar qilib yuboring — "
    "bot matn va ovoz bilan javob beradi. Guruhda botning xabariga ovozli javob qiling.\n"
    "/ask savol — matnli savol\n"
    "/reset — suhbat tarixini tozalash\n\n"
    "Har kuni soat {time} da tekshiriladi. Oldindan eslatmalar ({days} kun oldin) "
    "adminlarga shaxsiy xabarda, tabriklar esa guruhga yuboriladi."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    days = ", ".join(map(str, REMIND_DAYS)) or "—"
    await update.effective_message.reply_text(
        HELP.format(time=NOTIFY_TIME, days=days), parse_mode=ParseMode.HTML
    )


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"👤 Sizning ID: <code>{update.effective_user.id}</code>\n"
        f"💬 Chat ID: <code>{update.effective_chat.id}</code>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    text = " ".join(context.args)
    if not text:
        return await update.effective_message.reply_text(
            "Foydalanish: /add Ism Familiya 15.03.1990"
        )
    try:
        name, d, m, y = parse_employee_line(text)
    except ValueError as e:
        return await update.effective_message.reply_text(f"❌ {e}")
    emp_id = db.add_employee(name, d, m, y)
    left = days_until(d, m, today())
    await update.effective_message.reply_text(
        f"✅ Qo'shildi (ID {emp_id}): <b>{esc(name)}</b> — {format_date(d, m, y)}\n"
        f"Tug'ilgan kunigacha: {left} kun",
        parse_mode=ParseMode.HTML,
    )


async def cmd_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    raw = update.effective_message.text.split(maxsplit=1)
    lines = [l for l in (raw[1] if len(raw) > 1 else "").splitlines() if l.strip()]
    if not lines:
        return await update.effective_message.reply_text(
            "Foydalanish (har qatorda bitta xodim):\n\n"
            "/import\nAli Valiyev 15.03.1990\nMalika Karimova 02.11"
        )
    ok, errors = 0, []
    for i, line in enumerate(lines, 1):
        try:
            name, d, m, y = parse_employee_line(line)
            db.add_employee(name, d, m, y)
            ok += 1
        except ValueError as e:
            errors.append(f"{i}-qator «{esc(line.strip())}»: {e}")
    msg = f"✅ Qo'shildi: {ok} ta"
    if errors:
        msg += "\n\n❌ Xatolar:\n" + "\n".join(errors[:20])
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if len(context.args) != 1 or not context.args[0].isdigit():
        return await update.effective_message.reply_text("Foydalanish: /del ID  (ID ni /list dan oling)")
    if db.delete_employee(int(context.args[0])):
        await update.effective_message.reply_text("🗑 O'chirildi.")
    else:
        await update.effective_message.reply_text("Bunday ID topilmadi.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = db.list_employees()
    if not rows:
        return await update.effective_message.reply_text("Ro'yxat bo'sh. /add bilan qo'shing.")
    t = today()
    rows.sort(key=lambda r: days_until(r[2], r[3], t))
    lines = [
        f"<code>{r[0]:>3}</code> {esc(r[1])} — {format_date(r[2], r[3], r[4])} "
        f"<i>({days_until(r[2], r[3], t)} kun)</i>"
        for r in rows
    ]
    await send_long(update, "📋 <b>Xodimlar</b> (yaqinlashish tartibida):\n\n", lines)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    people = birthdays_in(0)
    if not people:
        return await update.effective_message.reply_text("Bugun tug'ilgan kun yo'q.")
    await update.effective_message.reply_text(congrats_text(people), parse_mode=ParseMode.HTML)


async def cmd_upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = int(context.args[0]) if context.args and context.args[0].isdigit() else 30
    n = min(n, 366)
    t = today()
    rows = [r for r in db.list_employees() if days_until(r[2], r[3], t) <= n]
    if not rows:
        return await update.effective_message.reply_text(f"Keyingi {n} kunda tug'ilgan kun yo'q.")
    rows.sort(key=lambda r: days_until(r[2], r[3], t))
    lines = []
    for _id, name, d, m, y in rows:
        left = days_until(d, m, t)
        bd = next_birthday(d, m, t)
        age = age_on(y, bd)
        when = "bugun" if left == 0 else ("ertaga" if left == 1 else f"{left} kundan keyin")
        extra = f", {age} yosh" if age else ""
        lines.append(f"• <b>{esc(name)}</b> — {format_date(d, m)} ({when}{extra})")
    await send_long(update, f"📅 <b>Keyingi {n} kun:</b>\n\n", lines)


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    chat = update.effective_chat
    db.add_chat(chat.id, chat.title or chat.full_name)
    await update.effective_message.reply_text(
        "🔔 Bu chat obuna qilindi. Tug'ilgan kun tabriklari shu yerga yuboriladi."
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if db.remove_chat(update.effective_chat.id):
        await update.effective_message.reply_text("🔕 Obuna bekor qilindi.")
    else:
        await update.effective_message.reply_text("Bu chat obuna qilinmagan edi.")


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    sent = await run_daily_check(context)
    await update.effective_message.reply_text(f"✅ Tekshiruv bajarildi. Yuborilgan xabarlar: {sent}")


# ---------- Yordamchi funksiyalar ----------

def birthdays_in(n_days: int) -> list[tuple]:
    t = today()
    return [r for r in db.list_employees() if days_until(r[2], r[3], t) == n_days]


def congrats_text(people: list[tuple]) -> str:
    t = today()
    lines = []
    for _id, name, d, m, y in people:
        age = age_on(y, next_birthday(d, m, t))
        lines.append(f"🎉 <b>{esc(name)}</b>" + (f" — {age} yosh!" if age else ""))
    return (
        "🎂 <b>Bugun tug'ilgan kun!</b>\n\n" + "\n".join(lines) +
        "\n\nChin qalbimizdan tabriklaymiz! Sizga mustahkam sog'lik, baxt va "
        "ishlaringizda omad tilaymiz! 🎁🎈"
    )


def reminder_text(people: list[tuple], n: int) -> str:
    when = "Ertaga" if n == 1 else f"{n} kundan keyin"
    t = today()
    lines = []
    for _id, name, d, m, y in people:
        age = age_on(y, next_birthday(d, m, t))
        lines.append(f"• <b>{esc(name)}</b> — {format_date(d, m)}" + (f" ({age} yosh)" if age else ""))
    return f"⏰ <b>{when} tug'ilgan kun:</b>\n\n" + "\n".join(lines) + "\n\nSovg'a tayyorlashni unutmang! 🎁"


async def send_long(update: Update, header: str, lines: list[str]) -> None:
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > 3900:
            await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def safe_send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> bool:
    try:
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:  # bot guruhdan chiqarilgan, admin botni bloklagan va h.k.
        log.warning("Xabar yuborilmadi %s: %s", chat_id, e)
        return False


async def run_daily_check(context: ContextTypes.DEFAULT_TYPE) -> int:
    sent = 0
    group_chats = set(db.list_chats()) | ENV_CHAT_IDS

    todays = birthdays_in(0)
    if todays:
        text = congrats_text(todays)
        # Guruh bo'lmasa, tabrik adminlarga yuboriladi
        for chat_id in (group_chats or ADMIN_IDS):
            sent += await safe_send(context, chat_id, text)

    for n in REMIND_DAYS:
        people = birthdays_in(n)
        if people:
            for admin_id in ADMIN_IDS:
                sent += await safe_send(context, admin_id, reminder_text(people, n))

    log.info("Kunlik tekshiruv: %d ta xabar yuborildi", sent)
    return sent


async def daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_daily_check(context)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan!")
    db.init_db()
    log.info("Baza: %s", "PostgreSQL" if db.IS_PG else f"SQLite ({db.DB_PATH})")
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS o'rnatilmagan — barcha foydalanuvchilar boshqara oladi!")

    app = Application.builder().token(BOT_TOKEN).build()
    handlers = {
        "start": cmd_start, "help": cmd_start, "myid": cmd_myid,
        "add": cmd_add, "import": cmd_import, "del": cmd_del,
        "list": cmd_list, "today": cmd_today, "upcoming": cmd_upcoming,
        "subscribe": cmd_subscribe, "unsubscribe": cmd_unsubscribe, "check": cmd_check,
    }
    for name, fn in handlers.items():
        app.add_handler(CommandHandler(name, fn))
    assistant.register(app, ADMIN_IDS)

    hh, mm = (int(x) for x in NOTIFY_TIME.split(":"))
    app.job_queue.run_daily(daily_job, time=time(hh, mm, tzinfo=TZ), name="daily_birthdays")
    log.info("Bot ishga tushdi. Kunlik tekshiruv: %s (%s)", NOTIFY_TIME, TZ)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
