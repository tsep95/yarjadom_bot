import os
from typing import Dict, Tuple, Optional
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

user_data: Dict[int, dict] = {}

SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога в мире и заботливого собеседника. 
Твоя задача — задавать пользователю вопросы о его состоянии и о том, что его беспокоит, 
чтобы глубоко и точно понять причину его чувств и эмоций — будь то что-то из известного списка или нечто уникальное.

Особые инструкции:
• Задавай вопросы по одному за раз, ожидая ответа перед следующим. 
  Минимально задай 5 вопросов, чтобы собрать достаточно информации, даже если причина кажется ясной раньше. 
  После 5 вопросов продолжай диалог, если глубинная причина (на уровне чувств и эмоций) ещё не полностью раскрыта.
• Каждый вопрос должен быть длиной 3-4 предложения, конкретным, тёплым и с искренним интересом, 
  чтобы раскрыть глубину (например, "Ого, а что именно в этой ситуации заставляет тебя чувствовать себя виноватым?\n\nНе отпускает какой-то момент?\n\nМожет, есть что-то, что ты хотел бы изменить?"). 
  Разделяй предложения двойным символом новой строки (\n\n) для удобства чтения. 
  Не используй короткие или общие вопросы вроде "Что тебя тревожит?".
• Добавляй 1-3 эмодзи в каждый вопрос для тепла и поддержки, 
  выбирая их в зависимости от контекста ответа (например, 🌧️ и 😔 для грусти, 🌟 и 🤗 для надежды, 💔 и 😞 для боли). 
  Подбирай эмодзи так, чтобы они усиливали эмоциональный тон вопроса и показывали твою вовлечённость.
• Если пользователь отвечает уклончиво (например, "Не знаю", "Всё нормально"), 
  мягко переформулируй вопрос или предложи копнуть в другом направлении, сохраняя тёплый тон 
  (например, "Хм, а что тогда, как тебе кажется, всё-таки цепляет внутри?\n\nМожет, что-то в мыслях незаметно давит?").
• Обращай внимание на ключевые слова, повторяющиеся темы и эмоциональные оттенки в ответах. 
  Завершай вопросы пустым ответом ("") только тогда, когда ты уверен, что понял глубинную причину на уровне чувств и эмоций 
  (например, после 5+ вопросов, когда эмоции и их источник стали ясны).
• Не ограничивайся известными причинами — будь готов увидеть что-то уникальное в ответах пользователя.
• Не предлагай решений в процессе вопросов и не добавляй фразы вроде "Ты можешь остановиться" или "Продолжим позже" — 
  просто задавай вопросы, пока не поймёшь причину.
• Не генерируй заключение здесь — только вопросы или пустой ответ (""), когда причина ясна. 
  Заключение сформирует код после твоего пустого ответа.
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

