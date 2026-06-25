# Economic Intelligence Bot V5.2

A Telegram economic intelligence bot designed for clear, useful, plain-English financial awareness.

## What changed in V5.2

- Daily brief now runs at **5:00 PM local time**.
- Weekly brief stays at **9:00 AM every Sunday**.
- `/news daily` and `/news weekly` are clearly labeled so you can instantly tell which report type you are reading.
- Simpler language throughout.
- Every major alert includes expandable Telegram buttons:
  - 📖 Why
  - 🌍 Effects
  - ⚙️ Mechanism
  - 📈 Opportunities
  - 📚 History
  - ⚠️ Risks
  - 🔮 Outlook
  - 📊 Markets
- `/help` and `/commands` show every available command.
- Uses diversified sources instead of relying on one feed.
- Uses Docker so Railway avoids the Python/mise issue.

## Deploy on Railway

1. Extract this ZIP.
2. Upload the files directly to your GitHub repo root.
3. Redeploy your Railway service.
4. Add this Railway variable:

```text
TELEGRAM_BOT_TOKEN=your_botfather_token
```

Optional variables:

```text
TIMEZONE=America/Edmonton
DAILY_BRIEF_HOUR=17
DAILY_BRIEF_MINUTE=0
WEEKLY_BRIEF_DAY=sun
WEEKLY_BRIEF_HOUR=9
WEEKLY_BRIEF_MINUTE=0
NEWS_CHECK_MINUTES=30
MIN_ALERT_SCORE=78
```

5. In Telegram, send your bot:

```text
/start
```

## Commands

```text
/news - latest high-impact headlines
/news daily - clearly labeled daily news view
/news weekly - clearly labeled weekly news view

/daily - daily brief now
/weekly - weekly brief now

/why - why latest event matters
/affects - what it affects
/how - cause/effect chain
/opportunity - areas to research
/history - historical context
/confidence - confidence score
/risks - risks and uncertainty
/outlook - what to watch next

/dashboard - macro dashboard
/crash - crash/risk monitor
/calendar - upcoming economic events

/learn CPI
/learn GDP
/learn Yield Curve
/learn QE
/learn Bonds

/search inflation
/search oil
/search unemployment

/stocks
/bonds
/oil
/gold
/forex
/crypto
/realestate

/ask <question>
/help
/commands
```

## Important note

This bot is for education and financial awareness. It does not give guaranteed trades or personal financial advice. Treat its “Opportunity Watch” section as research ideas, not buy/sell instructions.
