import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import re

# Токен Telegram и ключ DeepSeek из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY")

# Подключение к DeepSeek API
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Хранилище состояний пользователей
user_states = {}

# Системный промпт для психолога
SYSTEM_PROMPT = """
Ты — заботливый и теплый собеседник-психолог в Telegram. 🌱  
Общайся сочувственно, задавай один вопрос за раз.  
Ответ должен быть из двух предложений, разделённых пустой строкой.  
Используй эмодзи (🌱, 🐾, 🌈, 🍉).  
Если уверен в эмоции, добавь [emotion:эмоция] в конец ответа.  
После 4 повторений одной эмоции заверши разговор финальным сообщением.  
"""

# Приветственное сообщение
WELCOME_MESSAGE = (
    "Привет, я рад, что ты здесь — это уже первый шаг к тому, чтобы стало легче! 🌈\n\n"
    "Что сейчас занимает твои мысли больше всего? 🐾"
)

# Финальное сообщение
FINAL_MESSAGE = (
    "Спасибо, что поделился — ты сделал важный шаг к пониманию себя! 🌱\n\n"
    "Похоже, твои чувства сейчас связаны с {emotion}, и это нормально — я рядом, чтобы помочь тебе с этим разобраться. 🌿"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    # Инициализация состояния пользователя
    user_states[user_id] = {
        "history": [{"role": "system", "content": SYSTEM_PROMPT}],
        "emotions": [],
        "question_count": 0
    }
    await update.message.reply_text(WELCOME_MESSAGE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_chat.id
    user_message = update.message.text

    # Если пользователь новый, инициализируем его состояние
    if user_id not in user_states:
        await start(update, context)
        return

    state = user_states[user_id]
    # Добавляем сообщение пользователя в историю
    state["history"].append({"role": "user", "content": user_message})
    state["question_count"] += 1

    # Запрос к DeepSeek API
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=state["history"],
        temperature=0.7
    )

    # Получаем ответ и очищаем от тегов эмоций
    assistant_response = response.choices[0].message.content
    emotion_match = re.search(r"\[emotion:([^\]]+)\]", assistant_response)
    emotion = emotion_match.group(1) if emotion_match else "неопределённость"
    clean_response = re.sub(r"\[emotion:[^\]]+\]", "", assistant_response).strip()

    # Сохраняем ответ в историю и эмоцию
    state["history"].append({"role": "assistant", "content": clean_response})
    state["emotions"].append(emotion)

    # Проверяем, не пора ли завершить разговор
    if state["emotions"].count(emotion) >= 4:
        final_text = FINAL_MESSAGE.format(emotion=emotion)
        await update.message.reply_text(final_text)
        del user_states[user_id]  # Очищаем состояние пользователя
    else:
        await update.message.reply_text(clean_response)

if __name__ == "__main__":
    # Создание и запуск бота
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling()
