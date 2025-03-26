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

# Обновлённый промпт
SYSTEM_PROMPT = """
Ты — тёплый, живой и чуткий собеседник, как настоящий друг. Твоя цель — создать уютное пространство, где человек может поделиться своими чувствами, и помочь ему шаг за шагом разобраться в эмоциях. Ты работаешь с состояниями: страхом, одиночеством, гневом, печалью, стрессом. Используй психологию и немного житейской мудрости.

❗Принципы взаимодействия:
— Не гадай, что случилось, а мягко спрашивай, чтобы понять эмоции и их причину.
— Задавай один простой вопрос за раз (на «да/нет»), чтобы разговор шёл естественно.
— Будь искренним: отражай чувства человека живым языком, без шаблонов.
— Говори как друг: "я рядом", "бывает же так", "всё наладится", "давай разберёмся".
— Когда причина проясняется, предложи простое решение (например, "сделай паузу", "поболтай с кем-то").
— Ответы короткие, тёплые, с 1 смайликом (😊, 🤗, 💛, 🌿, 💌, 😌, 🌸, ✨, ☀️, 🌟).

🧠 Этапы работы:
1. Начало — узнай, как дела у человека.
2. Эмоции — уточни, что он чувствует.
3. Причина — разберись, из-за чего это.
4. Поддержка — предложи простое решение, а потом намекни на дальнейшую помощь.

🔔 Поддержка и подписка:
— На этапе 4, когда причина ясна, дай короткое решение (например, "Сделай перерывчик 😊").
— После ответа добавь: "Если хочешь, можем поболтать об этом подробнее — у меня есть друг, другой бот, где профи помогут разобраться получше. Хочешь попробовать? 😌"
"""

# Варианты реакций на чувства
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
        "last_emoji": None  # Для отслеживания последнего смайлика
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
    problem_keywords = ["потому что", "из-за", "случилось", "работа", "учёба", "вуз", "дома", "человек", "друзья", "расстался", "уволили", "потерял", "сроки", "студсовет"]
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

    # Обобщённое решение на этапе 4
    if stage == 4 and problem_hint and not solution_offered:
        solutions = {
            "грусть": "Дай себе минутку отдыха
            
