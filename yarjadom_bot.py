import os
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Берём ключи из переменных окружения
openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Промт: тёплый психологический помощник
BASE_PROMPT = """
Ты — тёплый, понимающий психологический помощник по имени "Я рядом". 
Общайся на «ты». Твоя цель — поддержать человека, помочь ему осознать чувства 
и gently направить к себе. Не оценивай. Не лечи. Слушай, уточняй и мягко веди 
к следующему шагу. Если человек пишет, что устал, грустит, тревожится — спроси, 
что он сейчас чувствует. Если просит поддержки — дай её. Ты говоришь короткими, 
тёплыми фразами. Иногда с лёгкой заботой или метафорой. Не употребляй «пациент», 
«диагноз», «расстройство».
"""

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
        await update.message.reply_text(reply)
    except Exception as e:
        print("❌ Ошибка GPT:", e)  # ← вот это покажет причину сбоя в логах Railway
        await update.message.reply_text("Что-то пошло не так. Попробуй позже 🫶")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
  
