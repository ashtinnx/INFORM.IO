from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def event_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Why", callback_data="section:why"), InlineKeyboardButton("🌍 Effects", callback_data="section:affects")],
        [InlineKeyboardButton("⚙️ Mechanism", callback_data="section:how"), InlineKeyboardButton("📈 Opportunities", callback_data="section:opportunity")],
        [InlineKeyboardButton("📚 History", callback_data="section:history"), InlineKeyboardButton("⚠️ Risks", callback_data="section:risks")],
        [InlineKeyboardButton("🔮 Outlook", callback_data="section:outlook"), InlineKeyboardButton("📊 Markets", callback_data="section:markets")],
    ])

HELP_TEXT = """📘 Economic Intelligence Bot Commands

📰 News
/news - latest high-impact headline
/news today - today’s high-impact news
/news week - this week’s key developments

📅 Reports
/daily - Daily Economic Intelligence now
/weekly - Weekly Economic Intelligence now

🔍 Expand latest event
/why
/affects
/how
/opportunity
/history
/confidence
/risks
/outlook

📊 Intelligence tools
/dashboard
/crash
/calendar
/adaptive

🧠 Fact database
/dbstatus
/facts inflation
/sources
/graph oil
/outcomes
/refresh

🎓 Learn
/learn CPI
/learn GDP
/learn Yield Curve
/learn QE
/learn Bonds

🔎 Search
/search inflation
/search oil
/search unemployment

📈 Markets
/stocks
/bonds
/oil
/gold
/forex
/crypto
/realestate

🤖 Assistant
/ask <question>
You can also type a normal question.
"""
