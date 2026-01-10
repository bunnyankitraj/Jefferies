import sqlite_utils
import sqlite3
import os
from datetime import datetime
import pytz

DATABASE_PATH = "data/market_data.db"

def get_db():
    # Ensure directory exists for Cloud deployment
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return sqlite_utils.Database(DATABASE_PATH)

def init_db():
    db = get_db()
    
    # News Articles Table
    if "news_articles" not in db.table_names():
        db["news_articles"].create({
            "id": int,
            "title": str,
            "url": str,
            "published_date": str,
            "source": str,
            "raw_content": str,
            "fetched_at": str
        }, pk="id")
        # Ensure unique URLs to avoid duplicates
        db["news_articles"].create_index(["url"], unique=True)

    # Stock Ratings/Targets Table
    if "stock_ratings" not in db.table_names():
        db["stock_ratings"].create({
            "id": int,
            "article_id": int,
            "stock_ticker": str,
            "stock_name": str,
            "rating": str,  # "Buy", "Sell", "Hold", "Unknown"
            "broker": str,  # "Jefferies" or "J.P. Morgan"
            "target_price": float,
            "entry_date": str
        }, pk="id", foreign_keys=[("article_id", "news_articles", "id")])
    else:
        # Migration: Ensure broker column exists
        if "broker" not in db["stock_ratings"].columns_dict:
            db["stock_ratings"].add_column("broker", str)
        
        # Always attempt to backfill NULLs (idempotent)
        db.execute("UPDATE stock_ratings SET broker = 'Jefferies' WHERE broker IS NULL")

    # Master Stock List Table
    if "known_stocks" not in db.table_names():
        db["known_stocks"].create({
            "symbol": str,
            "company_name": str,
            "isin": str
        }, pk="symbol")
        
        # Enable FTS for fuzzy search
        try:
            db["known_stocks"].enable_fts(["symbol", "company_name"], create_triggers=True)
        except Exception:
            pass # FTS might already be enabled

    return db

def save_article(db, title, url, published_date, source, raw_content=""):
    try:
        # Check if exists
        try:
             # Try to insert, if fails due to unique constraint, it raises error
            return db["news_articles"].insert({
                "title": title,
                "url": url,
                "published_date": published_date,
                "source": source,
                "raw_content": raw_content,
                "fetched_at": datetime.now(pytz.utc).isoformat()
            }).last_rowid
            
        except sqlite3.IntegrityError:
            # Article exists, return existing ID
            return list(db["news_articles"].rows_where("url = ?", [url]))[0]["id"]
            
    except Exception as e:
        print(f"Error saving article {url}: {e}")
        return None

def save_rating(db, article_id, stock_name, rating, target_price, broker):
    # Prevent duplicate stock-article pairs for the same broker
    existing = list(db["stock_ratings"].rows_where("article_id = ? AND stock_name = ? AND broker = ?", [article_id, stock_name, broker]))
    if not existing:
        db["stock_ratings"].insert({
            "article_id": article_id,
            "stock_ticker": stock_name.upper().replace(" ", ""),
            "stock_name": stock_name,
            "rating": rating,
            "broker": broker,
            "target_price": target_price,
            "entry_date": datetime.now().date().isoformat()
        })
