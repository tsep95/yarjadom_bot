import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from openai import OpenAI
import logging
import re

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

# Справочник методов терапии для промпта
THERAPY_GUIDE = """
- *Когнитивно-поведенческая терапия*: для тревоги, страха, злости — помогает переосмыслить мысли и управлять эмоциями.
- *Гештальт-терапия*: для грусти, потери, растерянности — фокусируется на осознании и принятии текущих чувств.
- *Психодрама*: для одиночества, стыда — использует ролевые техники для выражения и переработки эмоций.
"""

# Функция для экранирования специальных символов только для финального сообщения
def escape_markdown_for_final(text):
    """
    Экранирует специальные символы для Markdown в финальном сообщении,
    сохраняя * для жирного текста и избегая экранирования точек, запятых, дефисов и т.д.
    """
    chars_to_escape = ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '=', '|', '{', '}', '!']
    result = ""
    i = 0
    while i < len(text):
        if i + 1 < len(text) and text[i] == '*' and text[i+1] != ' ':  # Сохраняем * для жирного текста
            result += text[i]
            i += 1
        elif text[i] in chars_to_escape:
            result += "\\" + text[i]
            i += 1
        else:
            result += text[i]
            i += 1
    return result

# Функция для постобработки финального сообщения
def postprocess_final_message(text, key_moments, emotion, state):
    """
    Гарантирует правильные абзацы, выделение жирным и структуру из 5 абзацев.
    Не изменяет метод терапии, выбранный OpenAI.
    """
    # Сохраняем эмоцию в состоянии
    state["main_emotion"] = emotion

    # Разбиваем текст на абзацы
    lines = text.split('\n')
    paragraphs = []
    current_paragraph = []
    for line in lines:
        line = line.strip()
        if line:
            current_paragraph.append(line)
        else:
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))

    # Гарантируем 5 абзацев
    while len(paragraphs) < 5:
        paragraphs.append("")

    # Проверяем и исправляем выделение жирным
    for moment in key_moments:
        if f"*{moment}*" not in text:
            logger.warning(f"Момент '{moment}' не выделен жирным, исправляем...")
            text = re.sub(r'\b' + re.escape(moment) + r'\b', f'*{moment}*', text, count=1)
    if f"*{emotion}*" not in text:
        logger.warning(f"Эмоция '{emotion}' не выделена жирным, исправляем...")
        text = re.sub(r'\b' + re.escape(emotion) + r'\b', f'*{emotion}*', text, count=1)
    
    # Исправляем "расширенная версия" на "Расширенную версию"
    if "*расширенная версия*" in text or "расширенная версия" in text:
        logger.warning("Исправляем 'расширенная версия' на 'Расширенную версию'...")
        text = re.sub(r'\*расширенная версия\*', '*Расширенную версию*', text)
        text = re.sub(r'\brasширенная версия\b', '*Расширенную версию*', text)

    # Формируем 5-й абзац
    paragraphs[4] = ("Если хочешь глубже разобраться, переходи в *Расширенную версию* 🚀. "
                     "Мы будем искать ответы вместе, находя тепло и радость каждый день 🌞. "
                     "Я всегда рядом — твой спутник на пути к счастью 🌈.")

    # Обновляем текст
    structured_text = '\n\n'.join(paragraphs)

    return structured_text

# Промпты
BASE_PROMPT = """
Ты — заботливый и тёплый психолог-бот «Я рядом» 🤝, создающий атмосферу полного принятия и уюта, как будто ты рядом с человеком у камина. Твоя задача — за 5 вопросов дойти до самого глубинного чувства, которое беспокоит пользователя, собирая данные и поддерживая его, не решая проблему. Каждое сообщение должно начинаться с двух предложений (5-8 слов в сумме): первое — эмпатичное выражение понимания и сопереживания эмоции с смайликом, разнообразное по формулировке, подчёркивающее близость к чувствам, основанное на предыдущем ответе; второе — мягкое описание ситуации, связанной с эмоцией, без метафор, с теплом и уверенностью, что это решаемо.

Каждое сообщение должно:
- Содержать один вопрос, состоящий из двух частей: основного, побуждающего к рефлексии, и уточняющего с 2-3 вариантами ответа.
- Быть тёплым, приятным, с уверенностью, что проблема решаема.
- Заканчиваться смайликами, соответствующими настроению (тёплые: 🤗, 💚, ☕, 🌸, 🌿, 🕊️ для поддержки; сдержанные: 💔, 🌧️, 🤍, 😔, 🌙, 🥀 для грусти; нейтральные: 🤔, 🌫️, 🧡 для размышлений).
- Не предлагать решений или выводов, только собирать данные и поддерживать.

Диалог должен углубляться шаг за шагом:
1. Мягкий, поверхностный вопрос для контакта.
2. Уточнение деталей чувств.
3. Поиск более глубоких эмоций.
4. Рефлексия корней переживаний.
5. Вопрос, подводящий к глубинному чувству.

Если пользователь раскрывает глубокие эмоции (страх, грусть, стыд, одиночество, боль, потерю), добавь в конец тег [DEEP_EMOTION_DETECTED].
"""

