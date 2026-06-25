import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TIMEZONE = os.getenv("TIMEZONE", "America/Edmonton")
DB_PATH = os.getenv("DB_PATH", "econ_intel.db")

DAILY_HOUR = int(os.getenv("DAILY_HOUR", "17"))
DAILY_MINUTE = int(os.getenv("DAILY_MINUTE", "0"))
WEEKLY_HOUR = int(os.getenv("WEEKLY_HOUR", "9"))
WEEKLY_MINUTE = int(os.getenv("WEEKLY_MINUTE", "0"))

RSS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews", "news", "global"),
    ("Reuters Markets", "https://feeds.reuters.com/news/markets", "news", "global"),
    ("Associated Press Business", "https://apnews.com/hub/business?output=rss", "news", "global"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "official", "us"),
    ("Bank of Canada", "https://www.bankofcanada.ca/feed/", "official", "canada"),
    ("BLS", "https://www.bls.gov/feed/news_release.rss", "official", "us"),
    ("BEA", "https://www.bea.gov/news/glance/rss.xml", "official", "us"),
    ("EIA", "https://www.eia.gov/rss/todayinenergy.xml", "official", "energy"),
    ("IMF", "https://www.imf.org/en/News/RSS", "institution", "global"),
    ("OECD", "https://www.oecd.org/newsroom/rss.xml", "institution", "global"),
    ("ECB", "https://www.ecb.europa.eu/rss/press.html", "official", "europe"),
]

CATEGORY_KEYWORDS = {
    "Inflation": ["inflation", "cpi", "ppi", "prices", "price growth", "cost of living"],
    "Interest Rates": ["interest rate", "rates", "fed", "central bank", "monetary policy", "rate cut", "rate hike", "fomc"],
    "Employment": ["jobs", "employment", "unemployment", "payrolls", "wages", "labor market"],
    "Growth": ["gdp", "growth", "recession", "slowdown", "expansion"],
    "Energy": ["oil", "gas", "energy", "opec", "crude"],
    "Housing": ["housing", "mortgage", "real estate", "home sales", "rent"],
    "Banking/Credit": ["bank", "credit", "lending", "default", "debt", "loan"],
    "Markets": ["stocks", "bonds", "yields", "dollar", "equities", "market"],
    "Trade/Geopolitics": ["tariff", "trade", "war", "sanctions", "geopolitical"],
}

AFFECTED_MARKETS = {
    "Inflation": ["Stocks", "Bonds", "Currencies", "Gold", "Housing", "Consumer spending"],
    "Interest Rates": ["Stocks", "Bonds", "Banks", "Housing", "Currencies", "Business investment"],
    "Employment": ["Stocks", "Bonds", "Consumer spending", "Interest rates", "Housing"],
    "Growth": ["Stocks", "Commodities", "Employment", "Credit", "Government policy"],
    "Energy": ["Oil", "Inflation", "Airlines", "Consumers", "Currencies"],
    "Housing": ["Real estate", "Banks", "Construction", "Consumers", "Credit"],
    "Banking/Credit": ["Banks", "Stocks", "Credit", "Consumers", "Business investment"],
    "Markets": ["Stocks", "Bonds", "Currencies", "Portfolio risk"],
    "Trade/Geopolitics": ["Inflation", "Currencies", "Commodities", "Supply chains", "Stocks"],
}

MAJOR_RELEASE_KEYWORDS = [
    "cpi", "ppi", "nonfarm payrolls", "jobs report", "employment report", "gdp",
    "fomc", "federal reserve", "bank of canada", "ecb", "interest rate decision",
    "rate decision", "inflation report"
]
