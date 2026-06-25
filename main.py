import os
import re
import html
import sqlite3
import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional, Tuple

import feedparser
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("econbot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TZ_NAME = os.getenv("TIMEZONE", "America/Edmonton")
TZ = ZoneInfo(TZ_NAME)
DB_PATH = os.getenv("DB_PATH", "econbot.sqlite3")
MIN_ALERT_SCORE = int(os.getenv("MIN_ALERT_SCORE", "78"))
NEWS_CHECK_MINUTES = int(os.getenv("NEWS_CHECK_MINUTES", "30"))
DAILY_HOUR = int(os.getenv("DAILY_BRIEF_HOUR", "17"))
DAILY_MIN = int(os.getenv("DAILY_BRIEF_MINUTE", "0"))
WEEKLY_DAY = os.getenv("WEEKLY_BRIEF_DAY", "sun")
WEEKLY_HOUR = int(os.getenv("WEEKLY_BRIEF_HOUR", "9"))
WEEKLY_MIN = int(os.getenv("WEEKLY_BRIEF_MINUTE", "0"))

if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")

FEEDS = [
    ("Reuters Markets", "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Bank of Canada", "https://www.bankofcanada.ca/feed/"),
    ("Statistics Canada", "https://www150.statcan.gc.ca/n1/rss/11-001-eng.xml"),
    ("BLS", "https://www.bls.gov/feed/news_release/rss.xml"),
    ("BEA", "https://www.bea.gov/news/glance/rss"),
    ("EIA Energy", "https://www.eia.gov/rss/todayinenergy.xml"),
    ("IMF", "https://www.imf.org/en/News/RSS"),
    ("World Bank", "https://www.worldbank.org/en/news/all?format=rss"),
    ("Yahoo Finance Economy", "https://finance.yahoo.com/news/rssindex"),
]

HIGH_IMPACT = {
    "inflation": 24, "cpi": 24, "ppi": 18, "interest rate": 24, "rates": 18,
    "fed": 20, "federal reserve": 22, "bank of canada": 22, "central bank": 20,
    "unemployment": 22, "jobs": 18, "payrolls": 22, "gdp": 20,
    "recession": 26, "bank failure": 28, "credit": 18, "liquidity": 18,
    "oil": 16, "energy": 14, "tariff": 18, "trade war": 22,
    "housing": 18, "mortgage": 18, "debt": 16, "yield": 18,
    "treasury": 16, "dollar": 12, "currency": 12, "gold": 10,
    "china": 12, "canada": 10, "us economy": 16, "consumer spending": 18
}

TOPIC_MAP = {
    "Inflation": ["inflation", "cpi", "ppi", "prices"],
    "Interest Rates": ["interest rate", "rates", "fed", "federal reserve", "bank of canada", "central bank"],
    "Jobs": ["jobs", "payrolls", "unemployment", "wages", "labor", "labour"],
    "Growth": ["gdp", "growth", "recession", "manufacturing", "services"],
    "Energy": ["oil", "energy", "gas", "opec", "crude"],
    "Housing": ["housing", "mortgage", "rent", "real estate", "construction"],
    "Credit/Banking": ["bank", "credit", "liquidity", "debt", "loan"],
    "Trade/Geopolitics": ["tariff", "trade", "china", "war", "sanction", "geopolitical"],
    "Markets": ["stocks", "bonds", "treasury", "yield", "dollar", "currency", "gold", "crypto"],
}

@dataclass
class Event:
    id: str
    title: str
    summary: str
    link: str
    source: str
    published: str
    score: int
    confidence: int
    novelty: int
    topic: str


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS chats(chat_id INTEGER PRIMARY KEY, created_at TEXT)")
        conn.execute("""CREATE TABLE IF NOT EXISTS events(
            id TEXT PRIMARY KEY, title TEXT, summary TEXT, link TEXT, source TEXT, published TEXT,
            score INTEGER, confidence INTEGER, novelty INTEGER, topic TEXT, created_at TEXT
        )""")
        conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")


def clean(text: str) -> str:
    text = BeautifulSoup(text or "", "html.parser").get_text(" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def eid(title: str, link: str) -> str:
    return hashlib.sha1((title + link).encode()).hexdigest()[:12]


def detect_topic(text: str) -> str:
    low = text.lower()
    for topic, keys in TOPIC_MAP.items():
        if any(k in low for k in keys):
            return topic
    return "Macro"


def score_event(title: str, summary: str, source: str) -> Tuple[int, int, int]:
    text = (title + " " + summary).lower()
    score = 35
    for key, pts in HIGH_IMPACT.items():
        if key in text:
            score += pts
    if source in {"Federal Reserve", "Bank of Canada", "BLS", "BEA", "Statistics Canada"}:
        score += 10
    if any(w in text for w in ["unexpected", "surprise", "above expectations", "below expectations", "crisis", "cuts", "raises"]):
        score += 12
    score = max(0, min(100, score))
    confidence = min(92, max(55, score - 8))
    novelty = min(95, max(50, score - (5 if "says" in text else 0)))
    return score, confidence, novelty


def fetch_events(limit_per_feed: int = 6) -> List[Event]:
    events = []
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for item in feed.entries[:limit_per_feed]:
                title = clean(getattr(item, "title", ""))
                link = getattr(item, "link", "")
                summary = clean(getattr(item, "summary", ""))[:600]
                if not title or not link:
                    continue
                score, confidence, novelty = score_event(title, summary, source)
                topic = detect_topic(title + " " + summary)
                published = clean(getattr(item, "published", "")) or datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
                events.append(Event(eid(title, link), title, summary, link, source, published, score, confidence, novelty, topic))
        except Exception as e:
            log.warning("Feed failed %s: %s", source, e)
    # diversify by source: max 2 per source in the first pass
    events.sort(key=lambda e: e.score, reverse=True)
    selected, counts = [], {}
    for e in events:
        if counts.get(e.source, 0) >= 2:
            continue
        selected.append(e)
        counts[e.source] = counts.get(e.source, 0) + 1
    return selected + [e for e in events if e not in selected]


def save_event(e: Event):
    with db() as conn:
        conn.execute("""INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                     (e.id, e.title, e.summary, e.link, e.source, e.published, e.score, e.confidence, e.novelty, e.topic, datetime.now(TZ).isoformat()))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('latest_event_id',?)", (e.id,))


def get_latest_event() -> Optional[sqlite3.Row]:
    with db() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='latest_event_id'").fetchone()
        if row:
            ev = conn.execute("SELECT * FROM events WHERE id=?", (row["value"],)).fetchone()
            if ev: return ev
        return conn.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 1").fetchone()


def search_events(q: str, limit: int = 5) -> List[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM events WHERE lower(title||' '||summary||' '||topic) LIKE ? ORDER BY score DESC, created_at DESC LIMIT ?", (f"%{q.lower()}%", limit)).fetchall()


def all_chats() -> List[int]:
    with db() as conn:
        return [r["chat_id"] for r in conn.execute("SELECT chat_id FROM chats").fetchall()]


def esc(s: str) -> str:
    return html.escape(s or "")


def bullets(items):
    return "\n".join(f"• {esc(i)}" for i in items)


def topic_impacts(topic: str) -> Dict[str, str]:
    base = {
        "Stocks": "Can move depending on whether the news helps or hurts company profits.",
        "Bonds": "Usually react when investors change their interest-rate expectations.",
        "Currencies": "Can move when one country looks stronger or rates look higher than others.",
        "Housing": "Mostly affected through mortgage rates, income, and confidence.",
        "Consumers": "Affected through prices, jobs, wages, and borrowing costs.",
        "Businesses": "Affected through demand, financing costs, and profit expectations.",
    }
    if topic == "Inflation":
        base.update({"Stocks":"High inflation can pressure stocks because rates may stay high.", "Bonds":"Yields may rise; older bonds can fall in price.", "Real Estate":"Mortgage rates may stay high, hurting affordability."})
    if topic == "Energy":
        base.update({"Inflation":"Higher oil can make transport and goods more expensive.", "Consumers":"Gas and heating costs can squeeze spending.", "Airlines/Transport":"Fuel costs can hurt margins."})
    if topic == "Jobs":
        base.update({"Stocks":"Strong jobs can help growth, but may delay rate cuts.", "Consumers":"Jobs and wages support spending.", "Central Banks":"Strong employment can make rate cuts less urgent."})
    if topic == "Credit/Banking":
        base.update({"Banks":"Credit stress can hurt lending and confidence.", "Stocks":"Banking stress can spread into broader market risk.", "Businesses":"Tighter credit makes expansion harder."})
    return base


def mechanism(topic: str) -> List[str]:
    chains = {
        "Inflation": ["Prices rise faster than expected", "Central banks may keep rates high", "Loans and mortgages stay expensive", "People and businesses spend less", "Company profits can slow", "Some stocks may come under pressure"],
        "Interest Rates": ["Rates stay high or move higher", "Borrowing becomes more expensive", "Consumers and businesses slow spending", "Housing and growth stocks feel pressure", "Economic growth can cool"],
        "Jobs": ["Job data changes the growth picture", "Investors adjust rate expectations", "Consumer spending outlook changes", "Company sales and profits may be repriced"],
        "Energy": ["Oil or energy prices change", "Transport and production costs change", "Inflation expectations shift", "Consumers have more or less money left over", "Markets adjust growth and rate expectations"],
        "Housing": ["Housing data changes", "Affordability and construction outlook shift", "Banks, builders, and consumer confidence are affected", "Broader growth expectations can change"],
        "Credit/Banking": ["Credit stress rises", "Banks become more cautious", "Loans become harder to get", "Businesses and households spend less", "Economic risk rises"],
    }
    return chains.get(topic, ["Important economic news comes out", "Investors reassess growth and inflation", "Interest rates, currencies, and stocks adjust", "The next data point confirms or weakens the signal"])


def opportunity(topic: str) -> List[str]:
    m = {
        "Inflation": ["Treasury yields", "USD strength", "Gold reaction", "Rate-sensitive technology stocks", "Real estate affordability"],
        "Interest Rates": ["Banks", "Bonds", "High-growth stocks", "Real estate", "Currency pairs"],
        "Jobs": ["Consumer stocks", "Bonds", "USD", "Rate-cut expectations", "Small-cap stocks"],
        "Energy": ["Oil producers", "Airlines/transport", "Inflation-sensitive assets", "CAD and energy-linked currencies"],
        "Housing": ["Homebuilders", "REITs", "Mortgage lenders", "Building materials", "Rental market trends"],
        "Credit/Banking": ["Regional banks", "Credit spreads", "Defensive sectors", "Treasury bonds", "Gold"],
    }
    return m.get(topic, ["The directly affected sector", "Bonds", "Currencies", "Defensive assets", "Related commodities"])


def keyboard(eid: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📖 Why", callback_data=f"why:{eid}"), InlineKeyboardButton("🌍 Effects", callback_data=f"affects:{eid}")],
        [InlineKeyboardButton("⚙️ Mechanism", callback_data=f"how:{eid}"), InlineKeyboardButton("📈 Opportunities", callback_data=f"opp:{eid}")],
        [InlineKeyboardButton("📚 History", callback_data=f"hist:{eid}"), InlineKeyboardButton("⚠️ Risks", callback_data=f"risks:{eid}")],
        [InlineKeyboardButton("🔮 Outlook", callback_data=f"outlook:{eid}"), InlineKeyboardButton("📊 Markets", callback_data=f"markets:{eid}")],
    ]
    return InlineKeyboardMarkup(rows)


def main_alert(e, label="📰 Latest High-Impact News") -> str:
    impacts = topic_impacts(e.topic)
    top = list(impacts.items())[:4]
    chain = "\n↓\n".join(mechanism(e.topic)[:5])
    takeaways = [
        f"This is mainly a {e.topic.lower()} story.",
        "The key question is whether this changes expectations for rates, growth, or risk.",
        "Use the buttons below to expand only the parts you care about."
    ]
    return f"""<b>{esc(label)}</b>

<b>🔴 HIGH IMPACT</b>
Impact: <b>{e.score}/100</b> | Confidence: <b>{e.confidence}%</b> | Novelty: <b>{e.novelty}%</b>

<b>{esc(e.title)}</b>

<b>What happened?</b>
{esc(e.summary[:450]) if e.summary else 'A relevant economic update was reported.'}

<b>Why it matters:</b>
This may affect how investors think about interest rates, growth, inflation, or financial risk.

<b>What it affects:</b>
{chr(10).join(f'• <b>{esc(k)}</b>: {esc(v)}' for k,v in top)}

<b>How:</b>
{esc(chain)}

<b>🧠 Three things to remember:</b>
{bullets(takeaways)}

<b>Sources:</b>
• {esc(e.source)} — <a href="{esc(e.link)}">open source</a>
"""


def section_text(kind: str, e) -> str:
    if kind == "why":
        return f"""<b>📖 Why This Matters</b>

<b>{esc(e.title)}</b>

This matters because it can change expectations for inflation, interest rates, growth, or risk.

Plain English:
When important economic news changes what investors expect next, prices in stocks, bonds, currencies, housing, and commodities can move quickly.

<b>Source:</b> <a href="{esc(e.link)}">{esc(e.source)}</a>"""
    if kind == "affects":
        return "<b>🌍 What It Affects</b>\n\n" + "\n".join(f"• <b>{esc(k)}</b>: {esc(v)}" for k,v in topic_impacts(e.topic).items()) + f"\n\n<b>Source:</b> <a href=\"{esc(e.link)}\">{esc(e.source)}</a>"
    if kind == "how":
        return "<b>⚙️ Cause and Effect</b>\n\n" + esc("\n↓\n".join(mechanism(e.topic))) + f"\n\n<b>Source:</b> <a href=\"{esc(e.link)}\">{esc(e.source)}</a>"
    if kind == "opp":
        items = opportunity(e.topic)
        return f"""<b>📈 Opportunity Watch</b>

These are not buy/sell signals. They are areas worth researching because this type of news often affects them first.

{bullets(items)}

<b>What to check before acting:</b>
• Was this already expected?
• Are bonds, currencies, and stocks confirming the move?
• Is this one data point or part of a trend?

<b>Source:</b> <a href="{esc(e.link)}">{esc(e.source)}</a>"""
    if kind == "hist":
        return f"""<b>📚 Historical Context</b>

Similar types of events have mattered in periods like 2008, 2011, 2018, 2020, and 2022, but the exact outcome depends on the full economic environment.

<b>Simple rule:</b>
Do not copy the past exactly. Use it to understand possible paths.

<b>Similarity score:</b> {max(55, e.confidence-8)}%

<b>Source:</b> <a href="{esc(e.link)}">{esc(e.source)}</a>"""
    if kind == "risks":
        return f"""<b>⚠️ Risks and Uncertainty</b>

<b>Main risk:</b>
The market may overreact to one headline.

<b>What could change the view?</b>
• A stronger or weaker next data report
• Central bank comments
• Bond market reaction
• Oil or currency moves
• New geopolitical news

<b>Confidence:</b> {e.confidence}%

<b>Source:</b> <a href="{esc(e.link)}">{esc(e.source)}</a>"""
    if kind == "outlook":
        return f"""<b>🔮 Outlook</b>

<b>Next 24 hours:</b>
Watch whether markets react strongly or ignore it.

<b>Next week:</b>
Watch for confirmation from related data and central bank comments.

<b>Next month:</b>
The key question is whether this becomes a trend.

<b>Source:</b> <a href="{esc(e.link)}">{esc(e.source)}</a>"""
    if kind == "markets":
        return f"""<b>📊 Market View</b>

<b>Stocks:</b> Watch growth and rate-sensitive sectors.
<b>Bonds:</b> Watch yields because they show rate expectations.
<b>Currencies:</b> Watch USD/CAD and major safe-haven moves.
<b>Commodities:</b> Watch oil and gold for inflation/risk signals.
<b>Real estate:</b> Watch mortgage-rate implications.

<b>Source:</b> <a href="{esc(e.link)}">{esc(e.source)}</a>"""
    return "Section not found."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO chats VALUES(?,?)", (chat_id, datetime.now(TZ).isoformat()))
    await update.message.reply_text("📊 Economic Intelligence Bot connected.\n\nDaily brief: 5:00 PM local time\nWeekly brief: Sunday 9:00 AM\n\nUse /help to see all commands.")

COMMANDS = """<b>📘 Commands</b>

<b>News</b>
/news - latest high-impact headlines
/news daily - clearly labeled daily news view
/news weekly - clearly labeled weekly news view

<b>Briefs</b>
/daily - daily brief now
/weekly - weekly brief now

<b>Expand latest event</b>
/why - why it matters
/affects - what it affects
/how - cause/effect chain
/opportunity - areas to research
/history - historical context
/confidence - confidence score
/risks - risks and uncertainty
/outlook - what to watch next

<b>Big picture</b>
/dashboard - macro dashboard
/crash - crash/risk monitor
/calendar - upcoming economic events

<b>Learn</b>
/learn CPI
/learn GDP
/learn Yield Curve
/learn QE
/learn Bonds

<b>Search</b>
/search inflation
/search oil
/search unemployment

<b>Markets</b>
/stocks /bonds /oil /gold /forex /crypto /realestate

<b>AI-style question</b>
/ask &lt;question&gt;

/help or /commands - show this list"""

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(COMMANDS, parse_mode=ParseMode.HTML)

async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = " ".join(context.args).lower().strip()
    if arg in ["daily", "today"]:
        label = "📅 Daily Economic Intelligence — Today’s News View"
        limit = 5
    elif arg in ["weekly", "week"]:
        label = "📊 Weekly Economic Intelligence — This Week’s News View"
        limit = 7
    else:
        label = "📰 Latest High-Impact News"
        limit = 3
    events = fetch_events()[:limit]
    events = [e for e in events if e.score >= 55]
    if not events:
        await update.message.reply_text(f"<b>{label}</b>\n\nNo major economic events found right now.", parse_mode=ParseMode.HTML)
        return
    for e in events[:limit]:
        save_event(e)
        await update.message.reply_text(main_alert(e, label), parse_mode=ParseMode.HTML, reply_markup=keyboard(e.id), disable_web_page_preview=True)

async def latest_section(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    e = get_latest_event()
    if not e:
        await update.message.reply_text("No saved event yet. Run /news first.")
        return
    await update.message.reply_text(section_text(kind, e), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def why(update, context): await latest_section(update, context, "why")
async def affects(update, context): await latest_section(update, context, "affects")
async def how(update, context): await latest_section(update, context, "how")
async def opp(update, context): await latest_section(update, context, "opp")
async def hist(update, context): await latest_section(update, context, "hist")
async def risks(update, context): await latest_section(update, context, "risks")
async def outlook(update, context): await latest_section(update, context, "outlook")
async def confidence(update, context):
    e = get_latest_event()
    if not e:
        await update.message.reply_text("No saved event yet. Run /news first.")
        return
    await update.message.reply_text(f"<b>✅ Confidence</b>\n\nConfidence: <b>{e['confidence']}%</b>\nNovelty: <b>{e['novelty']}%</b>\nImpact: <b>{e['score']}/100</b>\n\nPlain English: this is how strong the signal looks based on topic, source quality, and likely economic relevance.\n\n<b>Source:</b> <a href=\"{esc(e['link'])}\">{esc(e['source'])}</a>", parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kind, event_id = q.data.split(":", 1)
    with db() as conn:
        e = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not e:
        await q.edit_message_text("That event is no longer available. Run /news again.")
        return
    await q.message.reply_text(section_text(kind, e), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_events()[:5]
    for e in events: save_event(e)
    top = events[0] if events else None
    if not top:
        await update.message.reply_text("<b>📅 Daily Economic Intelligence — Today’s Summary</b>\n\nNo major updates found.", parse_mode=ParseMode.HTML)
        return
    text = f"""<b>📅 Daily Economic Intelligence — Today’s Summary</b>
<b>Schedule:</b> 5:00 PM daily

<b>Market mood:</b> Cautious / data-dependent

<b>Most important event:</b>
{esc(top.title)}

<b>Impact:</b> {top.score}/100

<b>Most affected areas:</b>
{bullets(list(topic_impacts(top.topic).keys())[:5])}

<b>Biggest thing to watch:</b>
Whether this changes expectations for rates, growth, inflation, or risk.

<b>🧠 Three things to remember:</b>
• This is a {esc(top.topic.lower())} story.
• The market reaction matters as much as the headline.
• One report is not a trend; watch the next confirmation.

<b>Sources:</b>
• <a href="{esc(top.link)}">{esc(top.source)}</a>"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_events()[:7]
    for e in events: save_event(e)
    lines = "\n".join(f"• {esc(e.topic)}: <a href=\"{esc(e.link)}\">{esc(e.title[:90])}</a> ({e.score}/100)" for e in events[:5])
    text = f"""<b>📊 Weekly Economic Intelligence — This Week’s Summary</b>
<b>Schedule:</b> Sunday 9:00 AM

<b>Biggest macro developments:</b>
{lines if lines else 'No major developments found.'}

<b>Emerging themes:</b>
• Inflation and rate expectations
• Growth and employment strength
• Credit and financial stress
• Energy and commodity prices

<b>What to monitor next week:</b>
• Inflation data
• Central bank comments
• Bond yields
• Oil prices
• Market breadth

<b>Plain-English takeaway:</b>
The goal is not to predict perfectly. The goal is to notice what is changing before it becomes obvious."""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def dashboard(update, context):
    await update.message.reply_text("""<b>📊 Macro Dashboard — Big Picture View</b>

Inflation: Elevated / watch trend
Employment: Still important for rate expectations
Growth: Watch GDP and business activity
Interest rates: Main driver for bonds, housing, and stocks
Oil: Can affect inflation and consumers
Gold: Risk and inflation signal
USD/CAD: Watch rate differences and oil
Housing: Sensitive to mortgage rates
Credit: Watch for stress

Overall macro risk: <b>Moderate to elevated</b>""", parse_mode=ParseMode.HTML)

async def crash(update, context):
    await update.message.reply_text("""<b>⚠️ Crash Monitor — Risk View</b>

This is not a crash prediction. It tracks stress.

Watch:
• Financial stress
• Liquidity
• Yield curve
• Credit markets
• Volatility
• Banking stress
• Consumer debt
• Commercial real estate

Overall risk: <b>Elevated, but not conclusive</b>""", parse_mode=ParseMode.HTML)

async def calendar(update, context):
    await update.message.reply_text("""<b>📆 Economic Calendar — What To Watch</b>

Key recurring events:
• CPI / inflation reports
• Jobs reports
• GDP updates
• Central bank decisions
• Oil inventory reports
• Retail sales
• Housing data

Plain English: these are the reports most likely to change expectations for rates, growth, inflation, and risk.""", parse_mode=ParseMode.HTML)

LEARN = {
    "cpi": "CPI means inflation. It tracks how quickly consumer prices are rising.",
    "gdp": "GDP means economic growth. It measures the total value of goods and services produced.",
    "yield curve": "The yield curve compares short-term and long-term interest rates. It can show how investors feel about future growth.",
    "qe": "QE means central banks buying assets to add money into the financial system.",
    "bonds": "Bonds are loans to governments or companies. Their prices often move opposite to yields.",
}
async def learn(update, context):
    term = " ".join(context.args).lower().strip()
    ans = LEARN.get(term, "Try /learn CPI, /learn GDP, /learn Yield Curve, /learn QE, or /learn Bonds.")
    await update.message.reply_text(f"<b>🎓 Learn: {esc(term.title() or 'Topic')}</b>\n\n{esc(ans)}", parse_mode=ParseMode.HTML)

async def search(update, context):
    q = " ".join(context.args).strip()
    if not q:
        await update.message.reply_text("Use it like: /search inflation")
        return
    rows = search_events(q)
    if not rows:
        await update.message.reply_text("No saved events found. Run /news first, then search again.")
        return
    text = f"<b>🔍 Search Results — {esc(q)}</b>\n\n" + "\n".join(f"• <a href=\"{esc(r['link'])}\">{esc(r['title'][:95])}</a> — {r['source']} ({r['score']}/100)" for r in rows)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def market(update, context):
    cmd = update.message.text.split()[0].replace("/", "").lower()
    names = {"stocks":"Stocks", "bonds":"Bonds", "oil":"Oil", "gold":"Gold", "forex":"Currencies", "crypto":"Crypto", "realestate":"Real Estate"}
    await update.message.reply_text(f"""<b>📊 {names.get(cmd, cmd.title())} — Market-Specific View</b>

<b>Current outlook:</b>
Watch how this market reacts to inflation, rates, growth, and risk.

<b>What moves it:</b>
• Interest-rate expectations
• Economic growth
• Inflation
• Risk appetite
• Sector-specific news

<b>Historical context:</b>
This market usually reacts differently depending on whether investors are worried about inflation, recession, or financial stress.""", parse_mode=ParseMode.HTML)

async def ask(update, context):
    question = " ".join(context.args).strip()
    e = get_latest_event()
    if not question:
        await update.message.reply_text("Use it like: /ask why did bonds move after this news?")
        return
    if not e:
        await update.message.reply_text("Run /news first so I have a latest event to use as context.")
        return
    await update.message.reply_text(f"""<b>❓ Ask — Context Answer</b>

<b>Your question:</b>
{esc(question)}

<b>Based on latest event:</b>
{esc(e['title'])}

Plain-English answer:
The likely reason is that this news may change expectations for rates, growth, inflation, or risk. Check the reaction in bonds, currencies, and stocks to see whether markets agree with the headline.

<b>Source:</b> <a href="{esc(e['link'])}">{esc(e['source'])}</a>""", parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def scheduled_daily(app: Application):
    for chat in all_chats():
        fake = type("obj", (), {})()
        # directly send a simple daily brief
        events = fetch_events()[:5]
        for e in events: save_event(e)
        if events:
            await app.bot.send_message(chat, main_alert(events[0], "📅 Daily Economic Intelligence — Today’s 5 PM Summary"), parse_mode=ParseMode.HTML, reply_markup=keyboard(events[0].id), disable_web_page_preview=True)

async def scheduled_weekly(app: Application):
    for chat in all_chats():
        events = fetch_events()[:7]
        for e in events: save_event(e)
        lines = "\n".join(f"• {esc(e.topic)}: {esc(e.title[:80])} ({e.score}/100)" for e in events[:5])
        await app.bot.send_message(chat, f"<b>📊 Weekly Economic Intelligence — Sunday 9 AM Summary</b>\n\n{lines}\n\n<b>Takeaway:</b> Look for what changed this week, not just what happened.", parse_mode=ParseMode.HTML)

async def periodic_alerts(app: Application):
    events = fetch_events()[:8]
    for e in events:
        if e.score < MIN_ALERT_SCORE:
            continue
        with db() as conn:
            exists = conn.execute("SELECT id FROM events WHERE id=?", (e.id,)).fetchone()
        if exists:
            continue
        save_event(e)
        for chat in all_chats():
            await app.bot.send_message(chat, main_alert(e), parse_mode=ParseMode.HTML, reply_markup=keyboard(e.id), disable_web_page_preview=True)


def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["help", "commands"], help_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(CommandHandler("why", why))
    app.add_handler(CommandHandler("affects", affects))
    app.add_handler(CommandHandler("how", how))
    app.add_handler(CommandHandler("opportunity", opp))
    app.add_handler(CommandHandler("history", hist))
    app.add_handler(CommandHandler("confidence", confidence))
    app.add_handler(CommandHandler("risks", risks))
    app.add_handler(CommandHandler("outlook", outlook))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("crash", crash))
    app.add_handler(CommandHandler("calendar", calendar))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler(["stocks", "bonds", "oil", "gold", "forex", "crypto", "realestate"], market))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CallbackQueryHandler(callback))

    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(lambda: app.create_task(scheduled_daily(app)), "cron", hour=DAILY_HOUR, minute=DAILY_MIN)
    scheduler.add_job(lambda: app.create_task(scheduled_weekly(app)), "cron", day_of_week=WEEKLY_DAY, hour=WEEKLY_HOUR, minute=WEEKLY_MIN)
    scheduler.add_job(lambda: app.create_task(periodic_alerts(app)), "interval", minutes=NEWS_CHECK_MINUTES)
    scheduler.start()
    log.info("Bot starting. Daily=%02d:%02d, Weekly=%s %02d:%02d, TZ=%s", DAILY_HOUR, DAILY_MIN, WEEKLY_DAY, WEEKLY_HOUR, WEEKLY_MIN, TZ_NAME)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
