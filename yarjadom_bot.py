import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен Telegram и ключ DeepSeek
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-d08c904a63614b7b9bbe96d08445426a")

# Проверка ключа
if DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY":
    logger.error("DeepSeek API key не задан! Укажите его в переменной окружения DEEPSEEK_API_KEY.")
    raise ValueError("DeepSeek API key не задан!")

# Подключение к DeepSeek API
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Хранилище состояний пользователей
user_states = {}

# Системный промпт для психолога
SYSTEM_PROMPT = """
Ты — заботливый и тёплый собеседник-психолог в Telegram. 🌱  
Твоя цель — выслушать пользователя, понять его проблему и мягко помочь разобраться в чувствах.  
Отвечай в двух предложениях, разделённых пустой строкой, используй эмодзи (🌱, 🐾, 🌈, 🍉).  
Если уверен в ключевой проблеме (например, тревога, грусть, одиночество), добавь [problem:название_проблемы] в конец.  
Когда проблема ясна (после 3-4 вопросов), предложи пользователю расширенную версию поддержки с приглашением:  
"Кажется, я понимаю, что тебя волнует. Хочешь, мы разберём это глубже в расширенной версии? 🌿 Просто напиши /extended, и начнём!"  
"""

# Приветственное сообщение
WELCOME_MESSAGE = (
    "Привет, я здесь, чтобы поддержать тебя — ты не один со своими мыслями! 🌈\n\n"
    "Что сейчас тебя больше всего волнует или занимает? 🐾"
)

# Сообщение для расширенной версии
EXTENDED_MESSAGE = (
    "Спасибо, что доверился мне — я готов помочь тебе глубже разобраться в этом! 🌱\n\n"
    "Теперь мы можем спокойно всё обсудить и найти пути, чтобы тебе стало легче. 🍉"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [{"role": "system", "content": SYSTEM_PROMPT}],
        "problems": [],
        "question_count": 0
    }
    await update.message.reply_text(WELCOME_MESSAGE)

async def extended(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /extended"""
    user_id = update.effective_chat.id
    if user_id in user_states:
        await update.message.reply_text(EXTENDED_MESSAGE)
    else:
        await update.message.reply_text(
            "Давай начнём с начала! 🌱\n\nЧто тебя сейчас волнует? Напиши мне об этом."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_chat.id
    user_message = update.message.text

    if user_id not in user_states:
        await start(update, context)
        return

    state = user_states[user_id]
    # Добавляем сообщение пользователя в историю (без reasoning_content)
    state["history"].append({"role": "user", "content": user_message})
    state["question_count"] += 1

    try:
        # Запрос к DeepSeek API с учётом ограничений параметров
        response = client.chat.completions.create(
            model="deepseek-reasoner",  # Используем модель с CoT
            messages=state["history"],
            max_tokens=4096  # Ограничиваем длину ответа (по умолчанию 4K, макс 8K)
        )

        # Получаем ответ и цепочку рассуждений
        assistant_response = response.choices[0].message.content
        reasoning_content = response.choices[0].message.reasoning_content
        logger.info(f"CoT для пользователя {user_id}: {reasoning_content}")

        # Извлекаем проблему, если указана
        problem_match = re.search(r"\[problem:([^\]]+)\]", assistant_response)
        problem = problem_match.group(1) if problem_match else "неопределённость"
        clean_response = re.sub(r"\[problem:[^\]]+\]", "", assistant_response).strip()

        # Сохраняем только content в историю (без reasoning_content)
        state["history"].append({"role": "assistant", "content": clean_response})
        state["problems"].append(problem)

        # Проверяем, не пора ли предложить расширенную версию
        if state["problems"].count(problem) >= 3 and "Хочешь, мы разберём это глубже" in clean_response:
            logger.info(f"Пользователь {user_id} готов к расширенной версии, проблема: {problem}")
        await update.message.reply_text(clean_response)

    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek API: {e}")
        await update.message.reply_text(
            "Ой, что-то пошло не так! 🌱\n\nДавай попробуем ещё раз — что тебя волнует?"
        )

if __name__ == "__main__":
    # Создание и запуск бота
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("extended", extended))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()
