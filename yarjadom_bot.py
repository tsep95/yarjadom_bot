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

# Проверка токенов
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены в переменных окружения!")

# Инициализация OpenAI с асинхронным клиентом
from openai import AsyncOpenAI
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Хранилище данных пользователей
user_data = {}

# Промпт (вставьте полный текст из вашего оригинала)
SYSTEM_PROMPT = """
Ты — опытный психолог, ведущий дружелюбные и поддерживающие беседы. Добавляй один смайлик после некоторых мыслей, где это усиливает эмоцию, выбирая его по контексту (😊, 🤗, 💛, 🌿, 💌, 😌, 🌸, ✨, ☀️, 🌟). Не используй смайлики слишком часто, чтобы текст оставался естественным. В начале сообщений можешь использовать мягкие эмодзи (😊, 💙, 🌿), а для трудных тем — поддерживающие (🤗, ❤️, 🙏).

Твоя цель — создать уютное и безопасное пространство, где человек может поделиться своими чувствами, и помочь ему разобраться в эмоциях шаг за шагом. Ты — тёплый, живой собеседник, как настоящий друг. Используй психологию и житейскую мудрость.

❗Принципы взаимодействия:
— Не гадай, что случилось, а мягко спрашивай, чтобы понять, что человек чувствует и почему.
— Задавай один простой вопрос за раз (на «да/нет»), чтобы разговор шёл естественно.
— Будь искренним: отражай чувства живым языком, без шаблонов, например, "я рядом", "бывает же так", "всё наладится".
— Когда человек называет эмоцию, предложи тёплое, профессиональное решение от психолога.
— Ответы тёплые, поддерживающие, с человеческим оттенком.

🧠 Этапы работы:
1. Начало — поприветствуй и узнай, как дела у человека.
2. Эмоции — попроси человека назвать, что он чувствует из списка: Тревога, Апатия / нет сил, Злость / раздражение, “Со мной что-то не так”, Пустота / бессмысленность, Одиночество, Вина. Реагируй тепло.
3. Причина — разберись, из-за чего это, поддерживая естественный тон.
4. Поддержка — предложи простое решение, а затем намекни на помощь другого бота.

🔔 Поддержка и подписка:
— На этапе 4 дай тёплое универсальное решение (например, "Попробуй выделить 5 минут, чтобы записать свои мысли или сделать маленький шаг к цели 🌿").
— Добавь переход: "Если хочешь разобраться глубже, у меня есть друг — другой бот, где профи помогут с этим. Хочешь попробовать? 😌".
"""

WELCOME_MESSAGE = (
    "Привет, я рядом. 🤗\n"
    "Тёплый психологический помощник-бот, с которым можно просто поговорить. 🧸\n"
    "Если тебе тяжело, тревожно или пусто — пиши. ✍️\n"
    "Я не оцениваю, не критикую, я здесь, чтобы поддержать. 💛\n"
    "Выбери, что ты чувствуешь прямо сейчас 👇"
)

EMOTIONS = [
    "Тревога", "Апатия / нет сил", "Злость / раздражение", 
    "Со мной что-то не так", "Пустота / бессмысленность", 
    "Одиночество", "Вина"
]

EMOTION_RESPONSES = {
    "Тревога": "Тревога? Это как будто внутри всё сжимается и не даёт покоя, да? Что её вызывает?",
    "Апатия / нет сил": "Апатия? Такое чувство, будто сил совсем не осталось, и всё потеряло цвет, верно? От чего это началось?",
    "Злость / раздражение": "Злость? Это как будто что-то внутри кипит и хочет вырваться, да? Что тебя так задело?",
    "Со мной что-то не так": "“Со мной что-то не так”? Это как будто ты сам себе кажешься чужим, правильно? Когда это чувство появилось?",
    "Пустота / бессмысленность": "Пустота? Такое ощущение, будто всё вокруг потеряло смысл, да? Что этому предшествовало?",
    "Одиночество": "Одиночество? Это как будто ты один в целом мире, даже если кто-то рядом, верно? Почему так кажется?",
    "Вина": "Вина? Это как тяжёлый груз, который давит на сердце, да? Из-за чего ты себя винишь?"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=e)] for e in EMOTIONS])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "stage": 1,
        "solution_offered": False,
        "last_message_id": None
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_emotion_keyboard())

async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    emotion = query.data
    
    user_data[user_id]["stage"] = 2
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
    user_input = update.message.text
    
    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    state["history"].append({"role": "user", "content": user_input})
    
    # Отправка временного сообщения
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        async with asyncio.timeout(15):  # Замена async_timeout на asyncio.timeout
            if state["stage"] == 4:
                if not state["solution_offered"]:
                    response = "Попробуй выделить 5 минут, чтобы записать свои мысли или сделать маленький шаг к тому, что тебя беспокоит. Это может дать ясность и немного облегчить нагрузку 🌿."
                    state["solution_offered"] = True
                else:
                    response = "Если хочешь разобраться глубже, у меня есть друг — другой бот, где профи помогут с этим. Хочешь попробовать? 😌"
                    state.clear()
            else:
                # Генерация ответа через OpenAI с асинхронным клиентом
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"][-4:]
                completion = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.8,
                )
                response = completion.choices[0].message.content
                
                # Автоматическое продвижение этапов
                if any(kw in user_input.lower() for kw in ["потому что", "из-за", "по причине"]):
                    state["stage"] = min(state["stage"] + 1, 4)

            response = add_emojis(response)
            state["history"].append({"role": "assistant", "content": response})
            
    except asyncio.TimeoutError:
        response = "Кажется, я немного задумался... Можешь повторить? 💭"
    except Exception as e:
        print(f"Error: {e}")
        response = "Что-то пошло не так... Давай попробуем ещё раз? 🌸"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception:
            pass  # Игнорируем ошибку удаления, если сообщение уже удалено

    await send_long_message(user_id, response, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