def analyze_responses(history: list[dict]) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
    user_responses = [msg["content"].lower() for msg in history if msg["role"] == "user"]
    
    # Если меньше 5 ответов, продолжаем задавать вопросы
    if len(user_responses) < 5:
        return None, None
    
    # Ключевые слова и соответствующие причины
    keywords = {
        "чувство одиночества и ненужности": ["один", "брошен", "никому не нужен", "друзья", "молчат", "пустота"],
        "подавленные эмоции": ["не могу", "не получается", "тяжело", "давит"],
        "внутренний конфликт": ["выбор", "конфликт", "не знаю что", "между"],
        "страх неудачи": ["боюсь", "не получится", "ошибка", "провал"],
        "потеря смысла": ["бессмысленно", "зачем", "пусто", "нет цели"]
    }
    
    # Методы терапии
    therapy_methods = {
        "чувство одиночества и ненужности": ("гештальт-терапии", "она помогает прожить эмоции и восстановить связь с собой и другими"),
        "подавленные эмоции": ("когнитивно-поведенческой терапии", "она помогает осознать и изменить негативные мыслительные паттерны"),
        "внутренний конфликт": ("гештальт-терапии", "она помогает завершить незакрытые ситуации и прожить подавленные эмоции"),
        "страх неудачи": ("когнитивно-поведенческой терапии", "она помогает перестроить мышление и справиться с тревогой"),
        "потеря смысла": ("арт-терапии", "она помогает выразить подавленные эмоции через творчество и найти новые ориентиры")
    }
    
    # Подсчёт веса причин
    causes = {}
    for response in user_responses:
        for cause, words in keywords.items():
            weight = sum(1 for word in words if word in response)
            if cause in causes:
                causes[cause] += weight
            else:
                causes[cause] = weight
    
    # Если есть явная причина
    if causes and max(causes.values()) > 0:
        top_cause = max(causes, key=causes.get)
        if causes[top_cause] >= 3 or len(user_responses) >= 6:  # Условие ясности (6 вопросов как в примере)
            return top_cause, therapy_methods.get(top_cause, ("разговорах с близким человеком или специалистом", "это помогает мягко разобраться в своих чувствах"))
    
    # Если причина не ясна после 6+ ответов
    if len(user_responses) >= 6:
        return ("что-то, что пока трудно назвать", ("разговорах с понимающим человеком или специалистом", "это помогает постепенно раскрыть, что тебя волнует"))
    
    return None, None

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
    "anxiety": "Напряжение кружит, как вихрь 🌀.\n\nЧто сейчас занимает твои мысли больше всего?\n\nМожет, есть что-то, что не отпускает? 🌟",
    "apathy": "Сил нет, будто всё замерло 🛌.\n\nЧто не отпускает тебя прямо сейчас?\n\nЕсть что-то, что тянет вниз? 😔",
    "anger": "Злость вспыхивает, как огонь 😠.\n\nЧто тревожит тебя больше всего?\n\nМожет, какой-то момент особенно цепляет? 💢",
    "self_doubt": "Ощущение, будто ты вне потока 🌧.\n\nЧто занимает твои мысли сейчас?\n\nЕсть что-то, что заставляет сомневаться? 🧐",
    "emptiness": "Пустота гудит внутри 🌌.\n\nКогда ты это сильнее всего ощущаешь?\n\nМожет, что-то её вызывает? 😞",
    "loneliness": "Одиночество давит даже в толпе 🌑.\n\nЧто тревожит тебя больше всего?\n\nЕсть что-то, что хочется изменить? 💭",
    "guilt": "Вина тянет вниз, как груз 💔.\n\nЧто занимает твои мысли сейчас?\n\nМожет, какой-то момент не отпускает? 😞",
    "indecision": "Смятение запутывает всё 🤯.\n\nЧто занимает твои мысли больше всего?\n\nЕсть что-то, что мешает выбрать? 💬"
}

SUBSCRIBE_URL = "https://example.com/subscribe"  # Замените на реальную ссылку

def create_emotion_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

def create_subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Оплатить подписку 💳", url=SUBSCRIBE_URL)]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "stage": 1,
        "dominant_emotion": None
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        user_data[user_id]["stage"] = 2
        await query.edit_message_text(response, reply_markup=create_emotion_keyboard())
        await query.answer()

async def handle_more_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def send_long_message(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + MAX_LENGTH])
        await asyncio.sleep(0.3)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        
        # Если это вопрос, отправляем его
        if response.strip().endswith("?"):
            state["history"].append({"role": "assistant", "content": response})
            state["stage"] += 1
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, response, context)
        
        # Если пустой ответ, анализируем и выдаём финальное сообщение
        elif not response.strip():
            cause, therapy = analyze_responses(state["history"])
            if cause and therapy:
                final_response = FINAL_MESSAGE.format(cause=cause, method=therapy[0], reason=therapy[1])
                state["stage"] += 1
                final_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее 🌼", callback_data="more_info")]])
                await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
                await context.bot.send_message(chat_id=user_id, text=final_response, reply_markup=final_keyboard)
                logger.info(f"User {user_id} reached final stage with cause: {cause}")
            else:
                # Если причина не ясна, задаём ещё один вопрос
                fallback_question = (
                    "Хм, похоже, мы ещё не до конца разобрались с тем, что внутри 🌱.\n\n"
                    "Что сейчас больше всего занимает твои мысли или чувства?\n\n"
                    "Может, есть что-то, что ты хотел бы добавить? 🤗"
                )
                state["history"].append({"role": "assistant", "content": fallback_question})
                state["stage"] += 1
                await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
                await send_long_message(user_id, fallback_question, context)
        
        # Если ответ не вопрос и не пустой, это ошибка — задаём запасной вопрос
        else:
            fallback_question = (
                "Хм, похоже, мы ещё не до конца разобрались с тем, что внутри 🌱.\n\n"
                "Что сейчас больше всего занимает твои мысли или чувства?\n\n"
                "Может, есть что-то, что ты хотел бы добавить? 🤗"
            )
            state["history"].append({"role": "assistant", "content": fallback_question})
            state["stage"] += 1
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, fallback_question, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message для user_id {user_id}: {str(e)}")
        response = "Что-то пошло не так... Давай попробуем ещё раз? 🌿"
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
