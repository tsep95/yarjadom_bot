import os
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import random
import asyncio
import re

# Установи эти переменные в Railway или напрямую здесь (для теста)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация OpenAI клиента
openai.api_key = OPENAI_API_KEY

# Словарь для хранения истории диалогов и этапов
user_data = {}

# Обновлённый промпт
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
4. Поддержка — предложи простое решение, а затем намекни на дальнейшую помощь.

🔔 Поддержка и подписка:
— На этапе 4 дай тёплое решение (например, "Попробуй остановиться и сделать несколько глубоких вдохов 🌿").
— Добавь переход: "Если хочешь, можем поболтать об этом побольше — у меня есть друг, другой бот, где профи помогут глубже разобраться. Хочешь попробовать? 😌".
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет, я рядом. 🤗\n"
    "Тёплый психологический помощник-бот, с которым можно просто поговорить. 🧸\n"
    "Если тебе тяжело, тревожно или пусто — пиши. ✍️\n"
    "Я не оцениваю, не критикую, я здесь, чтобы поддержать. 💛\n"
    "Выбери, что ты чувствуешь прямо сейчас 👇"
)

# Список эмоций
EMOTIONS = [
    "Тревога", "Апатия / нет сил", "Злость / раздражение", 
    "Со мной что-то не так", "Пустота / бессмысленность", 
    "Одиночество", "Вина"
]

# Ответы с "эмоциональным зеркалом"
EMOTION_RESPONSES = {
    "Тревога": "Тревога? Это как будто внутри всё сжимается и не даёт покоя, да? Что её вызывает?",
    "Апатия / нет сил": "Апатия? Такое чувство, будто сил совсем не осталось, и всё потеряло цвет, верно? От чего это началось?",
    "Злость / раздражение": "Злость? Это как будто что-то внутри кипит и хочет вырваться, да? Что тебя так задело?",
    "Со мной что-то не так": "“Со мной что-то не так”? Это как будто ты сам себе кажешься чужим, правильно? Когда это чувство появилось?",
    "Пустота / бессмысленность": "Пустота? Такое ощущение, будто всё вокруг потеряло смысл, да? Что этому предшествовало?",
    "Одиночество": "Одиночество? Это как будто ты один в целом мире, даже если кто-то рядом, верно? Почему так кажется?",
    "Вина": "Вина? Это как тяжёлый груз, который давит на сердце, да? Из-за чего ты себя винишь?"
}

# Создание клавиатуры с эмоциями
def create_emotion_keyboard():
    keyboard = [
        [InlineKeyboardButton(emotion, callback_data=emotion)] for emotion in EMOTIONS
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчик команды /start
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

# Обработчик выбора эмоции
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

# Добавление смайликов с учётом естественности
def add_emojis_to_response(response):
    emoji_list = ["😊", "🤗", "💛", "🌿", "💌", "😌", "🌸", "✨", "☀️", "🌟"]
    sentences = re.split(r'(?<=[.!?])\s+', response.strip())  # Разделяем по точкам и вопросам
    result = []
    used_emojis = set()  # Отслеживаем использованные смайлики в этом сообщении
    
    for i, sentence in enumerate(sentences):
        if sentence:
            # Добавляем смайлик только в 50% случаев для естественности
            if random.random() > 0.5 and i < len(sentences) - 1:  # Не добавляем в конце всегда
                available_emojis = [e for e in emoji_list if e not in used_emojis]
                if not available_emojis:  # Если закончились уникальные, сбрасываем
                    available_emojis = emoji_list
                selected_emoji = random.choice(available_emojis)
                used_emojis.add(selected_emoji)
                # Удаляем точку или вопрос перед смайликом
                sentence = re.sub(r'[.!?]$', '', sentence.strip()) + f" {selected_emoji}"
            result.append(sentence)
    
    return " ".join(result)

# Обработчик текстовых сообщений
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

    thinking_message = await update.message.reply_text("Думаю над этим... 🌿")

    stage = user_data[user_id]["stage"]
    dominant_emotion = user_data[user_id]["dominant_emotion"]
    problem_hint = user_data[user_id]["problem_hint"]
    solution_offered = user_data[user_id]["solution_offered"]

    if stage == 2 and problem_hint:
        user_data[user_id]["stage"] = 3
    elif stage == 3 and problem_hint:
        user_data[user_id]["stage"] = 4
    elif stage == 4 and not solution_offered:
        user_data[user_id]["solution_offered"] = True
        gpt_response = "Понимаю, разработка бота — это большая задача. Попробуй начать с малого: определи основные функции и запиши их. Это даст тебе ясность и первый шаг вперёд."
    elif stage == 4 and solution_offered:
        gpt_response = "Если хочешь, можем поболтать об этом побольше. У меня есть друг, другой бот, где профи помогут разобраться глубже. Хочешь попробовать?"
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *user_data[user_id]["history"]
        ]
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.8,
                max_tokens=100,
                timeout=5
            )
            gpt_response = response.choices[0].message["content"]
        except Exception as e:
            gpt_response = "Ой, что-то пошло не так. Давай попробуем ещё раз? Что тебя сейчас больше всего беспокоит?"

    problem_keywords = ["потому что", "из-за", "случилось", "работа", "учёба", "вуз", "дома", "человек", "друзья", "расстался", "уволили", "потерял", "сроки", "дела"]
    if any(keyword in user_input for keyword in problem_keywords):
        user_data[user_id]["problem_hint"] = True

    gpt_response = add_emojis_to_response(gpt_response)
    user_data[user_id]["history"].append({"role": "assistant", "content": gpt_response})

    if len(user_data[user_id]["history"]) > 10:
        user_data[user_id]["history"] = user_data[user_id]["history"][-10:]

    await context.bot.delete_message(chat_id=user_id, message_id=thinking_message.message_id)
    await update.message.reply_text(gpt_response)

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен!")
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены!")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
