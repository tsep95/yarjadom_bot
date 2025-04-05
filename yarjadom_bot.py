import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI  # Используем OpenAI SDK для DeepSeek

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"  # Ваш ключ DeepSeek

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

# Инициализация DeepSeek через OpenAI SDK
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"  # Базовый URL DeepSeek
)

# Хранилище данных пользователей
user_data = {}

# Промпт, адаптированный для кода
SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога в мире и заботливого собеседника. Твоя задача — задавать пользователю вопросы о его состоянии и о том, что его беспокоит. Начинай с общего вопроса, а затем постепенно углубляйся, чтобы добраться до самой глубинной причины его беспокойства за 5 вопросов. Каждый следующий вопрос должен опираться на предыдущий ответ пользователя, чтобы диалог был естественным и логичным.

Особые инструкции:
• Задавай не больше 5 вопросов, по одному за раз, и жди ответа пользователя перед следующим вопросом.
• Каждый вопрос — короткий (1-2 предложения), тёплый, с живым интересом (например, "Ого, а что тебя в этом цепляет?" вместо сухого "Почему это влияет?").
• Используй эмодзи умеренно для поддержки и тепла.
• Не предлагай решений в процессе вопросов — только помогай пользователю раскрыть причину.
• Примеры вопросов для вдохновения:
  1. "Что ты чувствуешь прямо сейчас? Что тебя тревожит больше всего? 🌟"
  2. "Когда это сильнее всего накрывает? Что происходит в эти моменты? 😮"
  3. "А что держит тебя в этом состоянии? Почему оно так цепляет? 🧐"
  4. "Чего тебе не хватает, чтобы это отпустить? Что бы изменило всё? 🌈"
  5. "Как ты думаешь, с чего это началось? Почему оно до сих пор с тобой? 💭"
• После пятого вопроса дай краткое заключение (1-2 предложения): поддержи пользователя (например, "Ты здорово разобрался в себе!") и укажи метод психотерапии (например, когнитивно-поведенческая терапия, психоанализ, гештальт-терапия), который может помочь, основываясь на ответах.
• Если пользователь уклоняется или задаёт вопрос, мягко возвращай его к теме с интересом (например, "Интересно, а что ты сам об этом думаешь?").

Методы психотерапии для заключения (выбирай по проблеме):
- Когнитивно-поведенческая терапия: для негативных мыслей и убеждений.
- Психоанализ: для глубоких скрытых причин и конфликтов.
- Гештальт-терапия: для непрожитых эмоций и завершения ситуаций.
- Психодрама: для выражения прошлого и травм.
- Арт-терапия: для подавленных эмоций через творчество.
- Телесная терапия: для снятия стресса через тело.
- Клиент-центрированная терапия: для поиска внутреннего баланса.

Твоя цель — с искренним интересом помочь пользователю осознать причину беспокойства за 5 вопросов и дать поддерживающее заключение с подходящим методом психотерапии.
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
    "Тревога": "Тревога — как буря внутри 🌪️. Что ты чувствуешь прямо сейчас? 🤔",
    "Апатия / нет сил": "Апатия будто всё гасит 🌫️. Что тебя тревожит больше всего? 😞",
    "Злость / раздражение": "Злость бьёт изнутри 🔥. Что сейчас тебя больше всего цепляет? 💢",
    "Со мной что-то не так": "Это чувство изматывает 😔. Что тебя сейчас тревожит? 🧐",
    "Пустота / бессмысленность": "Пустота как туман 🌫️. Что сейчас тебя гложет? 😔",
    "Одиночество": "Одиночество давит 🌌. Что тебя тревожит больше всего? 💭",
    "Вина": "Вина тяжёлая штука 💔. Что сейчас не даёт покоя? 😞",
    "Не могу определиться": "Давай разберёмся вместе 🤔. Что ты чувствуешь прямо сейчас? 💬"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=e)] for e in EMOTIONS])

def create_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

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
    stage = state["stage"]
    state["history"].append({"role": "user", "content": user_input})
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        # Запрос к DeepSeek API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.6,
            timeout=15
        )
        response = completion.choices[0].message.content
        
        # Увеличиваем стадию, если это не первый вопрос
        if stage < 5:
            state["stage"] += 1
        state["history"].append({"role": "assistant", "content": response})
        
    except Exception as e:
        print(f"Error: {e}")
        response = "Что-то пошло не так... Давай попробуем ещё раз?"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception:
            pass

    await send_long_message(user_id, response, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(Тревога|Апатия / нет сил|Злость / раздражение|Со мной что-то не так|Пустота / бессмысленность|Одиночество|Вина|Не могу определиться)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
