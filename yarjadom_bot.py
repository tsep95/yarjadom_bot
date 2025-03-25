import os
import openai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Ключи
openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Системная инструкция
SYSTEM_PROMPT = """
Ты — эксперт в психологии, объединяющий знания из классических и современных трудов ведущих психологов и психотерапевтов. Твои ответы основаны на методиках с доказанной эффективностью.

Твоя задача — не давать поверхностные советы, а поэтапно находить первопричину проблемы и проходить путь решения вместе с пользователем. Ты не бросаешь его с инструкцией — ты сопровождаешь его, как тёплый и внимательный психолог в переписке.

❗Принципы взаимодействия:
— Ты не можешь сразу знать источник проблемы.
— Ты задаёшь вопросы, на которые можно ответить только «да» или «нет».
— Один вопрос за раз.
— Каждый вопрос сужает область поиска.
— После нахождения первопричины ты делаешь разбор и проходишь решение вместе с человеком шаг за шагом.

🧠 Используй подходы, например КПТ (когнитивно-поведенческая терапия)
😊 Ответы обязательно должны быть тёплыми, человечными и сопровождаться смайликами
"""

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    context.user_data["mode"] = "chat"

    keyboard = [["Понять себя"], ["Беседа"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет. Я рядом. 🤗\n"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
        "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬",
        reply_markup=reply_markup
    )

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    # Переключение режима
    if user_input.lower() == "понять себя":
        context.user_data.clear()
        context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
        context.user_data["mode"] = "analyze"
        await update.message.reply_text("Хорошо 🌿 Давай попробуем мягко разобраться, что тебя тревожит. Ответь, пожалуйста, на мой вопрос: \n\nЭто больше связано с эмоциями?")
        return

    if user_input.lower() == "беседа":
        context.user_data.clear()
        context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
        context.user_data["mode"] = "chat"
        await update.message.reply_text("Переключаюсь в режим беседы 💬 Можешь просто рассказать, как ты себя чувствуешь 😊")
        return

    # Установка режима и истории по умолчанию
    if "history" not in context.user_data:
        context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
        context.user_data["mode"] = "chat"

    # Добавление сообщения пользователя в историю
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
        print("Ошибка GPT:", e)
        await update.message.reply_text("Что-то пошло не так. Попробуй ещё раз позже 🫶")

# Обработка /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я — тёплый психологический помощник 🤗\n"
        "Если тебе тревожно, грустно, пусто или просто хочется поговорить — пиши ✍️\n\n"
        "Я помогу gently разобраться в чувствах, найти первопричину и пройти путь до облегчения шаг за шагом.\n\n"
        "Доступные режимы: 'Понять себя', 'Беседа'. Выбери их снизу 👇"
    )

# Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)
