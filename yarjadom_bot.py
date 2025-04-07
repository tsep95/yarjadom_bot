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
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY")

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
Ты — тёплый, эмпатичный психолог. Общайся коротко, с душой и поддержкой. 
Цель: углубляться в чувства через наводящие вопросы. 
Задавай один короткий вопрос, копающий в эмоции. 
Используй 1 смайлик (😊, 🌿, ✨, 🤍, ☀️, 🙏). 
Если выявил глубокую эмоцию или причину (страх, стыд, неуверенность и т.д.), добавь [deep_reason_detected].
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный психолог. Дай короткий вывод: 
- Похвали усилия, поддержи. 
- Назови причину состояния (мягко). 
- Предложи метод психотерапии (КПТ, гештальт и т.д.). 
- Пригласи: «Хочешь глубже разобраться? Напиши /extended. Я рядом 🤍». 
Используй 1–2 смайлика (😊, 🌿, ✨, 🤍, ☀️, 🙏).
"""

# Промежуточное сообщение
INTERMEDIATE_MESSAGE = "Думаю над этим... 🌿"

# Приветственное сообщение
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать 😊. Что тебя волнует?"

# Сообщение для расширенной версии
EXTENDED_MESSAGE = "Спасибо, что поделился! 🌿 Теперь можем глубже разобраться. Я рядом 🤍."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "deep_reason_detected": False,
        "last_intermediate_message_id": None
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
    chat_id = update.effective_chat.id
    user_message = update.message.text

    if user_id not in user_states:
        await start(update, context)
        return

    state = user_states[user_id]

    # Удаляем предыдущее промежуточное сообщение, если оно есть
    if state["last_intermediate_message_id"]:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

    state["history"].append({"role": "user", "content": user_message})

    try:
        # Выбираем промпт
        if state["deep_reason_detected"]:
            system_prompt = FINAL_PROMPT
        else:
            system_prompt = BASE_PROMPT

        # Формируем сообщения
        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        # Проверяем глубинную причину
        if "[deep_reason_detected]" in assistant_response:
            state["deep_reason_detected"] = True
            assistant_response = assistant_response.replace("[deep_reason_detected]", "").strip()

        state["history"].append({"role": "assistant", "content": assistant_response})
        await update.message.reply_text(assistant_response)
        logger.info(f"Сообщение для пользователя {user_id}: {assistant_response}")

        # Если диалог продолжается (не финал), отправляем промежуточное сообщение
        if not state["deep_reason_detected"]:
            thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
            state["last_intermediate_message_id"] = thinking_msg.message_id

    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek API: {e}")
        await update.message.reply_text("Ой, что-то не так 🌿. Давай ещё раз?")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("extended", extended))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()
