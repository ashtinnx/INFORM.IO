from config import CATEGORY_KEYWORDS, AFFECTED_MARKETS, MAJOR_RELEASE_KEYWORDS

def categorize(text):
    lower = text.lower()
    scores = {cat: sum(1 for w in words if w in lower) for cat, words in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Markets"

def infer_country(text):
    low = text.lower()
    if "canada" in low or "bank of canada" in low:
        return "Canada"
    if "u.s." in low or "us " in low or "united states" in low or "federal reserve" in low:
        return "United States"
    if "euro" in low or "ecb" in low or "europe" in low:
        return "Europe"
    return "Global"

def score_event(title, summary, category, source_name, source_type):
    text = f"{title} {summary}".lower()
    impact = 45
    high_words = ["unexpected","surprise","cuts","hikes","inflation","recession","crisis","jobs","gdp","oil","bank","tariff","default","war"]
    impact += min(35, 7 * sum(1 for w in high_words if w in text))
    if category in ["Inflation","Interest Rates","Employment","Banking/Credit"]:
        impact += 12
    if source_type == "official":
        impact += 10

    novelty = 55
    if any(w in text for w in ["unexpected","surprise","record","first time","largest","falls","rises","slumps","jumps"]):
        novelty += 25

    confidence = 65
    if source_type == "official":
        confidence += 22
    elif source_name.lower().startswith(("reuters","associated press")):
        confidence += 12

    urgency = impact
    if any(k in text for k in MAJOR_RELEASE_KEYWORDS):
        urgency += 12

    return min(100, impact), min(100, novelty), min(100, confidence), min(100, urgency)

def simple_summary(category):
    summaries = {
        "Inflation": "Prices are changing in a way that could affect interest rates, borrowing costs, stocks, housing, and consumer spending.",
        "Interest Rates": "Interest-rate news matters because it affects loans, mortgages, bond yields, stocks, and business investment.",
        "Employment": "Jobs data matters because it shows whether people are earning and spending, and whether the economy is strong or slowing.",
        "Growth": "Growth news matters because it shows whether the economy is expanding, slowing, or becoming more fragile.",
        "Energy": "Energy news matters because oil and gas prices can affect inflation, transport costs, and consumer spending.",
        "Housing": "Housing news matters because it affects mortgages, banks, construction, household wealth, and affordability.",
        "Banking/Credit": "Banking and credit news matters because it shows how easily money is moving through the economy.",
        "Trade/Geopolitics": "Trade and geopolitical news matters because it can affect supply chains, inflation, currencies, and business confidence.",
    }
    return summaries.get(category, "This matters because it may affect markets, businesses, consumers, or the broader economic outlook.")

def build_fact_from_entry(entry, source_name, source_type="unknown", source_region="global"):
    title = getattr(entry, "title", "Untitled").strip()
    link = getattr(entry, "link", "").strip()
    raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    published = getattr(entry, "published", None)
    text = f"{title} {raw_summary}"
    category = categorize(text)
    impact, novelty, confidence, urgency = score_event(title, raw_summary, category, source_name, source_type)
    return {
        "title": title[:240],
        "summary": simple_summary(category),
        "category": category,
        "country": infer_country(text),
        "lifecycle_status": "breaking" if urgency >= 80 else "monitoring",
        "impact_score": impact,
        "novelty_score": novelty,
        "confidence_score": confidence,
        "urgency_score": urgency,
        "affected_markets": AFFECTED_MARKETS.get(category, ["Stocks","Bonds","Currencies","Consumers"]),
        "source_name": source_name,
        "source_url": link,
        "source_type": source_type,
        "source_region": source_region,
        "published_at": published,
    }

def format_fact_alert(fact):
    affected = fact["affected_markets"] if isinstance(fact["affected_markets"], list) else str(fact["affected_markets"]).split(",")
    return f"""🔴 HIGH-IMPACT ECONOMIC EVENT
Impact: {fact['impact_score']}/100
Novelty: {fact.get('novelty_score', 0)}/100
Confidence: {fact['confidence_score']}/100
Status: {fact.get('lifecycle_status', 'monitoring').title()}

What happened?
{fact['title']}

Plain-English summary:
{fact['summary']}

Category:
{fact['category']}

What it affects:
{', '.join([a for a in affected if a])}

Three things to remember:
1. This matters if it changes expectations.
2. The first market reaction is not always the final reaction.
3. Watch whether more sources confirm the trend.

Source:
{fact['source_name']} — {fact['source_url']}"""
