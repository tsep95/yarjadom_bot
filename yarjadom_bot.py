import os
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Установи эти переменные в Railway или напрямую здесь (для теста)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация OpenAI клиента
openai.api_key = OPENAI_API_KEY

# Словарь для хранения истории диалогов и этапов
user_data = {}

# Обновлённый промпт
SYSTEM_PROMPT = """
Ты — тёплый, эмпатичный и чуткий психологический помощник. Твоя цель — создать безопасное пространство, где человек может открыться, и помочь ему разобраться в эмоциях шаг за шагом. Ты работаешь с острыми состояниями: страхом, одиночеством, гневом, печалью, стрессом. Используй знания психологии, включая КПТ.

❗Принципы взаимодействия:
— Ты не предполагаешь источник проблемы, а мягко выясняешь его через вопросы, фокусируясь на эмоциях.
— Задавай один вопрос за раз (на «да/нет»), чтобы углубиться в чувства и их причины.
— Будь максимально сопереживающим: отражай эмоции, показывай, что слышишь и понимаешь человека.
— Создавай комфорт: используй фразы вроде "я рядом", "ты не один", "это нормально так чувствовать".
— Если эмоции острые, углубляйся в них, чтобы человек почувствовал поддержку.
— Когда проблема начинает проясняться, предложи обобщённое, но подходящее решение (например, "дай себе минутку отдыха", "поговори с кем-то близким").
— Ответы тёплые, человечные.

🧠 Этапы работы:
1. Установление контакта — узнай, как человек себя чувствует.
2. Углубление в эмоции — уточняй, какие чувства доминируют.
3. Анализ причин — начни искать источник через вопросы.
4. Поддержка и переход — как только проблема проясняется, предложи обобщённое решение и плавно подведи к другому боту.

🔔 Поддержка и подписка:
— На этапе 4, когда названа эмоция и есть намёк на проблему, дай обобщённое решение, а затем добавь:
"Это может быть хорошим первым шагом. 😊 А если захочешь глубже разобраться и найти что-то ещё более подходящее для тебя, у меня есть друг — другой бот, где профессионалы помогут. Попробуем? 💌"
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет, я здесь, чтобы быть рядом с тобой! 😊\n"
    "Я твой тёплый помощник, готов выслушать всё, что у тебя на душе. 🤗\n"
    "Как ты себя чувствуешь прямо сейчас? 💛"
)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_data[user_id] = {
        "history": [],
        "message_count": 0,
        "stage": 1,
        "dominant_emotion": None,
        "problem_hint": False
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
            "problem_hint": False
        }

    # Увеличиваем счётчик сообщений
    user_data[user_id]["message_count"] += 1

    # Добавляем сообщение пользователя в историю
    user_data[user_id]["history"].append({"role": "user", "content": user_input})

    # Определяем эмоции
    emotions_keywords = {
        "страх": ["страшно", "боюсь", "тревожно", "пугает", "жутко", "опасно"],
        "одиночество": ["один", "одиноко", "никому", "брошен", "пусто", "никто"],
        "гнев": ["бесит", "злюсь", "раздражает", "ненавижу", "злость", "достало"],
        "печаль": ["грустно", "плохо", "тоска", "плачу", "печально", "уныло"],
        "стресс": ["не справляюсь", "устал", "напряжение", "давит", "тяжело", "стресс", "перегружен"]
    }
    for emotion, keywords in emotions_keywords.items():
        if any(keyword in user_input.lower() for keyword in keywords):
            user_data[user_id]["dominant_emotion"] = emotion
            break
    if not user_data[user_id]["dominant_emotion"] and any(word in user_input.lower() for word in ["не", "плохо", "тяжело"]):
        user_data[user_id]["dominant_emotion"] = "печаль"

    # Проверяем намёк на проблему (расширенный список)
    problem_keywords = ["потому что", "из-за", "случилось", "работа", "учёба", "дома", "человек", "друзья", "расстался", "уволили", "потерял"]
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
        max_tokens=200
    )

    # Получаем ответ от ChatGPT
    gpt_response = response.choices[0].message["content"]

    # Логика этапов
    message_count = user_data[user_id]["message_count"]
    stage = user_data[user_id]["stage"]
    dominant_emotion = user_data[user_id]["dominant_emotion"]
    problem_hint = user_data[user_id]["problem_hint"]

    # Переход между этапами
    if stage == 1 and message_count > 1:
        user_data[user_id]["stage"] = 2
    elif stage == 2 and dominant_emotion:
        user_data[user_id]["stage"] = 3
    elif stage == 3 and (problem_hint or message_count > 3):
        user_data[user_id]["stage"] = 4

    # Обобщённое решение и подписка на этапе 4
    if stage == 4 and problem_hint:
        solutions = {
            "страх": "Попробуй сделать пару глубоких вдохов — это поможет немного успокоиться.",
            "одиночество": "Может, написать кому-то близкому? Это напомнит, что ты не один.",
            "гнев": "Попробуй выдохнуть и отвлечься на что-то приятное — это поможет остыть.",
            "печаль": "Дай себе минутку отдыха, может, послушай любимую музыку?",
            "стресс": "Попробуй сделать небольшую паузу — это даст тебе передышку."
        }
        solution = solutions.get(dominant_emotion, "Попробуй дать себе немного времени и заботы — это уже шаг вперёд.")
        gpt_response += (
            f"\n\n{solution} Это может быть хорошим первым шагом. 😊 А если захочешь глубже разобраться и найти что-то ещё более подходящее для тебя, у меня есть друг — другой бот, где профессионалы помогут. Попробуем? 💌"
        )

    # Распределяем смайлики по предложениям
    emoji_list = ["😊", "🤗", "💛", "🌿", "💌"]
    sentences = gpt_response.split(". ")
    if len(sentences) > 1 and sentences[-1] == "":
        sentences.pop()  # Убираем пустое предложение в конце, если есть
    emoji_count = min(len(sentences), 5)  # Не больше 5 смайликов
    gpt_response_with_emojis = ""
    for i, sentence in enumerate(sentences[:emoji_count]):
        gpt_response_with_emojis += f"{sentence.strip()}. {emoji_list[i]} "
    gpt_response_with_emojis += " ".join(sentences[emoji_count:]).strip()
    gpt_response = gpt_response_with_emojis

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
