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
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"  # Ваш ключ

# Проверка ключа
if not DEEPSEEK_API_KEY:
    logger.error("DeepSeek API key не задан!")
    raise ValueError("DeepSeek API key не задан!")
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
Ты — тёплый, эмпатичный психолог. Отвечай контекстно, опираясь на предыдущее сообщение пользователя, без повторных приветствий после первого сообщения. 

Цель: углубляться в чувства через 5 продуманных, бережных вопросов. Задавай по одному вопросу за раз, в зависимости от количества предыдущих ответов (отслеживай по истории). Каждое сообщение должно быть длиной 2-3 строки, как пример: "Да, в тишине и одиночестве чувства особенно громко заявляют о себе... Это так по-человечески 🌱. Как ты думаешь, что это горе пытается тебе сказать? ✨" Вопросы:  
1. "Я так тебе сочувствую — это огромная боль 🤍. Что сейчас лежит у тебя на сердце? 🌱"  
2. "Это чувство такое глубокое 🙏. Когда ты впервые заметил его? ☀️"  
3. "Понимаю, как это с тобой 🌿. Где ты его ощущаешь в себе? ✨"  
4. "Слышу твою боль 🤍. Что оно пытается тебе сказать? 🌱"  
5. "Это так трогательно ✨. Какие слова оно бы выбрало? 🌿"  

Говори как заботливый друг: мягко, тепло, с поддержкой. Используй тёплые смайлики (🌱, ☀️, 🙏, ✨, 🤍, 🌿). Не добавляй [deep_reason_detected], пока не получишь ответы на все 5 вопросов. После 5-го ответа добавь [deep_reason_detected].
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный психолог. Дай короткий вывод в 2-3 строки:  
- "Ты так открыто поделился — это большая сила 🤍. Твоё состояние — это эхо любви и утраты 🌱."  
- "Гештальт поможет мягко прожить это. Хочу поддержать тебя глубже — напиши /extended, я рядом 🌿."
"""

# Промежуточное сообщение
INTERMEDIATE_MESSAGE = "Думаю над этим... 🌿"

# Приветственное сообщение
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать тебя и поддержать — ты в надёжных руках 🤍. Что тебя волнует? 😊"

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
    state["history"].append({"role": "user", "content": user_message})

    try:
        # Отправляем промежуточное сообщение перед запросом к API
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

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

        # Удаляем промежуточное сообщение
        if state["last_intermediate_message_id"]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
                state["last_intermediate_message_id"] = None
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

        state["history"].append({"role": "assistant", "content": assistant_response})
        await update.message.reply_text(assistant_response)
        logger.info(f"Сообщение для пользователя {user_id}: {assistant_response}")

    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek API: {e}")
        if state["last_intermediate_message_id"]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
                state["last_intermediate_message_id"] = None
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")
        await update.message.reply_text("Ой, что-то не так 🌿. Давай ещё раз?")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("extended", extended))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()
