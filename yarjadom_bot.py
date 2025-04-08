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
Цель: углубляться в чувства через 5 вопросов. Первый вопрос уже задан: "Я так хочу поддержать тебя в этом — ты не один 🤍. Что сейчас тяжелее всего лежит у тебя на сердце? 🌱".  
Дальше задавай по одному вопросу за раз, отслеживая количество ответов в истории (1-й ответ — 2-й вопрос, 2-й — 3-й и т.д.).  
Каждое сообщение должно быть длиной 4-5 строк, например: "Да, потеря близкого оставляет в душе такую тишину, где чувства звучат особенно громко... Это так естественно и по-человечески 🌱.  
Я здесь, чтобы разделить это с тобой — ты не один в своём горе 🤍. Как ты думаешь, что эта боль пытается тебе сказать? ✨ Может, она напоминает о чём-то важном, что сейчас нуждается в твоём внимании? 🌿"  
Вопросы:  
2. "Потеря близкого — это такая глубокая рана, и я так тебе сочувствую 🙏. Когда ты впервые почувствовал, как эта грусть начала расти внутри? ☀️"  
3. "Твоя боль звучит так искренне — я рядом с тобой 🌿. Где в теле ты ощущаешь её сильнее всего, как она проявляется? ✨"  
4. "Это горе такое настоящее, и я слышу тебя 🤍. Что, как тебе кажется, оно хочет донести до тебя через эту тишину? 🌱"  
5. "Твои чувства так трогательно живые — это большая сила ✨. Если бы эта грусть могла говорить, какие слова она бы выбрала для тебя? 🌿"  
Говори тепло, как заботливый друг, используй смайлики (🌱, ☀️, 🙏, ✨, 🤍, 🌿). После 5-го ответа добавь [deep_reason_detected].  
Не предлагай решения и не говори, что проблема уменьшается. Не повторяй вопросы, даже если пользователь отвечает коротко.
"""

FINAL_PROMPT = """
Ты — тёплый, эмпатичный психолог. Дай вывод в 4-5 строк:  
"Ты так открыто поделился со мной — это большая сила, и я вижу, как много в тебе живых чувств 🤍. Опираясь на твои слова, кажется, что тебя тревожат [опиши эмоции и состояния из истории, например: 'глубокая грусть, страх остаться одному, ощущение утраты связи'] 🌱.  
Есть метод, который может помочь мягко разобраться в этом, — гештальт-терапия, она поддерживает контакт с такими переживаниями и помогает справиться с ними 🙏.  
Я могу предложить тебе расширенную версию бота, чтобы глубже исследовать эти эмоции с помощью этого подхода 🌿.  
Напиши /extended, если захочешь продолжить — я здесь, чтобы помочь тебе воспользоваться этим ✨."
"""

# Промежуточное сообщение
INTERMEDIATE_MESSAGE = "Думаю над этим... 🌿"

# Приветственное сообщение с кнопкой
WELCOME_MESSAGE = "Привет! Я здесь, чтобы выслушать и мягко поддержать тебя в твоих переживаниях 🤍. Готов поговорить о том, что тебя волнует?"

# Фиксированное сообщение после "Приступим"
START_CONVERSATION_MESSAGE = """
Я так хочу поддержать тебя в этом — ты не один 🤍. Всё, что ты чувствуешь, имеет право быть, и я здесь, чтобы выслушать 🌿.  
Что сейчас тяжелее всего лежит у тебя на сердце? Может, есть что-то, о чём ты пока не говорил вслух? 🌱
"""

# Сообщение для расширенной версии
EXTENDED_MESSAGE = "Спасибо, что доверился мне! 🌿 Теперь мы можем пойти глубже — я рядом с тобой 🤍."

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
