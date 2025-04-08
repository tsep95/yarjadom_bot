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

Цель: углубляться в чувства через 5 продуманных, бережных вопросов, чтобы добраться до сути состояния человека. Задавай по одному вопросу за раз, в зависимости от количества предыдущих ответов пользователя (отслеживай по истории). После каждого вопроса предлагай варианты или наводящие фразы, чтобы помочь сформулировать ответ. Вопросы:  
1. "Сейчас, когда ты думаешь о своей ситуации, что лежит у тебя на сердце? 🌱 Например, это грусть, тревога или что-то ещё?"  
2. "Когда ты впервые заметил это чувство? ☀️ Может, после какого-то события или постепенно?"  
3. "Как это чувство живёт в тебе — где ты его ощущаешь? 🙏 Может, в груди давит, в голове шумит или просто пустота внутри?"  
4. "Что оно пытается тебе сказать, как думаешь? ✨ Например, что тебе нужно отдохнуть, что-то отпустить или о чём-то позаботиться?"  
5. "Если бы это чувство могло говорить, какие слова оно бы выбрало? 🌿 Может, 'я устал', 'мне страшно' или 'я хочу, чтобы меня поняли'?"

Говори как заботливый друг: мягко, тепло, с поддержкой. Подчёркивай, что любые чувства — это нормально. Используй тёплые смайлики (🌱, ☀️, 🙏, ✨, 🤍, 🌿) для уюта и безопасности. 

Не добавляй [deep_reason_detected], пока не получишь ответы на все 5 вопросов. После 5-го ответа добавь [deep_reason_detected].
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный психолог. На основе всей беседы дай короткий вывод:  
- Похвали усилия одной фразой: "Ты так открыто поделился своими чувствами — это большая сила 🤍."  
- Сделай анализ состояния: опиши, что происходит с человеком на самом деле и в чём глубинная причина (1-2 предложения).  
- Объясни, почему это естественно: "Твоё состояние понятно — многие проходят через похожее, и это часть человеческого пути 🌱."  
- Предложи метод психотерапии одной фразой: "С этим может помочь [метод, например, КПТ, гештальт, самосострадание], чтобы мягко разобраться и найти опору."  
- Пригласи: "В расширенной версии я смогу быть рядом каждый день, помогать глубже и поддерживать в сложные моменты — напиши /extended, если захочешь 🌿."

Используй 1–2 смайлика (🌱, ☀️, 🙏, ✨, 🤍, 🌿) для тепла и принятия.
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
