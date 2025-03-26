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

# Обновлённый промпт с акцентом на острые эмоции
SYSTEM_PROMPT = """
Ты — тёплый, эмпатичный и чуткий психологический помощник. Твоя цель — глубоко понять чувства человека, поддержать его и помочь разобраться в эмоциях шаг за шагом. Ты работаешь с острыми состояниями: страхом, одиночеством, гневом, печалью, стрессом. Используй знания классической и современной психологии, включая КПТ.

❗Принципы взаимодействия:
— Ты не предполагаешь источник проблемы сразу, а мягко выясняешь его через вопросы, фокусируясь на эмоциях.
— Задавай один вопрос за раз (на «да/нет»), чтобы углубиться в чувства и их причины.
— Будь предельно сопереживающим: отражай эмоции, показывай, что слышишь и понимаешь человека.
— Если эмоции острые (страх, одиночество, гнев, печаль, стресс), углубляйся в них, чтобы человек почувствовал, что его слышат.
— После выявления первопричины предлагай шаги к облегчению с заботой и намёком, что более глубокая работа возможна.
— Ответы тёплые, человечные, с эмодзи (😊, 🤗, 💛).

🧠 Этапы работы:
1. Установление контакта — узнай, как человек себя чувствует сегодня.
2. Углубление в эмоции — уточняй, какие чувства доминируют (страх, гнев, печаль и т.д.).
3. Анализ причин — через вопросы найди источник острого состояния.
4. Поддержка и шаги — предложи простые действия и намекни на более глубокую помощь.
5. Предложение продолжения — если эмоции сильные или после 3-5 сообщений, предложи подписку как заботу.

🔔 Если человек упоминает острые эмоции или фразы вроде "мне страшно", "я один", "всё бесит", "грустно", "не справляюсь", или после 5 сообщений, добавь:
"Знаешь, я вижу, как тебе непросто. 🤗 Если хочешь, у меня есть друг — другой бот, где профессионалы помогут глубже разобраться с этим. Попробуем? 💌"
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет, я здесь, чтобы тебя поддержать. 🤗\n"
    "Я твой тёплый помощник, готов выслушать всё, что у тебя на душе. 💛\n\n"
    "Если тебе страшно, одиноко или просто тяжело — расскажи мне. 😊\n"
    "Как ты себя чувствуешь прямо сейчас? 🌿"
)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_data[user_id] = {
        "history": [],
        "message_count": 0,
        "stage": 1,
        "dominant_emotion": None  # Добавляем поле для отслеживания ключевой эмоции
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
            "dominant_emotion": None
        }

    # Увеличиваем счётчик сообщений
    user_data[user_id]["message_count"] += 1

    # Добавляем сообщение пользователя в историю
    user_data[user_id]["history"].append({"role": "user", "content": user_input})

    # Определяем доминирующую эмоцию (грубо, на основе ключевых слов)
    emotions_keywords = {
        "страх": ["страшно", "боюсь", "тревожно", "пугает"],
        "одиночество": ["один", "одиноко", "никому", "брошен"],
        "гнев": ["бесит", "злюсь", "раздражает", "ненавижу"],
        "печаль": ["грустно", "плохо", "тоска", "плачу"],
        "стресс": ["не справляюсь", "устал", "напряжение", "давит"]
    }
    for emotion, keywords in emotions_keywords.items():
        if any(keyword in user_input.lower() for keyword in keywords):
            user_data[user_id]["dominant_emotion"] = emotion
            break

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
        max_tokens=200  # Увеличиваем токены для более глубоких ответов
    )

    # Получаем ответ от ChatGPT
    gpt_response = response.choices[0].message["content"]

    # Логика этапов и предложения подписки
    message_count = user_data[user_id]["message_count"]
    stage = user_data[user_id]["stage"]
    dominant_emotion = user_data[user_id]["dominant_emotion"]

    # Переход между этапами
    if stage == 1 and message_count > 1:
        user_data[user_id]["stage"] = 2  # Углубление в эмоции
    elif stage == 2 and message_count > 2 and dominant_emotion:
        user_data[user_id]["stage"] = 3  # Анализ причин
    elif stage == 3 and message_count > 3:
        user_data[user_id]["stage"] = 4  # Поддержка и шаги
    elif stage == 4 and message_count >= 5:
        user_data[user_id]["stage"] = 5  # Предложение продолжения

    # Триггеры для предложения подписки
    subscription_triggers = [
        "мне страшно", "я один", "всё бесит", "грустно", "не справляюсь",
        "хочу больше помощи", "как дальше", "что делать", "хочу лучше"
    ]
    if (stage >= 5 or dominant_emotion or any(trigger in user_input.lower() for trigger in subscription_triggers)) and message_count >= 3:
        gpt_response += (
            "\n\nЗнаешь, я вижу, как тебе непросто. 🤗 Если хочешь, у меня есть друг — другой бот, "
            "где профессионалы помогут глубже разобраться с этим. Попробуем? 💌"
        )

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
