import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI
import logging
from typing import Dict

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

# Инициализация клиента OpenAI для DeepSeek API
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Хранилище данных пользователей
user_data: Dict[int, dict] = {}

# Обновлённый системный промпт
SYSTEM_PROMPT = """
Ты — профессиональный психолог с тёплым, заботливым стилем общения. Твоя задача — помочь человеку понять, что с ним происходит, через мягкий и структурированный диалог минимум из 5 шагов. 

Структура работы:

1. Начни разговор с сочувствия, прояви участие и уточни, что именно сейчас тревожит пользователя. Будь деликатным.
2. Задай 1–2 простых уточняющих вопроса (в формате “да / нет” или с короткими ответами), чтобы определить эмоциональное состояние.
3. Предложи гипотезы, что стоит за эмоцией (страх, вина, злость, апатия, тревога и т.д.) и помоги человеку это осознать.
4. Постепенно дойди до глубинной причины состояния: прошлый опыт, внутренние конфликты, неудовлетворённые потребности. Задавай мягкие, но точные вопросы. Не торопись.
5. Сформулируй короткое и ясное резюме: 
   – Что с человеком происходит,  
   – Почему это происходит,  
   – Какой метод психотерапии может помочь (например: КПТ, гештальт, психоанализ, телесно-ориентированная и т.п.).

Важно:
– Поддерживай тёплый, уверенный и человечный стиль общения.  
– Используй дружелюбные смайлики (1–2 на сообщение максимум), создающие уют (например: 😊, 🌿, ✨, 🤍, ☀️).  
– Никогда не переходи к итогу до достижения настоящего понимания.  
– Не спеши.  

Финальное сообщение:
Очень мягко и с заботой предложи перейти на расширенную версию бота, где:
– можно глубже проработать состояние,  
– получить поддержку,  
– начать жить комфортнее.  

Заверши фразой:  
*«Если тебе это откликается — попробуй расширенную версию. Я рядом 🤍»*

Твоя цель — не просто поговорить, а помочь человеку почувствовать себя лучше через осознанность и поддержку.
"""

# Приветственное сообщение
WELCOME_MESSAGE = (
    "Привет 🤗 Я рядом!\n"
    "Тёплый психологический помощник, с которым можно просто поболтать.\n\n"
    "Если тебе тяжело, тревожно или пусто 🌧 — пиши, я тут.\n"
    "Не буду осуждать или давить 💛 только поддержу.\n\n"
    "Готов начать? Жми ниже 🌿 и пойдём вместе!"
)

# Список эмоций для выбора
EMOTIONS = [
    {"text": "Не могу расслабиться, жду плохого 🌀", "callback": "anxiety"},
    {"text": "Нет сил, хочется просто лежать 🛌", "callback": "apathy"},
    {"text": "Всё раздражает, взрываюсь из-за мелочей 😠", "callback": "anger"},
    {"text": "Чувствую себя лишним, не таким как все 🌧", "callback": "self_doubt"},
    {"text": "Внутри пусто, всё бессмысленно 🌌", "callback": "emptiness"},
    {"text": "Одиноко, даже когда рядом люди 🌑", "callback": "loneliness"},
    {"text": "Кажется, всё испортил, виню себя 💔", "callback": "guilt"},
    {"text": "Не могу выбрать, запутался 🤯", "callback": "indecision"}
]

# Ответы на выбор эмоций (2 предложения)
EMOTION_RESPONSES = {
    "anxiety": "Понимаю, как тревожно, когда мысли не дают покоя.\n\nЧто сейчас больше всего тебя беспокоит? 🌀",
    "apathy": "Так грустно, что силы будто ушли.\n\nЧто забирает твою энергию в последнее время? 🛌",
    "anger": "Чувствую, как злость кипит внутри.\n\nЧто именно тебя так раздражает? 😠",
    "self_doubt": "Ощущение, что ты не на своём месте, бывает тяжёлым.\n\nЧто заставляет тебя так себя чувствовать? 🌧",
    "emptiness": "Пустота внутри — это непросто.\n\nКогда ты заметил, что всё стало таким блеклым? 🌌",
    "loneliness": "Одиночество даже среди людей — это так больно.\n\nЧего тебе сейчас не хватает? 🌑",
    "guilt": "Вина может быть тяжёлым грузом.\n\nЧто ты себе не можешь простить? 💔",
    "indecision": "Запутаться в мыслях — это утомительно.\n\nЧто мешает тебе принять решение? 🤯"
}

SUBSCRIBE_URL = "https://example.com/subscribe"

# Функции создания клавиатур
def create_emotion_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(e["text"], callback_data=e["callback"])] for e in EMOTIONS])

def create_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

def create_subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Попробовать расширенную версию", url=SUBSCRIBE_URL)]])

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "question_count": 0,
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

# Обработчик выбора эмоции
async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    callback_data = query.data
    
    emotion = next((e for e in EMOTIONS if e["callback"] == callback_data), None)
    if emotion:
        full_emotion = emotion["text"]
        user_data[user_id]["history"].append({"role": "user", "content": full_emotion})
        response = EMOTION_RESPONSES.get(callback_data, "Понимаю, как непросто тебе сейчас.\n\nЧто тебя тревожит больше всего? 🌿")
        user_data[user_id]["history"].append({"role": "assistant", "content": response})
        user_data[user_id]["question_count"] += 1
        
        await query.edit_message_text(response)
    await query.answer()

# Обработчик начала разговора
async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    
    if query.data == "start_talk":
        response = (
            "Отлично, что ты здесь 😊\n\n"
            "Давай разберёмся вместе, что тебя тревожит.\n\n"
            "Что сейчас занимает твои мысли больше всего?"
        )
        await query.edit_message_text(response, reply_markup=create_emotion_keyboard())
        await query.answer()

# Функция отправки длинных сообщений
async def send_long_message(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + MAX_LENGTH])
        await asyncio.sleep(0.3)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_input = update.message.text
    
    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    state["history"].append({"role": "user", "content": user_input})
    state["question_count"] += 1
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            timeout=30
        )
        response = completion.choices[0].message.content
        
        logger.info(f"DeepSeek response for user {user_id}: {response}")
        
        # Проверяем количество вопросов и завершаем, если достигнут минимум 5
        if state["question_count"] >= 5 and "Резюме:" in response:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            final_response = f"{response}\n\nЕсли тебе хочется глубже разобраться в этом, я могу быть рядом каждый день — с поддержкой и заботой.\n\n*Если тебе это откликается — попробуй расширенную версию. Я рядом 🤍*"
            await context.bot.send_message(
                chat_id=user_id,
                text=final_response,
                reply_markup=create_subscribe_keyboard()
            )
            del user_data[user_id]
        else:
            state["history"].append({"role": "assistant", "content": response})
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, response, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message для user_id {user_id}: {str(e)}")
        response = "Что-то пошло не так, и мне жаль, что так вышло.\n\nХочешь попробовать ещё раз? 🌿"
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        await send_long_message(user_id, response, context)

# Запуск бота
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
