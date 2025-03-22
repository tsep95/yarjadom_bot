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

# Этапы диалога
STAGE_GREETING = "greeting"
STAGE_ASK_1 = "ask_1"
STAGE_ASK_2 = "ask_2"
STAGE_RESULT = "result"

# Сценарий вопросов для диагностики (упрощённый)
questions = [
    ("Это связано с будущим?", "future"),
    ("Это больше про неуверенность в себе?", "self_doubt")
]

problem_summaries = {
    "future": "Похоже, тревога связана с неопределённостью будущего.",
    "self_doubt": "Похоже, ты испытываешь неуверенность в себе."
}

problem_solutions = {
    "future": "Иногда помогает: маленький чёткий шаг вперёд, фокус на сегодняшнем дне, или просто выдохнуть и позволить себе не знать всё заранее.",
    "self_doubt": "Попробуй напомнить себе, в чём ты уже справлялся. Представь, что говоришь с собой как с близким. Ты можешь быть поддержкой себе."
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["stage"] = STAGE_GREETING
    await update.message.reply_text(
        "Привет,Я рядом.\n"
        "Я тёплый психологический помощник, с которым можно просто поговорить.\n\n"
        "Если тебе тяжело, тревожно, пусто или не с кем поделиться — пиши. "
        "Я не оцениваю, не критикую, не заставляю. Я рядом, чтобы поддержать.\n\n"
        "💬 Моя задача — помочь тебе почувствовать себя лучше прямо сейчас. "
        "Мы можем мягко разобраться, что тебя беспокоит, и найти, что с этим можно сделать.\n\n"
        "Бот полностью анонимный — ты можешь быть собой.\n\n"
        "Хочешь — начнём с простого: расскажи, как ты сейчас?"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    stage = context.user_data.get("stage")

    if stage == STAGE_GREETING:
        await update.message.reply_text(
            "Звучит, как что-то важное. Я рядом.\n"
            "Хочешь — задам тебе пару простых вопросов, чтобы лучше понять, что происходит? (да / нет)"
        )
        context.user_data["stage"] = STAGE_ASK_1
        return

    if stage == STAGE_ASK_1:
        if "да" in text:
            context.user_data["stage"] = STAGE_ASK_2
            context.user_data["current_question"] = 0
            context.user_data["matched_key"] = None
            await update.message.reply_text(questions[0][0] + " (да / нет)")
        else:
            await update.message.reply_text("Хорошо, просто напиши, если захочется поговорить. Я рядом.")
            context.user_data.clear()
        return

    if stage == STAGE_ASK_2:
        current_q = context.user_data.get("current_question", 0)
        if current_q < len(questions):
            if "да" in text:
                matched_key = questions[current_q][1]
                context.user_data["matched_key"] = matched_key
                context.user_data["stage"] = STAGE_RESULT
                summary = problem_summaries.get(matched_key, "Это что-то важное.")
                solution = problem_solutions.get(matched_key, "Попробуй быть с собой чуть мягче. Это уже многое меняет.")
                await update.message.reply_text(f"{summary}\n\n{solution}\n\nТебе это откликается? (да / нет)")
                return
            else:
                context.user_data["current_question"] = current_q + 1
                if context.user_data["current_question"] < len(questions):
                    next_question = questions[context.user_data["current_question"]][0]
                    await update.message.reply_text(next_question + " (да / нет)")
                    return
        await update.message.reply_text("Похоже, сложно точно понять, в чём причина. Но я рядом. Можем просто поговорить.")
        context.user_data.clear()
        return

    if stage == STAGE_RESULT:
        if "да" in text:
            await update.message.reply_text("Рад, что это тебе откликается. Если хочешь — можем продолжить или просто поболтать дальше. ✨")
        else:
            await update.message.reply_text("Хорошо, тогда давай попробуем посмотреть на это с другой стороны. Расскажешь чуть больше?")
        context.user_data.clear()
        return

    # fallback — если нет стадии
    await update.message.reply_text("Я с тобой. Можем начать сначала — просто напиши, как ты.")
    context.user_data.clear()

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
