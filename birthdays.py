"""Tug'ilgan kun hisob-kitoblari (Telegram'ga bog'liq emas)."""
import calendar
import re
from datetime import date

MONTHS_UZ = [
    "", "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]

_DATE_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})(?:[./-](\d{4}))?$")


def parse_date(text: str) -> tuple[int, int, int | None]:
    """'15.03.1990' yoki '15.03' -> (kun, oy, yil|None). Xato bo'lsa ValueError."""
    m = _DATE_RE.match(text.strip())
    if not m:
        raise ValueError("Sana formati noto'g'ri. Masalan: 15.03.1990 yoki 15.03")
    day, month = int(m.group(1)), int(m.group(2))
    year = int(m.group(3)) if m.group(3) else None
    if year is not None and not (1900 <= year <= date.today().year):
        raise ValueError("Yil noto'g'ri.")
    # 29-fevralni tekshirish uchun kabisa yilini olamiz
    check_year = year if year is not None else 2000
    try:
        date(check_year, month, day)
    except ValueError:
        raise ValueError("Bunday sana mavjud emas.")
    return day, month, year


def parse_employee_line(line: str) -> tuple[str, int, int, int | None]:
    """'Ism Familiya 15.03.1990' -> (ism, kun, oy, yil)."""
    parts = line.strip().rsplit(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Format: Ism Familiya KK.OO.YYYY")
    name, date_str = parts[0].strip(), parts[1]
    if len(name) > 100:
        raise ValueError("Ism juda uzun.")
    day, month, year = parse_date(date_str)
    return name, day, month, year


def birthday_in_year(day: int, month: int, year: int) -> date:
    """Berilgan yildagi tug'ilgan kun. 29-fevral kabisa bo'lmagan yilda 28-fevral."""
    if month == 2 and day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def next_birthday(day: int, month: int, today: date) -> date:
    bd = birthday_in_year(day, month, today.year)
    if bd < today:
        bd = birthday_in_year(day, month, today.year + 1)
    return bd


def days_until(day: int, month: int, today: date) -> int:
    return (next_birthday(day, month, today) - today).days


def age_on(year: int | None, bd: date) -> int | None:
    return bd.year - year if year else None


def format_date(day: int, month: int, year: int | None = None) -> str:
    s = f"{day}-{MONTHS_UZ[month]}"
    return f"{s} {year}" if year else s
