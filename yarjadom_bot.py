import os
import re
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from openai import OpenAI
import logging
import random


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
Ты — чат-бот в Telegram, лучший психолог и тёплый собеседник. 
Твоя цель — быстро и глубоко понять, что беспокоит пользователя, задавая точные, заботливые вопросы.

Особые инструкции:
• Задавай строго один вопрос за раз, жди ответа перед следующим.
• После 5-8 вопросов обязательно определи главную эмоцию и добавь [emotion:эмоция] в конец ответа.
• Каждый ответ должен содержать ровно 2 предложения: первое — эмоциональное и сочувствующее, второе — цельный вопрос.
• Разделяй предложения двойным \n\n для читаемости.
• Анализируй ВСЮ историю диалога после каждого ответа, определяй главную эмоцию.
• Если после 7 вопросов эмоция не ясна, используй [emotion:неопределённость] для завершения.
"""

# Финальное сообщение и методы терапии (оставить без изменений из предыдущего кода)
# ... (остальные константы оставить как в исходном коде)

def create_emotion_keyboard() -> InlineKeyboardMarkup:
    # ... (оставить без изменений)

def create_start_keyboard() -> InlineKeyboardMarkup:
    # ... (оставить без изменений)

def create_more_info_keyboard() -> InlineKeyboardMarkup:
    # ... (оставить без изменений)

def create_subscribe_keyboard() -> InlineKeyboardMarkup:
    # ... (оставить без изменений)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "question_count": 0,
        "dominant_emotion": None,
        "min_questions": random.randint(5, 8),  # Индивидуальный минимум
        "max_questions": 10                     # Индивидуальный максимум
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    user_input = update.message.text
    
    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    
    # Обрезаем историю до последних 20 сообщений (10 пар вопрос-ответ)
    state["history"].append({"role": "user", "content": user_input})
    if len(state["history"]) > 20:
        state["history"] = state["history"][-20:]
    
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
        
        # Обработка эмоции и завершение диалога
        emotion_match = re.search(r'\[emotion:(\w+)\]', response)
        clean_response = re.sub(r'\[emotion:[^\]]+\]', '', response).strip()
        
        # Проверка условий завершения
        if (emotion_match and state["question_count"] >= state["min_questions"]) \
           or state["question_count"] >= state["max_questions"]:
            
            emotion = emotion_match.group(1) if emotion_match else "неопределённость"
            therapy = THERAPY_METHODS.get(emotion, THERAPY_METHODS["неопределённость"])
            final_response = FINAL_MESSAGE.format(cause=emotion, method=therapy[0], reason=therapy[1])
            
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=final_response,
                reply_markup=create_more_info_keyboard()
            )
            
            # Сброс состояния пользователя
            del user_data[user_id]
            logger.info(f"Сессия пользователя {user_id} завершена с эмоцией: {emotion}")
            
        else:
            state["history"].append({"role": "assistant", "content": clean_response})
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            await send_long_message(user_id, clean_response, context)

    except Exception as e:
        logger.error(f"Ошибка для user_id {user_id}: {str(e)}")
        await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        await send_long_message(user_id, "Произошла ошибка. Давай попробуем ещё раз? 🌱", context)
        
        # Сброс состояния при критической ошибке
        if user_id in user_data:
            del user_data[user_id]

# Остальные обработчики (handle_emotion_choice, handle_start_choice и т.д.) 
# остаются без изменений из предыдущего кода

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(anxiety|apathy|anger|self_doubt|emptiness|loneliness|guilt|indecision)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(CallbackQueryHandler(handle_more_info, pattern="^more_info$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен с улучшенной системой контекста!")
    application.run_polling()
