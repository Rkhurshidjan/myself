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

## 🎙 Ovozli yordamchi

Umumiy savol-javob yordamchisi: ovozli xabar → **Groq Whisper** matnga aylantiradi (bepul) → **Claude Haiku 5.5** javob beradi (~$0.0005 / savol) → **Edge TTS** o'zbek ovozida o'qiydi (bepul). Bot aniqlangan matnni, javob matnini va ovozli javobni yuboradi.

- **Shaxsiy chatda:** istalgan ovozli yoki matnli xabar (matnga faqat matn bilan javob beradi).
- **Guruhda:** faqat botning xabariga *reply* qilingan ovozli xabarlar yoki `/ask savol`.
- `/reset` — suhbat tarixini tozalash. Bot har chat bo'yicha oxirgi 10 ta savol-javobni eslab qoladi (qayta ishga tushganda tarix o'chadi).
- Yoqish uchun `ANTHROPIC_API_KEY` va `GROQ_API_KEY` kerak. Ulardan biri bo'lmasa, yordamchi o'chiq turadi, tug'ilgan kun qismi ishlayveradi.
- Xarajatni nazorat qilish uchun standart holatda faqat `ADMIN_IDS` dagilar foydalana oladi. Boshqalarga ruxsat: `ASSISTANT_USERS=111,222` yoki hamma uchun `ASSISTANT_USERS=*`.
- Groq bepul tarifida daqiqalik/kunlik limit bor; limitga yetilsa bot "ovozni tanib bo'lmadi" deydi, birozdan keyin yana ishlaydi.
- Edge TTS — Microsoftning norasmiy bepul xizmati. U ishlamay qolsa, bot faqat matn bilan javob beradi.
- `CLAUDE_MODEL` ni `claude-sonnet-5-5` yoki `claude-opus-5-5` ga o'zgartirsangiz javoblar aqlliroq, lekin qimmatroq bo'ladi; bu modellarda Claude rad etgan so'rov avtomatik zaxira modelda qayta ishlanadi.

| O'zgaruvchi | Standart | Tavsif |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | [console.anthropic.com](https://console.anthropic.com) |
| `GROQ_API_KEY` | — | [console.groq.com/keys](https://console.groq.com/keys) (bepul) |
| `ASSISTANT_USERS` | (adminlar) | `*` yoki ID lar |
| `CLAUDE_MODEL` | `claude-haiku-5-5` | Claude modeli |
| `CLAUDE_EFFORT` | `low` | `low`/`medium`/`high` — yuqorisi aqlliroq, lekin sekin va qimmat |
| `TTS_VOICE` | `uz-UZ-SardorNeural` | Ayol ovozi: `uz-UZ-MadinaNeural` |
| `STT_LANGUAGE` | `uz` | Nutq tili (`ru`, `en`...). Bo'sh — avtomatik |
| `STT_MODEL` | `whisper-large-v3` | Groq nutqni tanish modeli |
| `VOICE_REPLY` | `1` | `0` — faqat matnli javob |
| `HISTORY_TURNS` | `10` | Eslab qolinadigan savol-javoblar soni |

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
