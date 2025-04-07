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

# Системные промпты
BASE_PROMPT = """
Ты — тёплый, эмпатичный психолог. Общайся с душой, без осуждения, с поддержкой. 
Цель: выслушать человека, понять его чувства и мягко углубляться в них через наводящие вопросы. 
Задавай вопрос в каждом ответе, чтобы копнуть глубже (например, "Что это для тебя значит?", "Когда ты это впервые заметил?"). 
Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏). Сохраняй спокойный и тёплый тон.
Если чувствуешь, что достиг глубинной причины (внутренний конфликт, травма, потребность), добавь в конец [deep_reason_detected].
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный психолог. На основе всей беседы сделай индивидуальный вывод: 
- Похвали усилия человека, дай поддержку. 
- Опиши, что с ним происходит и почему (мягко, без осуждения). 
- Укажи подходящий метод психотерапии (КПТ, гештальт, психоанализ, телесно-ориентированная и т.д.). 
- Предложи расширенную версию: «Если тебе это откликается — напиши /extended. Я рядом 🤍». 
Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏). Будь заботливым и уверенным.
"""

# Приветственное сообщение
WELCOME_MESSAGE = "Привет! Я здесь, чтобы тебя выслушать и поддержать 😊. Что сейчас тебя волнует?"

# Сообщение для расширенной версии
EXTENDED_MESSAGE = (
    "Спасибо, что доверился мне — теперь мы можем спокойно всё разобрать! 🌿\n\n"
    "Я рядом, чтобы помочь тебе найти ответы и тепло внутри 🤍."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "deep_reason_detected": False
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
    state["history"].append({"role": "user", "content": user_message})

    try:
        # Выбираем промпт в зависимости от состояния
        if state["deep_reason_detected"]:
            system_prompt = FINAL_PROMPT
        else:
            system_prompt = BASE_PROMPT

        # Формируем сообщения с системным промптом и историей
        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        # Проверяем, достиг ли бот глубинной причины
        if "[deep_reason_detected]" in assistant_response:
            state["deep_reason_detected"] = True
            assistant_response = assistant_response.replace("[deep_reason_detected]", "").strip()

        state["history"].append({"role": "assistant", "content": assistant_response})
        await update.message.reply_text(assistant_response)
        logger.info(f"Сообщение для пользователя {user_id}: {assistant_response}")

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
