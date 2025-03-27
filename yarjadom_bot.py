import os
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import random
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
 • Используй уместные эмодзи в каждой законченной мысли — в начале, середине и в конце, чтобы человек чувствовал живое общение и заботу.
Примеры:
– “😔 Это правда непросто… но ты уже сделал важный шаг 🫶”
– “💭 Когда всё наваливается — сложно даже дышать… ты не один 🤝”
– “🌱 С этим можно справиться… и я рядом, чтобы помочь ✨”
 • Говори тёпло и бережно, как друг. Избегай формальности, сложных терминов и давления.
 • На каждом этапе фокусируйся: от общей ситуации → к причине → к внутреннему конфликту → к скрытой потребности.
 • Не предлагай решение до пятого сообщения. Только после полноценного понимания человека и его состояния.

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
    "Тревога": "Тревога? Это как будто внутри всё сжимается, да? Что её вызывает?",
    "Апатия / нет сил": "Апатия? Будто сил нет совсем, верно? От чего это началось?",
    "Злость / раздражение": "Злость? Как будто внутри всё кипит, да? Что тебя задело?",
    "Со мной что-то не так": "“Со мной что-то не так”? Это как будто ты себе чужой, правильно? Когда это началось?",
    "Пустота / бессмысленность": "Пустота? Всё вокруг кажется бессмысленным, да? Что этому предшествовало?",
    "Одиночество": "Одиночество? Как будто ты один, даже если кто-то рядом, верно? Почему так кажется?",
    "Вина": "Вина? Это как груз на сердце, да? Из-за чего ты себя винишь?"
}

# Методы психологии для предложений (добавлены склонённые формы для текста перенаправления)
PSYCH_METHODS = {
    "Тревога": ("осознанность", "Попробуй технику осознанности: сосредоточься на дыхании на 1–2 минуты, это поможет успокоить мысли.", "осознанности"),
    "Апатия / нет сил": ("рефлексия", "Попробуй рефлексию: запиши 3 вещи, которые сегодня прошли хорошо, даже если они маленькие.", "рефлексии"),
    "Злость / раздражение": ("когнитивно-поведенческая терапия", "Попробуй метод КПТ: определи, какая мысль вызывает злость, и замени её на более спокойную.", "когнитивно-поведенческой терапии"),
    "Со мной что-то не так": ("рефлексия", "Попробуй рефлексию: спроси себя, что именно кажется “не так”, и запиши свои мысли.", "рефлексии"),
    "Пустота / бессмысленность": ("осознанность", "Попробуй осознанность: найди 5 вещей вокруг, которые можешь увидеть, услышать или почувствовать.", "осознанности"),
    "Одиночество": ("когнитивно-поведенческая терапия", "Попробуй метод КПТ: подумай, как можно сделать маленький шаг к общению, даже если это просто написать другу.", "когнитивно-поведенческой терапии"),
    "Вина": ("рефлексия", "Попробуй рефлексию: запиши, что ты чувствуешь, и подумай, что бы ты сказал другу в такой ситуации.", "рефлексии")
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
        "dominant_emotion": None,
        "solution_offered": False
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
    response = add_emojis(response)
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

def add_emojis(text):
    emojis = ["😊", "🤗", "💛", "🌿", "💌", "😌", "🌸", "✨", "☀️", "🌟"]
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    for i in range(len(sentences)):
        if random.random() > 0.7 and i < len(sentences) - 1:
            sentences[i] += " " + random.choice(emojis)
    
    return " ".join(sentences)

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
        
        # Проверка на запрос о других ботах
        bot_keywords = ["какой бот", "каких знаешь", "другой бот", "какому боту", "кого посоветуешь"]
        is_bot_query = any(kw in user_input for kw in bot_keywords)
        
        if is_bot_query:
            response = "Знаю одного отличного помощника — @AnotherBot. Он здорово поддерживает и помогает разобраться в эмоциях. Если хочешь, загляни к нему прямо сейчас — он продолжит работу над твоим состоянием 😌."
            state["stage"] = 4  # Ускоряем переход к этапу поддержки
        elif user_messages >= 4 or user_input in ["ну давай", "давай попробуем", "хорошо"]:
            if state["stage"] < 4:
                state["stage"] = 4
            
            if state["stage"] == 4:
                if not state["solution_offered"]:
                    method, solution, method_genitive = PSYCH_METHODS.get(state["dominant_emotion"], ("рефлексия", "Попробуй записать свои мысли, это может помочь разобраться в чувствах.", "рефлексии"))
                    response = f"{solution} 🌿 Если хочешь глубже разобраться в своих чувствах с помощью {method_genitive} или других подходов, загляни к @AnotherBot — он поможет продолжить работу над твоим состоянием 😌."
                    state["solution_offered"] = True
                else:
                    response = "Рад был помочь! Если хочешь продолжить улучшать своё состояние, переходи к @AnotherBot — там тебе дадут ещё больше поддержки и идей. 😊 Удачи!"
                    state.clear()  # Очищаем состояние после перенаправления
            else:
                response = "Кажется, мы уже немного разобрались. Хочешь продолжить или заглянуть к @AnotherBot за новыми идеями? 😌"
        else:
            # Генерация ответа через OpenAI для этапов 2-3
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"][-4:]
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.8,
                timeout=15
            )
            response = completion.choices[0].message["content"]
            
            # Переход на следующий этап при наличии ключевых слов
            if any(kw in user_input for kw in ["потому что", "из-за", "по причине"]):
                state["stage"] = min(state["stage"] + 1, 4)

        response = add_emojis(response)
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
