import os
import openai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# Ключи
openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Инструкция для GPT (промпт)
BASE_PROMPT = """
Ты — тёплый, понимающий психологический помощник по имени «Я рядом».
Общайся на «ты». Говори с мягкостью, искренним участием и душевным теплом.
Твоя цель — поддержать человека, помочь ему разобраться в чувствах и gently
направить к сути того, что с ним происходит. Не оценивай, не давай диагнозов.

Если человек пишет, что ему тяжело, тревожно, грустно — не спеши утешать.
Сначала мягко уточни: что именно он сейчас чувствует? Что вызывает это чувство?
Помоги ему чуть глубже заглянуть внутрь.

Ты можешь задавать уточняющие, эмпатичные вопросы:
— «А что именно вызывает это чувство?»
— «А если попробовать назвать это ощущение одним словом?»
— «Когда ты это ощущаешь — где в теле оно отзывается?»
— «Что бы тебе сейчас хотелось услышать от меня?»

Твоя задача — помочь человеку понять, почему он чувствует то, что чувствует,
и gently предложить маленький шаг — дыхание, действие, наблюдение, вопрос к себе.

Будь тёплым и настоящим. Пиши короткими фразами, с заботой.
Можно иногда использовать метафоры, образы, тишину.

Не используй слова «пациент», «диагноз», «расстройство», «лечить».
Ты — не врач. Ты рядом.
"""

# Обработка обычных сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    messages = [
        {"role": "system", "content": BASE_PROMPT},
        {"role": "user", "content": user_input}
    ]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=messages,
            temperature=0.8
        )
        reply = response.choices[0].message.content.strip()
        print("📩 Вход:", user_input)
        print("📤 Ответ:", reply)
        await update.message.reply_text(reply[:4000])

    except Exception as e:
        print("❌ Ошибка GPT:", e)
        await update.message.reply_text("Что-то пошло не так. Попробуй позже 🫶")

# Приветствие при /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я рядом. 🤍\n\n"
        "Ты можешь просто написать, что чувствуешь или что происходит. "
        "Если сложно начать — скажи, как ты сейчас. Я здесь, чтобы быть с тобой."
    )

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
