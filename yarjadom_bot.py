import os
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
import openai

# Настройка этапов диалога
GREETING, ANALYSIS, DEEP_ANALYSIS, SOLUTION, SUBSCRIPTION = range(5)

# Конфигурация OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Хранилище состояний пользователей (для продакшена лучше использовать БД)
user_states = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

async def start(update: Update, context: CallbackContext) -> int:
    welcome_message = (
        "Привет! Я рядом. 🤗\n"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
        "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
    )
    
    await update.message.reply_text(welcome_message)
    user_states[update.effective_chat.id] = {
        "stage": GREETING,
        "history": [{"role": "system", "content": "Ты опытный психолог..."}]
    }
    return GREETING

def generate_gpt_response(prompt: str, chat_id: int) -> str:
    try:
        user_states[chat_id]["history"].append({"role": "user", "content": prompt})
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=user_states[chat_id]["history"],
            temperature=0.7,
            max_tokens=500
        )
        
        assistant_reply = response.choices[0].message['content']
        user_states[chat_id]["history"].append({"role": "assistant", "content": assistant_reply})
        
        return assistant_reply
    
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "Кажется, я временно не могу ответить. 🫣 Давай попробуем ещё раз?"

async def handle_message(update: Update, context: CallbackContext) -> int:
    chat_id = update.effective_chat.id
    user_input = update.message.text
    
    if chat_id not in user_states:
        return await start(update, context)
    
    current_stage = user_states[chat_id]["stage"]
    
    # Логика перехода между этапами
    if current_stage == GREETING:
        response = generate_gpt_response(f"Пользователь ответил: {user_input}. Начни сессию с вопроса 'да/нет' по методике КПТ", chat_id)
        user_states[chat_id]["stage"] = ANALYSIS
    
    elif current_stage == ANALYSIS:
        response = generate_gpt_response(f"Ответ: {user_input}. Задай следующий уточняющий вопрос 'да/нет'", chat_id)
        user_states[chat_id]["stage"] = DEEP_ANALYSIS
    
    elif current_stage == DEEP_ANALYSIS:
        response = generate_gpt_response(f"Ответ: {user_input}. Перейди к глубокому анализу проблемы", chat_id)
        user_states[chat_id]["stage"] = SOLUTION
    
    elif current_stage == SOLUTION:
        response = generate_gpt_response(f"Ответ: {user_input}. Предложи решение и мягко упомяни о подписке", chat_id)
        user_states[chat_id]["stage"] = SUBSCRIPTION
    
    else:
        response = generate_gpt_response(user_input, chat_id)
    
    await update.message.reply_text(response)
    return user_states[chat_id]["stage"]

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Всегда буду рад помочь снова! 💖")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GREETING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ANALYSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            DEEP_ANALYSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            SOLUTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            SUBSCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
