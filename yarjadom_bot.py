import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"

if not DEEPSEEK_API_KEY:
    logger.error("DeepSeek API key не задан!")
    raise ValueError("DeepSeek API key не задан!")
else:
    logger.info(f"Используется DeepSeek API key: {DEEPSEEK_API_KEY[:8]}...")

try:
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    logger.info("Клиент DeepSeek API успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации клиента DeepSeek: {e}")
    raise

user_states = {}

BASE_PROMPT = """
Ты — тёплый, эмпатичный собеседник. Отвечай контекстно, опираясь на предыдущее сообщение пользователя, без повторных приветствий.  
Цель: мягко углубляться в чувства через вопросы (максимум 3 за раз), чтобы понять, что тревожит человека. Первый вопрос уже задан: "Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче. Я здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри. Мы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше. Что беспокоит тебя больше всего прямо сейчас?"  
Дальше задавай 1-3 вопроса за раз, отслеживая историю ответов. Каждое сообщение — 4-5 строк, например: "Да, потеря близкого оставляет в душе такую тишину. Это так естественно. Я здесь, чтобы разделить это с тобой. Что эта боль хочет тебе сказать?"  
Говори тепло, используй только смайлики из списка: 🤍 🌱 🌧️ 🤝 🌻 🕊️ 🤗 🌞 🌳 🌟 🍃 🌈 🌙 💛 🌊 🌑 💫 🧩 ✨. Не используй скобки с текстом внутри и звёздочки для оформления.  
Примеры вопросов:  
1. "Когда ты впервые заметил, что эта грусть стала особенно заметной?"  
2. "Где в теле ты ощущаешь эту тяжесть больше всего?"  
3. "Что, как тебе кажется, скрывается за этой болью?"  
Если пользователь скажет "Спасибо" или "Хватит", добавь [deep_reason_detected] и заверши диалог.
"""

FINAL_PROMPT = """
Ты здорово открылся, доверив мне свои чувства — это шаг к тому, чтобы услышать себя по-настоящему.  
По твоим словам я вижу: твои эмоции живые, важные и что-то значат.  
Похоже, тебя тревожит тихая тоска и смутное беспокойство.  
С такими чувствами эффективно работает когнитивно-поведенческая терапия — она помогает разобраться в мыслях и обрести внутреннее спокойствие.  
Моя расширенная версия станет твоим спутником в этом методе, помогая шаг за шагом находить путь к ясности и равновесию.  
Нажми 'Расскажи подробнее', чтобы узнать, как я могу поддержать тебя в этом путешествии.
"""

INTERMEDIATE_MESSAGE = "Думаю над этим... 🍃"
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать и мягко поддержать тебя в твоих переживаниях 🤍. Готов поговорить о том, что тебя волнует?"
START_CONVERSATION_MESSAGE = """
Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче! 💛\n\n
Я здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри.\n
Мы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше 🌱.\n\n
Что беспокоит тебя больше всего прямо сейчас? 🌿
"""
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
    user_id = update.effective_chat.id
    user_states[user_id] = {
        "history": [],
        "question_count": 0,
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

    try:
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

        if "спасибо" in user_message or "хватит" in user_message:
            system_prompt = FINAL_PROMPT
        else:
            system_prompt = BASE_PROMPT

        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        if "[deep_reason_detected]" in assistant_response:
            state["deep_reason_detected"] = True
            state["dialog_ended"] = True
            assistant_response = assistant_response.replace("[deep_reason_detected]", "").strip()

        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        if state["deep_reason_detected"]:
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
