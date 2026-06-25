# Economic Intelligence Bot V6.2 — Adaptive Economic OS

This version keeps the current bot design and adds the Adaptive Intelligence Engine.

## Main upgrades

- Adaptive refresh system
- Active market-hour refresh logic
- Weekend refresh logic
- High-priority economic release windows
- Source balancing
- Duplicate/near-duplicate filtering
- Event lifecycle tracking
- Database health score
- Knowledge freshness score
- Structured fact database
- Plain-English responses
- Daily brief at 5:00 PM local time
- Weekly brief at 9:00 AM Sunday local time
- Inline expansion buttons
- `/help` and `/commands`
- `/dbstatus`, `/sources`, `/graph`, `/facts`, `/refresh`, `/adaptive`

## Required Railway variable

```text
TELEGRAM_BOT_TOKEN=your_bot_token
```

## Optional Railway variables

```text
TIMEZONE=America/Edmonton
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
```

The bot works without OpenAI/Tavily, but `/ask` is much stronger with them.

## Update schedule

The bot runs a lightweight adaptive monitor every minute. It only performs a full refresh when needed:

| Situation | Target refresh |
|---|---:|
| Major scheduled release window | 1 minute |
| Active market hours | 10 minutes |
| Outside market hours | 30 minutes |
| Weekend | 60 minutes |

## Commands

```text
/start
/help
/commands
/news
/news today
/news week
/daily
/weekly
/why
/affects
/how
/opportunity
/history
/confidence
/risks
/outlook
/dashboard
/crash
/calendar
/dbstatus
/sources
/facts inflation
/graph oil
/outcomes
/adaptive
/refresh
/learn CPI
/search inflation
/stocks
/bonds
/oil
/gold
/forex
/crypto
/realestate
/ask <question>
```

## Deploy

Upload the files in this ZIP directly to your GitHub repo root. Do not upload the folder itself.

Railway will redeploy automatically if your repo is connected.
