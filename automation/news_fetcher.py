from GoogleNews import GoogleNews
import dateparser
from datetime import datetime
import time

def fetch_news(broker_name, queries, days=7):
    """
    Fetches news about a specific broker and India/Stocks from the last N days.
    """
    gn = GoogleNews(lang='en', region='IN')
    gn.set_period(f'{days}d')
    
    all_articles = []
    seen_urls = set()
    seen_titles = set()
    
    BLACKLIST_SOURCES = ["scanx.trade", "market screener", "marketscreener"]

    print(f"Fetching news for {broker_name} with queries: {queries}")

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
                # Check for broker name in text
                match = False
                if broker_name.lower() in text_blob:
                    match = True
                elif broker_name == "JPMC" and ("jp morgan" in text_blob or "jpmorgan" in text_blob or "jpmc" in text_blob):
                    match = True
                elif broker_name == "Kotak" and ("kotak institutional equities" in text_blob or "kotak securities" in text_blob):
                    match = True
                
                if match:
                    all_articles.append(article)
            
            gn.clear()
            time.sleep(1)
            
        except Exception as e:
            print(f"Error fetching for query '{query}': {e}")
            
    return all_articles
