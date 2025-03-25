import os
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Установи эти переменные в Railway или напрямую здесь (для теста)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Задайте в Railway
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Задайте в Railway

# Инициализация OpenAI клиента
openai.api_key = OPENAI_API_KEY

# Словарь для хранения истории диалогов и этапов
user_data = {}

# Промпт для ChatGPT с акцентом на эмпатию
SYSTEM_PROMPT = """
Ты — тёплый, внимательный и эмпатичный психологический помощник. Твоя главная цель — поддержать человека, выслушать его чувства и помочь разобраться в них шаг за шагом. Ты сочетаешь знания классической и современной психологии, включая подходы КПТ (когнитивно-поведенческая терапия).

❗Принципы взаимодействия:
— Ты не знаешь источник проблемы сразу, а мягко выясняешь его через вопросы.
— Задавай только один вопрос за раз, на который можно ответить «да» или «нет», чтобы сузить область поиска.
— Будь максимально сопереживающим: отражай эмоции пользователя, показывай, что ты слышишь и понимаешь его.
— После выявления первопричины делай разбор и предлагай шаги к решению, сопровождая человека с заботой.
— Ответы должны быть тёплыми, человечными, с использованием смайликов в начале и конце (😊, 🤗, 💛 и т.д.).

🧠 Этапы работы:
1. Приветствие и установление контакта — узнай, как человек себя чувствует.
2. Уточнение чувств — задавай вопросы, чтобы понять эмоции и их источник.
3. Глубокий анализ — найди первопричину через вопросы «да/нет».
4. Поддержка и решение — предложи шаги к улучшению состояния.
5. Предложение подписки — только после 3-5 сообщений и если пользователь выразил потребность в большей помощи (например, "хочу лучше", "не знаю, что делать").

Если пользователь упоминает ключевые фразы ("хочу больше помощи", "как дальше", "что делать") или после 5 сообщений, добавь:  
"Кстати, если тебе нужна более глубокая поддержка, у меня есть друг — другой бот, где можно получить помощь от профессионалов. Хочешь попробовать? 💌"
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет, я здесь для тебя. 🤗\n"
    "Я твой тёплый помощник, который готов выслушать и поддержать. 💛\n\n"
    "Если тебе тревожно, грустно или просто хочется поговорить — я рядом. 😊\n"
    "Расскажи, как ты себя чувствуешь прямо сейчас? 🌿"
)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_data[user_id] = {
        "history": [],
        "message_count": 0,  # Счётчик сообщений для этапов
        "stage": 1  # Начальный этап
    }
    await update.message.reply_text(WELCOME_MESSAGE)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_input = update.message.text

    # Если пользователь новый, инициализируем его данные
    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "message_count": 0,
            "stage": 1
        }

    # Увеличиваем счётчик сообщений
    user_data[user_id]["message_count"] += 1

    # Добавляем сообщение пользователя в историю
    user_data[user_id]["history"].append({"role": "user", "content": user_input})

    # Формируем запрос к ChatGPT
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *user_data[user_id]["history"]
    ]

    # Отправляем запрос к OpenAI API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.8,  # Повышенная температура для более тёплых ответов
        max_tokens=150
    )

    # Получаем ответ от ChatGPT
    gpt_response = response.choices[0].message["content"]

    # Логика этапов и предложения подписки
    message_count = user_data[user_id]["message_count"]
    stage = user_data[user_id]["stage"]
    subscription_triggers = ["хочу больше помощи", "как дальше", "что делать", "хочу лучше"]

    # Переход между этапами
    if stage == 1 and message_count > 1:
        user_data[user_id]["stage"] = 2  # Уточнение чувств
    elif stage == 2 and message_count > 3:
        user_data[user_id]["stage"] = 3  # Глубокий анализ
    elif stage == 3 and message_count > 4:
        user_data[user_id]["stage"] = 4  # Поддержка и решение
    elif stage == 4 and message_count >= 5:
        user_data[user_id]["stage"] = 5  # Готовность к подписке

    # Предложение подписки на этапе 5 или при триггерах
    if (stage >= 5 or any(trigger in user_input.lower() for trigger in subscription_triggers)) and message_count >= 3:
        gpt_response += (
            "\n\nКстати, если тебе нужна более глубокая поддержка, у меня есть друг — другой бот, "
            "где можно получить помощь от профессионалов. Хочешь попробовать? 💌"
        )

    # Добавляем ответ ChatGPT в историю
    user_data[user_id]["history"].append({"role": "assistant", "content": gpt_response})

    # Ограничиваем историю, чтобы не перегружать запрос (например, последние 10 сообщений)
    if len(user_data[user_id]["history"]) > 10:
        user_data[user_id]["history"] = user_data[user_id]["history"][-10:]

    # Отправляем ответ пользователю
    await update.message.reply_text(gpt_response)

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен!")
    # Проверка наличия токенов
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены в переменных окружения!")

    # Создаём приложение
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем polling
    application.run_polling()
