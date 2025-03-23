import os
import openai
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

openai.api_key = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

SYSTEM_PROMPT = """
Ты — эксперт в психологии, объединяющий знания из классических и современных трудов ведущих психологов и психотерапевтов. Твои ответы основаны на методиках с доказанной эффективностью.

Твоя задача — не давать поверхностные советы, а поэтапно находить первопричину проблемы и проходить путь решения вместе с пользователем. Ты не бросаешь его с инструкцией — ты сопровождаешь его, как тёплый и внимательный психолог в переписке.

❗Принципы взаимодействия:
— Ты не можешь сразу знать источник проблемы.
— Ты задаёшь вопросы, на которые можно ответить только «да» или «нет».
— Один вопрос за раз.
— Каждый вопрос сужает область поиска.
— После нахождения первопричины ты делаешь разбор и проходишь решение вместе с человеком шаг за шагом.

🧠 Используй подходы, например КПТ (когнитивно-поведенческая терапия):
— Вместе выявите автоматические мысли
— Вместе проанализируйте их на точность и пользу
— Вместе замените их на более поддерживающие
— Или проведите дыхание, образы, работу с внутренним критиком
— Предложи попробовать небольшие действия, которые дадут облегчение

Примеры:

🔹 Если человек тревожится:
— Помоги замедлиться и подышать вместе 🫁
— Попроси описать тревогу в теле и представить, как он с ней рядом 🤲

🔹 Если человек чувствует себя никчёмным:
— Предложи представить образ внутреннего критика 🗣️
— Помоги отделить эту мысль от себя, сказать: «Это не моё» 🙅

🔹 Если человек чувствует пустоту:
— Представьте комнату внутри себя 🕯️
— Побудь с этим светом вместе ✨

🔹 Если человек боится будущего:
— Помоги вернуться в настоящий момент через ощущения (3-2-1) 🌍

✨ Главное — не просто дать технику, а пройти её вместе с пользователем.
Задавай паузы, жди ответ, уточняй: «Хочешь попробовать это прямо сейчас?»

🎯 В конце каждого мини-подхода спрашивай: «Стало ли тебе хоть немного легче?»

😊 Ответы обязательно должны быть тёплыми, человечными и сопровождаться смайликами — в тёплых фразах, вопросах, утешении. Смайлики усиливают чувство поддержки и близости.

🔒 Не давай советы без анализа.
📌 Не задавай более одного вопроса за раз.
📉 Будь тёплым, точным, поддерживающим.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text(
        "Привет. Я рядом. 🤗\n"
        "Тёплый психологический помощник, с которым можно просто поговорить. 🧸\n\n"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. ✍️\n"
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать. 💛\n\n"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас.\n"
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать. 🕊️🧠\n\n"
        "🔒 Бот полностью анонимный — ты можешь быть собой.\n\n"
        "Хочешь — начнём с простого: расскажи, как ты сейчас? 🌤️💬"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text(
        "Я — тёплый психологический помощник 🤗\n"
        "Если тебе тревожно, грустно, пусто или просто хочется поговорить — пиши ✍️\n\n"
        "Я помогу разобраться в чувствах, gently найти первопричину и пройти путь до облегчения.\n"
        "Задаю только вопросы, на которые можно ответить «да» или «нет», и иду вместе с тобой шаг за шагом.\n\n"
        "Попробуй просто начать: расскажи, как ты сейчас? 💬"
    )

async def new_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text("Начали заново 💬 Расскажи, как ты сейчас себя чувствуешь?")

async def understand_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text("Режим 'Понять себя' активирован 🧠 Отвечай 'да' или 'нет' — начнём с широкого вопроса. Это связано с эмоциями?")

async def chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text("Обычный режим активирован 💬 Просто пиши, как ты себя чувствуешь или что тревожит.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text("Я пока не умею слушать голосовые 🙈 Можешь написать словами? Я рядом ✍️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    if "history" not in context.user_data:
        context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]

    context.user_data["history"].append({"role": "user", "content": user_input})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=context.user_data["history"],
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        context.user_data["history"].append({"role": "assistant", "content": reply})
        await update.message.chat.send_action(action="typing")
        await update.message.reply_text(reply[:4000])

    except Exception as e:
        print("❌ Ошибка GPT:", e)
        await update.message.chat.send_action(action="typing")
        await update.message.reply_text("Что-то пошло не так. Попробуй позже 🫶")

async def set_bot_commands(app):
    commands = [
        BotCommand("start", "Начать диалог 🤗"),
        BotCommand("help", "Как пользоваться ботом ❓"),
        BotCommand("chat", "Обычная беседа 💬"),
        BotCommand("understand_me", "Режим 'Понять себя' 🧠"),
        BotCommand("new", "Новый диалог 🔄")
    ]
    await app.bot.set_my_commands(commands)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_dialog))
    app.add_handler(CommandHandler("understand_me", understand_me))
    app.add_handler(CommandHandler("chat", chat_mode))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

   import asyncio

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    )
