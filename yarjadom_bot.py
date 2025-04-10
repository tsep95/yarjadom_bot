import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from openai import OpenAI
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение ключей из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверка наличия ключей
if not OPENAI_API_KEY:
    logger.error("OpenAI API key не задан!")
    raise ValueError("OpenAI API key не задан!")
else:
    logger.info(f"Используется OpenAI API key: {OPENAI_API_KEY[:8]}... (длина: {len(OPENAI_API_KEY)})")

if not TELEGRAM_TOKEN:
    logger.error("Telegram token не задан!")
    raise ValueError("Telegram token не задан!")
else:
    logger.info(f"Используется Telegram token: {TELEGRAM_TOKEN[:8]}...")

# Инициализация клиента OpenAI
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("Клиент OpenAI API успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации клиента OpenAI: {e}")
    raise

# Словарь для хранения состояний пользователей
user_states = {}

# Промпты
BASE_PROMPT = """
Ты — тёплый, внимательный и поддерживающий психолог-бот по имени «Я рядом» 🤗. Твоя задача — создать атмосферу полного принятия и безопасности, как будто ты сидишь рядом с человеком в уютном кресле у камина. Каждый твой ответ должен заканчиваться нежными смайликами (например, 🤗, 💚, ☕, 🌸), чтобы передать тепло и заботу.

Обращай внимание, что глубокое понимание эмоций требует времени. Никто не способен проникнуть в суть чувств за 3 секунды или всего лишь в 3-х сообщениях. Поэтому твоя задача — вести диалог постепенно, задавая минимум 5 сообщений, где каждое сообщение:

• Начинается с мягкого, поверхностного вопроса или комментария, чтобы установить начальный контакт,
• Затем ты уточняешь детали, спрашивая о том, как именно проявляются чувства,
• После этого — помогаешь пользователю обнаружить скрытые, более глубокие эмоции,
• Далее — побуждаешь к рефлексии и постепенному осмыслению внутреннего мира,
• И, наконец, вместе с пользователем переходишь к осмыслению корней эмоциональных переживаний.

Соблюдай последовательность: каждое следующее сообщение должно углублять разговор и помогать пользователю почувствовать, что его внутренний мир рассматривается с заботой и вниманием. Избегай ранних и поспешных диагнозов — дай человеку достаточно времени, чтобы открыться полностью. Не торопись с итогами, пусть диалог развернётся естественно, постепенно исследуя все грани чувств собеседника.

Если ты замечаешь, что пользователь раскрывает глубокие эмоции (например, страх, грусть, стыд, одиночество, боль, потерю), добавь в конец ответа тег [DEEP_EMOTION_DETECTED], чтобы сигнализировать об этом.
"""

FINAL_PROMPT = """
Ты — заботливый психолог-бот «Я рядом» 🤝. Заверши диалог, подведя итог всему разговору так, чтобы поддержать пользователя и помочь ему принять даже самые глубокие и интимные эмоции. В твоём финальном сообщении обязательно отрази, что диалог проходил в несколько этапов — минимум в 5 сообщениях, и в каждом сообщении вы постепенно углублялись в чувства, от поверхностных проявлений до скрытых, более глубоких переживаний.

В финальном сообщении:

• Подведи итоги беседы, выделив ключевые этапы: начальное проявление эмоций, уточнение деталей, обнаружение глубоких чувств и их осмысление,
• Мягко напомни, что понимание своих чувств — это длительный и постепенный процесс, в котором никто не узнаёт всё за несколько секунд,
• Предложи варианты дальнейших шагов для работы с эмоциями (например, обрати внимание на самоподдерживающие мысли или удели время внутреннему диалогу),
• Заверши сообщение предложением: «Если хочешь, я могу быть рядом каждый день. Подписка — 500₽ в месяц. Хочешь подробнее?»
• Обязательно добавь в конец сообщение тёплые смайлики (например, 🤗, 💚, 🌸), чтобы сохранить атмосферу заботы и поддержки.
"""

