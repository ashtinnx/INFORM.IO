from datetime import datetime, timezone
from database import latest_fact, recent_facts, high_impact_facts, search_facts, db_stats, source_stats, relationships_for
from intelligence import format_fact_alert

def row_to_dict(row):
    return dict(row) if row else None

def latest_alert_text():
    fact = row_to_dict(latest_fact())
    if not fact:
        return "No stored facts yet. Use /refresh or wait for the automatic update."
    return format_fact_alert(fact)

def section_text(section):
    fact = row_to_dict(latest_fact())
    if not fact:
        return "No latest event found yet."

    title, cat, affected = fact["title"], fact["category"], fact["affected_markets"]
    source = f"{fact['source_name']} — {fact['source_url']}"

    if section == "why":
        return f"""📖 Why this matters

Event:
{title}

Simple explanation:
This matters because it may change expectations about {cat.lower()}. Markets usually move when expectations change.

Key question:
Does this become a trend or fade as a one-time event?

Source:
{source}"""

    if section == "affects":
        return f"""🌍 What it affects

Main areas:
{affected}

Plain English:
These areas may react because money, borrowing costs, confidence, or business expectations can change.

Source:
{source}"""

    if section == "how":
        chains = {
            "Inflation": "Prices rise faster → central banks may keep rates high → loans stay expensive → spending can slow → stocks and housing may feel pressure",
            "Interest Rates": "Rates change → borrowing costs change → mortgages, loans, bonds, and stock valuations adjust",
            "Energy": "Oil/energy changes → transport costs change → inflation may move → consumers and companies adjust spending",
            "Employment": "Jobs/wages change → consumer income changes → spending changes → company revenue and rate expectations change",
            "Housing": "Housing changes → mortgages, banks, construction, and household wealth are affected",
        }
        return f"""⚙️ Cause-and-effect chain

{chains.get(cat, "New information → expectations change → money moves → markets and the economy adjust")}

Three things to remember:
1. The chain shows what usually happens.
2. Real markets can react differently.
3. Follow-up data matters."""

    if section == "opportunity":
        return f"""📈 Opportunity Watch

This is not a buy/sell signal.

Areas to research:
{affected}

What to check:
• Is this already priced in?
• Are several sources confirming it?
• Is the market reaction strong or weak?
• Does the next data point support it?

Confidence:
{fact['confidence_score']}/100"""

    if section == "history":
        return f"""📚 Historical context

Category:
{cat}

How to use history:
Look for past events in this same category and compare what happened afterward.

Try:
/facts {cat}
/graph {cat}

Source:
{source}"""

    if section == "risks":
        return f"""⚠️ Risks and uncertainty

Main risk:
The first interpretation may be wrong.

What could change the view:
• Follow-up data says the opposite
• Central bank comments change the story
• Markets ignore the headline
• A bigger event overtakes it

Confidence:
{fact['confidence_score']}/100"""

    if section == "outlook":
        return f"""🔮 What to watch next

Next 24 hours:
Watch market reaction and related headlines.

Next week:
Watch whether more sources confirm the same trend.

Next month:
Watch whether this becomes part of a larger pattern."""

    if section == "markets":
        return f"""📊 Market view

Most affected:
{affected}

Plain English:
The market impact depends on whether this changes expectations about growth, inflation, interest rates, profits, or risk.

Source:
{source}"""

    return "Unknown section."

def daily_brief():
    facts = recent_facts(7)
    lines = ["📅 Daily Economic Intelligence", "Today’s Summary — 5:00 PM", ""]
    if not facts:
        return "\n".join(lines + ["No stored facts yet."])
    top = sorted(facts, key=lambda f: f["impact_score"], reverse=True)[0]
    lines += [
        "Most important event:",
        top["title"], "",
        f"Impact: {top['impact_score']}/100",
        f"Category: {top['category']}", "",
        "Top developments:"
    ]
    for i, f in enumerate(facts[:5], 1):
        lines.append(f"{i}. {f['title']} ({f['source_name']})")
    lines += ["", "Three things to remember:", "1. Focus on what changed today.", "2. Watch whether the trend continues.", "3. Use sources before making conclusions."]
    return "\n".join(lines)

