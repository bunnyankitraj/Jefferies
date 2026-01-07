from GoogleNews import GoogleNews
import dateparser
from datetime import datetime
import time

def fetch_jefferies_news(days=1):
    """
    Fetches news about 'Jefferies' and 'India' or 'Stocks' from the last N days.
    """
    gn = GoogleNews(lang='en', region='IN')
    # ... (rest of configuration)

    # Note: dateparser is heavy, but useful for '5 hours ago'
    
    gn.set_period(f'{days}d')
    
    queries = [
        "Jefferies India stock target",
        "Jefferies upgrade India stock",
        "Jefferies downgrade India stock",
        "Jefferies maintain buy India"
    ]
    
    all_articles = []
    seen_urls = set()
    seen_titles = set()
    
    BLACKLIST_SOURCES = ["scanx.trade", "market screener", "marketscreener"]

    print(f"Fetching news for queries: {queries}")

    for query in queries:
        try:
            gn.search(query)
            results = gn.results()
            
            for res in results:
                url = res.get('link')
                # Clean URL (remove Google tracking)
                if url:
                    url = url.split('&ved=')[0].split('&usg=')[0]
                    
                title = res.get('title')
                source = res.get('media', '').lower()
                
                # Deduplication & Filtering
                if url in seen_urls or title in seen_titles:
                    continue
                    
                if any(b in source for b in BLACKLIST_SOURCES):
                    continue
                    
                seen_urls.add(url)
                seen_titles.add(title)
                
                # Parse Date
                raw_date = res.get('date')
                parsed_date = dateparser.parse(raw_date) if raw_date else datetime.now()
                
                # Format as compatible string for DB (ISO format is best)
                published_date_str = parsed_date.isoformat() if parsed_date else str(raw_date)
                
                article = {
                    "title": res.get('title'),
                    "url": url,
                    "published_date": published_date_str, 
                    "source": res.get('media', 'Google News'),
                    "desc": res.get('desc', '') 
                }
                
                text_blob = (article['title'] + " " + article['desc']).lower()
                if "jefferies" in text_blob:
                    all_articles.append(article)
            
            gn.clear()
            time.sleep(1)
            
        except Exception as e:
            print(f"Error fetching for query '{query}': {e}")
            
    return all_articles
