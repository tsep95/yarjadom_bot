import os
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
import re
import random

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены!")

# Инициализация OpenAI (старая версия)
openai.api_key = OPENAI_API_KEY

# Хранилище данных пользователей
user_data = {}

# Категории эмодзи для контекстного добавления
EMOJI_CATEGORIES = {
    "positive": ["😊", "🌱", "✨", "💛", "🤗"],  # Позитив, надежда
    "support": ["🕊", "🌿", "🧸", "🤝"],         # Поддержка, тепло
    "sad": ["😔", "🌧", "⏳"],                   # Грусть, тяжесть
    "thoughtful": ["💭", "🤔", "🧠"]            # Размышления, вопросы
}

# Ключевые слова для определения тона
EMOTION_KEYWORDS = {
    "positive": ["хорошо", "лучше", "рада", "рад", "спасибо", "круто"],
    "support": ["рядом", "помочь", "вместе", "не один", "справимся"],
    "sad": ["грустно", "тяжело", "плохо", "сложно", "больно"],
    "thoughtful": ["думаю", "кажется", "почему", "что", "когда"]
}

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
 • НЕ используй фразу "понимаю тебя" — вместо этого говори разнообразно и живо, как друг. Примеры: "Ох, это правда непросто…", "Чувствую, как тебе сейчас тяжело…", "Знаешь, это знакомо многим…", "Слышу тебя, и мне не всё равно…".
 • Эмодзи будут добавлены автоматически кодом, поэтому не вставляй их сам. Пиши только текст.
 • Говори тёпло и просто, как близкий друг. Никаких сложных слов, формальностей или давления.
 • На каждом этапе держи фокус: от общей картины → к причинам → к внутреннему конфликту → к скрытой потребности.
 • Не предлагай решения до пятого сообщения. Сначала полностью пойми человека и его состояние.
 • Помни всё, что говорил пользователь, и ссылайся на это в ответах, чтобы он чувствовал, что ты слушаешь. Например, если он сказал “Я злюсь, когда меня не слышат”, напиши позже: “Ты упомянул, что злишься, когда тебя не слышат… что ты чувствуешь в такие моменты внутри?”
"""

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

EMOTIONS = [
    "Тревога", "Апатия / нет сил", "Злость / раздражение", 
    "Со мной что-то не так", "Пустота / бессмысленность", 
    "Одиночество", "Вина", "Не могу определиться"
]

EMOTION_RESPONSES = {
    "Тревога": "Тревога — это как буря внутри, когда мысли не дают покоя. Расскажи, когда она накрывает сильнее всего?",
    "Апатия / нет сил": "Апатия — будто всё серое и плоское. Я рядом. Что-то раньше радовало, а теперь нет?",
    "Злость / раздражение": "Злость иногда защищает нас, когда внутри неспокойно. В какие моменты она вспыхивает чаще?",
    "Со мной что-то не так": "Это чувство, будто ты не вписываешься, изматывает. Сравниваешь себя с кем-то или ждёшь чего-то от себя?",
    "Пустота / бессмысленность": "Пустота — как туман внутри, когда ничего не цепляет. Что приходит в голову, когда она накрывает?",
    "Одиночество": "Одиночество — это про глубину, а не про людей вокруг. Хватает ли тех, с кем можно быть собой?",
    "Вина": "Вина давит изнутри, особенно когда кажется, что мог бы лучше. Что ты себе говоришь, когда она приходит?",
    "Не могу определиться": "Ничего страшного, давай пообщаемся о том, что тебя беспокоит?"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=e)] for e in EMOTIONS])

def create_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

# Обновлённая функция для контекстного добавления эмодзи
def add_contextual_emojis(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    result = []
    total_emojis = 0
    
    for sentence in sentences:
        words = sentence.split()
        length = len(words)
        lower_sentence = sentence.lower()
        
        if total_emojis >= 3:  # Лимит 3 эмодзи для всего сообщения
            result.append(sentence)
            continue
        
        # Определяем эмоциональный тон
        tone = "support"  # По умолчанию — поддержка
        for category, keywords in EMOTION_KEYWORDS.items():
            if any(keyword in lower_sentence for keyword in keywords):
                tone = category
                break
        
        # Добавляем не более 1 эмодзи в предложении
        if length <= 4 and total_emojis < 3:  # Очень короткое — 1 эмодзи в конце
            emoji = random.choice(EMOJI_CATEGORIES[tone])
            sentence += f" {emoji}"
            total_emojis += 1
        elif 4 < length <= 8 and total_emojis < 3:  # Среднее — 1 эмодзи в конце
            emoji = random.choice(EMOJI_CATEGORIES[tone])
            sentence += f" {emoji}"
            total_emojis += 1
        elif length > 8 and total_emojis < 3:  # Длинное — 1 эмодзи в середине
            half = len(words) // 2
            emoji = random.choice(EMOJI_CATEGORIES[tone])
            sentence = " ".join(words[:half]) + f" {emoji} " + " ".join(words[half:])
            total_emojis += 1
        
        result.append(sentence)
    
    return "\n".join(result)

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
    # Без добавления эмодзи в заготовленные сообщения
    user_data[user_id]["history"].append({"role": "assistant", "content": response})
    
    await query.edit_message_text(response)
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
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        user_messages = len([m for m in state["history"] if m["role"] == "user"])
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.6,
            timeout=15
        )
        response = completion.choices[0].message["content"]
        
        # Добавляем контекстные эмодзи только к ответам GPT
        response_with_emojis = add_contextual_emojis(response)
        
        if any(kw in user_input for kw in ["потому что", "из-за", "по причине"]):
            state["stage"] = min(state["stage"] + 1, 5)

        state["history"].append({"role": "assistant", "content": response_with_emojis})
        
    except Exception as e:
        print(f"Error: {e}")
        response_with_emojis = "Что-то пошло не так... Давай попробуем ещё раз? 🌸"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception:
            pass

    await send_long_message(user_id, response_with_emojis, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(Тревога|Апатия / нет сил|Злость / раздражение|Со мной что-то не так|Пустота / бессмысленность|Одиночество|Вина|Не могу определиться)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
