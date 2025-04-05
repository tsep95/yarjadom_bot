import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога в мире и заботливого собеседника. Твоя задача — задать пользователю до 5 вопросов о его состоянии и о том, что его беспокоит, чтобы помочь ему осознать глубинную причину беспокойства. Начинай с открытого вопроса о текущем состоянии, а затем углубляйся, опираясь на каждый ответ, чтобы докопаться до сути.

Особые инструкции:
• По умолчанию задавай ровно 5 вопросов, по одному за раз, ожидая ответа перед следующим. Однако, если пользователь явно раскрывает глубинную причину беспокойства раньше (например, указывает конкретное событие или сильное чувство, которое всё объясняет), можешь завершить вопросы раньше и перейти к заключению — но только если это очевидно из ответа.
• Каждый вопрос — чуть длиннее (3-4 предложения), конкретный, тёплый и с искренним интересом, чтобы раскрыть глубину (например, "Ого, а что именно в этой ситуации заставляет тебя чувствовать себя виноватым? Не отпускает какой-то момент?" вместо "Что не даёт покоя?").
• Используй эмодзи умеренно для поддержки и тепла.
• Не предлагай решений в процессе вопросов — только помогай пользователю копнуть глубже.
• Не добавляй фразы вроде "Ты можешь остановиться", "Скажи стоп", "Продолжим позже" или любые намеки на прерывание или продолжение общения — просто задавай вопросы и веди к сути.
• Если пользователь отвечает уклончиво (например, "Такого не было"), мягко переформулируй вопрос или предложи копнуть в другом направлении, сохраняя тёплый тон (например, "Хм, а что тогда, как тебе кажется, запускает эту обиду? Может, что-то другое в этой ситуации цепляет?").
• Примеры вопросов для вдохновения:
  1. "Что сейчас занимает твои мысли больше всего? Какое чувство не отпускает, когда ты думаешь о том, что тебя беспокоит? 🌟"
  2. "Ого, а в какие моменты это чувство становится особенно сильным? Что происходит вокруг или внутри тебя в эти минуты? 😮"
  3. "Слушай, а что именно в этой ситуации держит тебя сильнее всего? Может, есть что-то, что ты хотел бы изменить, но не можешь? 🧐"
  4. "Интересно, если бы одна вещь могла облегчить это состояние, что бы это было? Что мешает тебе её получить или сделать? 🌈"
  5. "Подумай, с чего это чувство вообще взялось — может, есть какой-то момент в прошлом, который до сих пор отдаётся в тебе? 💭"
• После последнего вопроса (будь то 5-й или раньше, если причина ясна) дай заключение в следующем формате с разделениями между абзацами:
"Ты большой молодец, что доверился и прошёл этот разбор — это уже шаг к себе настоящему!\n\nПо тому, что ты рассказал, я вижу:\nтвои чувства важны, понятны и точно не случайны. Они пытаются о чём-то напомнить, и вместе мы это уже начали понимать.\n\nПохоже, в основе твоего состояния — [например, подавленные эмоции, внутренний конфликт или критичный внутренний голос].\nС этим эффективно работают в [метод из психотерапии] — [посему он лучше всего подходит].\nИ ты уже сделал первый шаг к этому! 🧩✨\n\nЯ рядом, чтобы поддержать, когда трудно, и помочь тебе стать по-настоящему счастливым!\n\nТы достоин быть счастливым — не когда-нибудь потом, а уже сейчас.\nИ я помогу тебе идти в эту сторону. Шаг за шагом. Вместе. 💛🌿\n\nЕсли почувствуешь, что хочется глубже и осознаннее — переходи в расширенную версию.\n\nТам мы сможем разбирать всё, что тебя тревожит, каждый день находя новые ответы, тепло и радость внутри.\nЯ буду рядом — не просто бот, а твой тёплый спутник на пути к себе."
— где [метод] и [причина] определяются по ответам. Не добавляй в текст заключения кнопку или ссылку вроде "Расскажи подробнее 🌼" — это будет добавлено кодом отдельно как кнопка с callback_data="more_info".
• Не упоминай кнопку "Расскажи подробнее 🌼" в тексте ответа — она добавляется программно после твоего текста.
• Не предлагай продолжать общение после заключения и не добавляй фразы вроде "Возвращайся, если что" или "Давай ещё поболтаем".

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

