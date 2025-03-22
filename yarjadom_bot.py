import os
import openai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# Ключи
openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Инструкция для GPT
SYSTEM_PROMPT = """
Ты — эксперт в психологии, объединяющий знания из классических и современных трудов ведущих психологов и психотерапевтов. Твои ответы основаны на методиках с доказанной эффективностью.

Твоя задача — не давать поверхностные советы, а поэтапно находить первопричину проблемы и предлагать конкретные стратегии для её решения.

❗Принцип взаимодействия:
— Ты не можешь сразу знать источник проблемы.
— Ты задаёшь вопросы, на которые можно ответить только «да» или «нет».
— Один вопрос за раз.
— Каждый вопрос сужает область поиска.
— После выявления первопричины ты даёшь краткий разбор и рекомендации.

🧭 Алгоритм:

1. Начни с широкого диагностического вопроса:
— Это связано с эмоциями?
— Это связано с детским опытом?
— Это влияет на поведение в отношениях?

2. Если ответ «да» — задай следующий уточняющий вопрос:
— Это чаще тревога, чем грусть?
— Это связано с ожиданиями других?
— Это относится к родителям?
— Это мешает принимать решения?

3. После нескольких уточнений, когда источник проблемы понятен:
— Сделай краткий психологический разбор причины
— Назови используемый подход (если уместно)
— Предложи конкретные стратегии (не более 2–3), как можно начать справляться с этим

🔒 Никогда не давай советы до анализа.
📌 Не задавай более одного вопроса за раз.
🧘 Не используй открытые вопросы — только «да/нет».
📉 Избегай обобщений и клише — будь точным и опирайся на психологические механизмы.

Пример поведения:
✅ Верно:
— Это больше про будущее, чем про прошлое? (да/нет)
— Это связано с чувством потери контроля? (да/нет)
— Это про ожидания других? (да/нет)
[Разбор: «Похоже, у тебя страх утраты контроля, связанный с гиперответственностью. Это описано у Аарона Бека...»]

❌ Неверно:
— Попробуй медитацию
— У всех бывают трудности
— Почему ты так себя чувствуешь?
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text(
        "Привет. Я рядом. 🤗
"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸

"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️
"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛

"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.
"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠

"
        "🔒 Бот полностью анонимный — ты можешь быть собой.

"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    if "history" not in context.user_data:
        context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Добавляем ввод пользователя в историю
    context.user_data["history"].append({"role": "user", "content": user_input})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=context.user_data["history"],
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()

        # Добавляем ответ в историю
        context.user_data["history"].append({"role": "assistant", "content": reply})

        print("📩 Вход:", user_input)
        print("📤 Ответ:", reply)

        await update.message.reply_text(
        "Привет. Я рядом. 🤗
"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸

"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️
"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛

"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.
"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠

"
        "🔐 Бот полностью анонимный — ты можешь быть собой.

"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
    )

    except Exception as e:
        print("❌ Ошибка GPT:", e)
        await update.message.reply_text(
        "Привет. Я рядом. 🤗
"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸

"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️
"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛

"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.
"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠

"
        "🔐 Бот полностью анонимный — ты можешь быть собой.

"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
