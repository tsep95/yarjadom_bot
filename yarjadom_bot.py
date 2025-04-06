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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")  # Замените на свой Telegram-токен
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"  # Ваш ключ DeepSeek API

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

# Инициализация клиента OpenAI для DeepSeek API
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Хранилище данных пользователей
user_data: Dict[int, dict] = {}

# Системный промпт
SYSTEM_PROMPT = """
Ты — чат-бот в Telegram, созданный для роли самого лучшего психолога в мире и заботливого собеседника. 
Твоя задача — задавать пользователю вопросы о его состоянии и о том, что его беспокоит, 
чтобы глубоко и точно понять причину его чувств и эмоций — будь то что-то из известного списка или нечто уникальное.

Особые инструкции:
• Задавай вопросы по одному за раз, ожидая ответа перед следующим. 
  Задай минимум 3 и максимум 12 вопросов, чтобы понять глубинные чувства и эмоции пользователя. 
  После 3 вопросов оценивай, достаточно ли информации: если причина ясна — заверши пустым ответом (""), если нет — продолжай до 12.
• Каждый вопрос — 3-4 предложения, конкретный, тёплый и с искренним интересом, 
  чтобы раскрыть глубину (например, "Ого, а что именно в этой ситуации заставляет тебя чувствовать себя виноватым?\n\nНе отпускает какой-то момент?\n\nМожет, есть что-то, что ты хотел бы изменить?"). 
  Разделяй предложения двойным символом новой строки (\n\n) для удобства чтения. 
  Избегай коротких или общих вопросов вроде "Что тебя тревожит?".
• Используй яркие и неожиданные эмодзи (не больше 3 в вопросе), миксуй их хаотично и креативно: от 🐾 до 🌈, от 🚀 до 🍉, чтобы удивить и поддержать пользователя.  
  Избегай однообразия — пусть смайлики добавляют живости и тепла (например, 🌟🐙, 🍓💥, 🚪✨)!
• Если пользователь отвечает уклончиво ("Не знаю", "Всё нормально"), 
  мягко переформулируй или предложи копнуть глубже (например, "Хм, а что тогда всё-таки цепляет внутри?\n\nМожет, что-то незаметно давит?").
• Обращай внимание на ключевые слова, повторяющиеся темы и эмоции в ответах. 
  После 3+ вопросов, если причина ясна на уровне чувств и эмоций, заверши пустым ответом ("").
• Не предлагай решений в процессе вопросов и не пиши "Продолжим позже" — просто задавай вопросы или завершай пустым ответом.
• Не генерируй заключение здесь — это сделает код после пустого ответа.
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
    "Если почувствуешь, что хочется глубже и осознаннее — "
    "переходи в расширенную версию 🚀.\n\n"
    "Там мы сможем разбирать всё, что тебя тревожит, "
    "каждый день находя новые ответы, тепло и радость внутри 🌞. "
    "Я буду рядом — не просто бот, а твой тёплый спутник на пути к себе 🌈."
)

# Функция анализа ответов с расширенными ключевыми словами
def analyze_responses(history: list[dict]) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
    user_responses = [msg["content"].lower() for msg in history if msg["role"] == "user"]
    combined_text = " ".join(user_responses)
    
    # Базовый список методов терапии
    default_therapy_methods = {
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
    
    # Расширенный список ключевых слов
    keywords = {
        "подавленные эмоции": ["не могу", "не получается", "тяжело", "давит"],
        "внутренний конфликт": ["выбор", "конфликт", "не знаю что", "между"],
        "критичный внутренний голос": ["критика", "себя", "вину", "плохо о себе", "ругает", "обесценивает"],
        "страх потери": ["потеря", "связь", "уйдут", "бросили"],
        "непрожитые эмоции": ["прошлое", "было", "до сих пор", "осталось"],
        "потребность в признании": ["признание", "хвалит", "не видят", "ценят", "не ценят", "тёплое", "ответственный", "хорошо"],
        "чувство одиночества": ["одиноко", "никого", "в толпе", "нет рядом"],
        "эмоциональное выгорание": ["устал", "нет сил", "всё равно", "выгорел"],
        "страх неудачи": ["боюсь", "не получится", "ошибка", "провал"],
        "потеря смысла": ["бессмысленно", "зачем", "пусто", "нет цели"]
    }
    
    causes = {}
    for response in user_responses:
        for cause, words in keywords.items():
            weight = sum(1 for word in words if word in response)
            if cause in causes:
                causes[cause] += weight
            else:
                causes[cause] = weight
    
    num_responses = len(user_responses)
    
    # Если меньше 3 ответов — продолжаем
    if num_responses < 3:
        return None, None
    
    # Если 3+ ответов и есть хоть одна причина
    if num_responses >= 3 and causes and max(causes.values()) > 0:
        top_cause = max(causes, key=causes.get)
        return top_cause, default_therapy_methods.get(top_cause, ("разговорах с близким человеком или специалистом", "это помогает мягко разобраться в своих чувствах"))
    
    # Динамическая причина
    if "боли" in combined_text or "грусть" in combined_text or "тоска" in combined_text:
        cause = "глубокая внутренняя боль"
        method = "терапии принятия и осознанности"
        reason = "она помогает мягко прожить эмоции и найти покой внутри"
    elif "тревога" in combined_text or "страх" in combined_text or "беспокойство" in combined_text:
        cause = "скрытая тревога"
        method = "когнитивно-поведенческой терапии"
        reason = "она помогает справиться с беспокойством и вернуть контроль"
    elif "радость" in combined_text or "счастье" in combined_text:
        cause = "поиск внутренней гармонии"
        method = "практиках осознанности"
        reason = "они помогают усилить позитивные чувства и сохранить баланс"
    else:
        if num_responses >= 12:  # Завершаем после 12 ответов
            cause = "что-то, что пока трудно назвать"
            method = "разговорах с понимающим человеком или специалистом"
            reason = "это помогает постепенно раскрыть, что тебя волнует"
            return cause, (method, reason)
        return None, None
    
    return cause, (method, reason)

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
    {"text": "Не могу расслабиться, жду плохого 🌀", "callback": "anxiety"},
    {"text": "Нет сил, хочется просто лежать 🛌", "callback": "apathy"},
    {"text": "Всё раздражает, взрываюсь из-за мелочей 😠", "callback": "anger"},
    {"text": "Чувствую себя лишним, не таким как все 🌧", "callback": "self_doubt"},
    {"text": "Внутри пусто, всё бессмысленно 🌌", "callback": "emptiness"},
    {"text": "Одиноко, даже когда рядом люди 🌑", "callback": "loneliness"},
    {"text": "Кажется, всё испортил, виню себя 💔", "callback": "guilt"},
    {"text": "Не могу выбрать, запутался 🤯", "callback": "indecision"}
]

# Ответы на выбор эмоций
EMOTION_RESPONSES = {
    "anxiety": "Напряжение кружит, как вихрь 🌀.\n\nЧто сейчас занимает твои мысли больше всего?\n\nЕсть что-то, что не отпускает? 🌟",
    "apathy": "Сил нет, будто всё замерло 🛌.\n\nЧто последнее время забирает твою энергию?\n\nМожет, что-то давит незаметно? 😔",
    "anger": "Злость вспыхивает, как огонь 😠.\n\nЧто именно выводит тебя из себя?\n\nЕсть момент, который особенно цепляет? 💢",
    "self_doubt": "Ощущение, будто ты вне потока 🌧.\n\nЧто заставляет тебя чувствовать себя не таким, как другие?\n\nМожет, что-то внутри подсказывает иначе? 🧐",
    "emptiness": "Пустота гудит внутри 🌌.\n\nКогда ты начал это замечать?\n\nЧто-то ушло из твоей жизни недавно? 😞",
    "loneliness": "Одиночество давит даже в толпе 🌑.\n\nЧто тебе сейчас больше всего не хватает рядом?\n\nМожет, есть что-то, чего ты давно ждёшь? 💭",
    "guilt": "Вина тянет вниз, как груз 💔.\n\nЧто именно ты себе не можешь простить?\n\nЕсть момент, который хочется переиграть? 😞",
    "indecision": "Смятение запутывает всё 🤯.\n\nЧто именно делает выбор таким сложным?\n\nМожет, что-то внутри подсказывает, но ты сомневаешься? 💬"
}

SUBSCRIBE_URL = "https://example.com/subscribe"

# Функции создания клавиатур
def create_emotion_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

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
        response = EMOTION_RESPONSES.get(callback_data, "Расскажи мне подробнее, что ты чувствуешь? 🌿")
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
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        logger.info(f"User {user_id} at question {state['question_count']}")
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            timeout=30
        )
        response = completion.choices[0].message.content
        
        if response.strip() == "" or state["question_count"] >= 12:
            cause, therapy = analyze_responses(state["history"])
            if cause and therapy:
                final_response = FINAL_MESSAGE.format(cause=cause, method=therapy[0], reason=therapy[1])
                final_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Расскажи подробнее 🌼", callback_data="more_info")]])
                await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
                await context.bot.send_message(chat_id=user_id, text=final_response, reply_markup=final_keyboard)
                logger.info(f"User {user_id} reached final stage with cause: {cause}")
            else:
                # Запасной вопрос, если причина не ясна
                fallback_question = (
                    "Кажется, мы ещё чуть-чуть не дошли до сути 🌱.\n\n"
                    "Что сейчас крутится у тебя в голове или давит на сердце?\n\n"
                    "Может, есть что-то ещё, что хочется сказать? 🤗✨"
                )
                state["history"].append({"role": "assistant", "content": fallback_question})
                state["question_count"] += 1
                await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
                await send_long_message(user_id, fallback_question, context)
        else:
            state["history"].append({"role": "assistant", "content": response})
            state["question_count"] += 1
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, response, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message для user_id {user_id}: {str(e)}")
        response = "Что-то пошло не так... Давай попробуем ещё раз? 🌿"
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
