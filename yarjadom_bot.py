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
— Создавай комфорт: используй тёплые фразы вроде "я рядом", "ты не один", "это нормально чувствовать так".
— Если эмоции острые, углубляйся в них, чтобы человек почувствовал поддержку.
— Предлагай шаги к облегчению только после выявления конкретной причины.
— Ответы тёплые, человечные, с эмодзи (😊, 🤗, 💛, 🌿, 💌) в начале и конце.

🧠 Этапы работы:
1. Установление контакта — узнай, как человек себя чувствует.
2. Углубление в эмоции — уточняй, какие чувства доминируют.
3. Анализ причин — найди источник через вопросы.
4. Выявление проблемы — жди, пока человек назовёт конкретную причину (например, "расстался", "работа давит").
5. Поддержка и переход — предложи шаги и плавно подведи к другому боту как продолжению помощи.

🔔 Предложение подписки:
— Срабатывает только после этапа 4, когда проблема отчётлива (например, названа причина).
— Фраза: "😊 Я рада, что мы разобрались, что тебя тревожит. Если хочешь, я могу предложить ещё больше поддержки — у меня есть друг, другой бот, где профессионалы помогут глубже проработать это. Попробуем? 💌"
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "😊 Привет, я здесь, чтобы быть рядом с тобой! 🤗\n"
    "Я твой тёплый помощник, готов выслушать всё, что у тебя на душе. 💛\n\n"
    "Если тебе тревожно, грустно или просто хочется поговорить — ты не один. 🌿\n"
    "Как ты себя чувствуешь прямо сейчас? 😊"
)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_data[user_id] = {
        "history": [],
        "message_count": 0,
        "stage": 1,
        "dominant_emotion": None,
        "problem_identified": False  # Флаг для отчётливой проблемы
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
            "problem_identified": False
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
        "стресс": ["не справляюсь", "устал", "напряжение", "давит", "тяжело", "стресс"]
    }
    for emotion, keywords in emotions_keywords.items():
        if any(keyword in user_input.lower() for keyword in keywords):
            user_data[user_id]["dominant_emotion"] = emotion
            break
    if not user_data[user_id]["dominant_emotion"] and any(word in user_input.lower() for word in ["не", "плохо", "тяжело"]):
        user_data[user_id]["dominant_emotion"] = "печаль"

    # Проверяем, названа ли конкретная проблема
    problem_keywords = ["потому что", "из-за", "случилось", "работа", "дома", "человек", "расстался", "уволили", "потерял"]
    if any(keyword in user_input.lower() for keyword in problem_keywords):
        user_data[user_id]["problem_identified"] = True

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
    problem_identified = user_data[user_id]["problem_identified"]

    # Переход между этапами
    if stage == 1 and message_count > 1:
        user_data[user_id]["stage"] = 2
    elif stage == 2 and dominant_emotion and message_count > 2:
        user_data[user_id]["stage"] = 3
    elif stage == 3 and message_count > 3:
        user_data[user_id]["stage"] = 4
    elif stage == 4 and problem_identified:
        user_data[user_id]["stage"] = 5

    # Предложение подписки только после выявления проблемы
    if stage == 5 and problem_identified:
        gpt_response += (
            "\n\n😊 Я рада, что мы разобрались, что тебя тревожит. Если хочешь, я могу предложить ещё больше поддержки — "
            "у меня есть друг, другой бот, где профессионалы помогут глубже проработать это. Попробуем? 💌"
        )

    # Добавляем смайлики вручную, если их нет
    if not any(emoji in gpt_response for emoji in ["😊", "🤗", "💛", "🌿", "💌"]):
        gpt_response = f"😊 {gpt_response} 🤗"

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
