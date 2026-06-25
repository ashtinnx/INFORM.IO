import sqlite3, hashlib
from datetime import datetime, timezone
from config import DB_PATH


def _columns(conn, table):
    try:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()

def _add_column_if_missing(conn, table, column, definition):
    cols = _columns(conn, table)
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def migrate_db(conn):
    # Safe migrations for users upgrading from older bot versions.
    fact_cols = _columns(conn, "facts")
    if fact_cols:
        _add_column_if_missing(conn, "facts", "canonical_key", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "facts", "lifecycle_status", "TEXT DEFAULT 'monitoring'")
        _add_column_if_missing(conn, "facts", "urgency_score", "INTEGER DEFAULT 50")
        _add_column_if_missing(conn, "facts", "source_type", "TEXT DEFAULT 'unknown'")
        _add_column_if_missing(conn, "facts", "source_region", "TEXT DEFAULT 'global'")
        _add_column_if_missing(conn, "facts", "updated_at", "TEXT DEFAULT ''")
        conn.execute("UPDATE facts SET canonical_key = title WHERE canonical_key = '' OR canonical_key IS NULL")
        conn.execute("UPDATE facts SET updated_at = created_at WHERE updated_at = '' OR updated_at IS NULL")

    source_cols = _columns(conn, "sources")
    if source_cols:
        _add_column_if_missing(conn, "sources", "source_type", "TEXT DEFAULT 'unknown'")
        _add_column_if_missing(conn, "sources", "region", "TEXT DEFAULT 'global'")
        _add_column_if_missing(conn, "sources", "success_count", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "sources", "error_count", "INTEGER DEFAULT 0")


def now_iso():
    return datetime.now(timezone.utc).isoformat()

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            source_type TEXT DEFAULT 'unknown',
            region TEXT DEFAULT 'global',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            success_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            UNIQUE(name, url)
        );

        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT UNIQUE NOT NULL,
            canonical_key TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            category TEXT NOT NULL,
            country TEXT DEFAULT 'Global',
            lifecycle_status TEXT DEFAULT 'breaking',
            actual_value TEXT,
            expected_value TEXT,
            previous_value TEXT,
            surprise TEXT,
            impact_score INTEGER NOT NULL,
            novelty_score INTEGER NOT NULL,
            confidence_score INTEGER NOT NULL,
            urgency_score INTEGER NOT NULL,
            affected_markets TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_type TEXT DEFAULT 'unknown',
            source_region TEXT DEFAULT 'global',
            published_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fact_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(fact_id, source_url)
        );

        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_node TEXT NOT NULL,
            relation TEXT NOT NULL,
            target_node TEXT NOT NULL,
            explanation TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            UNIQUE(source_node, relation, target_node)
        );

        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_id INTEGER NOT NULL,
            horizon_days INTEGER NOT NULL,
            outcome_summary TEXT NOT NULL,
            checked_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS refresh_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            inserted_count INTEGER NOT NULL,
            merged_count INTEGER NOT NULL,
            error_count INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
        CREATE INDEX IF NOT EXISTS idx_facts_created_at ON facts(created_at);
        CREATE INDEX IF NOT EXISTS idx_facts_canonical ON facts(canonical_key);
        """)
        migrate_db(conn)
        seed_relationships(conn)

def register_chat(chat_id:int):
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO chats(chat_id, created_at) VALUES (?, ?)", (chat_id, now_iso()))

def get_chats():
    with connect() as conn:
        return [r["chat_id"] for r in conn.execute("SELECT chat_id FROM chats").fetchall()]

def canonicalize(title):
    stop = {"the","a","an","to","of","and","in","on","for","with","as","by","from","after","over","under","new","latest"}
    words = []
    for w in "".join(ch.lower() if ch.isalnum() else " " for ch in title).split():
        if len(w) > 2 and w not in stop:
            words.append(w)
    return " ".join(words[:12])

def fingerprint(title, source_url):
    return hashlib.sha256((title.lower().strip()+"|"+source_url.lower().strip()).encode()).hexdigest()

def upsert_source(name, url, source_type="unknown", region="global", success=True):
    with connect() as conn:
        ts = now_iso()
        conn.execute("""
        INSERT INTO sources(name,url,source_type,region,first_seen,last_seen,success_count,error_count)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(name,url) DO UPDATE SET
            last_seen=excluded.last_seen,
            success_count=sources.success_count + ?,
            error_count=sources.error_count + ?
        """, (name,url,source_type,region,ts,ts,1 if success else 0,0 if success else 1,1 if success else 0,0 if success else 1))

def find_similar_fact(canonical_key):
    with connect() as conn:
        key_words = set(canonical_key.split())
        rows = conn.execute("SELECT * FROM facts ORDER BY created_at DESC LIMIT 80").fetchall()
        for r in rows:
            other = set(r["canonical_key"].split())
            if not key_words or not other:
                continue
            overlap = len(key_words & other) / max(1, min(len(key_words), len(other)))
            if overlap >= 0.65:
                return r
    return None

def insert_or_merge_fact(fact):
    fp = fingerprint(fact["title"], fact["source_url"])
    ckey = canonicalize(fact["title"])
    ts = now_iso()
    similar = find_similar_fact(ckey)

    with connect() as conn:
        if similar:
            fact_id = similar["id"]
            new_conf = min(100, max(similar["confidence_score"], fact["confidence_score"]) + 3)
            new_status = "verified" if new_conf >= 78 else similar["lifecycle_status"]
            conn.execute("""
            UPDATE facts SET confidence_score=?, lifecycle_status=?, updated_at=?
            WHERE id=?
            """, (new_conf, new_status, ts, fact_id))
            conn.execute("""
            INSERT OR IGNORE INTO fact_sources(fact_id, source_name, source_url, created_at)
            VALUES(?,?,?,?)
            """, (fact_id, fact["source_name"], fact["source_url"], ts))
            return fact_id, "merged"

        try:
            cur = conn.execute("""
            INSERT INTO facts(
                fingerprint, canonical_key, title, summary, category, country, lifecycle_status,
                actual_value, expected_value, previous_value, surprise,
                impact_score, novelty_score, confidence_score, urgency_score,
                affected_markets, source_name, source_url, source_type, source_region,
                published_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                fp, ckey, fact["title"], fact["summary"], fact["category"], fact.get("country","Global"), fact.get("lifecycle_status","breaking"),
                fact.get("actual_value"), fact.get("expected_value"), fact.get("previous_value"), fact.get("surprise"),
                fact["impact_score"], fact["novelty_score"], fact["confidence_score"], fact["urgency_score"],
                ",".join(fact.get("affected_markets",[])),
                fact["source_name"], fact["source_url"], fact.get("source_type","unknown"), fact.get("source_region","global"),
                fact.get("published_at"), ts, ts
            ))
            fact_id = cur.lastrowid
            conn.execute("""
            INSERT OR IGNORE INTO fact_sources(fact_id, source_name, source_url, created_at)
            VALUES(?,?,?,?)
            """, (fact_id, fact["source_name"], fact["source_url"], ts))
            return fact_id, "inserted"
        except sqlite3.IntegrityError:
            return None, "duplicate"