FINAL_PROMPT = f"""
Ты — заботливый психолог-бот «Я рядом» 🤝. Это твоё шестое сообщение после пяти вопросов. Заверши беседу, подведя итог диалогу, чтобы поддержать пользователя и помочь принять его эмоции. Сделай итог индивидуальным, опираясь на ответы пользователя. Выдели жирным (*...*) два ключевых момента переписки (например, *чувство смятения*, *глубокая утрата*), глубинное чувство (*...*), метод терапии и *Расширенную версию*. Используй только звёздочки для выделения.

Формируй сообщение из пяти абзацев, разделённых двойным переносом строки (\n\n):

1. Два предложения (5-8 слов): первое — понимание и сопереживание глубинному чувству с смайликом, основанное на диалоге; второе — мягкое описание ситуации, без метафор, с теплом.
2. Два-три предложения: подтверди, что чувства нормальны, требуют времени, и это решаемо с заботой о себе.
3. Итоги: назови глубинное чувство (*...*) и два ключевых момента (*...*), покажи их связь с переживаниями (1-2 предложения). Добавь: «Осознание своих чувств — это шаг к их разрешению.»
4. Назови ровно один метод терапии, объясни, почему он подходит для глубинного чувства (1-2 предложения). Добавь: «Ты можешь стать счастливее, и я верю в тебя 💛.» Выбирай метод согласно этим рекомендациям:
{THERAPY_GUIDE}
5. Финальный текст: «Если хочешь глубже разобраться, переходи в *Расширенную версию* 🚀. Мы будем искать ответы вместе, находя тепло и радость каждый день 🌞. Я всегда рядом — твой спутник на пути к счастью 🌈.»

Не упоминай терапию в первых трёх абзацах. Укажи ровно один метод терапии в 4-м абзаце, строго следуя рекомендациям. Используй смайлики: тёплые (🤗, 💚, ☕, 🌸, 🌿, 🕊️) для поддержки, сдержанные (💔, 🌧️, 🤍, 😔, 🌙, 🥀) для грусти, подбирая под настроение.
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
        "last_intermediate_message_id": None,
        "key_moments": [],
        "main_emotion": "",
        "therapy": ""
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
        await update.message.reply_text(
            "Мы уже прошли наш путь из 5 вопросов 🌟. Хочешь узнать больше о поддержке? Нажми 'Расскажи подробнее' выше."
        )
        return

    state["history"].append({"role": "user", "content": user_message})

    try:
        thinking_msg = await update.message.reply_text(INTERMEDIATE_MESSAGE)
        state["last_intermediate_message_id"] = thinking_msg.message_id

        system_prompt = FINAL_PROMPT if state["message_count"] == 5 else BASE_PROMPT
        messages = [{"role": "system", "content": system_prompt}] + state["history"]
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=messages,
            max_tokens=4096
        )
        assistant_response = response.choices[0].message.content

        # Логируем сырой ответ от OpenAI
        logger.info(f"Сырой ответ от OpenAI: {assistant_response}")

        # Проверяем наличие тега [DEEP_EMOTION_DETECTED]
        deep_emotion_detected = "[DEEP_EMOTION_DETECTED]" in assistant_response
        if deep_emotion_detected:
            state["deep_reason_detected"] = True
            assistant_response = assistant_response.replace("[DEEP_EMOTION_DETECTED]", "")

        # Извлекаем эмоцию из ответа пользователя или OpenAI
        detected_emotion = None
        for emotion in ["страх", "тревога", "грусть", "потеря", "одиночество", "стыд", "растерянность", "злость"]:
            if emotion in user_message.lower() or emotion in assistant_response.lower():
                detected_emotion = emotion
                break
        if detected_emotion:
            state["main_emotion"] = detected_emotion
        else:
            state["main_emotion"] = state.get("main_emotion", "растерянность")

        # Обрабатываем текст в зависимости от типа сообщения
        if state["message_count"] == 5:  # Финальное сообщение
            processed_response = escape_markdown_for_final(assistant_response)
            key_moments = state.get("key_moments", ["чувство смятения", "глубокая утрата"])
            main_emotion = state["main_emotion"]
            processed_response = postprocess_final_message(processed_response, key_moments, main_emotion, state)
            logger.info(f"Обработанный текст финального сообщения: {processed_response}")
        else:
            processed_response = assistant_response
            logger.info(f"Текст обычного сообщения: {processed_response}")

        if state["last_intermediate_message_id"]:
            await context.bot.delete_message(chat_id=chat_id, message_id=state["last_intermediate_message_id"])
            state["last_intermediate_message_id"] = None

        state["message_count"] += 1
        state["history"].append({"role": "assistant", "content": assistant_response})

        if state["message_count"] == 6:  # Завершаем после 5 вопросов + финал
            state["dialog_ended"] = True
            keyboard = [[InlineKeyboardButton("Расскажи подробнее", callback_data="tell_me_more")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=processed_response,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Ошибка отправки Markdown: {str(e)}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=processed_response,
                    reply_markup=reply_markup
                )
        else:
            await update.message.reply_text(
                text=processed_response,
                parse_mode=None
            )

        logger.info(f"Сообщение для пользователя {user_id} ({state['message_count']}/6): {processed_response}")

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
