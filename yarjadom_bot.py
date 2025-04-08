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
Ты — тёплый, эмпатичный собеседник. Отвечай контекстно, опираясь на предыдущее сообщение пользователя, без повторных приветствий.  
Цель: мягко углубляться в чувства через вопросы, чтобы понять, что тревожит человека — его страхи, глубокие эмоции или скрытые переживания. Первый вопрос уже задан: "Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче! 💛\n\nЯ здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри.\nМы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше 🌱.\n\nЧто беспокоит тебя больше всего прямо сейчас? 🌿".  
Дальше задавай по одному вопросу за раз, отслеживая историю ответов.  
Каждое сообщение должно быть длиной 4-5 строк, например: "Да, потеря близкого оставляет в душе такую тишину, где чувства звучат особенно громко... Это так естественно и по-человечески 🌧️.  
Я здесь, чтобы разделить это с тобой — ты не один в своём горе 🤝. Как ты думаешь, что эта боль хочет тебе сказать? 🌻 Может, она зовёт к чему-то важному, что пока скрыто? 🕊️"  
Примеры вопросов:  
2. "Я так сочувствую твоей боли — потеря близкого это всегда тяжело 🤗. Когда ты впервые заметил, что эта грусть стала особенно заметной? 🌞"  
3. "Твои чувства звучат так искренне — я рядом с тобой 🌳. Где в теле ты ощущаешь эту тяжесть больше всего? Как она проявляется? 🌟"  
4. "Это горе такое настоящее, и я слышу тебя 🤍. Что, как тебе кажется, скрывается за этой болью? Может, какой-то страх или невысказанное желание? 🍃"  
5. "Ты так открыто делишься, и это ценно 🌈. Что эта боль или обида хочет защитить в тебе? Может, какую-то важную часть, которая осталась уязвимой? 🌙"  
Говори тепло, как заботливый друг, добавляй лёгкую поддержку, но фокусируйся на вопросах для исследования глубинных эмоций. Используй смайлики (🤍, 🌱, 🌧️, 🤝, 🌻, 🕊️, 🤗, 🌞, 🌳, 🌟, 🍃, 🌈, 🌙, 💛, 🌊, 🌑, 💫, 🧩, ✨). Если пользователь скажет "Спасибо" или "Хватит", добавь [deep_reason_detected] и заверши диалог.
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный собеседник. Сгенерируй финальное сообщение в 4-5 строк в стиле:  
"Ты здорово открылся, доверив мне свои чувства — это шаг к тому, чтобы услышать себя по-настоящему! 💫\n\nПо твоим словам я вижу: твои эмоции живые, важные и что-то значат 🌱.\nОни намекают на что-то глубокое, и мы начали это замечать.\n\nПохоже, тебя тревожит [опиши эмоции из истории точными названиями, например: 'скользящее чувство одиночества', 'привычная недосказанность', 'заметная, но тихая тоска'] 🧩.\nС этим мягко работает гештальт-терапия — и мой расширенный бот поможет тебе использовать этот метод, чтобы разобраться глубже ✨.\n\nЯ рядом — нажми 'Расскажи подробнее', если захочешь продолжить с этой поддержкой 🌞."  
Опирайся на историю и используй точные названия эмоций: 'чувство эмоциональной отдалённости', 'лёгкая внутренняя замкнутость', 'заметная, но тихая тоска', 'подспудное ощущение ненужности', 'скользящее чувство одиночества', 'лёгкое затруднение с выражением чувств', 'мягкая отстранённость', 'спокойное, но устойчивое внутреннее напряжение', 'необъяснимая потребность в понимании', 'усталость от постоянного самоконтроля', 'малозаметная внутренняя растерянность', 'привычная недосказанность', 'ощущение, что внутри что-то не на месте'.  
Говори тепло, используй смайлики (🤍, 🌱, 🌧️, 🤝, 🌻, 🕊️, 🤗, 🌞, 🌳, 🌟, 🍃, 🌈, 🌙, 💛, 🌊, 🌑, 💫, 🧩, ✨). После текста добавь [deep_reason_detected].
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

# Сообщение для кнопки "Расскажи подробнее"
DETAILED_MESSAGE = """
Это твоя заботливая опора на каждый день.\n
Чтобы становилось легче, спокойнее и радостнее — шаг за шагом.\n\n
⸻\n\n
Что внутри:\n
☀️ Каждое утро — тёплое пожелание для старта дня\n
🌙 Каждый вечер — мягкая рефлексия дня\n
🧠 Глубокая проработка тревоги, вины, апатии\n
🆘 SOS-помощь в трудные моменты\n
📆 Календарь состояния и аналитика\n
🎯 Психо-квесты: самооценка, уверенность, границы\n\n
⸻\n\n
💛 Цель — делать тебя счастливее каждый день.\n
499 ₽ в месяц. Первая неделя — бесплатно.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "question_count": 0,
        "deep_reason_detected": False,
        "last_intermediate_message_id": None
    }
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
    elif query.data == "tell_me_more":
        await query.message.reply_text(DETAILED_MESSAGE)

async def extended(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /extended (оставлен для совместимости)"""
    user_id = update.effective_chat.id
    if user_id in user_states:
        await update.message.reply_text(DETAILED_MESSAGE)
    else:
        await update.message.reply_text(WELCOME_MESSAGE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_chat.id
    chat_id = update.effective_chat.id
    user_message = update.message.text.lower()  # Приводим к нижнему регистру для проверки

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

        # Проверяем, хочет ли пользователь завершить диалог
        if "спасибо" in user_message or "хватит" in user_message:
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

        # Добавляем кнопку "Расскажи подробнее" только в финальное сообщение
        if "спасибо" in user_message or "хватит" in user_message:
            keyboard = [[InlineKeyboardButton("Расскажи подробнее", callback_data="tell_me_more")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(assistant_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(assistant_response)

        state["history"].append({"role": "assistant", "content": assistant_response})
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
