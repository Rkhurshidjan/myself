"""Umumiy ovozli yordamchi.

Ovozli xabar -> Groq Whisper (matnga, bepul) -> Claude (javob) -> Edge TTS (ovozga, bepul).
Matnli xabarlarga ham (shaxsiy chatda) javob beradi.
"""
import io
import logging
import os
from collections import defaultdict, deque
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
import edge_tts
from openai import AsyncOpenAI  # Groq OpenAI bilan mos API beradi
from telegram import InputFile, Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

log = logging.getLogger("assistant")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "low")  # suhbat uchun low yetarli va tez
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "uz").strip()  # bo'sh = tilni avtomatik aniqlash
TTS_VOICE = os.getenv("TTS_VOICE", "uz-UZ-SardorNeural")  # ayol ovozi: uz-UZ-MadinaNeural
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Server tomonidagi zaxira model (refusal fallback) faqat shu modellarda ishlaydi
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
VOICE_REPLY = os.getenv("VOICE_REPLY", "1") != "0"
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "10"))  # chat bo'yicha eslab qolinadigan savol-javoblar
TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Tashkent"))

# "*" = hamma; bo'sh = faqat adminlar (adminlar ham bo'lmasa — hamma)
_users_raw = os.getenv("ASSISTANT_USERS", "").replace(" ", "")
ASSISTANT_PUBLIC = _users_raw == "*"
ASSISTANT_USERS = {int(x) for x in _users_raw.split(",") if x.lstrip("-").isdigit()}

MAX_VOICE_SECONDS = 300
TTS_MAX_CHARS = 4000

SYSTEM_PROMPT = """Sen ishxona Telegram botidagi aqlli yordamchisan. Foydalanuvchilar senga ko'pincha ovozli xabar yuborishadi; ularning nutqi avtomatik matnga aylantirilgan, shuning uchun unda xatolar bo'lishi mumkin — ma'noni kontekstdan tushun.

Foydalanuvchi qaysi tilda yozsa yoki gapirsa, o'sha tilda javob ber (odatda o'zbek tili, lotin yozuvida).
Javobing ovozga aylantirilib o'qib beriladi, shuning uchun:
- qisqa va aniq javob ber, odatda 1-5 gap; foydalanuvchi batafsil so'rasagina uzunroq yoz;
- Markdown, jadval, sarlavha, emoji va maxsus belgilarni ishlatma — oddiy gaplar bilan yoz;
- ro'yxat kerak bo'lsa, "birinchidan, ikkinchidan" kabi so'zlar bilan ayt.
Bilmagan narsangni o'ylab topma — bilmasligingni ochiq ayt. Real vaqtdagi ma'lumotlarga (ob-havo, valyuta kursi, yangiliklar) kiring yo'q."""

_claude: anthropic.AsyncAnthropic | None = None
_groq: AsyncOpenAI | None = None
_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=HISTORY_TURNS * 2))


def enabled() -> bool:
    return bool(ANTHROPIC_API_KEY and GROQ_API_KEY)


def _allowed(update: Update, admin_ids: set[int]) -> bool:
    if ASSISTANT_PUBLIC:
        return True
    allowed = admin_ids | ASSISTANT_USERS
    return not allowed or (update.effective_user is not None and update.effective_user.id in allowed)


async def transcribe(audio: bytes, filename: str) -> str:
    kwargs = {"language": STT_LANGUAGE} if STT_LANGUAGE else {}
    resp = await _groq.audio.transcriptions.create(
        model=STT_MODEL, file=(filename, io.BytesIO(audio)), **kwargs
    )
    return (resp.text or "").strip()


async def synthesize(text: str) -> bytes:
    """Microsoft Edge TTS orqali MP3 (Telegram sendVoice MP3 ni qabul qiladi)."""
    communicate = edge_tts.Communicate(text[:TTS_MAX_CHARS], voice=TTS_VOICE)
    buf = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    if not buf:
        raise RuntimeError("Edge TTS bo'sh audio qaytardi")
    return bytes(buf)


