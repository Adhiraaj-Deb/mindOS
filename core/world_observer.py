"""
core/world_observer.py — Internet-connected world knowledge ingestor.

Fetches data from public RSS news feeds and major stock indices.
Automatically writes structured markdown into `09_World_Knowledge` in the vault.
"""
import os
import sys
import threading
from datetime import datetime
import feedparser
import yfinance as yf

# Insert project path to ensure config is visible from any context
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import VAULT_DIR

# Global configs
NEWS_FEEDS = {
    "BBC World News": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "Reuters Top News": "https://news.yahoo.com/rss/world", # Reuters removed standard RSS, yahoo is reliable proxy for general Top News
}

TICKERS = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Bitcoin": "BTC-USD",
    "Gold": "GC=F",
    "Apple": "AAPL"
}

def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def fetch_major_news() -> str:
    """Fetch top global news stories as markdown strings."""
    out = [f"# Current World News\n\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"]
    for source_name, url in NEWS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            out.append(f"## {source_name}")
            for entry in feed.entries[:7]:  # Top 7 from each source
                title = entry.title.replace("\n", " ").strip()
                summary = getattr(entry, "summary", "").replace("\n", " ")
                # Truncate summary if too long to prevent gigantic embeds
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                out.append(f"- **{title}** \\n  {summary}")
            out.append("")
        except Exception as e:
            out.append(f"## {source_name}\\n*Failed to fetch: {e}*\\n")
            
    return "\n".join(out)

def fetch_market_data() -> str:
    """Fetch current market pricing and 24h variation."""
    out = [f"# Global Market Overview\n\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"]
    try:
        # Batch download is much faster
        symbols = " ".join(TICKERS.values())
        data = yf.download(symbols, period="2d", interval="1d", progress=False)

        # yfinance returns a MultiIndex column DataFrame when requesting multiple tickers
        for name, symbol in TICKERS.items():
            try:
                # Close row is generic. If shape differs, handle generic extraction:
                if len(TICKERS) > 1:
                    close_prices = data["Close"][symbol]
                else:
                    close_prices = data["Close"]

                if len(close_prices) >= 1:
                    current = close_prices.iloc[-1]
                    if len(close_prices) >= 2:
                        previous = close_prices.iloc[-2]
                        diff = current - previous
                        pct = (diff / previous) * 100
                        sign = "+" if diff >= 0 else ""
                        trend = "📈" if diff >= 0 else "📉"
                        out.append(f"- **{name}** ({symbol}): ${current:,.2f} ({sign}{pct:.2f}%) {trend}")
                    else:
                        out.append(f"- **{name}** ({symbol}): ${current:,.2f}")
            except Exception as inner_e:
                out.append(f"- **{name}** ({symbol}): *Data unavailable*")
                
    except Exception as e:
        out.append(f"*Failed to fetch comprehensive market data: {e}*")

    return "\n".join(out)

def sync_world_state_sync():
    """Blocking function to write latest states to vault."""
    try:
        target_dir = os.path.join(VAULT_DIR, "09_World_Knowledge")
        
        # 1. Write News
        news_path = os.path.join(target_dir, "Current_World_News.md")
        _ensure_dir(news_path)
        news_md = fetch_major_news()
        with open(news_path, "w", encoding="utf-8") as f:
            f.write(news_md)
            
        # 2. Write Stocks
        market_path = os.path.join(target_dir, "Market_Overview.md")
        _ensure_dir(market_path)
        market_md = fetch_market_data()
        with open(market_path, "w", encoding="utf-8") as f:
            f.write(market_md)
            
        print("World state successfully synced to vault.")
    except Exception as e:
        print(f"Failed to sync world state: {e}")

def sync_world_state_async():
    """Fires the sync event on a background python thread (safe for non-UI apps)."""
    t = threading.Thread(target=sync_world_state_sync, daemon=True)
    t.start()

if __name__ == "__main__":
    sync_world_state_sync()
