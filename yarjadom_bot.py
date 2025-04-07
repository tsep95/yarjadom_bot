import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен Telegram и ключ DeepSeek
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-d08c904a63614b7b9bbe96d08445426a")

# Проверка ключа
if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY":
    logger.error("DeepSeek API key не задан или неверный!")
    raise ValueError("DeepSeek API key не задан или неверный!")
else:
    logger.info(f"Используется DeepSeek API key: {DEEPSEEK_API_KEY[:8]}...")

# Подключение к DeepSeek API
try:
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    logger.info("Клиент DeepSeek API успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации клиента DeepSeek: {e}")
    raise

# Хранилище состояний пользователей
user_states = {}

# Системные промпты для каждого этапа
SYSTEM_PROMPTS = {
    1: """
    Ты — тёплый, эмпатичный психолог. Начни с сочувствия и поддержки. 
    Уточни, что беспокоит человека, задай наводящий вопрос (например, "Что тебя сейчас тревожит?"). 
    Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏). Сохраняй спокойный тон.
    """,
    2: """
    Ты — тёплый, эмпатичный психолог. Прояви участие, помоги уточнить состояние: как оно ощущается, когда началось, как влияет. 
    Задай углубляющий вопрос (например, "Как это проявляется в твоей жизни?"). 
    Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏). Будь поддерживающим.
    """,
    3: """
    Ты — тёплый, эмпатичный психолог. Предложи гипотезу об эмоции (страх, апатия, тревога и т.д.), помоги осознать. 
    Задай вопрос об источнике чувства (например, "Что могло это запустить?"). 
    Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏). Сохраняй тепло.
    """,
    4: """
    Ты — тёплый, эмпатичный психолог. Подведи к глубинной причине (конфликт, прошлое, потребность). 
    Задай вопрос, связывающий настоящее с прошлым (например, "Был ли момент, когда это началось?"). 
    Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏). Будь уверенным.
    """,
    5: """
    Ты — тёплый, эмпатичный психолог. Сделай индивидуальный вывод: 
    - Похвали усилия, дай поддержку. 
    - Опиши состояние и причину (мягко, без осуждения). 
    - Укажи метод психотерапии (КПТ, гештальт и т.д.). 
    - Предложи расширенную версию: «Если тебе это откликается — напиши /extended. Я рядом 🤍». 
    Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏).
    """
}

# Приветственное сообщение
WELCOME_MESSAGE = "Привет! Я здесь, чтобы тебя поддержать 😊. Что сейчас тебя волнует?"

# Сообщение для расширенной версии
EXTENDED_MESSAGE = (
    "Спасибо, что доверился мне — теперь мы можем копнуть глубже! 🌿\n\n"
    "Я рядом, чтобы помочь тебе разобраться и найти спокойствие 🤍."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "message_count": 0
    }
    await update.message.reply_text(WELCOME_MESSAGE)

async def extended(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /extended"""
    user_id = update.effective_chat.id
    if user_id in user_states:
        await update.message.reply_text(EXTENDED_MESSAGE)
    else:
        await update.message.reply_text(WELCOME_MESSAGE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_chat.id
    user_message = update.message.text

    if user_id not in user_states:
        await start(update, context)
        return

    state = user_states[user_id]
    state["message_count"] += 1
    step = min(state["message_count"], 5)  # Ограничиваем 5 шагами
    state["history"].append({"role": "user", "content": user_message})

    try:
        # Формируем сообщения с системным промптом и историей
        messages = [{"role": "system", "content": SYSTEM_PROMPTS[step]}] + state["history"]
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content
        state["history"].append({"role": "assistant", "content": assistant_response})
        
        await update.message.reply_text(assistant_response)
        logger.info(f"Сообщение {step} для пользователя {user_id}: {assistant_response}")

    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek API: {e}")
        await update.message.reply_text("Ой, что-то пошло не так 🌿. Давай попробуем ещё раз?")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("extended", extended))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()
