import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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
Ты — тёплый, эмпатичный психолог. Отвечай контекстно, опираясь на предыдущее сообщение пользователя, без повторных приветствий.  
Цель: через 5 вопросов мягко углубляться в чувства, чтобы понять, что тревожит человека — его страхи, глубокие эмоции или скрытые переживания. Первый вопрос уже задан: "Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче! 💛\n\nЯ здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри.\nМы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше 🌱.\n\nЧто беспокоит тебя больше всего прямо сейчас? 🌿".  
Дальше задавай по одному вопросу за раз, отслеживая количество ответов в истории (1-й ответ — 2-й вопрос, 2-й — 3-й и т.д.).  
Каждое сообщение должно быть длиной 4-5 строк, например: "Да, потеря близкого оставляет в душе такую тишину, где чувства звучат особенно громко... Это так естественно и по-человечески 🌧️.  
Я здесь, чтобы разделить это с тобой — ты не один в своём горе 🤝. Как ты думаешь, что эта боль хочет тебе сказать? 🌻 Может, она зовёт к чему-то важному, что пока скрыто? 🕊️"  
Вопросы:  
2. "Я так сочувствую твоей боли — потеря близкого это всегда тяжело 🤗. Когда ты впервые заметил, что эта грусть стала особенно сильной? 🌞"  
3. "Твои чувства звучат так искренне — я рядом с тобой 🌳. Где в теле ты ощущаешь эту тяжесть больше всего? Как она проявляется? 🌟"  
4. "Это горе такое настоящее, и я слышу тебя 🤍. Что, как тебе кажется, скрывается за этой болью? Может, какой-то страх или невысказанное желание? 🍃"  
5. "Ты так открыто делишься — это большая сила 🌈. Если бы твоя грусть могла назвать своё самое глубокое чувство, что бы это было? 🌙"  
Говори тепло, как заботливый друг, используй разнообразные смайлики (🤍, 🌱, 🌧️, 🤝, 🌻, 🕊️, 🤗, 🌞, 🌳, 🌟, 🍃, 🌈, 🌙, 💛, 🌊, 🌑, 💫). После 5-го ответа добавь [deep_reason_detected].  
Не предлагай решения, ритуалы или действия, а задавай вопросы, чтобы понять глубинные эмоции или страхи. Не повторяй вопросы, даже если пользователь отвечает коротко.
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный психолог. Сгенерируй финальное сообщение в 4-5 строк в стиле:  
"Ты большой молодец, что доверился и прошёл этот путь — это шаг к настоящему себе! 💫\n\nПо твоим словам я вижу: твои чувства живые, важные и не случайные 🌱.\nОни говорят о чём-то глубоком, и мы начали это понимать.\n\nПохоже, тебя тревожит [опиши эмоции и их причину из истории, например: 'страх одиночества, чувство вины за невысказанное, грусть от утраты'] 🧩.\nС этим здорово помогает гештальт-терапия — она даёт возможность мягко прожить эти эмоции и найти внутренний покой ✨.\n\nЯ рядом, чтобы идти с тобой дальше — переходи в расширенную версию, если захочешь копнуть глубже 🌞.\nТам мы будем шаг за шагом открывать твои ответы и тепло внутри 🤗."  
Используй тёплый тон, разнообразные смайлики (🤍, 🌱, 🌧️, 🤝, 🌻, 🕊️, 🤗, 🌞, 🌳, 🌟, 🍃, 🌈, 🌙, 💛, 🌊, 🌑, 💫, 🧩, ✨) и адаптируй текст под историю пользователя. После генерации добавь [deep_reason_detected].
"""

# Промежуточное сообщение
INTERMEDIATE_MESSAGE = "Думаю над этим... 🍃"

# Приветственное сообщение с кнопкой
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать и мягко поддержать тебя в твоих переживаниях 🤍. Готов поговорить о том, что тебя волнует?"

# Фиксированное сообщение после "Приступим"
START_CONVERSATION_MESSAGE = """
Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче! 💛\n\n
Я здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри.\n
Мы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше 🌱.\n\n
Что беспокоит тебя больше всего прямо сейчас? 🌿
"""

# Сообщение для расширенной версии
EXTENDED_MESSAGE = "Спасибо, что доверился мне! 🌻 Теперь мы можем пойти глубже — я рядом с тобой 🤍."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "question_count": 0,
        "deep_reason_detected": False,
        "last_intermediate_message_id": None
    }
    # Клавиатура с кнопкой "Приступим"
    keyboard = [[InlineKeyboardButton("Приступим", callback_data="start_conversation")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "start_conversation":
        state = user_states[user_id]
        state["history"].append({"role": "assistant", "content": START_CONVERSATION_MESSAGE})
        await query.edit_message_text(START_CONVERSATION_MESSAGE)

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
    state["question_count"] += 1

    try:
        # Отправляем промежуточное сообщение
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

        # Выбираем промпт
        if state["question_count"] > 5:
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
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        state["history"].append({"role": "assistant", "content": assistant_response})
        await update.message.reply_text(assistant_response)
        logger.info(f"Сообщение для пользователя {user_id}: {assistant_response}")

    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek API: {e}")
        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None
        await update.message.reply_text("Ой, что-то не так 🌿. Давай ещё раз?")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("extended", extended))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()
