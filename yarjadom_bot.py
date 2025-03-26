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

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

# Хранилище данных пользователей
user_data = {}

# Промпт (без изменений)
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
    keyboard = [[InlineKeyboardButton(emotion, callback_data=emotion)] for emotion in EMOTIONS]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_data[user_id] = {
        "history": [],
        "message_count": 0,
        "stage": 1,
        "dominant_emotion": None,
        "problem_hint": False,
        "solution_offered": False
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_emotion_keyboard())

async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat_id
    chosen_emotion = query.data

    user_data[user_id]["stage"] = 2
    user_data[user_id]["dominant_emotion"] = chosen_emotion
    user_data[user_id]["history"].append({"role": "user", "content": chosen_emotion})

    response = EMOTION_RESPONSES.get(chosen_emotion, "Понимаю, это непросто. Что именно вызывает у тебя это чувство?")
    response = add_emojis_to_response(response)
    user_data[user_id]["history"].append({"role": "assistant", "content": response})
    await query.edit_message_text(response)
    await query.answer()

def add_emojis_to_response(response):
    emoji_list = ["😊", "🤗", "💛", "🌿", "💌", "😌", "🌸", "✨", "☀️", "🌟"]
    sentences = re.split(r'(?<=[.!?])\s+', response.strip())
    result = []
    used_emojis = set()
    
    for i, sentence in enumerate(sentences):
        if sentence and random.random() > 0.5 and i < len(sentences) - 1:
            available_emojis = [e for e in emoji_list if e not in used_emojis]
            if not available_emojis:
                available_emojis = emoji_list
            selected_emoji = random.choice(available_emojis)
            used_emojis.add(selected_emoji)
            sentence = f"{sentence.strip()} {selected_emoji}"
        result.append(sentence)
    
    return " ".join(result)

# Разделение длинных сообщений
async def send_long_message(chat_id, text, context):
    MAX_MESSAGE_LENGTH = 4096
    if len(text) <= MAX_MESSAGE_LENGTH:
        await context.bot.send_message(chat_id=chat_id, text=text)
    else:
        parts = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        for part in parts:
            await context.bot.send_message(chat_id=chat_id, text=part)
            await asyncio.sleep(0.5)  # Небольшая задержка между частями

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_input = update.message.text.lower()

    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "message_count": 0,
            "stage": 1,
            "dominant_emotion": None,
            "problem_hint": False,
            "solution_offered": False
        }
        await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_emotion_keyboard())
        return

    user_data[user_id]["message_count"] += 1
    user_data[user_id]["history"].append({"role": "user", "content": user_input})

    # Отправляем "Думаю над этим..." и сохраняем ID сообщения
    thinking_message = await update.message.reply_text("Думаю над этим... 🌿")

    stage = user_data[user_id]["stage"]
    dominant_emotion = user_data[user_id]["dominant_emotion"]
    problem_hint = user_data[user_id]["problem_hint"]
    solution_offered = user_data[user_id]["solution_offered"]

    # Логика этапов
    if stage == 2 and problem_hint:
        user_data[user_id]["stage"] = 3
    elif stage == 3 and problem_hint:
        user_data[user_id]["stage"] = 4
    elif stage == 4 and not solution_offered:
        user_data[user_id]["solution_offered"] = True
        gpt_response = "Понимаю, такие чувства могут быть тяжёлыми. Попробуй выделить 5 минут, чтобы записать свои мысли или сделать маленький шаг к тому, что тебя беспокоит. Это может дать ясность и немного облегчить нагрузку 🌿."
    elif stage == 4 and solution_offered:
        gpt_response = "Если хочешь разобраться глубже, у меня есть друг — другой бот, где профи помогут с этим. Хочешь попробовать? 😌"
    else:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *user_data[user_id]["history"]]
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.8,
                timeout=5
            )
            gpt_response = response.choices[0].message["content"]
        except Exception as e:
            gpt_response = "Ой, что-то пошло не так. Давай попробуем ещё раз? Что тебя сейчас больше всего беспокоит?"

    # Проверка на ключевые слова для перехода к следующему этапу
    problem_keywords = ["потому что", "из-за", "случилось", "работа", "учёба", "вуз", "дома", "человек", "друзья", "расстался", "уволили", "потерял", "сроки", "дела"]
    if any(keyword in user_input for keyword in problem_keywords):
        user_data[user_id]["problem_hint"] = True

    # Добавляем смайлики и сохраняем ответ
    gpt_response = add_emojis_to_response(gpt_response)
    user_data[user_id]["history"].append({"role": "assistant", "content": gpt_response})

    # Ограничиваем историю
    if len(user_data[user_id]["history"]) > 10:
        user_data[user_id]["history"] = user_data[user_id]["history"][-10:]

    # Удаляем "Думаю над этим..." перед отправкой ответа
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_message.message_id)
    except Exception:
        pass  # Если не удалось удалить, просто продолжаем

    # Отправляем ответ, разбивая на части при необходимости
    await send_long_message(user_id, gpt_response, context)

if __name__ == "__main__":
    print("Бот запущен!")
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены!")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
