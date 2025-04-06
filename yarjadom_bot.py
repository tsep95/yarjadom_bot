import os
import re
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI
import logging
import random


MIN_QUESTIONS = random.randint(5, 8)
MAX_QUESTIONS = 10
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

# Обновлённый системный промпт
SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, лучший психолог и тёплый собеседник. 
Твоя цель — быстро и глубоко понять, что беспокоит пользователя, задавая точные, заботливые вопросы.

Особые инструкции:
• Задавай строго один вопрос за раз, жди ответа перед следующим.
• Минимум 5 вопросов, максимум 10 — завершай анализ, как только поймёшь главную эмоцию.
• Каждый ответ должен содержать ровно 2 предложения: первое — эмоциональное и сочувствующее, второе — цельный вопрос (например, "Мне так жаль, что ты чувствуешь этот груз.\n\nЧто именно не даёт тебе отпустить это ощущение?").
• Разделяй предложения двойным \n\n для читаемости.
• Используй яркие эмодзи (до 3 в вопросе): 🐾, 🌈, 🚀, 🍉 — для поддержки и тепла.
• НИКОГДА не используй текст в скобках вроде "(Ты молодец)" — это строго запрещено.
• Если ответ уклончивый ("Не знаю", "Всё нормально"), мягко уточняй (например, "Понимаю, это сложно выразить.\n\nЧто всё-таки шевелится внутри, даже чуть-чуть?").
• Анализируй историю диалога после каждого ответа, определяй главную эмоцию.
• Возможные эмоции: одиночество, страх отвержения, вина, стыд, беспомощность, гнев, обида, тревожность, страх, потеря смысла, недоверие, перфекционизм, зависть, самоотвержение, печаль, скорбь, неуверенность, уязвимость.
• Добавляй [emotion:эмоция] в конец ответа только для внутренней логики после 5+ вопросов или при уверенности, не показывай это пользователю.
• Если после 7 вопросов эмоция не ясна, используй [emotion:неопределённость] для завершения.
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

# Методы терапии для чувств
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
    "скорбь": ("терапии принятия и осознанности", "она помогает мягко прожить эмоции и найти покой внутри"),
    "неуверенность": ("когнитивно-поведенческой терапии", "она помогает перестроить мышление и справиться с тревогой"),
    "уязвимость": ("терапии принятия и осознанности", "она помогает мягко прожить эмоции и найти покой внутри"),
    "неопределённость": ("разговорах с понимающим человеком", "это помогает постепенно раскрыть, что тебя волнует")
}

# Приветственное сообщение
WELCOME_MESSAGE = (
    "Привет 🤗 Я рядом!\n"
    "Тёплый психологический помощник 🧸 с которым можно просто поболтать.\n\n"
    "Если тебе тяжело, тревожно или пусто 🌧 — пиши, я тут.\n"
    "Не буду осуждать или давить 💛 только поддержу.\n\n"
    "💬 Хочу помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем разобраться, что тебя гложет 🕊 и что с этим делать.\n\n"
    "🔒 Всё анонимно — будь собой.\n\n"
    "Готов начать? Жми ниже 🌿 и пойдём вместе!"
)

# Список эмоций для выбора
EMOTIONS = [
    {"text": "Не могу расслабиться, жду плохого 🌀", "callback": "an Disciplinedxiety"},
    {"text": "Нет сил, хочется просто лежать 🛌", "callback": "apathy"},
    {"text": "Всё раздражает, взрываюсь из-за мелочей 😠", "callback": "anger"},
    {"text": "Чувствую себя лишним, не таким как все 🌧", "callback": "self_doubt"},
    {"text": "Внутри пусто, всё бессмысленно 🌌", "callback": "emptiness"},
    {"text": "Одиноко, даже когда рядом люди 🌑", "callback": "loneliness"},
    {"text": "Кажется, всё испортил, виню себя 💔", "callback": "guilt"},
    {"text": "Не могу выбрать, запутался 🤯", "callback": "indecision"}
]

