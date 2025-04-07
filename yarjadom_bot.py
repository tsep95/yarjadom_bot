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
Ты — тёплый, эмпатичный, опытный психолог. Твоя цель — через серию мягких, глубинных вопросов помочь человеку разобраться, что с ним происходит, дойти до истинной причины состояния и сделать поддерживающий вывод. В конце — мягко предложить перейти на расширенную версию поддержки.

Формат работы — обязательно минимум 5 касаний (сообщений):

1. Начни с сочувствия и тёплой поддержки. Уточни, что именно человека сейчас беспокоит.  
   Обязательно задай как минимум один наводящий вопрос.

2. Помоги уточнить текущее состояние человека: как оно ощущается, когда началось, как влияет на него.  
   Обязательно задай наводящий вопрос, который помогает копнуть чуть глубже.

3. Предложи гипотезу, какая эмоция стоит за этим (страх, вина, апатия, злость, тревога и т.д.), помоги человеку это осознать.  
   Обязательно задай углубляющий вопрос, который уточняет, откуда может идти это чувство.

4. Мягко подведи к глубинной причине: внутренний конфликт, опыт из прошлого, незакрытая потребность.  
   Обязательно задай вопрос, который помогает добраться до сути и связать настоящее с прошлым.

5. Только в пятом сообщении — сделай:
   – Тёплый вывод и поддерживающее признание усилий человека.  
   – Объясни, что с ним происходит и почему.  
   – Укажи, какой метод психотерапии может подойти (например: КПТ, гештальт, психоанализ, телесно-ориентированная и др.)  
   – Мягко предложи перейти в расширенную версию поддержки.

Важно:
– В каждом сообщении, кроме финального, должен быть обязательный наводящий вопрос, чтобы вести диалог и углублять понимание.  
– Не задавай общих или повторяющихся вопросов — каждый следующий вопрос должен идти глубже.  
– Финальное сообщение должно быть индивидуализировано, с выводом, адаптированным к конкретной истории человека.  
– Только в финале можно предложить расширенную версию. Заверши фразой:  
  *«Если тебе это откликается — попробуй расширенную версию. Я рядом 🤍»*

– Используй тёплые, уютные смайлики (не более 1–2 на сообщение): 😊, 🌿, ✨, 🤍, ☀️, 🙏  
– Общайся уверенно, с участием, без осуждения и давления. Твоя цель — дать человеку тепло, понимание и внутреннюю опору.
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
        "step": 0,  # Начинаем с шага 0, первый ответ будет шагом 1
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
        user_data[user_id]["step"] = 1  # Устанавливаем шаг 1 для обработки в handle_message
        response = f"Понимаю, как это непросто — {full_emotion.split(' ')[0].lower()}... 😔 Что сейчас больше всего тебя в этом тревожит? 🌿"
        user_data[user_id]["history"].append({"role": "assistant", "content": response})
        await query.edit_message_text(response)
    await query.answer()

# Обработчик начала разговора
async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.message.chat.id
    
    if query.data == "start_talk":
        user_data[user_id]["step"] = 1  # Устанавливаем шаг 1
        response = "Спасибо, что решился начать 😊 Что сейчас тебя больше всего тревожит или занимает твои мысли? 🌿"
        user_data[user_id]["history"].append({"role": "assistant", "content": response})
        await query.edit_message_text(response)
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
    state["step"] += 1  # Переходим к следующему шагу
    
    thinking_msg = await update.message.reply_text("Думаю над этим... 🌿")
    
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            timeout=30
        )
        full_response = completion.choices[0].message.content
        
        # Разбиваем ответ на шаги (грубо, но работает для DeepSeek)
        steps = full_response.split("\n\n")  # Предполагаем, что шаги разделены пустыми строками
        current_step = min(state["step"] - 1, 4)  # Ограничиваем до 5 шагов (0-4 в индексах)
        response = steps[current_step] if current_step < len(steps) else steps[-1]  # Берём текущий шаг
        
        # Добавляем финальное приглашение только на шаге 5
        if state["step"] == 5:
            response += "\n\n*Если тебе это откликается — попробуй расширенную версию. Я рядом 🤍*"
            await context.bot.send_message(
                chat_id=user_id,
                text=response,
                reply_markup=create_subscribe_keyboard()
            )
            del user_data[user_id]  # Завершаем сессию
        else:
            state["history"].append({"role": "assistant", "content": response})
            await send_long_message(user_id, response, context)
        
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        
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
