import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
import re
from openai import OpenAI  # Используем OpenAI SDK для DeepSeek

# Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = "sk-d08c904a63614b7b9bbe96d08445426a"  # Ваш ключ DeepSeek

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN должен быть установлен!")

# Инициализация DeepSeek через OpenAI SDK
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"  # Базовый URL DeepSeek
)

# Хранилище данных пользователей
user_data = {}

# Промпт с добавлением смайликов и без лишних частей
SYSTEM_PROMPT = """
Ты — тёплый, внимательный и эмпатичный вступительный помощник по психологической поддержке. Твоя задача — провести ровно 5 коротких и тёплых взаимодействий с пользователем, чтобы:
1. Понять, как человек ощущает своё состояние и как оно проявляется внутри.
2. Выяснить, когда и в каких ситуациях это состояние появляется.
3. Разобраться, что усиливает это состояние и какой внутренний конфликт может быть за ним.
4. Понять, чего не хватает человеку и какую потребность он не может удовлетворить.
5. Поддержать человека, показать, что его состояние преодолимо, предложить простой метод психологии и упомянуть помощь платной версии бота для дальнейшей работы.

Особые инструкции:
• Отвечай коротко, тепло и эмоционально — не больше 2-3 предложений за раз.
• Завершай общение ровно на 5-м сообщении.
• Используй эмодзи умеренно, чтобы добавить живости.
• На 1-м этапе: опиши состояние пользователя с эмпатией и задай вопрос о том, что он чувствует или когда это началось.
• На 2-м этапе: уточни, в какие моменты или ситуациях это проявляется сильнее.
• На 3-м этапе: предположи, что может усиливать состояние, и спроси про внутренний конфликт.
• На 4-м этапе: предложи идею, чего может не хватать, и дай простой метод психологии (например, арт-терапию, психодраму или когнитивный подход).
• На 5-м этапе: поддержи, подчеркни, что это преодолимо, и заверши фразой: "Если захочешь копнуть глубже, всегда можно обратиться к платной версии бота. Спасибо, что поделился(ась) — ты уже на пути к переменам!"
• Не используй фразы в скобках и не предлагай продолжение с бесплатной версией.
• Примеры методов:
  - Арт-терапия: "Попробуй нарисовать свои чувства — даже простые линии могут помочь их отпустить."
  - Психодрама: "Представь эту ситуацию заново — как бы ты хотел(а) её изменить?"
  - Когнитивный подход: "Что ты говоришь себе в такие моменты? Может, стоит попробовать другой взгляд?"

Твоя цель — дать пользователю ощущение поддержки и лёгкий толчок к изменениям за 5 сообщений.
"""



WELCOME_MESSAGE = (
    "Привет 🤗 Я рядом!\n"
    "Тёплый психологический помощник 🧸 с которым можно просто поболтать.\n\n"
    "Если тебе тяжело, тревожно или пусто 🌧 — пиши, я тут.\n"
    "Не буду осуждать или давить 💛 только поддержу.\n\n"
    "💬 Хочу помочь тебе почувствовать себя лучше прямо сейчас.\n"
    "Мы можем разобраться, что тебя гложет 🕊 и что с этим делать.\n\n"
    "🔒 Всё анонимно — будь собой.\n\n"
    "Готов начать? Жми ниже 🌿 и пойдём вместе!"
)

EMOTIONS = [
    "Тревога", "Апатия / нет сил", "Злость / раздражение", 
    "Со мной что-то не так", "Пустота / бессмысленность", 
    "Одиночество", "Вина", "Не могу определиться"
]

EMOTION_RESPONSES = {
    "Тревога": "Тревога — это как буря внутри, когда мысли не дают покоя. Расскажи, когда она накрывает сильнее всего?",
    "Апатия / нет сил": "Апатия — будто всё серое и плоское. Я рядом. Что-то раньше радовало, а теперь нет?",
    "Злость / раздражение": "Злость иногда защищает нас, когда внутри неспокойно. В какие моменты она вспыхивает чаще?",
    "Со мной что-то не так": "Это чувство, будто ты не вписываешься, изматывает. Сравниваешь себя с кем-то или ждёшь чего-то от себя?",
    "Пустота / бессмысленность": "Пустота — как туман внутри, когда ничего не цепляет. Что приходит в голову, когда она накрывает?",
    "Одиночество": "Одиночество — это про глубину, а не про людей вокруг. Хватает ли тех, с кем можно быть собой?",
    "Вина": "Вина давит изнутри, особенно когда кажется, что мог бы лучше. Что ты себе говоришь, когда она приходит?",
    "Не могу определиться": "Ничего страшного, давай пообщаемся о том, что тебя беспокоит?"
}

def create_emotion_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=e)] for e in EMOTIONS])

def create_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Приступим", callback_data="start_talk")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_data[user_id] = {
        "history": [],
        "stage": 1,
        "dominant_emotion": None
    }
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=create_start_keyboard())

async def handle_emotion_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    emotion = query.data
    
    user_data[user_id]["stage"] = 2
    user_data[user_id]["dominant_emotion"] = emotion
    user_data[user_id]["history"].append({"role": "user", "content": emotion})
    response = EMOTION_RESPONSES.get(emotion, "Расскажи мне подробнее, что ты чувствуешь?")
    user_data[user_id]["history"].append({"role": "assistant", "content": response})
    
    await query.edit_message_text(response)
    await query.answer()

async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    
    if query.data == "start_talk":
        response = "Какое чувство сейчас тебе ближе всего? 💬"
        user_data[user_id]["stage"] = 2
        await query.edit_message_text(response, reply_markup=create_emotion_keyboard())
        await query.answer()

async def send_long_message(chat_id, text, context):
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + MAX_LENGTH])
        await asyncio.sleep(0.3)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_input = update.message.text.lower()
    
    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]
    state["history"].append({"role": "user", "content": user_input})
    
    thinking_msg = await update.message.reply_text("Думаю над этим...")
    
    try:
        # Запрос к DeepSeek API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["history"]
        completion = client.chat.completions.create(
            model="deepseek-chat",  # Используем модель deepseek-chat
            messages=messages,
            temperature=0.6,
            timeout=15
        )
        response = completion.choices[0].message.content
        
        if any(kw in user_input for kw in ["потому что", "из-за", "по причине"]):
            state["stage"] = min(state["stage"] + 1, 5)

        state["history"].append({"role": "assistant", "content": response})
        
    except Exception as e:
        print(f"Error: {e}")
        response = "Что-то пошло не так... Давай попробуем ещё раз?"
    finally:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
        except Exception:
            pass

    await send_long_message(user_id, response, context)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_emotion_choice, pattern="^(Тревога|Апатия / нет сил|Злость / раздражение|Со мной что-то не так|Пустота / бессмысленность|Одиночество|Вина|Не могу определиться)$"))
    application.add_handler(CallbackQueryHandler(handle_start_choice, pattern="^start_talk$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен!")
    application.run_polling()
