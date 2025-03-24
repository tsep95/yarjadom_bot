from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
import openai
import os

# Состояния диалога
STAGE1, STAGE2, STAGE3 = range(3)

# Ключи берём из переменных окружения для Railway
openai.api_key = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['history'] = [
        {"role": "system", "content": "Ты поддерживающий психолог, который помогает человеку добраться до сути его состояния. Ты задаёшь вопросы по очереди, чтобы помочь человеку понять себя. После серии вопросов ты даёшь краткий анализ и мягкий совет."},
        {"role": "user", "content": "Начни с приветствия и задай первый вопрос по теме: тревога, апатия, злость, вина, 'просто плохо' или 'всё нормально, но чего-то не хватает'."}
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=context.user_data['history']
    )
    reply = response.choices[0].message['content']
    await update.message.reply_text(reply)
    return STAGE1

async def stage1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    context.user_data['history'].append({"role": "user", "content": user_input})

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=context.user_data['history']
    )
    reply = response.choices[0].message['content']
    context.user_data['history'].append({"role": "assistant", "content": reply})

    # Определяем, завершать ли диалог
    if any(x in reply.lower() for x in ["вот краткий анализ", "вот что я понял", "совет", "рекомендую"]):
        await update.message.reply_text(reply)
        await update.message.reply_text(
            "Если хочешь глубже проработать это состояние, я могу быть рядом каждый день. Подписка — 500₽ в месяц. Хочешь узнать подробнее? ✨",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(reply)
        return STAGE1

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Хорошо, если что — я рядом ❤️", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STAGE1: [MessageHandler(filters.TEXT & ~filters.COMMAND, stage1)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

app.add_handler(conv_handler)

if __name__ == '__main__':
    app.run_polling()
