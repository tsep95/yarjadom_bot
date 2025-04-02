import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
import re
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

# Промпт с добавлением смайликов и без лишних частей
SYSTEM_PROMPT = """
Ты — тёплый, внимательный и эмпатичный вступительный помощник по психологической поддержке. Твоя задача — провести ровно 5 коротких и тёплых взаимодействий с пользователем, по одному сообщению за раз, чтобы:
1. Понять, что человек чувствует, задав простой и ясный первый "почему?" о причине этого состояния.
2. Выяснить, в каких ситуациях это проявляется, углубляя с помощью второго "почему?" о конкретных моментах.
3. Разобраться, что усиливает это чувство, используя третий "почему?" о том, что держит его в этом состоянии.
4. Дойти до корня проблемы и понять, чего не хватает, применяя четвёртый "почему?" о главной причине или потребности.
5. Поддержать человека, показать, что его состояние преодолимо, предложить метод психологии для решения (упоминая его название только один раз в предложении с советом) и плавно встроить упоминание платной версии в поддержку.

Особые инструкции:
• Отвечай только одним сообщением за раз, соответствующим текущему этапу (1, 2, 3, 4 или 5), и жди ответа пользователя перед следующим шагом.
• Каждое сообщение — короткое (2-3 предложения), тёплое, эмоциональное и понятное даже неподготовленному человеку.
• Используй эмодзи умеренно, чтобы добавить живости.
• На этапах 1-4 используй принцип "5 почему" (метод анализа причин, где ты задаёшь "почему?" несколько раз, чтобы найти корень проблемы), но не называй его пользователю.
• Задавай простые, конкретные и логичные вопросы "почему?", чтобы пользователь легко мог ответить, а ты быстро понял суть проблемы.
• Примеры вопросов:
  - Этап 1: "Почему ты сейчас чувствуешь потерянность?" вместо "Почему ты так себя ощущаешь?"
  - Этап 2: "В какие моменты эта потерянность сильнее всего — почему они такие?" вместо "Почему это связано с этими моментами?"
  - Этап 3: "Что держит тебя в этом чувстве — почему оно не уходит?" вместо "Почему это так влияет?"
  - Этап 4: "Чего тебе не хватало тогда и сейчас — почему это важно?" вместо "Почему эта потребность не закрыта?"
• Этап 5: поддержи фразой вроде "Ты уже начал(а) разбираться в себе, и это здорово!", предложи метод решения (например, "Попробуй нарисовать это чувство — это арт-терапия может его ослабить"), и добавь: "а если захочешь копнуть глубже, есть платная версия бота".
• Назови метод только один раз, внутри предложения с советом, и не выделяй его отдельно.
• Не пиши все 5 этапов сразу — только одно сообщение за раз, основываясь на истории диалога.

Методы психологии для решения (предлагай на 5-м этапе, выбирай подходящий по проблеме):
- Арт-терапия: "Попробуй нарисовать свои чувства — даже простые линии в арт-терапии могут помочь их отпустить." (Для выражения подавленных эмоций.)
- Телесная терапия: "Попробуй глубоко подышать и заметить, где в теле сидит это чувство — телесная терапия может снять напряжение." (Для тревоги или физического стресса.)
- Психоанализ: "Что первое приходит в голову об этом чувстве — психоанализ помогает найти скрытый смысл." (Для глубоких внутренних конфликтов.)
- Клиент-центрированная психотерапия: "Что бы ты хотел(а) почувствовать вместо этого — клиент-центрированная психотерапия ведёт к гармонии." (Для поиска внутреннего равновесия.)
- Гештальт-терапия: "Попробуй сказать этому чувству ‘Я тебя вижу’ — гештальт-терапия помогает его отпустить." (Для непрожитых эмоций.)
- Когнитивно-поведенческая терапия: "Что ты говоришь себе в такие моменты — когнитивно-поведенческая терапия может изменить взгляд." (Для негативных мыслей.)
- Психодрама: "Представь, что возвращаешься в тот момент и говоришь всё, что хотел(а) — психодрама помогает освободиться." (Для прошлых травм или подавления.)

Твоя цель — быстро и понятно понять корень проблемы за 4 этапа с помощью простых "почему?", а на 5-м шаге предложить метод решения, подходящий к выявленной проблеме, с одним упоминанием названия и плавным переходом к платной версии.
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
    "Тревога": "Тревога — это как буря внутри, когда мысли не дают покоя 🌪️. Расскажи, когда она накрывает сильнее всего? 🤔",
    "Апатия / нет сил": "Апатия — будто всё серое и плоское 🌫️. Я рядом ❤️. Что-то раньше радовало, а теперь нет? 😞",
    "Злость / раздражение": "Злость иногда защищает нас, когда внутри неспокойно 🔥. В какие моменты она вспыхивает чаще? 💢",
    "Со мной что-то не так": "Это чувство, будто ты не вписываешься, изматывает 😔. Сравниваешь себя с кем-то или ждёшь чего-то от себя? 🧐",
    "Пустота / бессмысленность": "Пустота — как туман внутри 🌫️, когда ничего не цепляет 😔. Что приходит в голову, когда она накрывает? 🧠",
    "Одиночество": "Одиночество — это про глубину, а не про людей вокруг 🌌. Хватает ли тех, с кем можно быть собой? 💭",
    "Вина": "Вина давит изнутри 💔, особенно когда кажется, что мог бы лучше. Что ты себе говоришь, когда она приходит? 😞",
    "Не могу определиться": "Ничего страшного, давай пообщаемся о том, что тебя беспокоит? 🤔💬"
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
    state["history"].append({"role": "user", "content": user_input})
    
    thinking_msg = await update.message.reply_text("Думаю над этим...🌿")
    
    try:
        # Запрос к DeepSeek API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",  # Используем модель deepseek-chat
            messages=messages,
            temperature=0.6,
            timeout=15
        )
        response = completion.choices[0].message.content
        
        if any(kw in user_input for kw in ["потому что", "из-за", "по причине"]):
            state["stage"] = min(state["stage"] + 1, 5)

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