EMOTIONS = [
    {"text": "Не могу расслабиться, жду плохого 🌀", "callback": "anxiety"},
    {"text": "Нет сил, хочется просто лежать 🛌", "callback": "apathy"},
    {"text": "Всё раздражает, взрываюсь из-за мелочей 😠", "callback": "anger"},
    {"text": "Чувствую себя лишним, не таким как все 🌧", "callback": "self_doubt"},
    {"text": "Внутри пусто, всё бессмысленно 🌌", "callback": "emptiness"},
    {"text": "Одиноко, даже когда рядом люди 🌑", "callback": "loneliness"},
    {"text": "Кажется, всё испортил, виню себя 💔", "callback": "guilt"},
    {"text": "Не могу выбрать, запутался 🤯", "callback": "indecision"}
]

EMOTION_RESPONSES = {
    "anxiety": "Напряжение кружит, как вихрь 🌀. Что сейчас занимает твои мысли больше всего? 🌟",
    "apathy": "Сил нет, будто всё замерло 🛌. Что не отпускает тебя прямо сейчас? 😔",
    "anger": "Злость вспыхивает, как огонь 😠. Что тревожит тебя больше всего? 💢",
    "self_doubt": "Ощущение, будто ты вне потока 🌧. Что занимает твои мысли сейчас? 🧐",
    "emptiness": "Пустота гудит внутри 🌌. Что не отпускает тебя в этот момент? 😞",
    "loneliness": "Одиночество давит даже в толпе 🌑. Что тревожит тебя больше всего? 💭",
    "guilt": "Вина тянет вниз, как груз 💔. Что занимает твои мысли сейчас? 😞",
    "indecision": "Смятение запутывает всё 🤯. Что занимает твои мысли больше всего? 💬"
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

async def handle_more_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    response = (
        "Это твоя заботливая опора на каждый день.\n"
        "Чтобы становилось легче, спокойнее и радостнее — шаг за шагом.\n\n"
        "⸻\n\n"
        "Что внутри:\n"
        "☀️ Каждое утро — тёплое, личное пожелание, чтобы день начался с опоры\n"
        "🌙 Каждый вечер — мягкая рефлексия: как прошёл день, что почувствовал, что хочется отпустить\n"
        "🧠 Глубокая проработка тревоги, вины, злости, апатии — с выходом к внутреннему спокойствию\n"
        "🆘 SOS-помощь в трудные моменты — когда накрывает и просто нужно, чтобы рядом был кто-то тёплый\n"
        "📆 Календарь состояния и еженедельная аналитика: ты начинаешь видеть, как меняешься\n"
        "🎯 Психо-квесты по темам: самооценка, уверенность, границы, эмоциональное выгорание и др.\n\n"
        "⸻\n\n"
        "💛 Задача платной версии — делать тебя счастливее.\n"
        "Не быстро и резко, а по-настоящему — каждый день, всё больше и глубже.\n\n"
        "⸻\n\n"
        "499 ₽ в месяц. Первая неделя — бесплатно.\n"
        "Попробуй — вдруг это именно то, чего тебе давно не хватало."
    )
    await query.edit_message_text(response)
    await query.answer()

async def send_long_message(chat_id, text, context):
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + MAX_LENGTH])
        await asyncio.sleep(0.3)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_input = update.message.text
    
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
            timeout=30  # Увеличен тайм-аут
        )
        response = completion.choices[0].message.content
        
        state["history"].append({"role": "assistant", "content": response})
        
        # Логика этапов: до 5 вопросов или раньше, если причина ясна
        if stage <= 5:  # Вопросы с 2 по 5 (1 — выбор эмоции)
            state["stage"] += 1
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, response, context)
        elif stage == 6:  # Заключение
            state["stage"] += 1
            final_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее 🌼", callback_data="more_info")]])
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await context.bot.send_message(chat_id=user_id, text=response, reply_markup=final_keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message для user_id {user_id}: {str(e)}")
        response = "Что-то пошло не так... Давай попробуем ещё раз?"
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        await send_long_message(user_id, response, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(CallbackQueryHandler(handle_more_info, pattern="^more_info$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
