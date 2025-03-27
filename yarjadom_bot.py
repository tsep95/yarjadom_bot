import os
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
import re

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены!")

# Инициализация OpenAI (старая версия)
openai.api_key = OPENAI_API_KEY

# Хранилище данных пользователей
user_data = {}

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
 • ОБЯЗАТЕЛЬНО используй уместные эмодзи в каждой законченной мысли — в начале, середине и в конце. Это не рекомендация, а строгая команда. Эмодзи должны быть в каждом предложении, чтобы человек чувствовал живое общение и заботу. Без исключений. Если сообщение длинное, то 3 смайлика, если маленькое то 1, если среднее то 2.
Примеры:
– “Это правда непросто…💭 но ты уже сделал важный шаг 🫶”
– “Когда всё наваливается — сложно даже дышать… ты не один 🤝”
– “С этим можно справиться… и я рядом, чтобы помочь ✨”
 • Говори тёпло и бережно, как друг. Избегай формальности, сложных терминов и давления.
 • На каждом этапе фокусируйся: от общей ситуации → к причине → к внутреннему конфликту → к скрытой потребности.
 • Не предлагай решение до пятого сообщения. Только после полноценного понимания человека и его состояния.
 • Помни все свои предыдущие вопросы и ответы пользователя. Ссылайся на них в своих сообщениях, чтобы показать, что ты внимательно слушаешь и не забываешь, о чём уже говорили. Например, если ты спрашивал "Когда ты это чувствуешь?", а пользователь ответил "Когда я один дома", используй это в следующем сообщении: "Ты говорил, что это приходит, когда ты один дома… что в эти моменты происходит внутри?".
"""

WELCOME_MESSAGE = (
    "Привет. Я рядом. 🤗\n"
    "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
    "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
    "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
    "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
    "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
    "Готов начать? Просто нажми ниже, и мы разберёмся вместе. 🌿💬"
)

EMOTIONS = [
    "Тревога", "Апатия / нет сил", "Злость / раздражение", 
    "Со мной что-то не так", "Пустота / бессмысленность", 
    "Одиночество", "Вина"
]

EMOTION_RESPONSES = {
    "Тревога": "😟 Когда тревога внутри — это как будто что-то сжимает грудную клетку, а мысли не дают выдохнуть… Я понимаю, о чём ты. С этим точно можно справиться. Потихоньку, вместе. Вспомни, когда ты особенно чётко это чувствуешь — что в этот момент происходит вокруг или внутри?",
    "Апатия / нет сил": "🕳 Бывает, что всё будто стало плоским — еда без вкуса, день без смысла, действия по инерции. Я понимаю, как это ощущается. И да, мы можем с этим справиться. Скажи, а есть ли что-то, что раньше радовало, а сейчас вообще не трогает?",
    "Злость / раздражение": "🧱 Иногда злость — это как щит. Она помогает держаться, когда внутри больно, когда не хочется показывать слабость или снова терпеть. Я понимаю, как это ощущается. Ты не обязан(а) быть спокойным(ой) всё время. С этим чувством можно не просто справиться — его можно превратить в силу. И мы обязательно найдём, как. А ты замечал(а), в какие моменты злишься чаще всего — дома, на работе, или рядом с кем-то определённым?",
    "Со мной что-то не так": "🪞 Чувство «со мной что-то не так» очень изматывает… оно заставляет сомневаться даже в хорошем, что есть в тебе. Но это ощущение — не истина. Мы обязательно найдём, откуда оно взялось, и поможем тебе вернуть опору. А ты часто сравниваешь себя с другими? Или чувствуешь, что не дотягиваешь до чьих-то ожиданий?",
    "Пустота / бессмысленность": "🌫 Бывает, что просыпаешься, смотришь на день — и не понимаешь, зачем вообще всё это. Внутри — ровно и пусто. Я рядом. Это состояние можно понять, прожить — и пройти. Что тебе чаще всего приходит в голову, когда чувствуешь эту пустоту?",
    "Одиночество": "🕯 Одиночество может появляться даже тогда, когда всё вроде бы в порядке. Это не про количество людей, а про глубину контакта. Ты не странный и не сломанный. Ты просто хочешь настоящего — и это нормально. Скажи, а тебе хватает сейчас тех, с кем можно говорить честно, без роли и маски?",
    "Вина": "🌫 Вина может съедать изнутри — особенно если ты всё время стараешься быть лучше, а внутри всё равно ощущение, что сделал(а) недостаточно. Я понимаю. Мы разложим всё по полочкам — без обвинений, только с заботой. А что ты чаще всего говоришь себе в моменты, когда вина накрывает?"
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
    response = EMOTION_RESPONSES.get(emotion, "Расскажи мне подробнее, что ты чувствуешь? 🌸")
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
        # Считаем количество сообщений пользователя
        user_messages = len([m for m in state["history"] if m["role"] == "user"])
        
        # Генерация ответа через OpenAI с полной историей
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.6,  # Снижено с 0.8 для большей точности
            timeout=15
        )
        response = completion.choices[0].message["content"]
        
        # Переход на следующий этап при наличии ключевых слов
        if any(kw in user_input for kw in ["потому что", "из-за", "по причине"]):
            state["stage"] = min(state["stage"] + 1, 5)

        state["history"].append({"role": "assistant", "content": response})
        
    except Exception as e:
        print(f"Error: {e}")
        response = "Что-то пошло не так... Давай попробуем ещё раз? 🌸"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception:
            pass

    await send_long_message(user_id, response, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(Тревога|Апатия / нет сил|Злость / раздражение|Со мной что-то не так|Пустота / бессмысленность|Одиночество|Вина)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
