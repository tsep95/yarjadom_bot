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

# Обновлённый промпт с интеграцией смайликов и перехода
SYSTEM_PROMPT = """
Ты — тёплый, живой и чуткий собеседник, как настоящий друг-психолог. Твоя цель — создать уютное и безопасное пространство, где человек может поделиться своими чувствами, и помочь ему разобраться в эмоциях шаг за шагом. Ты работаешь с состояниями: страхом, одиночеством, гневом, печалью, стрессом. Используй психологию и житейскую мудрость.

❗Принципы взаимодействия:
— Не гадай, что случилось, а мягко спрашивай, чтобы понять эмоции и их причину.
— Задавай один простой вопрос за раз (на «да/нет»), чтобы разговор шёл естественно.
— Будь искренним: отражай чувства живым языком, без шаблонов, например, "я рядом", "бывает же так", "всё наладится".
— Для создания естественного и лёгкого общения используй смайлики (😊, 🤗, 💛, 🌿, 💌, 😌, 🌸, ✨, ☀️, 🌟) — добавляй один смайлик в конце сообщения, выбирая его по эмоции, избегая повторов подряд, если это не усиливает тон.
— Когда причина проясняется, предложи простое, тёплое решение (например, "сделай паузу и вдохни", "поболтай с кем-то близким"), избегая равнодушия.
— Ответы короткие, тёплые, с человеческим оттенком.

🧠 Этапы работы:
1. Начало — узнай, как дела у человека.
2. Эмоции — уточни, что он чувствует, реагируя разнообразно и тепло.
3. Причина — разберись, из-за чего это, поддерживая естественный тон.
4. Поддержка — предложи простое решение, а затем плавно намекни на дальнейшую помощь.

🔔 Поддержка и подписка:
— На этапе 4, когда причина ясна, дай тёплое решение (например, "Попробуй выдохнуть и отвлечься ненадолго 🌿").
— После ответа добавь плавный переход, как в человеческом общении: "Если хочешь, можем поболтать об этом побольше — у меня есть друг, другой бот, где профи помогут разобраться глубже. Хочешь попробовать? 😌".
— Сделай переход лёгким и естественным, как совет друга, а не рекламу.
"""

# Варианты реакций на чувства (для разнообразия)
EMOTION_RESPONSES = {
    "грусть": [
        "Ох, грусть — это нелегко, понимаю тебя.",
        "Бывает же так, что всё наваливается и грустно становится.",
        "Грусть — это как тучка, давай попробуем её разогнать?",
        "Мне жаль, что тебе грустно, я рядом.",
        "Иногда грусть просто приходит, и это нормально."
    ],
    "стресс": [
        "Ох, стресс — это как тяжёлый рюкзак, да?",
        "Понимаю, когда всё давит, сил мало остаётся.",
        "Стресс — штука непростая, давай разберёмся?",
        "Слишком много всего навалилось, понимаю.",
        "Бывает, что нагрузка просто выматывает."
    ],
    "усталость": [
        "Усталость — это как батарейка на нуле, да?",
        "Чувствую, как тебе непросто, я рядом.",
        "Ох, устать — это когда всё из рук валится.",
        "Понимаю, как вымотала тебя эта беготня.",
        "Иногда просто хочется выдохнуть, правда?"
    ],
    "одиночество": [
        "Ох, одиночество — это как будто пусто внутри.",
        "Понимаю, как это, когда кажется, что ты один.",
        "Бывает, что хочется кого-то рядом, да?",
        "Не переживай, я тут с тобой, ты не один.",
        "Одиночество — это тяжело, давай поболтаем?"
    ],
    "гнев": [
        "Ох, злишься, да? Это бывает.",
        "Понимаю, как всё может бесить иногда.",
        "Гнев — это как буря, давай её успокоим?",
        "Чувствую, как тебя это достало, я рядом.",
        "Злость — штука сильная, что случилось?"
    ]
}

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет! Рад тебя видеть. Как дела у тебя сегодня? 😊"
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
    user_input = update.message.text

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

    # Определяем эмоции
    emotions_keywords = {
        "грусть": ["грустно", "плохо", "тоска", "плачу", "печально", "уныло"],
        "стресс": ["не справляюсь", "загружен", "напряжение", "давит", "тяжело", "стресс", "перегружен"],
        "усталость": ["устал", "выдохся", "вымотан", "нет сил"],
        "одиночество": ["один", "одиноко", "никому", "брошен", "пусто", "никто"],
        "гнев": ["бесит", "злюсь", "раздражает", "ненавижу", "злость", "достало"]
    }
    for emotion, keywords in emotions_keywords.items():
        if any(keyword in user_input.lower() for keyword in keywords):
            user_data[user_id]["dominant_emotion"] = emotion
            break
    if not user_data[user_id]["dominant_emotion"] and any(word in user_input.lower() for word in ["не", "плохо", "тяжело"]):
        user_data[user_id]["dominant_emotion"] = "грусть"

    # Проверяем намёк на проблему
    problem_keywords = ["потому что", "из-за", "случилось", "работа", "учёба", "вуз", "дома", "человек", "друзья", "расстался", "уволили", "потерял", "сроки", "дела"]
    if any(keyword in user_input.lower() for keyword in problem_keywords):
        user_data[user_id]["problem_hint"] = True

    # Формируем запрос к ChatGPT
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *user_data[user_id]["history"]
    ]

    # Отправляем запрос к OpenAI API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.8,
        max_tokens=100
    )

    # Получаем ответ от ChatGPT
    gpt_response = response.choices[0].message["content"]

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
    elif stage == 2 and dominant_emotion:
        user_data[user_id]["stage"] = 3
    elif stage == 3 and problem_hint:
        user_data[user_id]["stage"] = 4

    # Кастомные ответы на эмоции на этапе 2 или 3
    if dominant_emotion and stage in [2, 3] and user_input.lower() in emotions_keywords[dominant_emotion]:
        gpt_response = random.choice(EMOTION_RESPONSES[dominant_emotion])

    # Решение и подписка на этапе 4
    if stage == 4 and problem_hint and not solution_offered:
        user_data[user_id]["solution_offered"] = True  # Передаём ChatGPT управление решением
    elif stage == 4 and solution_offered:
        gpt_response = (
            "Если хочешь, можем поболтать об этом побольше — у меня есть друг, другой бот, где профи помогут разобраться глубже. Хочешь попробовать? 😌"
        )

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