def weekly_brief():
    facts = recent_facts(20)
    lines = ["📊 Weekly Economic Intelligence", "This Week’s Summary — Sunday 9:00 AM", ""]
    if not facts:
        return "\n".join(lines + ["No stored facts yet."])
    cats = {}
    for f in facts:
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    lines.append("Main themes:")
    for c, n in sorted(cats.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"• {c}: {n} items")
    lines += ["", "Most important developments:"]
    for i, f in enumerate(sorted(facts, key=lambda f: f["impact_score"], reverse=True)[:5], 1):
        lines.append(f"{i}. {f['title']} — {f['source_name']}")
    return "\n".join(lines)

def dashboard():
    st = db_stats()
    last = st["last_refresh"]
    last_text = last["created_at"] if last else "No refresh logged yet"
    health = min(100, 50 + st["sources"] * 3 + min(st["facts"], 40))
    return f"""📊 Macro Dashboard

Economic OS health:
{health}/100

Facts stored:
{st['facts']}

Sources tracked:
{st['sources']}

Relationships mapped:
{st['relationships']}

Last update:
{last_text}

Plain English:
The more facts and sources the bot stores, the stronger its reports, search, graph, and history become."""

def crash_monitor():
    facts = recent_facts(30)
    risk_terms = ["recession","default","crisis","bank","credit","inflation","unemployment","debt","war"]
    text = " ".join([f["title"].lower() for f in facts])
    score = min(100, 40 + 5 * sum(1 for t in risk_terms if t in text))
    return f"""⚠️ Crash Monitor

Overall risk score:
{score}/100

Plain English:
This is not a crash prediction. It tracks stress signals in the fact database.

Main things to watch:
• Credit conditions
• Employment
• Inflation
• Banking stress
• Market volatility"""

def dbstatus():
    st = db_stats()
    last = st["last_refresh"]
    last_text = last["created_at"] if last else "No refresh yet"
    return f"""🧠 Fact Database Status

Facts: {st['facts']}
Sources: {st['sources']}
Relationships: {st['relationships']}
Outcomes: {st['outcomes']}
Registered chats: {st['chats']}

Last refresh:
{last_text}

Meaning:
The bot stores structured facts, not just articles. This makes reports, search, history, and the economic graph more useful over time."""

def facts_search(query):
    facts = search_facts(query, 8)
    if not facts:
        return f"No stored facts found for: {query}"
    lines = [f"🧠 Stored facts for: {query}", ""]
    for i, f in enumerate(facts, 1):
        lines.append(f"{i}. {f['title']}")
        lines.append(f"   Category: {f['category']} | Impact: {f['impact_score']}/100 | Status: {f['lifecycle_status']}")
        lines.append(f"   Source: {f['source_name']}")
    return "\n".join(lines)

def sources_text():
    rows = source_stats()
    if not rows:
        return "No source stats yet."
    lines = ["🧾 Source Balance", ""]
    for r in rows:
        lines.append(f"• {r['source_name']} ({r['source_type']}, {r['source_region']}): {r['count']} facts")
    lines += ["", "Goal: avoid relying on one source, one country, or one type of information."]
    return "\n".join(lines)

def graph_text(topic):
    rows = relationships_for(topic)
    if not rows:
        return f"No relationships found for: {topic}"
    lines = [f"🕸 Economic Graph: {topic}", ""]
    for r in rows:
        lines.append(f"{r['source_node']} → {r['target_node']}")
        lines.append(f"How: {r['explanation']}")
        lines.append(f"Confidence: {r['confidence']}/100\n")
    return "\n".join(lines)

def outcomes_text():
    return """📈 Outcomes

Outcome tracking is prepared.

Next implementation step:
Automatically check what happened 7, 30, and 90 days after high-impact events, then compare the original expectation with reality."""

def simple_static(name):
    return f"""📌 {name.title()} View

This section uses the fact database and economic graph.

Best commands:
/facts {name}
/graph {name}
/news

Plain English:
This will become stronger as the bot stores more events and outcomes."""
