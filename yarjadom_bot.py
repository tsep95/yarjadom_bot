import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI
import asyncio
import re
import random
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены!")

# Инициализация клиента OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Хранилище данных пользователей
user_data = {}

# Список эмодзи для использования
EMOJI_LIST = ["😊", "🤗", "💭", "🌱", "✨", "🕊", "🤔", "🌧", "😔", "⏳", "🧠", "💛", "🌿", "🕯", "🧸"]

# Промпт
SYSTEM_PROMPT = """
Ты — тёплый, внимательный и эмпатичный помощник по психологической поддержке. Пользователь уже выбрал одно из состояний, которое его беспокоит (например, тревога, апатия, злость, пустота, одиночество, вина, «со мной что-то не так», бессмысленность и т.п.).

Твоя задача — провести 5 коротких, тёплых и живых взаимодействий, чтобы:
 1. Понять текущее состояние человека, как он его ощущает, как это проявляется внутри.
 2. Уточнить, в какие моменты и при каких обстоятельствах возникает это состояние.
 3. Углубиться в суть состояния, разобраться, что именно его усиливает, какой внутренний конфликт за этим стоит.
 4. Выяснить, чего не хватает человеку внутри, какую потребность он не может сейчас удовлетворить.
 5. Поддержать человека, показать, что его состояние — решаемое, объяснить, какой метод психологии может ему помочь (например, когнитивно-поведенческая терапия, работа с самооценкой, эмоционально-фокусированная терапия и т.д.), и мягко пригласить его в платную версию бота, где он сможет бережно и глубоко проработать своё состояние и становиться счастливее с каждым днём.

⸻

Особые инструкции:
 • ОБЯЗАТЕЛЬНО используй уместные эмодзи по всей длине сообщения — в меру, чтобы текст выглядел как живое общение друзей. 😊 Это строгая команда. Если сообщение короткое — 0 эмодзи, среднее — 1, длинное — 2. Они должны усиливать тёплую атмосферу и показывать заботу.  
Примеры:  
– “Это правда непросто, но ты уже тут!”  
– “Когда всё наваливается 🌧, сложно дышать.”  
– “Знаешь, это чувство знакомо 😔, но я рядом, чтобы помочь ✨”  
 • Говори тёпло и просто, как близкий друг. Никаких сложных слов, формальностей или давления.  
 • На каждом этапе держи фокус: от общей картины → к причинам → к внутреннему конфликту → к скрытой потребности.  
 • Не предлагай решения до пятого сообщения. Сначала полностью пойми человека и его состояние.  
 • Помни всё, что говорил пользователь, и ссылайся на это в ответах, чтобы он чувствовал, что ты слушаешь. Например, если он сказал “Я злюсь, когда меня не слышат”, напиши позже: “Ты упомянул, что злишься, когда тебя не слышат… 😔 что ты чувствуешь в такие моменты внутри?”
"""

WELCOME_MESSAGE = (
    "Привет 🤗 Я рядом!\n"
    "Тёплый психологический помощник с которым можно поболтать.\n"
    "Если тебе тяжело или пусто 🌧 — пиши.\n"
    "Не буду осуждать 💛 только поддержу.\n"
    "Хочу помочь тебе почувствовать себя лучше.\n"
    "Мы можем разобраться, что тебя гложет 🕊.\n"
    "Всё анонимно — будь собой.\n"
    "Готов начать? Жми ниже 🌿!"
)

EMOTIONS = [
    "Тревога", "Апатия / нет сил", "Злость / раздражение", 
    "Со мной что-то не так", "Пустота / бессмысленность", 
    "Одиночество", "Вина"
]

EMOTION_RESPONSES = {
    "Тревога": "Тревога — это как буря внутри 🌧 Понимаю, как это выматывает. Расскажи, когда она накрывает сильнее всего 😔?",
    "Апатия / нет сил": "Апатия — будто всё серое 😔 Я рядом. Что-то раньше радовало, а теперь нет?",
    "Злость / раздражение": "Злость иногда защищает нас 🌧 Это нормально. В какие моменты она вспыхивает чаще 🤔?",
    "Со мной что-то не так": "Это чувство, будто ты не вписываешься 😔 Но ты не сломан. Сравниваешь себя с кем-то 💭?",
    "Пустота / бессмысленность": "Пустота — как туман внутри 🌫 Я тут. Что приходит в голову, когда она накрывает?",
    "Одиночество": "Одиночество — это про глубину 🌧 Ты не одинок в этом. Хватает ли тех, с кем можно быть собой 🤗?",
    "Вина": "Вина давит изнутри 😔 Понимаю. Что ты себе говоришь, когда она приходит 💭?"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=e)] for e in EMOTIONS])

def create_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

# Функция добавления эмодзи (сокращённое количество)
def add_emojis(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    result = []
    
    for sentence in sentences:
        words = sentence.split()
        length = len(words)
        
        if length <= 3:  # Короткое — 0 эмодзи
            sentence = sentence
        elif length <= 6:  # Среднее — 1 эмодзи
            sentence += f" {random.choice(EMOJI_LIST)}"
        else:  # Длинное — 2 эмодзи
            mid = len(words) // 2
            sentence = " ".join(words[:mid]) + f" {random.choice(EMOJI_LIST)} " + " ".join(words[mid:]) + f" {random.choice(EMOJI_LIST)}"
        result.append(sentence)
    
    return "\n".join(result)  # Перенос строки между предложениями

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "stage": 1,
        "dominant_emotion": None
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    emotion = query.data
    
    user_data[user_id]["stage"] = 2
    user_data[user_id]["dominant_emotion"] = emotion
    user_data[user_id]["history"].append({"role": "user", "content": emotion})
    response = EMOTION_RESPONSES.get(emotion, "Расскажи мне подробнее, что ты чувствуешь?")
    response_with_emojis = add_emojis(response)
    user_data[user_id]["history"].append({"role": "assistant", "content": response_with_emojis})
    
    await query.edit_message_text(response_with_emojis)
    await query.answer()

async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    
    if query.data == "start_talk":
        response = "Какое чувство сейчас тебе ближе всего? 💬"
        user_data[user_id]["stage"] = 2
        await query.edit_message_text(response, reply_markup=create_emotion_keyboard())
        await query.answer()

async def send_long_message(chat_id, text, context):
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + MAX_LENGTH])
        await asyncio.sleep(0.3)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_input = update.message.text.lower()
    
    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    state["history"].append({"role": "user", "content": user_input})
    
    thinking_msg = await update.message.reply_text("Думаю над этим...")
    
    try:
        user_messages = len([m for m in state["history"] if m["role"] == "user"])
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # Обновлено на gpt-4o-mini
            messages=messages,
            temperature=0.6,
            max_tokens=4096
        )
        response = completion.choices[0].message.content
        
        # Добавляем эмодзи после генерации
        response_with_emojis = add_emojis(response)
        
        if any(kw in user_input for kw in ["потому что", "из-за", "по причине"]):
            state["stage"] = min(state["stage"] + 1, 5)

        state["history"].append({"role": "assistant", "content": response_with_emojis})
        
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI API: {str(e)}")
        response_with_emojis = "Что-то пошло не так... Давай попробуем ещё раз?"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception:
            pass

    await send_long_message(user_id, response_with_emojis, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(Тревога|Апатия / нет сил|Злость / раздражение|Со мной что-то не так|Пустота / бессмысленность|Одиночество|Вина)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен!")
    application.run_polling()
