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
Ты — тёплый, эмпатичный собеседник. Отвечай контекстно, опираясь на предыдущее сообщение пользователя, без повторных приветствий.  
Цель: мягко углубляться в чувства через 1-2 вопроса в конце сообщения, чтобы понять, что тревожит человека. Первый вопрос уже задан: "Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче. Я здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри. Мы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше. Что беспокоит тебя больше всего прямо сейчас?"  
Пиши лаконично, естественно, в стиле: "Это нормально — не всегда легко сформулировать свои чувства. Бывает, что просто накапливается много всего, и трудно понять, с чего начать. Может быть, есть что-то конкретное, что ты ощущаешь в теле или голове? 🌱"  
Оставляй целую пустую строку между сообщениями (используй \n\n).  
Задавай 1-2 вопроса за раз, отслеживая историю ответов.  
Говори тепло, используй только смайлики из списка: 🤍 🌱 🌧️ 🤝 🌻 🕊️ 🤗 🌞 🌳 🌟 🍃 🌈 🌙 💛 🌊 🌑 💫 🧩 ✨.  
Если пользователь отвечает коротко 3 раза подряд (менее 10 слов), считай, что глубокая причина близка, и переходи к финальному сообщению.
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный собеседник. Сгенерируй финальное сообщение:  
Подведи итог диалога на основе истории, упомяни конкретный метод психологии (например, когнитивно-поведенческая терапия, гештальт-терапия, арт-терапия или другой), который может помочь с выявленными чувствами.  
Предложи расширенную версию бота как спутника в этом методе.  
Пиши лаконично, в стиле: "Это нормально — не всегда легко сформулировать свои чувства. Бывает, что просто накапливается много всего, и трудно понять, с чего начать. Может быть, есть что-то конкретное, что ты ощущаешь в теле или голове? 🌱"  
Оставляй целую пустую строку между сообщениями (используй \n\n).  
Пример:  
"Твои слова показывают, как много чувств скопилось внутри.  
Когнитивно-поведенческая терапия могла бы помочь мягко разобраться в них.  
Моя расширенная версия станет твоим спутником в этом пути.  
Нажми 'Расскажи подробнее', чтобы узнать, как я могу поддержать. 🌟"  
Используй только смайлики из списка: 🤍 🌱 🌧️ 🤝 🌻 🕊️ 🤗 🌞 🌳 🌟 🍃 🌈 🌙 💛 🌊 🌑 💫 🧩 ✨.
"""

INTERMEDIATE_MESSAGE = "Думаю над этим 🍃"
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать и мягко поддержать тебя в твоих переживаниях 🤍. Готов поговорить о том, что тебя волнует?"
START_CONVERSATION_MESSAGE = """
Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче.  
Я здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри.  
Мы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше.  
Что беспокоит тебя больше всего прямо сейчас?
"""
DETAILED_MESSAGE = """
Это твоя заботливая опора на каждый день.  
Чтобы становилось легче, спокойнее и радостнее — шаг за шагом.  
Что внутри:  
Каждое утро — тёплое пожелание для старта дня.  
Каждый вечер — мягкая рефлексия дня.  
Глубокая проработка тревоги, вины, апатии.  
SOS-помощь в трудные моменты.  
Календарь состояния и аналитика.  
Психо-квесты: самооценка, уверенность, границы.  
Цель — делать тебя счастливее каждый день.  
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

        # Условие для перехода к финалу: 3 коротких ответа подряд или "спасибо"/"хватит"
        if state["short_answers"] >= 3 or "спасибо" in user_message or "хватит" in user_message:
            system_prompt = FINAL_PROMPT
        else:
            system_prompt = BASE_PROMPT

        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        if state["short_answers"] >= 3 or "спасибо" in user_message or "хватит" in user_message:
            state["deep_reason_detected"] = True
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
