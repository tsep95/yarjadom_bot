import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

user_data = {}

SYSTEM_PROMPT = """Твой текущий промт (без изменений)"""

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

# Обновлённые эмоции на кнопках
EMOTIONS = [
    {"text": "Не могу расслабиться, жду плохого 🌀", "callback": "anxiety"},
    {"text": "Нет сил, хочется просто лежать 🛌", "callback": "apathy"},
    {"text": "Всё раздражает, взрываюсь из-за мелочей 😠", "callback": "anger"},
    {"text": "Чувствую себя лишним, не таким 🌧", "callback": "self_doubt"},
    {"text": "Внутри пусто, нет смысла 🌌", "callback": "emptiness"},
    {"text": "Одиноко даже среди людей 🌑", "callback": "loneliness"},
    {"text": "Кажется, всё испортил, виню себя 💔", "callback": "guilt"},
    {"text": "Не могу выбрать, запутался 🤯", "callback": "indecision"}
]

EMOTION_RESPONSES = {
    "anxiety": "Напряжение висит в воздухе 🌪️. Что занимает твои мысли сейчас? 🌟",
    "apathy": "Сил совсем нет 🌫️. Что не отпускает тебя сейчас? 😔",
    "anger": "Злость прямо зашкаливает 🔥. Что особенно задевает тебя? 💢",
    "self_doubt": "Ощущение, что не на своём месте 🌧️. О чём думаешь чаще всего? 🧐",
    "emptiness": "Пустота кажется бескрайней 🌌. Что тебя беспокоит глубже всего? 😞",
    "loneliness": "Одиночество внутри, даже среди людей 🌑. Что сильнее всего тревожит тебя сейчас? 🌫️",
    "guilt": "Вина сильно давит 💔. Из-за чего ты чувствуешь это особенно остро? 😞",
    "indecision": "Трудно принять решение 🤯. Что особенно запутывает сейчас? 💬"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим 🌿", callback_data="start_talk")]])

def create_more_info_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее", callback_data="more_info")]])

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
    callback_data = query.data
    
    emotion = next((e for e in EMOTIONS if e["callback"] == callback_data), None)
    if emotion:
        full_emotion = emotion["text"]
        user_data[user_id]["stage"] = 2
        user_data[user_id]["dominant_emotion"] = full_emotion
        user_data[user_id]["history"].append({"role": "user", "content": full_emotion})
        response = EMOTION_RESPONSES.get(callback_data, "Расскажи подробнее, что чувствуешь?")
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

async def send_long_message(chat_id, text, context, reply_markup=None):
    MAX_LENGTH = 4096
    parts = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
    for part in parts[:-1]:
        await context.bot.send_message(chat_id, part)
        await asyncio.sleep(0.3)
    await context.bot.send_message(chat_id, parts[-1], reply_markup=reply_markup)

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
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.6,
            timeout=15
        )
        response = completion.choices[0].message.content

        reply_markup = None
        if stage < 5:
            state["stage"] += 1
        else:
            reply_markup = create_more_info_keyboard()

        state["history"].append({"role": "assistant", "content": response})

    except Exception as e:
        print(f"Ошибка: {e}")
        response = "Что-то пошло не так... Давай попробуем ещё раз?"

    finally:
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)

    await send_long_message(user_id, response, context, reply_markup)

async def handle_more_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Платная версия поможет глубже понять себя и найти внутреннюю гармонию 🌟.\n\n"
        "Если интересно узнать подробности, напиши мне! 💛"
    )

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(CallbackQueryHandler(handle_more_info, pattern="^more_info$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен!")
    application.run_polling()
