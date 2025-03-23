import os
import openai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackContext,
    filters,
)

openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

SYSTEM_PROMPT = """
Ты — эксперт в психологии. Твоя задача — не давать советы, а поэтапно понять суть проблемы и пройти решение вместе с человеком. Используй КПТ и другие проверенные методы. Ты не бросаешь человека с инструкцией, ты рядом.
Принципы:
— Один вопрос за раз, ответы — только «да» или «нет»
— Не переходи к техникам, пока не понята суть проблемы
— Используй смайлики для поддержки
— В конце — спроси, стало ли легче 💬
"""

START_MESSAGE = (
    "Привет. Я рядом. 🤗\n"
    "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
    "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
    "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
    "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
    "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
    "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
)

analyze_questions = [
    "Твоя проблема больше связана с эмоциями?",
    "Это чаще тревога, чем грусть?",
    "Это связано с ожиданиями других людей?",
    "Это влияет на твою самооценку?",
    "Ты чувствуешь вину или стыд из-за этого?",
    "Это мешает тебе делать важные дела?"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "chat"
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text(START_MESSAGE, reply_markup=main_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я могу помочь тебе разобраться в чувствах, gently найти причину и пройти путь до облегчения. 💛\n\n"
        "Ты можешь переключаться между режимами:\n"
        "👉 /analyze — Понять себя\n"
        "👉 /chat — Беседа"
    )

async def set_mode_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "analyze"
    context.user_data["analyze_index"] = 0
    await update.message.reply_text("Давай вместе попробуем добраться до сути. Отвечай только «да» или «нет». ✍️")
    await update.message.reply_text(analyze_questions[0])

async def set_mode_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "chat"
    await update.message.reply_text("Хорошо, теперь мы просто беседуем. Можешь написать, что чувствуешь. 😊")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().lower()
    mode = context.user_data.get("mode", "chat")

    if mode == "analyze":
        index = context.user_data.get("analyze_index", 0)
        if user_input not in ["да", "нет"]:
            await update.message.reply_text("Пожалуйста, ответь только «да» или «нет» 🙏")
            return

        if index + 1 < len(analyze_questions):
            context.user_data["analyze_index"] = index + 1
            await update.message.reply_text(analyze_questions[index + 1])
        else:
            context.user_data["mode"] = "chat"
            await update.message.reply_text(
                "Спасибо, что прошёл этот путь 🙏\n\n"
                "Исходя из твоих ответов, похоже, что суть проблемы — \n"
                "в переживаниях, связанных с ожиданиями и самооценкой. 💭\n"
                "Это может вызывать тревогу, вину или мешать действовать.\n\n"
                "Хочешь, я предложу тёплую практику, чтобы стало немного легче? ✨"
            )
    else:
        context.user_data["history"].append({"role": "user", "content": user_input})
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4-1106-preview",
                messages=context.user_data["history"],
                temperature=0.7
            )
            reply = response.choices[0].message.content.strip()
            context.user_data["history"].append({"role": "assistant", "content": reply})
            await update.message.reply_text(reply[:4000])
        except Exception as e:
            print("GPT Error:", e)
            await update.message.reply_text("Что-то пошло не так. Попробуй позже 🫶")

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["/chat", "/analyze"]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("analyze", set_mode_analyze))
    app.add_handler(CommandHandler("chat", set_mode_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)
