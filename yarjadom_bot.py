import os
import re
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

# Инициализация клиента OpenAI для DeepSeek API
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Хранилище данных пользователей
user_data: Dict[int, dict] = {}

# Константы
MIN_CONFIRMATION_QUESTIONS = 4  # Минимальное количество одинаковых эмоций для уверенности
MAX_QUESTIONS = 15  # Максимальное количество вопросов

# Обновлённый системный промпт
SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, лучший психолог и тёплый собеседник. 
Твоя цель — глубоко понять, что беспокоит пользователя, задавая точные, заботливые вопросы.

Особые инструкции:
• Задавай строго один вопрос за раз, жди ответа перед следующим.
• Задавай минимум 5 вопросов, продолжай до 15, если эмоция не ясна.
• Каждый ответ — ровно 2 предложения: первое — сочувствие, второе — вопрос.
• Разделяй предложения двойным \n\n для читаемости.
• Используй до 3 эмодзи в вопросе (🐾, 🌈, 🚀, 🍉) для тепла.
• Иногда добавляй в вопросы выбор "или" (например, "Тебе хочется спрятаться или что-то изменить?"), чтобы помочь пользователю выразить себя.
• НИКОГДА не используй скобки вроде "(Ты молодец)".
• Если ответ уклончивый ("Не знаю", "Всё нормально"), уточняй мягко.
• Анализируй историю, определяй эмоцию после каждого ответа.
• Возможные эмоции: одиночество, страх отвержения, вина, стыд, беспомощность, гнев, обида, тревожность, страх, потеря смысла, недоверие, перфекционизм, зависть, самоотвержение, печаль, неуверенность, уязвимость.
• Добавляй [emotion:эмоция] в конец ответа для внутренней логики, когда уверен.
• Если после 15 вопросов эмоция не ясна, используй эмоцию с наибольшим количеством определений.
"""

# Финальное сообщение
FINAL_MESSAGE = (
    "Ты большой молодец, что доверился и прошёл этот разбор — это уже шаг к себе настоящему! 💫\n\n"
    "По тому, что ты рассказал, я вижу:\n"
    "твои чувства важны, понятны и точно не случайны 🌱. "
    "Они пытаются о чём-то напомнить, и вместе мы уже начали это понимать.\n\n"
    "Похоже, в основе твоего состояния — {cause} 🧩. "
    "С этим эффективно работают в {method} — "
    "{reason}. "
    "И ты уже сделал первый шаг к этому! ✨\n\n"
    "Я рядом, чтобы поддержать, когда трудно, "
    "и помочь тебе стать по-настоящему счастливым 🤗.\n\n"
    "Ты достоин быть счастливым — не когда-нибудь потом, а уже сейчас 💛. "
    "И я помогу тебе идти в эту сторону. "
    "Шаг за шагом. "
    "Вместе 🌿.\n\n"
    "Если захочешь копнуть глубже — "
    "переходи в расширенную версию 🚀.\n\n"
    "Там я буду рядом каждый день, "
    "помогая находить ответы и тепло внутри 🌞."
)

# Методы терапии
THERAPY_METHODS = {
    "одиночество": ("гештальт-терапии", "она помогает прожить эмоции и восстановить связь с собой и другими"),
    "страх отвержения": ("когнитивно-поведенческой терапии", "она помогает справиться с беспокойством и вернуть контроль"),
    "вина": ("клиент-центрированной терапии", "она помогает найти внутренний баланс и принять себя"),
    "стыд": ("терапии принятия и осознанности", "она помогает мягко прожить эмоции и найти покой внутри"),
    "беспомощность": ("когнитивно-поведенческой терапии", "она помогает перестроить мышление и справиться с тревогой"),
    "гнев": ("гештальт-терапии", "она помогает завершить незакрытые ситуации и прожить подавленные эмоции"),
    "обида": ("гештальт-терапии", "она помогает завершить незакрытые ситуации и прожить подавленные эмоции"),
    "тревожность": ("когнитивно-поведенческой терапии", "она помогает справиться с беспокойством и вернуть контроль"),
    "страх": ("когнитивно-поведенческой терапии", "она помогает справиться с беспокойством и вернуть контроль"),
    "потеря смысла": ("арт-терапии", "она помогает выразить эмоции через творчество и найти новые ориентиры"),
    "недоверие": ("психоанализе", "он раскрывает глубокие скрытые причины и конфликты"),
    "перфекционизм": ("когнитивно-поведенческой терапии", "она помогает осознать и изменить негативные паттерны"),
    "зависть": ("когнитивно-поведенческой терапии", "она помогает осознать и изменить негативные паттерны"),
    "самоотвержение": ("клиент-центрированной терапии", "она помогает найти внутренний баланс и принять себя"),
    "печаль": ("терапии принятия и осознанности", "она помогает мягко прожить эмоции и найти покой внутри"),
    "неуверенность": ("когнитивно-поведенческой терапии", "она помогает перестроить мышление и справиться с тревогой"),
    "уязвимость": ("терапии принятия и осознанности", "она помогает мягко прожить эмоции и найти покой внутри"),
    "неопределённость": ("разговорах с понимающим человеком", "это помогает постепенно раскрыть, что тебя волнует")
}

# Приветственное сообщение с кнопкой
WELCOME_MESSAGE = (
    "Привет 🤗 Я рядом!\n"
    "Тёплый психологический помощник 🧸 с которым можно просто поболтать.\n\n"
    "Если тебе тяжело, тревожно или пусто 🌧 — пиши, я тут.\n"
    "Не буду осуждать или давить 💛 только поддержу.\n\n"
    "💬 Хочу помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем разобраться, что тебя гложет 🕊 и что с этим делать.\n\n"
    "🔒 Всё анонимно — будь собой.\n\n"
    "Готов начать? Нажми ниже! 🌿"
)

# Увеличенное второе сообщение после нажатия кнопки
START_QUESTION = (
    "Отлично, что ты решился начать — это уже маленький шаг к тому, чтобы стало легче! 💛\n\n"
    "Я здесь, чтобы выслушать тебя и помочь разобраться в том, что творится внутри.\n"
    "Мы пойдём шаг за шагом, без спешки, чтобы ты мог почувствовать себя лучше 🌱.\n\n"
    "Что беспокоит тебя больше всего прямо сейчас? 🌿"
)

SUBSCRIBE_URL = "https://example.com/subscribe"

# Функции создания клавиатур
def create_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

def create_more_info_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее 🌼", callback_data="more_info")]])

def create_subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Оплатить подписку 💳", url=SUBSCRIBE_URL)]])

# Обновляем функцию start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "question_count": 0,
        "emotion_history": [],  # Список эмоций по каждому ответу
        "dominant_emotion": None,
        "max_questions": MAX_QUESTIONS,
        "started": False  # Флаг начала разговора
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

# Обработчик начала разговора
async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    
    if query.data == "start_talk" and not user_data[user_id]["started"]:
        user_data[user_id]["started"] = True
        await query.edit_message_text(START_QUESTION)
        await query.answer()

# Обработчик кнопки "Расскажи подробнее"
async def handle_more_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    response = (
        "Это твоя заботливая опора на каждый день.\n"
        "Чтобы становилось легче, спокойнее и радостнее — шаг за шагом.\n\n"
        "⸻\n\n"
        "Что внутри:\n"
        "☀️ Каждое утро — тёплое пожелание для старта дня\n"
        "🌙 Каждый вечер — мягкая рефлексия дня\n"
        "🧠 Глубокая проработка тревоги, вины, апатии\n"
        "🆘 SOS-помощь в трудные моменты\n"
        "📆 Календарь состояния и аналитика\n"
        "🎯 Психо-квесты: самооценка, уверенность, границы\n\n"
        "⸻\n\n"
        "💛 Цель — делать тебя счастливее каждый день.\n"
        "499 ₽ в месяц. Первая неделя — бесплатно."
    )
    await query.edit_message_text(response, reply_markup=create_subscribe_keyboard())
    await query.answer()

# Функция отправки длинных сообщений
async def send_long_message(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + MAX_LENGTH])
        await asyncio.sleep(0.3)

# Функция завершения диалога
async def finish_conversation(user_id: int, emotion: str, context: ContextTypes.DEFAULT_TYPE, state: dict):
    therapy = THERAPY_METHODS.get(emotion, THERAPY_METHODS["неопределённость"])
    final_response = FINAL_MESSAGE.format(cause=emotion, method=therapy[0], reason=therapy[1])
    thinking_msg_id = state.get("thinking_msg_id")
    if thinking_msg_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {thinking_msg_id}: {str(e)}")
    await context.bot.send_message(
        chat_id=user_id,
        text=final_response,
        reply_markup=create_more_info_keyboard()
    )
    logger.info(f"Диалог завершен. Пользователь: {user_id}, Эмоция: {emotion}")
    del user_data[user_id]

# Проверка количества одинаковых эмоций
def check_emotion_confidence(emotion_history: list) -> tuple:
    if not emotion_history:
        return None, 0
    emotion_counts = {}
    for emotion in emotion_history:
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    dominant_emotion = max(emotion_counts, key=emotion_counts.get)
    count = emotion_counts[dominant_emotion]
    return dominant_emotion, count

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_input = update.message.text
    
    if user_id not in user_data:
        await start(update, context)
        return
    
    state = user_data[user_id]
    if not state["started"]:
        return  # Ждём нажатия кнопки "Приступим"

    state["history"].append({"role": "user", "content": user_input})
    if len(state["history"]) > 30:  # Храним последние 15 пар вопрос-ответ
        state["history"] = state["history"][-30:]
    state["question_count"] += 1
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    state["thinking_msg_id"] = thinking_msg.message_id
    
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            timeout=30
        )
        response = completion.choices[0].message.content
        
        logger.info(f"DeepSeek response for user {user_id}: {response}")
        
        # Убираем [emotion:эмоция] и скобки
        clean_response = re.sub(r'\[emotion:[^\]]+\]', '', response)
        clean_response = re.sub(r'\(.*?\)', '', clean_response).strip()
        
        # Проверяем формат (2 предложения)
        sentences = clean_response.split('\n\n')
        if len(sentences) != 2:
            clean_response = "Понимаю, как непросто тебе сейчас.\n\nЧувствуешь ли ты усталость или раздражение из-за этого? 🌱"
        
        # Извлекаем эмоцию от DeepSeek
        emotion_match = re.search(r'\[emotion:([^\]]+)\]', response)
        detected_emotion = emotion_match.group(1) if emotion_match else "неопределённость"
        state["emotion_history"].append(detected_emotion)
        
        # Проверка уверенности
        dominant_emotion, emotion_count = check_emotion_confidence(state["emotion_history"])
        
        logger.info(f"User {user_id} - Detected emotion: {detected_emotion}, Dominant: {dominant_emotion}, Count: {emotion_count}")
        
        # Условия завершения
        if emotion_count >= MIN_CONFIRMATION_QUESTIONS and dominant_emotion != "неопределённость":
            await finish_conversation(user_id, dominant_emotion, context, state)
        elif state["question_count"] >= state["max_questions"]:
            # Если достигнут лимит в 15 вопросов, берём эмоцию с максимальным количеством очков
            final_emotion = dominant_emotion if dominant_emotion else "неопределённость"
            await finish_conversation(user_id, final_emotion, context, state)
        else:
            state["history"].append({"role": "assistant", "content": clean_response})
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, clean_response, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message для user_id {user_id}: {str(e)}")
        response = "Что-то пошло не так, и мне жаль, что так вышло.\n\nХочешь ли ты продолжить или взять паузу? 🌿"
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception as delete_error:
            logger.warning(f"Не удалось удалить сообщение {thinking_msg.message_id}: {str(delete_error)}")
        await send_long_message(user_id, response, context)

# Запуск бота
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(CallbackQueryHandler(handle_more_info, pattern="^more_info$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
