from automation.news_fetcher import fetch_jefferies_news
from automation.analyzer import analyze_article
from automation.database import init_db, save_article, save_rating
from dotenv import load_dotenv
import datetime

def run_job():
    load_dotenv()
    print(f"--- Job Started at {datetime.datetime.now()} ---")
    
    # 1. Init DB
    db = init_db()
    
    # 2. Fetch News
    articles = fetch_jefferies_news(days=2) # Look back 2 days to be safe
    print(f"Fetched {len(articles)} articles.")
    
    new_ratings_count = 0
    
    for art in articles:
        # 3. Save Article
        # We skip if existing to avoid re-analysis duplicate work, 
        # or we could just check if we analyzed it. 
        # save_article handles deduplication by returning existing ID.
        
        art_id = save_article(db, art['title'], art['url'], art['published_date'], art['source'], art.get('desc', ''))
        
        if not art_id:
            continue

        # Check if we already have ratings for this article?
        # For simplicity, we can just strictly rely on unique Art ID. 
        # But if we improve analyzer, we might want to re-analyze. 
        # For now, let's assume if it is NOT new (fetched previously), we blindly re-analyze 
        # creates potential duplicates in 'stock_ratings'. 
        # Ideally we check:
        existing_ratings = list(db["stock_ratings"].rows_where("article_id = ?", [art_id]))
        if existing_ratings:
            # Already analyzed
            continue
            
        # 4. Analyze
        ratings = analyze_article(art)
        
        for r in ratings:
            raw_name = r.stock_name
            valid_name = None
            
            # Validate against Master List
            try:
                # FTS Search
                results = list(db["known_stocks"].search(raw_name, limit=1))
                if results:
                    valid_name = results[0]['company_name']
            except Exception as e:
                print(f"Validation Error: {e}")
            
            if valid_name:
                print(f"Found Rating: {valid_name} ({r.rating}) in {art['title']}")
                save_rating(db, art_id, valid_name, r.rating, r.target_price)
                new_ratings_count += 1
            else:
                print(f"Skipped unknown stock: {raw_name}")
            
    print(f"Job Finished. Added {new_ratings_count} new ratings.")
    print("-----------------------------------")

if __name__ == "__main__":
    run_job()
