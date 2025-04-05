import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = "ВАШ_API_КЛЮЧ"

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

user_data = {}

SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога и заботливого собеседника. Твоя задача — задавать пользователю вопросы, чтобы за 5 шагов помочь осознать глубинную причину беспокойства.

Особые инструкции:
• Задавай ровно 5 вопросов по очереди.
• Каждый вопрос живой, искренний, добрый, с эмодзи.
• Не используй цифры и звёздочки в ответах.
• После пятого вопроса предложи подходящий метод терапии и упомяни платную версию.
• Эмодзи должны быть живыми и уместными.
"""

WELCOME_MESSAGE = (
    "Привет 🤗 Я рядом!\n"
    "Тёплый психологический помощник 🧸, с которым можно просто поболтать.\n\n"
    "Если тебе тяжело, тревожно или пусто 🌧 — пиши, я тут.\n"
    "Не буду осуждать или давить 💛 только поддержу.\n\n"
    "Готов начать? 🌿"
)

EMOTIONS = [
    {"text": "Не могу расслабиться, жду чего-то плохого 🌀", "callback": "anxiety"},
    {"text": "Нет сил, хочу просто лежать 🛌", "callback": "apathy"},
    {"text": "Раздражает всё подряд! 😠", "callback": "anger"},
    {"text": "Чувствую себя не таким, лишним 🌧", "callback": "self_doubt"},
    {"text": "Внутри пустота, нет смысла 🌌", "callback": "emptiness"},
    {"text": "Одиноко даже среди людей 🌑", "callback": "loneliness"},
    {"text": "Чувствую вину за всё 💔", "callback": "guilt"},
    {"text": "Не могу принять решение 🤯", "callback": "indecision"}
]

EMOTION_RESPONSES = {
    "anxiety": "Напряжение висит в воздухе 🌪️ Что занимает твои мысли больше всего сейчас?",
    "apathy": "Совсем нет сил даже на простые вещи 🌫️ Что гложет тебя в эти минуты?",
    "anger": "Похоже, внутри всё кипит 🔥 Что больше всего тебя сейчас тревожит?",
    "self_doubt": "Ощущение, будто ты не на своём месте 😔 Какие мысли приходят чаще всего?",
    "emptiness": "Пустота, которую сложно объяснить 🌌 Что тебя тревожит глубже всего?",
    "loneliness": "Одиночество может сильно давить изнутри 🌑 Поделись, что особенно беспокоит?",
    "guilt": "Вина давит на плечи 💔 Что заставляет тебя винить себя больше всего?",
    "indecision": "Иногда так сложно сделать выбор 🤯 Что именно тебя сейчас тревожит больше всего?"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_more_info_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее", callback_data="more_info")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_data[user_id] = {"history": [], "stage": 1, "emotion": None}
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_emotion_keyboard())

async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    callback_data = query.data
    emotion_text = next(e["text"] for e in EMOTIONS if e["callback"] == callback_data)
    
    user_data[user_id].update({"emotion": emotion_text, "stage": 2})
    user_data[user_id]["history"].append({"role": "user", "content": emotion_text})

    response = EMOTION_RESPONSES.get(callback_data, "Расскажи подробнее, что чувствуешь? 😊")
    user_data[user_id]["history"].append({"role": "assistant", "content": response})

    await query.edit_message_text(response)
    await query.answer()

async def send_long_message(chat_id, text, context, reply_markup=None):
    MAX_LENGTH = 4096
    parts = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
    for part in parts[:-1]:
        await context.bot.send_message(chat_id, part)
        await asyncio.sleep(0.3)
    await context.bot.send_message(chat_id, parts[-1], reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_input = update.message.text

    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    state["history"].append({"role": "user", "content": user_input})
    stage = state["stage"]

    thinking_msg = await update.message.reply_text("Слушаю внимательно... 🌿")

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            timeout=15
        )
        response = completion.choices[0].message.content

        if stage < 5:
            state["stage"] += 1
            reply_markup = None
        else:
            reply_markup = create_more_info_keyboard()

        state["history"].append({"role": "assistant", "content": response})

    except Exception as e:
        response = "Ой, что-то пошло не так... Можешь повторить? 😅"
        print(f"Ошибка: {e}")
        reply_markup = None

    finally:
        await context.bot.delete_message(user_id, thinking_msg.message_id)

    await send_long_message(user_id, response, context, reply_markup)

async def handle_more_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "В моей платной версии мы сможем глубже разобраться с твоими эмоциями и найти путь к внутренней гармонии 🌟\n\n"
        "Напиши мне, если захочешь узнать условия! 🌿"
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    app.add_handler(CallbackQueryHandler(handle_more_info, pattern="^more_info$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен! 🚀")
    app.run_polling()
