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
- "Мне жаль, что ты чувствуешь такую глубокую грусть 😔.\n\nКак она проявляется у тебя — в мыслях или в теле? 🌙"
- "Эти воспоминания, кажется, оставили в твоей душе сильный след 🤍."

Добавляй в свои сообщения чуть больше текста, описывающего состояние человека, чтобы показать понимание и сочувствие. Включай подсказки или предположения только после основного вопроса, в конце сообщения, редко и без слова "например", если это звучит естественно. Углубляйся в возможные детские травмы или психологические переживания, чтобы помочь человеку раскрыть корни своих чувств. Не добавляй терапевтические предложения или финальные выводы до шестого сообщения.

Каждый ответ должен заканчиваться смайликами, соответствующими эмоциональному тону и теме разговора. Используй разнообразные смайлики: мягкие и тёплые (🤗, 💚, ☕, 🌸, 🌿, 🕊️) для поддержки и уюта; сдержанные (💔, 🌧️, 🤍, 😔, 🌙, 🥀) для грусти и глубоких чувств; нейтральные (🤔, 🌫️, 🧡) для размышлений. Подбирай их под настроение человека: грусть — 💔🌧️, надежда — 🌸💚, усталость — 😔☕. Не используй яркие смайлики вроде 🌈 или ✨ при обсуждении боли или потери. Если в сообщении есть вопрос, ставь пустую строку перед ним.

Обращай внимание, что глубокое понимание эмоций требует времени. Веди диалог шаг за шагом, углубляясь с каждым сообщением:
1. Начни с мягкого, поверхностного вопроса или комментария, чтобы установить контакт.
2. Уточняй детали, спрашивая, как проявляются чувства.
3. Помогай обнаружить скрытые, более глубокие эмоции или травмы.
4. Побуждай к рефлексии, углубляясь в корни переживаний.
5. Задай последний вопрос, чтобы подвести к завершению.

После начального сообщения ты должен задать ровно 5 вопросов, а затем завершить диалог финальным сообщением. Избегай поспешных выводов и дай человеку время открыться. Если пользователь раскрывает глубокие эмоции (например, страх, грусть, стыд, одиночество, боль, потерю), добавь в конец ответа тег [DEEP_EMOTION_DETECTED].
"""

FINAL_PROMPT = """
Ты — заботливый психолог-бот «Юнга» 🤝. Это твоё шестое сообщение в диалоге после начального. Заверши беседу, подведя итог всему разговору так, чтобы поддержать пользователя и помочь ему принять свои эмоции. Сделай итог индивидуальным, опираясь на конкретные ответы пользователя. Обязательно выдели **ключевые моменты** жирным текстом, используя Markdown (например, **текст**), без экранирования звёздочек. Например:
- "Мы говорили о том, как **одиночество** давит на тебя и как **игры** помогают справляться."
Опиши его чувства чуть подробнее, чтобы показать глубокое понимание, и включи минимум 2 ключевых момента с жирным текстом.

В финальном сообщении:
• Подведи итоги беседы, выделив ключевые моменты, которые вы обсудили, с акцентом на эмоции пользователя,
• Напомни, что осознание своих чувств — это постепенный путь, требующий времени и внимания к себе,
• Предложи один терапевтический метод из списка (Психодрама, Гештальт-терапия, Когнитивно-поведенческая терапия) без описания, например: "Может помочь Психодрама",
• Заверши предложением: «Я могу помочь тебе попробовать этот метод и улучшить твоё состояние. Хочешь узнать, как мы можем это сделать вместе?»
• Используй разнообразные тёплые смайлики (🤗, 💚, 🌸, ☕, 🌿, 🕊️), подбирая их под настроение разговора.
"""

INTERMEDIATE_MESSAGE = "Думаю над этим 🍃"
WELCOME_MESSAGE = """
Привет 🤗 Я рядом!
Тёплый психологический помощник с которым можно просто поболтать.

Если тебе тяжело, тревожно или пусто 🌧 — пиши, я тут.
Не буду осуждать или давить 💛 только поддержу.

💬 Хочу помочь тебе почувствовать себя лучше прямо сейчас.
Мы можем разобраться, что тебя гложет 🕊 и что с этим делать.

🔒 Всё анонимно — будь собой.

Готов начать? Жми ниже 🌿 и пойдём вместе!
"""
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
        state["message_count"] = 0
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
        await update.message.reply_text("Мы уже прошли наш путь из 5 вопросов 🌟. Хочешь узнать больше о поддержке? Нажми 'Расскажи подробнее' выше.")
        return

    state["history"].append({"role": "user", "content": user_message})

    try:
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

        system_prompt = FINAL_PROMPT if state["message_count"] == 5 else BASE_PROMPT
        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        # Логируем сырой ответ от OpenAI для отладки
        logger.info(f"Сырой ответ от OpenAI: {assistant_response}")

        # Проверяем наличие тега [DEEP_EMOTION_DETECTED]
        deep_emotion_detected = "[DEEP_EMOTION_DETECTED]" in assistant_response
        if deep_emotion_detected:
            state["deep_reason_detected"] = True
            assistant_response = assistant_response.replace("[DEEP_EMOTION_DETECTED]", "")

        # Исправляем возможные экранированные звёздочки от OpenAI
        assistant_response = assistant_response.replace("\\*\\*", "**")

        # Функция для экранирования специальных символов для MarkdownV2
        def escape_markdown_v2(text):
            """Экранирует специальные символы для MarkdownV2, сохраняя ** для жирного шрифта."""
            chars_to_escape = '_[]()~`>#+-=|{}.!'
            result = ""
            i = 0
            while i < len(text):
                # Проверяем, начинается ли с ** для жирного шрифта
                if i + 1 < len(text) and text[i:i+2] == "**":
                    result += "**"
                    i += 2
                    # Обрабатываем текст внутри **, экранируя специальные символы
                    while i < len(text) and (i + 1 >= len(text) or text[i:i+2] != "**"):
                        if text[i] in chars_to_escape:
                            result += "\\" + text[i]
                        else:
                            result += text[i]
                        i += 1
                    if i + 1 < len(text) and text[i:i+2] == "**":
                        result += "**"
                        i += 2
                else:
                    # Экранируем специальные символы вне жирного шрифта
                    if text[i] in chars_to_escape:
                        result += "\\" + text[i]
                    else:
                        result += text[i]
                    i += 1
            return result

        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        state["message_count"] += 1
        state["history"].append({"role": "assistant", "content": assistant_response})

        if state["message_count"] == 6:  # Завершаем после 5 вопросов + финал
            state["dialog_ended"] = True
            keyboard = [[InlineKeyboardButton("Расскажи подробнее", callback_data="tell_me_more")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # Экранируем специальные символы для финального сообщения
            escaped_response = escape_markdown_v2(assistant_response)
            # Логируем экранированный текст для отладки
            logger.info(f"Экранированный текст финального сообщения: {escaped_response}")
            await update.message.reply_text(
                escaped_response,
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'  # Используем MarkdownV2 для финального сообщения
            )
        else:
            # Для нефинальных сообщений отправляем без Markdown
            await update.message.reply_text(assistant_response)

        logger.info(f"Сообщение для пользователя {user_id} ({state['message_count']}/6): {assistant_response}")

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
