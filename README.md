# 🎂 Tug'ilgan kun eslatuvchi Telegram bot

Ishxonadagi xodimlarning tug'ilgan kunlarini saqlaydi va:
- **N kun oldin** (standart: 3 va 1 kun) adminlarga shaxsiy xabarda eslatadi — sovg'a tayyorlash uchun;
- **tug'ilgan kun kuni** ishxona guruhiga tabrik yuboradi.

## Buyruqlar

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/start`, `/help` | hamma | Yordam |
| `/today` | hamma | Bugungi tug'ilgan kunlar |
| `/upcoming [kun]` | hamma | Yaqin kunlardagilar (standart 30) |
| `/list` | hamma | Barcha xodimlar (ID bilan) |
| `/myid` | hamma | Telegram ID va chat ID |
| `/add Ism Familiya 15.03.1990` | admin | Xodim qo'shish (yil ixtiyoriy: `15.03`) |
| `/import` + qatorlar | admin | Ko'p xodimni birdan qo'shish |
| `/del ID` | admin | O'chirish |
| `/subscribe` / `/unsubscribe` | admin | Guruhni tabriklar uchun ulash/uzish |
| `/check` | admin | Tekshiruvni hozir ishga tushirish |

`/import` misoli:
```
/import
Ali Valiyev 15.03.1990
Malika Karimova 02.11
```

29-fevralda tug'ilganlar kabisa bo'lmagan yillarda 28-fevralda tabriklanadi.

## Muhit o'zgaruvchilari

| O'zgaruvchi | Majburiy | Standart | Tavsif |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | @BotFather tokeni |
| `ADMIN_IDS` | tavsiya | — | Admin ID lari, vergul bilan. Bo'sh bo'lsa hamma boshqaradi |
| `DATABASE_URL` | tavsiya | — | PostgreSQL. Bo'sh bo'lsa SQLite ishlatiladi |
| `CHAT_IDS` | yo'q | — | Tabrik guruhlari (`/subscribe` o'rniga) |
| `NOTIFY_TIME` | yo'q | `09:00` | Kunlik tekshiruv vaqti |
| `TZ_NAME` | yo'q | `Asia/Tashkent` | Vaqt zonasi |
| `REMIND_DAYS` | yo'q | `3,1` | Necha kun oldin eslatish |
| `DB_PATH` | yo'q | `data/birthdays.db` | SQLite fayl yo'li |

## Railway'ga deploy

1. [railway.com](https://railway.com) → **New Project → Deploy from GitHub repo** → shu repozitoriyni tanlang.
2. Loyihaga **+ New → Database → PostgreSQL** qo'shing (aks holda har deployda ma'lumotlar o'chib ketadi).
3. Bot servisining **Variables** bo'limiga qo'shing:
   - `BOT_TOKEN` = tokeningiz
   - `ADMIN_IDS` = sizning ID (botga `/myid` yozib bilasiz)
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
4. Deploy tugagach, botni ishxona guruhiga qo'shing va guruhda `/subscribe` yozing.

> Postgres o'rniga SQLite ishlatmoqchi bo'lsangiz: servisga **Volume** ulang (masalan `/data`) va `DB_PATH=/data/birthdays.db` qo'ying.

Bot polling rejimida ishlaydi — domen yoki port kerak emas. Faqat **bitta** nusxa (replica) ishlashi kerak.

## Lokal ishga tushirish

```bash
pip install -r requirements.txt
set BOT_TOKEN=...      # Linux/macOS: export BOT_TOKEN=...
python main.py
```
