import os
import openai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from gtts import gTTS

# Ключи
openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Инструкции для режимов
MAIN_PROMPT = """... (тот же основной текст без изменений) ..."""

DIAGNOSTIC_PROMPT = """... (тот же диагностический текст без изменений) ..."""

MEDITATION_PROMPT = """
Ты создаёшь индивидуальную медитацию для человека на основе его состояния. 
Она должна быть мягкой, тёплой, направленной на облегчение именно того состояния, которое он описал. Используй дыхание, образы, тело, визуализацию, свет, заботу. Медитация не должна быть длинной — около 1–2 минут текста. Говори от первого лица, спокойно, с паузами. Не используй сложные фразы.
"""

KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("Понять себя"), KeyboardButton("Беседа")],
        [KeyboardButton("Создать медитацию")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "main"
    context.user_data["history"] = [{"role": "system", "content": MAIN_PROMPT}]
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text(
        "Привет. Я рядом. 🤗\n"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
        "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬",
        reply_markup=KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text(
        "Я — тёплый психологический помощник 🤗\n"
        "Если тебе тревожно, грустно, пусто или просто хочется поговорить — пиши ✍️\n\n"
        "Я помогу разобраться в чувствах, gently найти первопричину и пройти путь до облегчения.\n"
        "Задаю только вопросы, на которые можно ответить «да» или «нет», и иду вместе с тобой шаг за шагом.\n\n"
        "Попробуй просто начать: расскажи, как ты сейчас? 💬"
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text("Я пока не умею слушать голосовые 🙈 Можешь написать словами? Я рядом ✍️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    if user_input.lower() == "понять себя":
        context.user_data.clear()
        context.user_data["mode"] = "diagnostic"
        context.user_data["history"] = [{"role": "system", "content": DIAGNOSTIC_PROMPT}]
        await update.message.reply_text("Давай попробуем вместе понять, что именно тебя беспокоит 💬 Отвечай просто: «да» или «нет». Начнём? ✨")
        return

    if user_input.lower() == "беседа":
        context.user_data.clear()
        context.user_data["mode"] = "main"
        context.user_data["history"] = [{"role": "system", "content": MAIN_PROMPT}]
        await update.message.reply_text("Хорошо, возвращаемся к обычной тёплой беседе 🤗 Расскажи, как ты сейчас? 💬")
        return

    if user_input.lower() == "создать медитацию":
        context.user_data.clear()
        context.user_data["mode"] = "meditation"
        await update.message.reply_text("Расскажи, что тебя сейчас беспокоит, и я создам медитацию только для тебя 🧘")
        return

    # Настройка истории под режим
    if "history" not in context.user_data:
        mode = context.user_data.get("mode", "main")
        if mode == "diagnostic":
            context.user_data["history"] = [{"role": "system", "content": DIAGNOSTIC_PROMPT}]
        elif mode == "meditation":
            context.user_data["history"] = [{"role": "system", "content": MEDITATION_PROMPT}]
        else:
            context.user_data["history"] = [{"role": "system", "content": MAIN_PROMPT}]

    mode = context.user_data.get("mode", "main")
    context.user_data["history"].append({"role": "user", "content": user_input})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=context.user_data["history"],
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        context.user_data["history"].append({"role": "assistant", "content": reply})
        await update.message.chat.send_action(action="typing")

        if mode == "meditation":
            tts = gTTS(text=reply, lang='ru')
            audio_path = "meditation.mp3"
            tts.save(audio_path)
            with open(audio_path, 'rb') as audio:
                await update.message.reply_voice(audio)
        else:
            await update.message.reply_text(reply[:4000])

    except Exception as e:
        print("❌ Ошибка GPT:", e)
        await update.message.chat.send_action(action="typing")
        await update.message.reply_text("Что-то пошло не так. Попробуй позже 🫶")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
