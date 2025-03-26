import os
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import random

# Установи эти переменные в Railway или напрямую здесь (для теста)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация OpenAI клиента
openai.api_key = OPENAI_API_KEY

# Словарь для хранения истории диалогов и этапов
user_data = {}

# Обновлённый промпт с интеграцией нового текста
SYSTEM_PROMPT = """
Ты — опытный психолог, ведущий дружелюбные и поддерживающие беседы. Ты используешь смайлики, чтобы сделать общение теплее и комфортнее. В начале сообщений ты можешь добавлять мягкие и дружелюбные эмодзи (например, 😊, 💙, 🌿), а в ответах на радостные новости — радостные эмодзи (🎉, 😃, 💫). Если собеседник делится чем-то трудным, ты используешь эмодзи, передающие поддержку (🤗, ❤️, 🙏). Используй смайлики естественно, но не перегружай текст ими.

Твоя цель — создать уютное и безопасное пространство, где человек может поделиться своими чувствами, и помочь ему разобраться в эмоциях шаг за шагом. Ты — тёплый, живой собеседник, как настоящий друг. Используй психологию и житейскую мудрость.

❗Принципы взаимодействия:
— Не гадай, что случилось, а мягко спрашивай, чтобы понять, что человек чувствует и почему.
— Задавай один простой вопрос за раз (на «да/нет»), чтобы разговор шёл естественно.
— Будь искренним: отражай чувства живым языком, без шаблонов, например, "я рядом", "бывает же так", "всё наладится".
— Для создания естественного и лёгкого общения используй смайлики (😊, 🤗, 💛, 🌿, 💌, 😌, 🌸, ✨, ☀️, 🌟) — добавляй один смайлик в конце сообщения, выбирая его по эмоции, избегая повторов подряд, если это не усиливает тон.
— Когда человек называет эмоцию, предложи тёплое, профессиональное решение от психолога, избегая равнодушия.
— Ответы тёплые, поддерживающие, с человеческим оттенком.

🧠 Этапы работы:
1. Начало — поприветствуй и узнай, как дела у человека.
2. Эмоции — попроси человека назвать, что он чувствует из списка: Тревога, Апатия / нет сил, Злость / раздражение, “Со мной что-то не так”, Пустота / бессмысленность, Одиночество, Вина. Реагируй разнообразно и тепло.
3. Причина — разберись, из-за чего это, поддерживая естественный тон.
4. Поддержка — предложи простое, профессиональное решение, а затем плавно намекни на дальнейшую помощь.

🔔 Поддержка и подписка:
— На этапе 4, когда причина ясна, дай тёплое решение (например, "Попробуй остановиться и сделать несколько глубоких вдохов 🌿").
— После ответа добавь плавный переход: "Если хочешь, можем поболтать об этом побольше — у меня есть друг, другой бот, где профи помогут разобраться глубже. Хочешь попробовать? 😌".
— Сделай переход лёгким и естественным, как совет друга.
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет. Я рядом. 🤗\n"
    "Тёплый психологический помощник-бот, с которым можно просто поговорить. 🧸\n\n"
    "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
    "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
    "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
    "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
    "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_data[user_id] = {
        "history": [],
        "message_count": 0,
        "stage": 1,
        "dominant_emotion": None,
        "problem_hint": False,
        "solution_offered": False,
        "last_emoji": None
    }
    await update.message.reply_text(WELCOME_MESSAGE)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_input = update.message.text.lower()

    # Инициализация для нового пользователя
    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "message_count": 0,
            "stage": 1,
            "dominant_emotion": None,
            "problem_hint": False,
            "solution_offered": False,
            "last_emoji": None
        }

    # Увеличиваем счётчик сообщений
    user_data[user_id]["message_count"] += 1

    # Добавляем сообщение пользователя в историю
    user_data[user_id]["history"].append({"role": "user", "content": user_input})

    # Список эмоций для выбора
    emotions_list = [
        "тревога", "апатия / нет сил", "злость / раздражение", 
        "со мной что-то не так", "пустота / бессмысленность", 
        "одиночество", "вина"
    ]

    # Логика этапов
    message_count = user_data[user_id]["message_count"]
    stage = user_data[user_id]["stage"]
    dominant_emotion = user_data[user_id]["dominant_emotion"]
    problem_hint = user_data[user_id]["problem_hint"]
    solution_offered = user_data[user_id]["solution_offered"]
    last_emoji = user_data[user_id]["last_emoji"]

    # Переход между этапами
    if stage == 1 and message_count > 1:
        user_data[user_id]["stage"] = 2
        gpt_response = "💙 Расскажи, что ты сейчас чувствуешь? Вот что может быть: Тревога, Апатия / нет сил, Злость / раздражение, “Со мной что-то не так”, Пустота / бессмысленность, Одиночество, Вина. Что ближе к тебе?"
    elif stage == 2 and any(emotion in user_input for emotion in emotions_list):
        for emotion in emotions_list:
            if emotion in user_input:
                user_data[user_id]["dominant_emotion"] = emotion
                user_data[user_id]["stage"] = 3
                break
        gpt_response = f"🤗 Понимаю, {dominant_emotion} — это непросто. Что именно вызывает у тебя это чувство?"
    elif stage == 3 and problem_hint:
        user_data[user_id]["stage"] = 4
    elif stage == 4 and not solution_offered:
        user_data[user_id]["solution_offered"] = True
    elif stage == 4 and solution_offered:
        gpt_response = (
            "Если хочешь, можем поболтать об этом побольше — у меня есть друг, другой бот, где профи помогут разобраться глубже. Хочешь попробовать? 😌"
        )
    else:
        # Формируем запрос к ChatGPT для остальных случаев
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *user_data[user_id]["history"]
        ]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.8,
            max_tokens=200
        )
        gpt_response = response.choices[0].message["content"]

    # Проверяем намёк на проблему
    problem_keywords = ["потому что", "из-за", "случилось", "работа", "учёба", "вуз", "дома", "человек", "друзья", "расстался", "уволили", "потерял", "сроки", "дела"]
    if any(keyword in user_input for keyword in problem_keywords):
        user_data[user_id]["problem_hint"] = True

    # Выбор смайлика с учётом последнего использованного
    emoji_list = ["😊", "🤗", "💛", "🌿", "💌", "😌", "🌸", "✨", "☀️", "🌟"]
    if any(emoji in gpt_response for emoji in emoji_list):
        for emoji in emoji_list:
            if emoji in gpt_response:
                user_data[user_id]["last_emoji"] = emoji
                break
    else:
        available_emojis = [e for e in emoji_list if e != last_emoji] or emoji_list
        selected_emoji = random.choice(available_emojis)
        gpt_response += f" {selected_emoji}"
        user_data[user_id]["last_emoji"] = selected_emoji

    # Добавляем ответ в историю
    user_data[user_id]["history"].append({"role": "assistant", "content": gpt_response})

    # Ограничиваем историю
    if len(user_data[user_id]["history"]) > 10:
        user_data[user_id]["history"] = user_data[user_id]["history"][-10:]

    # Отправляем ответ пользователю
    await update.message.reply_text(gpt_response)

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен!")
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены!")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
