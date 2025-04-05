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

SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога в мире и заботливого собеседника. Твоя задача — задавать пользователю вопросы о его состоянии и о том, что его беспокоит, чтобы за 5 шагов помочь ему осознать глубинную причину беспокойства. Начинай с открытого вопроса о текущем состоянии, а затем углубляйся, опираясь на каждый ответ, чтобы докопаться до сути.

Особые инструкции:
• Задавай ровно 5 вопросов, по одному за раз, ожидая ответа перед следующим.
• Каждый вопрос — чуть длиннее (3-4 предложения), конкретный, тёплый и с искренним интересом, чтобы раскрыть глубину (например, "Ого, а что именно в этой ситуации заставляет тебя чувствовать себя виноватым? Не отпускает какой-то момент?" вместо "Что не даёт покоя?").
• Используй эмодзи умеренно для поддержки и тепла.
• Не предлагай решений в процессе вопросов — только помогай пользователю копнуть глубже.
• Примеры вопросов для вдохновения:
  1. "Что сейчас занимает твои мысли больше всего? Какое чувство не отпускает, когда ты думаешь о том, что тебя беспокоит? 🌟"
  2. "Ого, а в какие моменты это чувство становится особенно сильным? Что происходит вокруг или внутри тебя в эти минуты? 😮"
  3. "Слушай, а что именно в этой ситуации держит тебя сильнее всего? Может, есть что-то, что ты хотел бы изменить, но не можешь? 🧐"
  4. "Интересно, если бы одна вещь могла облегчить это состояние, что бы это было? Что мешает тебе её получить или сделать? 🌈"
  5. "Подумай, с чего это чувство вообще взялось — может, есть какой-то момент в прошлом, который до сих пор отдаётся в тебе? 💭"
• После пятого вопроса дай заключение в формате: "Ты здорово разобрался в себе! 🌟 Тебе бы отлично помог [метод], есть моя платная версия — она поможет!" — где [метод] — подходящий метод психотерапии, основанный на ответах.
• Не предлагай продолжать общение после заключения и не добавляй фразы вроде "Возвращайся, если что" или "Давай ещё поболтаем".
• Если пользователь уклоняется, мягко возвращай его к теме с любопытством (например, "Хм, а как это связано с тем, что ты чувствуешь внутри?").

Методы психотерапии для заключения (выбирай по проблеме):
- Когнитивно-поведенческая терапия: для негативных мыслей и убеждений.
- Психоанализ: для глубоких скрытых причин и конфликтов.
- Гештальт-терапия: для непрожитых эмоций и завершения ситуаций.
- Психодрама: для выражения прошлого и травм.
- Арт-терапия: для подавленных эмоций через творчество.
- Телесная терапия: для снятия стресса через тело.
- Клиент-центрированная терапия: для поиска внутреннего баланса.
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

# Список эмоций с короткими callback_data
EMOTIONS = [
    {"text": "Я не могу расслабиться, жду плохого.", "callback": "anxiety"},
    {"text": "Мне ничего не хочется, просто лежать.", "callback": "apathy"},
    {"text": "Меня всё бесит, взрываюсь по мелочам.", "callback": "anger"},
    {"text": "Я не такой, сломанный, не вписываюсь.", "callback": "self_doubt"},
    {"text": "Нет смысла, внутри пусто.", "callback": "emptiness"},
    {"text": "Я один, даже среди людей.", "callback": "loneliness"},
    {"text": "Я всё испортил, это моя вина.", "callback": "guilt"},
    {"text": "Не могу определиться.", "callback": "indecision"}
]

# Реакции на выбор эмоций
EMOTION_RESPONSES = {
    "anxiety": "Напряжение висит в воздухе 🌪️. Что занимает твои мысли? 🌟",
    "apathy": "Сил нет даже на простое 🌫️. Что не отпускает тебя? 😔",
    "anger": "Злость как вулкан 🔥. Что тревожит больше всего? 💢",
    "self_doubt": "Ощущение, что ты не на месте 😔. Что занимает мысли? 🧐",
    "emptiness": "Пустота как эхо 🌌. Что не отпускает тебя сейчас? 😞",
    "loneliness": "Одиночество внутри, несмотря на шум 💭. Что тревожит? 🌫️",
    "guilt": "Вина давит как камень 💔. Что занимает твои мысли? 😞",
    "indecision": "Всё мутно, сложно выбрать 🤔. Что занимает мысли? 💬"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

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
    callback_data = query.data
    
    # Находим полное описание эмоции по callback_data
    emotion = next((e for e in EMOTIONS if e["callback"] == callback_data), None)
    if emotion:
        full_emotion = emotion["text"]
        user_data[user_id]["stage"] = 2
        user_data[user_id]["dominant_emotion"] = full_emotion
        user_data[user_id]["history"].append({"role": "user", "content": full_emotion})
        response = EMOTION_RESPONSES.get(callback_data, "Расскажи мне подробнее, что ты чувствуешь?")
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
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.6,
            timeout=15
        )
        response = completion.choices[0].message.content
        
        if stage < 5:
            state["stage"] += 1
        state["history"].append({"role": "assistant", "content": response})
        
    except Exception as e:
        print(f"Ошибка в handle_message: {e}")
        response = "Что-то пошло не так... Давай попробуем ещё раз?"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    await send_long_message(user_id, response, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