def log_refresh(mode, inserted, merged, errors):
    with connect() as conn:
        conn.execute("""
        INSERT INTO refresh_log(mode, inserted_count, merged_count, error_count, created_at)
        VALUES(?,?,?,?,?)
        """, (mode, inserted, merged, errors, now_iso()))

def latest_fact():
    with connect() as conn:
        return conn.execute("SELECT * FROM facts ORDER BY impact_score DESC, created_at DESC LIMIT 1").fetchone()

def recent_facts(limit=10, category=None):
    with connect() as conn:
        if category:
            return conn.execute("SELECT * FROM facts WHERE category LIKE ? ORDER BY created_at DESC LIMIT ?", (f"%{category}%", limit)).fetchall()
        return conn.execute("SELECT * FROM facts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()

def high_impact_facts(limit=10):
    with connect() as conn:
        return conn.execute("SELECT * FROM facts ORDER BY impact_score DESC, created_at DESC LIMIT ?", (limit,)).fetchall()

def search_facts(query, limit=10):
    q = f"%{query.lower()}%"
    with connect() as conn:
        return conn.execute("""
        SELECT * FROM facts
        WHERE lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(category) LIKE ? OR lower(affected_markets) LIKE ?
        ORDER BY created_at DESC LIMIT ?
        """, (q,q,q,q,limit)).fetchall()

def db_stats():
    with connect() as conn:
        last = conn.execute("SELECT * FROM refresh_log ORDER BY created_at DESC LIMIT 1").fetchone()
        return {
            "facts": conn.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"],
            "sources": conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"],
            "relationships": conn.execute("SELECT COUNT(*) c FROM relationships").fetchone()["c"],
            "outcomes": conn.execute("SELECT COUNT(*) c FROM outcomes").fetchone()["c"],
            "chats": conn.execute("SELECT COUNT(*) c FROM chats").fetchone()["c"],
            "last_refresh": dict(last) if last else None,
        }

def source_stats(limit=12):
    with connect() as conn:
        return conn.execute("""
        SELECT source_name, source_type, source_region, COUNT(*) count
        FROM facts GROUP BY source_name, source_type, source_region
        ORDER BY count DESC LIMIT ?
        """, (limit,)).fetchall()

def relationships_for(topic):
    q = f"%{topic.lower()}%"
    with connect() as conn:
        return conn.execute("""
        SELECT * FROM relationships WHERE lower(source_node) LIKE ? OR lower(target_node) LIKE ?
        ORDER BY confidence DESC LIMIT 12
        """, (q,q)).fetchall()

def seed_relationships(conn):
    rows = [
        ("Oil", "can increase", "Inflation", "Higher oil can raise transport and production costs.", 85),
        ("Inflation", "can lead to", "Higher Interest Rates", "Central banks may keep rates high when prices rise too quickly.", 90),
        ("Higher Interest Rates", "can raise", "Mortgage Costs", "Higher rates often push borrowing costs higher.", 88),
        ("Mortgage Costs", "can reduce", "Housing Demand", "Higher monthly payments make homes less affordable.", 86),
        ("Housing Demand", "can affect", "Construction", "Lower demand can slow new building activity.", 75),
        ("Employment", "supports", "Consumer Spending", "More jobs and wages usually help people spend more.", 84),
        ("Consumer Spending", "drives", "Corporate Earnings", "Many companies earn more when consumers spend more.", 80),
        ("Credit Tightening", "can reduce", "Business Investment", "If loans become harder to get, companies may invest less.", 82),
        ("Strong USD", "can pressure", "Commodities", "A stronger dollar can make dollar-priced commodities more expensive abroad.", 70),
        ("Weak Growth", "can pressure", "Stocks", "Slower growth can reduce company earnings expectations.", 78),
    ]
    for r in rows:
        conn.execute("""
        INSERT OR IGNORE INTO relationships(source_node, relation, target_node, explanation, confidence)
        VALUES(?,?,?,?,?)
        """, r)
