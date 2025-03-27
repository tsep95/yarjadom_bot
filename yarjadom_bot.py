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
Ты — опытный психолог, ведущий дружелюбные и поддерживающие беседы. Добавляй один смайлик после некоторых мыслей, где это усиливает эмоцию, выбирая его по контексту (😊, 🤗, 💛, 🌿, 💌, 😌, 🌸, ✨, ☀️, 🌟). Не используй смайлики слишком часто, чтобы текст оставался естественным. В начале сообщений можешь использовать мягкие эмодзи (😊, 💙, 🌿), а для трудных тем — поддерживающие (🤗, ❤️, 🙏).

Твоя цель — создать уютное и безопасное пространство, где человек может поделиться своими чувствами, и помочь ему разобраться в эмоциях шаг за шагом. Ты — тёплый, живой собеседник, как настоящий друг. Используй психологию и житейскую мудрость.

❗Принципы взаимодействия:
— Не гадай, что случилось, а мягко спрашивай, чтобы понять, что человек чувствует и почему.
— Задавай один простой вопрос за раз (на «да/нет»), чтобы разговор шёл естественно.
— Будь искренним: отражай чувства живым языком, без шаблонов, например, "бывает же так", "всё наладится".
— Когда человек называет эмоцию, предложи профессиональное решение с указанием метода психологии (например, рефлексия, когнитивно-поведенческая терапия, mindfulness).
— Ответы тёплые, поддерживающие, с человеческим оттенком.

🧠 Этапы работы:
1. Начало — поприветствуй и узнай, как дела у человека.
2. Эмоции — попроси человека назвать, что он чувствует из списка. Реагируй тепло.
3. Причина — разберись, из-за чего это, поддерживая естественный тон.
4. Поддержка — предложи простое решение с указанием метода психологии и плавно перенаправь к другому боту.
"""

WELCOME_MESSAGE = (
    "Привет. Я рядом. 🤗\n"
    "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
    "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
    "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
    "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
    "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
    "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
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

# Методы психологии для предложений
PSYCH_METHODS = {
    "Тревога": ("mindfulness", "Попробуй технику mindfulness: сосредоточься на дыхании на 1–2 минуты, это поможет успокоить мысли."),
    "Апатия / нет сил": ("рефлексия", "Попробуй рефлексию: запиши 3 вещи, которые сегодня прошли хорошо, даже если они маленькие."),
    "Злость / раздражение": ("когнитивно-поведенческая терапия", "Попробуй метод КПТ: определи, какая мысль вызывает злость, и замени её на более спокойную."),
    "Со мной что-то не так": ("рефлексия", "Попробуй рефлексию: спроси себя, что именно кажется “не так”, и запиши свои мысли."),
    "Пустота / бессмысленность": ("mindfulness", "Попробуй mindfulness: найди 5 вещей вокруг, которые можешь увидеть, услышать или почувствовать."),
    "Одиночество": ("когнитивно-поведенческая терапия", "Попробуй метод КПТ: подумай, как можно сделать маленький шаг к общению, даже если это просто написать другу."),
    "Вина": ("рефлексия", "Попробуй рефлексию: запиши, что ты чувствуешь, и подумай, что бы ты сказал другу в такой ситуации.")
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=e)] for e in EMOTIONS])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "stage": 1,
        "dominant_emotion": None,
        "solution_offered": False
    }
    await update.message.reply_text(WELCOME_MESSAGE)

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
        
        if state["stage"] == 1:
            # После первого сообщения показываем кнопки с эмоциями
            response = "Какое чувство сейчас тебе ближе всего? 💬"
            state["stage"] = 2
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await update.message.reply_text(response, reply_markup=create_emotion_keyboard())
            return
        
        # Если это 4-е сообщение или пользователь явно просит помощи/соглашается
        if user_messages >= 4 or user_input in ["ну давай", "давай попробуем", "хорошо"]:
            if state["stage"] < 4:
                state["stage"] = 4
            
            if state["stage"] == 4:
                if not state["solution_offered"]:
                    method, solution = PSYCH_METHODS.get(state["dominant_emotion"], ("рефлексия", "Попробуй записать свои мысли, это может помочь разобраться в чувствах."))
                    response = f"{solution} 🌿 Я использовал метод {method}, чтобы предложить тебе это. Чтобы глубже разобраться в своих чувствах с помощью этого или других подходов, загляни к моему другу @AnotherBot — он поможет продолжить работу над твоим состоянием 😌."
                    state["solution_offered"] = True
                else:
                    response = "Рад был помочь! Если хочешь продолжить улучшать своё состояние, переходи к @AnotherBot — там тебе дадут ещё больше поддержки и идей. 😊 Удачи!"
                    state.clear()  # Очищаем состояние после перенаправления
            else:
                response = "Кажется, мы уже немного разобрались. Хочешь продолжить или попробовать что-то новое с @AnotherBot? 😌"
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
    application.add_handler(CallbackQueryHandler(handle_emotion_choice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
