import feedparser
from config import RSS_FEEDS
from database import insert_or_merge_fact, upsert_source, log_refresh
from intelligence import build_fact_from_entry

def refresh_fact_database(max_per_feed=4, mode="manual"):
    inserted = 0
    merged = 0
    errors = []
    new_facts = []

    # Source balancing: don't let any one feed dominate each refresh.
    for source_name, feed_url, source_type, region in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            upsert_source(source_name, feed_url, source_type, region, success=True)
            per_feed_count = 0
            for entry in feed.entries[:max_per_feed]:
                if per_feed_count >= max_per_feed:
                    break
                fact = build_fact_from_entry(entry, source_name, source_type, region)
                fact_id, status = insert_or_merge_fact(fact)
                if status == "inserted":
                    inserted += 1
                    fact["id"] = fact_id
                    new_facts.append(fact)
                    per_feed_count += 1
                elif status == "merged":
                    merged += 1
        except Exception as e:
            upsert_source(source_name, feed_url, source_type, region, success=False)
            errors.append((source_name, str(e)))

    log_refresh(mode, inserted, merged, len(errors))
    return new_facts, merged, errors
