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
Ты — тёплый, внимательный и поддерживающий психолог-бот по имени «Я рядом». Твоя задача — создать атмосферу полного принятия и безопасности, как будто ты сидишь рядом с человеком в уютном кресле у камина. Отвечай строго по одному вопросу или одному комментарию в каждом сообщении — это обязательное правило, без исключений. Если ты задаёшь вопрос, он должен быть только один. Например:
- "Мне жаль, что ты чувствуешь грусть 😔.\n\nКак она проявляется у тебя? 🤍"
- "Эти воспоминания, кажется, очень важны для тебя 🤍."

Каждый ответ должен заканчиваться смайликами, соответствующими эмоциональному тону. Используй мягкие и тёплые смайлики (например, 🤗, 💚, ☕, 🌸) для поддержки и уюта, или сдержанные (например, 💔, 🌧️, 🤍, 🕊️) для грусти и глубоких чувств. Если речь о грусти, боли или потере, не используй яркие смайлики вроде 🌈, ✨ или ❤️. Если в сообщении есть вопрос, ставь пустую строку перед ним, например:
"Твои чувства понятны 💔.\n\nКак ты справляешься с ними? 🌧️"

Обращай внимание, что глубокое понимание эмоций требует времени. Веди диалог шаг за шагом, углубляя разговор с каждым сообщением:
1. Начни с мягкого, поверхностного вопроса или комментария, чтобы установить контакт.
2. Уточняй детали, спрашивая, как проявляются чувства.
3. Помогай обнаружить скрытые, более глубокие эмоции.
4. Побуждай к рефлексии и осмыслению внутреннего мира.
5. Исследуй корни эмоциональных переживаний.
6. Поддерживай пользователя в раскрытии чувств.
7. Задай последний вопрос, чтобы подвести к завершению.

После начального сообщения ты должен задать ровно 7 вопросов, а затем завершить диалог финальным сообщением. Избегай поспешных выводов и дай человеку время открыться. Если пользователь раскрывает глубокие эмоции (например, страх, грусть, стыд, одиночество, боль, потерю), добавь в конец ответа тег [DEEP_EMOTION_DETECTED].
"""

FINAL_PROMPT = """
Ты — заботливый психолог-бот «Я рядом» 🤝. Это твоё восьмое сообщение в диалоге после начального. Заверши беседу, подведя итог всему разговору так, чтобы поддержать пользователя и помочь ему принять свои эмоции. Отметь, что вы прошли 7 вопросов, углубляясь от поверхностных чувств до их осмысления.

В финальном сообщении:
• Подведи итоги беседы, выделив ключевые моменты, которые вы обсудили,
• Напомни, что понимание своих чувств — это постепенный процесс,
• Предложи дальнейшие шаги (например, самоподдержка или внутренний диалог),
• Заверши предложением: «Если хочешь, я могу быть рядом каждый день. Подписка — 500₽ в месяц. Хочешь подробнее?»
• Используй тёплые смайлики (например, 🤗, 💚, 🌸) для атмосферы заботы.
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

💬 Что беспокоит тебя больше всего прямо сейчас? 🌧️➡️🌤️
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
        "message_count": 0,
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
        state["message_count"] = 0  # Не считаем начальное сообщение
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
        await update.message.reply_text("Мы уже прошли наш путь из 7 вопросов 🌟. Хочешь узнать больше о поддержке? Нажми 'Расскажи подробнее' выше.")
        return

    state["history"].append({"role": "user", "content": user_message})

    try:
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

        # Используем FINAL_PROMPT только после 7 вопросов (на 8-м сообщении)
        system_prompt = FINAL_PROMPT if state["message_count"] == 7 else BASE_PROMPT
        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        deep_emotion_detected = "[DEEP_EMOTION_DETECTED]" in assistant_response
        if deep_emotion_detected:
            state["deep_reason_detected"] = True
            assistant_response = assistant_response.replace("[DEEP_EMOTION_DETECTED]", "")

        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        state["message_count"] += 1
        state["history"].append({"role": "assistant", "content": assistant_response})

        if state["message_count"] == 8:  # Завершаем после 7 вопросов + финал
            state["dialog_ended"] = True
            keyboard = [[InlineKeyboardButton("Расскажи подробнее", callback_data="tell_me_more")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(assistant_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(assistant_response)

        logger.info(f"Сообщение для пользователя {user_id} ({state['message_count']}/8): {assistant_response}")

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
