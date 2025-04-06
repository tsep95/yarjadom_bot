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
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога в мире и заботливого собеседника. 
Твоя задача — задавать пользователю вопросы о его состоянии и о том, что его беспокоит, 
чтобы постепенно раскрыть глубинную причину его чувств. 
Начинай с открытого вопроса о текущем состоянии, а затем продолжай углубляться, опираясь на каждый ответ, 
пока не станет ясно, что лежит в основе его переживаний.

Особые инструкции:
• Задавай вопросы по одному за раз, ожидая ответа перед следующим. 
  Продолжай задавать вопросы, пока не соберёшь достаточно информации, 
  чтобы понять глубинную причину состояния пользователя (например, подавленные эмоции, страх неудачи, чувство одиночества и т.д.). 
  Не ограничивайся заранее заданным числом вопросов — иди до конца.
• Каждый вопрос должен быть длиной 3-4 предложения, конкретным, тёплым и с искренним интересом, 
  чтобы раскрыть глубину (например, "Ого, а что именно в этой ситуации заставляет тебя чувствовать себя виноватым?\n\nНе отпускает какой-то момент?\n\nМожет, есть что-то, что ты хотел бы изменить?"). 
  Разделяй предложения на строки с помощью двойного символа новой строки (\n\n), чтобы между ними был пробел в виде пустой строки для удобства чтения. 
  Не используй короткие или общие вопросы вроде "Что тебя тревожит?".
• Добавляй 1-3 эмодзи в каждый вопрос для тепла и поддержки, 
  выбирая их в зависимости от контекста ответа пользователя (например, 🌧️ и 😔 для грусти, 🌟 и 🤗 для надежды, 💔 и 😞 для боли). 
  Подбирай эмодзи так, чтобы они усиливали эмоциональный тон вопроса и показывали твою вовлечённость.
• Если пользователь отвечает уклончиво (например, "Не знаю", "Всё нормально" или "Да, так и есть"), 
  мягко переформулируй вопрос или предложи копнуть в другом направлении, сохраняя тёплый тон 
  (например, "Хм, а что тогда, как тебе кажется, всё-таки цепляет внутри?\n\nМожет, что-то в мыслях или вокруг незаметно давит?").
• Не предлагай решений в процессе вопросов и не добавляй фразы вроде "Ты можешь остановиться", "Скажи стоп" или "Продолжим позже" — 
  просто продолжай задавать вопросы, пока не станет ясно, что происходит.
• Определяй момент, когда причина становится понятной, на основе накопленных ответов 
  (например, если пользователь упоминает страх, вину, пустоту или конкретные ситуации, которые повторяются). 
  Как только причина ясна, больше не задавай вопросы — код сам добавит заключение.
• Не генерируй заключение здесь — только вопросы. 
  Заключение будет сформировано кодом после того, как ты решишь, что понял причину.
"""

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
    "Если почувствуешь, что хочется глубже и осознаннее — "
    "переходи в расширенную версию 🚀.\n\n"
    "Там мы сможем разбирать всё, что тебя тревожит, "
    "каждый день находя новые ответы, тепло и радость внутри 🌞. "
    "Я буду рядом — не просто бот, а твой тёплый спутник на пути к себе 🌈."
)

THERAPY_METHODS = {
    "подавленные эмоции": ("когнитивно-поведенческой терапии", "она помогает осознать и изменить негативные мыслительные паттерны"),
    "внутренний конфликт": ("гештальт-терапии", "она помогает завершить незакрытые ситуации и прожить подавленные эмоции"),
    "критичный внутренний голос": ("клиент-центрированной терапии", "она помогает найти внутренний баланс и принять себя"),
    "страх потери": ("психоанализе", "он раскрывает глубокие скрытые причины и конфликты"),
    "непрожитые эмоции": ("гештальт-терапии", "она помогает завершить незакрытые ситуации и прожить подавленные эмоции"),
    "потребность в признании": ("когнитивно-поведенческой терапии", "она помогает осознать и изменить негативные мыслительные паттерны"),
    "чувство одиночества": ("гештальт-терапии", "она помогает прожить эмоции и восстановить связь с собой и другими"),
    "эмоциональное выгорание": ("телесной терапии", "она помогает снять стресс через тело и вернуть энергию"),
    "страх неудачи": ("когнитивно-поведенческой терапии", "она помогает перестроить мышление и справиться с тревогой"),
    "потеря смысла": ("арт-терапии", "она помогает выразить подавленные эмоции через творчество и найти новые ориентиры")
}

def analyze_responses(history):
    user_responses = [msg["content"].lower() for msg in history if msg["role"] == "user"]
    causes = {}
    
    keywords = {
        "подавленные эмоции": ["не могу", "не получается", "тяжело", "давит"],
        "внутренний конфликт": ["выбор", "конфликт", "не знаю что", "между"],
        "критичный внутренний голос": ["критика", "себя", "вину", "плохо о себе"],
        "страх потери": ["потеря", "связь", "уйдут", "бросили"],
        "непрожитые эмоции": ["прошлое", "было", "до сих пор", "осталось"],
        "потребность в признании": ["признание", "хвалит", "не видят", "ценят"],
        "чувство одиночества": ["одиноко", "никого", "в толпе", "нет рядом"],
        "эмоциональное выгорание": ["устал", "нет сил", "всё равно", "выгорел"],
        "страх неудачи": ["боюсь", "не получится", "ошибка", "провал"],
        "потеря смысла": ["бессмысленно", "зачем", "пусто", "нет цели"]
    }
    
    for response in user_responses:
        for cause, words in keywords.items():
            weight = sum(1 for word in words if word in response)
            if cause in causes:
                causes[cause] += weight
            else:
                causes[cause] = weight
    
    if not causes or max(causes.values()) == 0:
        return "непрожитые эмоции", THERAPY_METHODS["непрожитые эмоции"]
    
    sorted_causes = sorted(causes.items(), key=lambda x: x[1], reverse=True)
    top_cause = sorted_causes[0][0]
    
    if len(sorted_causes) > 1 and sorted_causes[0][1] - sorted_causes[1][1] <= 1:
        second_cause = sorted_causes[1][0]
        combined_cause = f"{top_cause} и {second_cause}"
        method, reason = THERAPY_METHODS[top_cause]
        return combined_cause, (method, reason)
    
    return top_cause, THERAPY_METHODS[top_cause]

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

SUBSCRIBE_URL = "https://example.com/subscribe"  # Замените на реальную ссылку для оплаты

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

def create_subscribe_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Оплатить подписку 💳", url=SUBSCRIBE_URL)]
    ])

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
    await query.edit_message_text(response, reply_markup=create_subscribe_keyboard())
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
    state["history"].append({"role": "user", "content": user_input})
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        logger.info(f"User {user_id} at stage {state['stage']}")
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.6,
            timeout=30
        )
        response = completion.choices[0].message.content
        
        # Если ответ — это вопрос, продолжаем
        if response.strip().endswith("?"):
            state["history"].append({"role": "assistant", "content": response})
            state["stage"] += 1
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, response, context)
        else:
            # Если бот решил, что причина ясна (нет вопроса), переходим к заключению
            cause, (method, reason) = analyze_responses(state["history"])
            final_response = FINAL_MESSAGE.format(cause=cause, method=method, reason=reason)
            state["stage"] += 1
            
            final_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее 🌼", callback_data="more_info")]])
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await context.bot.send_message(chat_id=user_id, text=final_response, reply_markup=final_keyboard)
            logger.info(f"User {user_id} reached final stage with button")
        
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