async def ask_claude(chat_id: int, user_text: str) -> str:
    history = _history[chat_id]
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    params = dict(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=f"{SYSTEM_PROMPT}\n\nBugungi sana: {today}.",
        messages=list(history) + [{"role": "user", "content": user_text}],
        output_config={"effort": CLAUDE_EFFORT},
    )
    if CLAUDE_MODEL in FALLBACK_MODELS:
        # Xavfsizlik filtri so'rovni rad etsa, server avtomatik boshqa modelda qayta urinadi
        response = await _claude.beta.messages.create(
            **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
        )
    else:
        response = await _claude.messages.create(**params)

    if response.stop_reason == "refusal":
        return "Kechirasiz, bu so'rovga javob bera olmayman."

    answer = "\n".join(b.text for b in response.content if b.type == "text").strip()
    if not answer:
        return "Kechirasiz, javob tayyorlay olmadim. Savolni boshqacha qilib bering."

    # Tarixda faqat matn saqlanadi; deque eng eski juftliklarni o'zi tashlab yuboradi
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": answer})
    return answer


async def _reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, with_voice: bool) -> None:
    chat_id = update.effective_chat.id
    msg = update.effective_message
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        answer = await ask_claude(chat_id, user_text)
    except anthropic.RateLimitError:
        await msg.reply_text("⏳ Juda ko'p so'rov bo'ldi, birozdan keyin qayta urinib ko'ring.")
        return
    except anthropic.APIConnectionError:
        await msg.reply_text("🌐 Claude serveriga ulanib bo'lmadi. Keyinroq urinib ko'ring.")
        return
    except anthropic.APIStatusError as e:
        log.error("Claude xatosi %s: %s", e.status_code, e.message)
        await msg.reply_text("⚠️ Yordamchida xatolik yuz berdi. Keyinroq urinib ko'ring.")
        return

    for i in range(0, len(answer), 4000):
        await msg.reply_text(answer[i:i + 4000])

    if with_voice and VOICE_REPLY:
        try:
            await context.bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)
            audio = await synthesize(answer)
            await msg.reply_voice(voice=InputFile(audio, filename="javob.mp3"))
        except Exception as e:
            log.warning("Ovoz yaratilmadi: %s", e)


def register(app: Application, admin_ids: set[int]) -> None:
    """Yordamchi handlerlarini botga ulaydi."""
    global _claude, _groq
    if not enabled():
        log.warning("Ovozli yordamchi o'chiq: ANTHROPIC_API_KEY va GROQ_API_KEY kerak.")
        return
    _claude = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    _groq = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

    async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _allowed(update, admin_ids):
            return
        msg = update.effective_message
        if update.effective_chat.type != ChatType.PRIVATE:
            replied = msg.reply_to_message
            if not (replied and replied.from_user and replied.from_user.id == context.bot.id):
                return  # guruhda faqat botning xabariga javob qilingan ovozlar
        media = msg.voice or msg.audio
        if media.duration and media.duration > MAX_VOICE_SECONDS:
            await msg.reply_text(f"Ovozli xabar {MAX_VOICE_SECONDS // 60} daqiqadan oshmasin.")
            return
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        try:
            tg_file = await context.bot.get_file(media.file_id)
            data = bytes(await tg_file.download_as_bytearray())
            name = "voice.ogg" if msg.voice else (getattr(media, "file_name", None) or "audio.mp3")
            text = await transcribe(data, name)
        except Exception as e:
            log.error("Nutqni tanib bo'lmadi: %s", e)
            await msg.reply_text("⚠️ Ovozli xabarni tanib bo'lmadi. Qayta urinib ko'ring.")
            return
        if not text:
            await msg.reply_text("Ovozli xabarda gap eshitilmadi.")
            return
        await msg.reply_text(f"🗣 {text}")
        await _reply(update, context, text, with_voice=True)

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _allowed(update, admin_ids):
            return
        await _reply(update, context, update.effective_message.text, with_voice=False)

    async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _allowed(update, admin_ids):
            return
        text = " ".join(context.args)
        if not text:
            await update.effective_message.reply_text("Foydalanish: /ask savolingiz")
            return
        await _reply(update, context, text, with_voice=False)

    async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _history.pop(update.effective_chat.id, None)
        await update.effective_message.reply_text("🧹 Suhbat tarixi tozalandi.")

    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("reset", cmd_reset))
    # Shaxsiy chatda: har qanday ovozli/matnli xabar. Guruhda: faqat botga javob (reply) qilinganda.
    to_bot = filters.REPLY & filters.ChatType.GROUPS
    app.add_handler(MessageHandler((filters.VOICE | filters.AUDIO) & (private | to_bot), on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private, on_text))
    log.info("Ovozli yordamchi yoqildi (model: %s)", CLAUDE_MODEL)
