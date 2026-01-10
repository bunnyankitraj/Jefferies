from .news_fetcher import fetch_news
from .analyzer import analyze_article
from .database import init_db, save_article, save_rating
from dotenv import load_dotenv
import datetime

def run_job():
    load_dotenv()
    print(f"--- Job Started at {datetime.datetime.now()} ---")
    
    # 1. Init DB
    db = init_db()
    
    brokers = {
        "Jefferies": [
            "Jefferies India stock target",
            "Jefferies upgrade India stock",
            "Jefferies downgrade India stock",
            "Jefferies maintain buy India"
        ],
        "JPMC": [
            "JP Morgan India stock target",
            "JP Morgan upgrade India stock",
            "JP Morgan overweight India stock",
            "J.P. Morgan India equity research"
        ],
        "Goldman Sachs": [
            "Goldman Sachs India stock target",
            "Goldman Sachs upgrade India stock",
            "Goldman Sachs India equity research"
        ],
        "ICICI Securities": [
            "ICICI Securities stock target buy",
            "ICICI Securities research report India",
            "ICICI Securities upgrade rating"
        ],
        "Kotak": [
            "Kotak Institutional Equities stock target",
            "Kotak Securities buy rating India",
            "Kotak Investment Banking research"
        ],
        "Axis Capital": [
            "Axis Capital India stock target",
            "Axis Capital research report",
            "Axis Capital buy rating"
        ],
        "JM Financial": [
            "JM Financial stock target buy",
            "JM Financial research India",
            "JM Financial upgrade rating"
        ]
    }
    
    new_ratings_count = 0
    days_to_fetch = 2
    
    for broker_name, queries in brokers.items():
        print(f"Processing {broker_name}...")
        # 2. Fetch News
        articles = fetch_news(broker_name, queries, days=days_to_fetch)
        print(f"Fetched {len(articles)} articles for {broker_name}.")
        
        for art in articles:
            # 3. Save Article
            art_id = save_article(db, art['title'], art['url'], art['published_date'], art['source'], art.get('desc', ''))
            
            if not art_id:
                continue

            # Check if we already have ratings for this article AND this broker
            existing_ratings = list(db["stock_ratings"].rows_where("article_id = ? AND broker = ?", [art_id, broker_name]))
            if existing_ratings:
                continue
                
            # 4. Analyze
            ratings = analyze_article(art, broker_name=broker_name)
            
            for r in ratings:
                raw_name = r.stock_name
                valid_name = None
                
                # Validate against Master List
                try:
                    # Clean and quote for FTS (dots/spaces break it)
                    clean_name = raw_name.replace(".", "").replace(",", "").replace("-", " ").replace("\"", "").replace("'", "")
                    search_term = f'"{clean_name}"'
                    results = list(db["known_stocks"].search(search_term, limit=1))
                    if results:
                        valid_name = results[0]['company_name']
                except Exception as e:
                    print(f"Validation Error: {e}")
                
                if valid_name:
                    print(f"Found Rating: {valid_name} ({r.rating}) from {broker_name} in {art['title']}")
                    save_rating(db, art_id, valid_name, r.rating, r.target_price, broker_name, currency=r.currency)
                    new_ratings_count += 1
                else:
                    print(f"Skipped unknown stock: {raw_name}")
            
    print(f"Job Finished. Added {new_ratings_count} new ratings.")
    print("-----------------------------------")

if __name__ == "__main__":
    run_job()
