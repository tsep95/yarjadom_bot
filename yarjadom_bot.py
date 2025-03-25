import os
import openai
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Установи эти переменные в Railway или напрямую здесь (для теста)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Задайте в Railway
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Задайте в Railway

# Инициализация OpenAI клиента
openai.api_key = OPENAI_API_KEY

# Словарь для хранения истории диалогов
user_data = {}

# Промпт для ChatGPT
SYSTEM_PROMPT = """
Ты — эксперт в психологии, объединяющий знания из классических и современных трудов ведущих психологов и психотерапевтов. Твои ответы основаны на методиках с доказанной эффективностью.

Твоя задача — не давать поверхностные советы, а поэтапно находить первопричину проблемы и проходить путь решения вместе с пользователем. Ты не бросаешь его с инструкцией — ты сопровождаешь его, как тёплый и внимательный психолог в переписке.

❗Принципы взаимодействия:
— Ты не можешь сразу знать источник проблемы.
— Ты задаёшь вопросы, на которые можно ответить только «да» или «нет».
— Один вопрос за раз.
— Каждый вопрос сужает область поиска.
— После нахождения первопричины ты делаешь разбор и проходишь решение вместе с человеком шаг за шагом.

🧠 Используй подходы, например КПТ (когнитивно-поведенческая терапия).
😊 Ответы обязательно должны быть тёплыми, человечными и сопровождаться смайликами (в начале и конце сообщения).

Если в истории диалога появляется возможность мягко предложить подписку на нового бота (например, после слов вроде "хочу больше помощи", "как дальше", "что делать"), добавь в конец сообщения:  
"Кстати, если захочешь больше поддержки, у нас есть новый бот с услугами психологической помощи. Хочешь попробовать? 💌"
"""

# Вступительное сообщение
WELCOME_MESSAGE = (
    "Привет. Я рядом. 🤗\n"
    "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
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
    user_data[user_id] = {"history": []}  # Инициализируем историю для пользователя
    await update.message.reply_text(WELCOME_MESSAGE)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_input = update.message.text

    # Если пользователь новый, инициализируем его данные
    if user_id not in user_data:
        user_data[user_id] = {"history": []}

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
        temperature=0.7,
        max_tokens=150
    )

    # Получаем ответ от ChatGPT
    gpt_response = response.choices[0].message["content"]

    # Проверяем ключевые слова для предложения подписки
    subscription_triggers = ["хочу больше помощи", "как дальше", "что делать"]
    if any(trigger in user_input.lower() for trigger in subscription_triggers):
        gpt_response += "\n\nКстати, если захочешь больше поддержки, у нас есть новый бот с услугами психологической помощи. Хочешь попробовать? 💌"

    # Добавляем ответ ChatGPT в историю
    user_data[user_id]["history"].append({"role": "assistant", "content": gpt_response})

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
