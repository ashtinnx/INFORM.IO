import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from config import TELEGRAM_BOT_TOKEN, TIMEZONE, DAILY_HOUR, DAILY_MINUTE, WEEKLY_HOUR, WEEKLY_MINUTE
from database import init_db, register_chat, get_chats
from news_ingest import refresh_fact_database
from adaptive import should_refresh, adaptive_status
from telegram_ui import HELP_TEXT, event_buttons
from responses import (
    latest_alert_text, section_text, daily_brief, weekly_brief, dashboard, crash_monitor,
    dbstatus, facts_search, sources_text, graph_text, outcomes_text, simple_static
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("econ-intel-v6-2")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    await update.message.reply_text("📊 Economic Intelligence Bot connected.\n\nDaily brief: 5:00 PM\nWeekly brief: Sunday 9:00 AM\n\nUse /help to see commands.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = [a.lower() for a in context.args]
    if "daily" in args or "today" in args:
        await update.message.reply_text(daily_brief())
    elif "weekly" in args or "week" in args:
        await update.message.reply_text(weekly_brief())
    else:
        await update.message.reply_text(latest_alert_text(), reply_markup=event_buttons(), disable_web_page_preview=True)

async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(daily_brief())

async def weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(weekly_brief())

async def section_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].replace("/", "").lower()
    mapping = {"confidence": "risks"}
    await update.message.reply_text(section_text(mapping.get(cmd, cmd)), disable_web_page_preview=True)

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("section:"):
        await query.message.reply_text(section_text(query.data.split(":",1)[1]), disable_web_page_preview=True)

async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(dashboard())
async def crash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(crash_monitor())
async def dbstatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(dbstatus())
async def sources_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(sources_text())
async def outcomes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(outcomes_text())
async def adaptive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(adaptive_status())

async def facts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args).strip() or "inflation"
    await update.message.reply_text(facts_search(q))

async def graph_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args).strip() or "inflation"
    await update.message.reply_text(graph_text(q))

async def refresh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_facts, merged, errors = refresh_fact_database(mode="manual")
    await update.message.reply_text(f"Database refreshed.\nNew facts: {len(new_facts)}\nMerged duplicates: {merged}\nErrors: {len(errors)}")

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args).strip()
    if not q:
        await update.message.reply_text("Ask a question after /ask.\nExample: /ask why do interest rates affect housing?")
        return
    await update.message.reply_text(
        f"🤖 Assistant\n\nQuestion: {q}\n\n"
        "Right now I can answer best from the fact database and economic graph.\n\n"
        f"Try:\n/facts {q[:40]}\n/graph {q.split()[0] if q.split() else 'inflation'}\n\n"
        "For broader live AI answers, add OPENAI_API_KEY and TAVILY_API_KEY."
    )

async def static_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].replace("/", "").lower()
    await update.message.reply_text(simple_static(cmd))

async def generic_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await update.message.reply_text(
        "I treated this as a question.\n\n"
        f"Question: {text}\n\n"
        "Database-backed options:\n"
        f"/facts {text[:40]}\n"
        f"/graph {text.split()[0] if text.split() else 'inflation'}"
    )

async def send_daily(app):
    for chat_id in get_chats():
        await app.bot.send_message(chat_id=chat_id, text=daily_brief())

async def send_weekly(app):
    for chat_id in get_chats():
        await app.bot.send_message(chat_id=chat_id, text=weekly_brief())

async def adaptive_refresh_job():
    do_refresh, mode, interval = should_refresh()
    if do_refresh:
        new_facts, merged, errors = refresh_fact_database(mode=mode)
        logger.info("Adaptive refresh mode=%s inserted=%s merged=%s errors=%s", mode, len(new_facts), merged, len(errors))

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")
    init_db()
    refresh_fact_database(max_per_feed=5, mode="startup")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["help","commands"], help_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("weekly", weekly_cmd))
    app.add_handler(CommandHandler(["why","affects","how","opportunity","history","risks","outlook","confidence"], section_cmd))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))
    app.add_handler(CommandHandler("crash", crash_cmd))
    app.add_handler(CommandHandler("dbstatus", dbstatus_cmd))
    app.add_handler(CommandHandler("facts", facts_cmd))
    app.add_handler(CommandHandler("sources", sources_cmd))
    app.add_handler(CommandHandler("graph", graph_cmd))
    app.add_handler(CommandHandler("outcomes", outcomes_cmd))
    app.add_handler(CommandHandler("adaptive", adaptive_cmd))
    app.add_handler(CommandHandler("refresh", refresh_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler(["calendar","learn","search","stocks","bonds","oil","gold","forex","crypto","realestate"], static_cmd))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generic_question))

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(adaptive_refresh_job, "interval", minutes=1)
    scheduler.add_job(lambda: send_daily(app), CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone=TIMEZONE))
    scheduler.add_job(lambda: send_weekly(app), CronTrigger(day_of_week="sun", hour=WEEKLY_HOUR, minute=WEEKLY_MINUTE, timezone=TIMEZONE))
    scheduler.start()

    logger.info("Economic Intelligence Bot V6.2 running.")
    app.run_polling()

if __name__ == "__main__":
    main()