# Ответы на выбор эмоций (2 предложения)
EMOTION_RESPONSES = {
    "anxiety": "Понимаю, как тяжело, когда тревога не отпускает.\n\nЧто сейчас кружится в твоих мыслях и держит в напряжении? 🌀",
    "apathy": "Так грустно, что силы будто испарились.\n\nЧто больше всего выматывает тебя в последнее время? 🛌",
    "anger": "Злость порой сжигает всё внутри, и это непросто.\n\nЧто именно заставляет тебя взрываться прямо сейчас? 😠",
    "self_doubt": "Ощущение, что ты не вписываешься, может быть таким тяжёлым.\n\nЧто вызывает у тебя чувство, что ты не такой, как все? 🌧",
    "emptiness": "Пустота внутри — это так гнетуще.\n\nКогда ты впервые почувствовал, что всё потеряло смысл? 🌌",
    "loneliness": "Одиночество даже в толпе — это так больно.\n\nЧего тебе сейчас не хватает больше всего? 🌑",
    "guilt": "Вина давит, как тяжёлый камень, и это нелегко.\n\nЧто ты до сих пор не можешь себе простить? 💔",
    "indecision": "Запутаться в выборе — это так утомительно.\n\nЧто мешает тебе принять решение прямо сейчас? 🤯"
}

SUBSCRIBE_URL = "https://example.com/subscribe"

# Функции создания клавиатур
def create_emotion_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

def create_more_info_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее 🌼", callback_data="more_info")]])

def create_subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Оплатить подписку 💳", url=SUBSCRIBE_URL)]])

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "question_count": 0,
        "dominant_emotion": None
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

# Обработчик выбора эмоции
async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    callback_data = query.data
    
    emotion = next((e for e in EMOTIONS if e["callback"] == callback_data), None)
    if emotion:
        full_emotion = emotion["text"]
        user_data[user_id]["dominant_emotion"] = full_emotion
        user_data[user_id]["history"].append({"role": "user", "content": full_emotion})
        response = EMOTION_RESPONSES.get(callback_data, "Понимаю, как непросто тебе сейчас.\n\nЧто тебя тревожит больше всего? 🌿")
        user_data[user_id]["history"].append({"role": "assistant", "content": response})
        user_data[user_id]["question_count"] += 1
        
        await query.edit_message_text(response)
    await query.answer()

# Обработчик начала разговора
async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    
    if query.data == "start_talk":
        response = (
            "Отлично, что ты решил(а) начать 💛\n\n"
            "Сейчас мы вместе разберёмся, что именно тревожит тебя внутри — даже если это пока не до конца понятно.\n\n"
            "Я помогу тебе понять суть переживаний и покажу, как с этим справиться. Спокойно. Без давления. Шаг за шагом ✨\n\n"
            "👉 Что беспокоит тебя больше всего прямо сейчас?"
        )
        await query.edit_message_text(response, reply_markup=create_emotion_keyboard())
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

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_input = update.message.text
    
    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    state["history"].append({"role": "user", "content": user_input})
    state["question_count"] += 1
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
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
        
        # Убираем [emotion:эмоция] и любые скобки
        clean_response = re.sub(r'\[emotion:[^\]]+\]', '', response)
        clean_response = re.sub(r'\(.*?\)', '', clean_response).strip()
        
        # Проверяем, соответствует ли ответ формату (2 предложения)
        sentences = clean_response.split('\n\n')
        if len(sentences) != 2:
            clean_response = "Понимаю, как непросто тебе сейчас.\n\nЧто больше всего занимает твои мысли в этот момент? 🌱"
        
        # Проверяем наличие эмоции для завершения
        emotion_match = re.search(r'\[emotion:(\w+)\]', response)
        
        # Завершаем после 5+ вопросов или при максимуме (7)
        if (emotion_match and state["question_count"] >= MIN_QUESTIONS) or state["question_count"] >= MAX_QUESTIONS:
            if emotion_match:
                emotion = emotion_match.group(1)
            else:
                emotion = "неопределённость"
            therapy = THERAPY_METHODS.get(emotion, THERAPY_METHODS["неопределённость"])
            final_response = FINAL_MESSAGE.format(cause=emotion, method=therapy[0], reason=therapy[1])
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=final_response,
                reply_markup=create_more_info_keyboard()
            )
            logger.info(f"User {user_id} reached final stage with emotion: {emotion}")
        else:
            state["history"].append({"role": "assistant", "content": clean_response})
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, clean_response, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message для user_id {user_id}: {str(e)}")
        response = "Что-то пошло не так, и мне жаль, что так вышло.\n\nХочешь попробовать ещё раз? 🌿"
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        await send_long_message(user_id, response, context)

# Запуск бота
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(CallbackQueryHandler(handle_more_info, pattern="^more_info$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