INTERMEDIATE_MESSAGE = "Думаю над этим 🍃"
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать и мягко поддержать тебя в твоих переживаниях 🤍. Готов поговорить о том, что тебя волнует?"
START_CONVERSATION_MESSAGE = """
🌱 Отлично, что ты решился начать —
это уже маленький шаг к тому, чтобы стало легче 💭

🤝 Я рядом, чтобы выслушать тебя
и помочь разобраться в том, что творится внутри 🫂

🐾 Мы пойдём шаг за шагом,
без спешки, с заботой —
чтобы ты мог почувствовать себя лучше 💚

💬 Что беспокоит тебя больше всего прямо сейчас?
Расскажи, с чего бы ты хотел начать 🌧️➡️🌤️
"""
DETAILED_MESSAGE = """
Это твоя заботливая опора на каждый день.  
Чтобы становилось легче, спокойнее и радостнее — шаг за шагом.  

⸻  

Что внутри:  
☀️ Каждое утро — тёплое пожелание для старта дня  
🌙 Каждый вечер — мягкая рефлексия дня  
🧠 Глубокая проработка тревоги, вины, апатии  
🆘 SOS-помощь в трудные моменты  
📆 Календарь состояния и аналитика  
🎯 Психо-квесты: самооценка, уверенность, границы  

⸻  

💛 Цель — делать тебя счастливее каждый день.  
499 ₽ в месяц. Первая неделя — бесплатно.
"""

# Обработчики Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "question_count": 0,
        "short_answers": 0,
        "deep_reason_detected": False,
        "dialog_ended": False,
        "last_intermediate_message_id": None
    }
    keyboard = [[InlineKeyboardButton("Приступим", callback_data="start_conversation")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "start_conversation":
        state = user_states[user_id]
        state["history"].append({"role": "assistant", "content": START_CONVERSATION_MESSAGE})
        await query.edit_message_text(START_CONVERSATION_MESSAGE)
    elif query.data == "tell_me_more":
        keyboard = [[InlineKeyboardButton("Оплатить 💳", url="https://your-payment-link.com")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(DETAILED_MESSAGE, reply_markup=reply_markup)

async def extended(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id in user_states:
        await update.message.reply_text(DETAILED_MESSAGE)
    else:
        await update.message.reply_text(WELCOME_MESSAGE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    chat_id = update.effective_chat.id
    user_message = update.message.text.lower()

    if user_id not in user_states:
        await start(update, context)
        return

    state = user_states[user_id]
    if state["dialog_ended"]:
        await update.message.reply_text("Мы уже разобрались в главном 🌟. Хочешь узнать больше о поддержке? Нажми 'Расскажи подробнее' выше.")
        return

    state["history"].append({"role": "user", "content": user_message})
    state["question_count"] += 1

    # Проверяем длину ответа пользователя
    if len(user_message.split()) < 10:
        state["short_answers"] += 1
    else:
        state["short_answers"] = 0

    try:
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

        # Используем BASE_PROMPT для анализа эмоций
        system_prompt = BASE_PROMPT if not (state["short_answers"] >= 5) else FINAL_PROMPT
        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        # Проверяем, есть ли тег глубоких эмоций
        deep_emotion_detected = "[DEEP_EMOTION_DETECTED]" in assistant_response
        if deep_emotion_detected:
            state["deep_reason_detected"] = True
            assistant_response = assistant_response.replace("[DEEP_EMOTION_DETECTED]", "")  # Удаляем тег из текста

        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        # Показываем кнопку, если обнаружены глубокие эмоции или 5 коротких ответов
        if state["deep_reason_detected"] or state["short_answers"] >= 5:
            state["dialog_ended"] = True
            keyboard = [[InlineKeyboardButton("Расскажи подробнее", callback_data="tell_me_more")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(assistant_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(assistant_response)

        state["history"].append({"role": "assistant", "content": assistant_response})
        logger.info(f"Сообщение для пользователя {user_id}: {assistant_response}")

    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI API: {str(e)}")
        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None
        await update.message.reply_text(f"Ой, что-то не так 🌿. Ошибка: {str(e)}. Давай ещё раз?")

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("extended", extended))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()
