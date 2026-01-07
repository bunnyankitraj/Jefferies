import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

# Load env if not already loaded (though job.py should do it)
load_dotenv()

class StockRating:
    def __init__(self, stock_name, rating, target_price):
        self.stock_name = stock_name
        self.rating = rating
        self.target_price = target_price
        
    def __repr__(self):
        return f"<StockRating {self.stock_name} {self.rating} {self.target_price}>"

def analyze_article(article_data):
    """
    Uses Groq LLM to analyze the article text and extract stock ratings.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY not found.")
        return []

    client = Groq(api_key=api_key)
    
    text = f"Title: {article_data['title']}\nDescription: {article_data.get('desc', '')}"
    
    prompt = f"""
    You are a financial news analyzer. 
    Analyze the following news snippet related to 'Jefferies' and extract structured data about stock ratings.
    
    News Snippet:
    {text}
    
    Extract the following for each stock mentioned:
    1. Stock Name (e.g. Tata Motors, HDFC Bank). 
       IMPORTANT: Do NOT extract generic SECTOR names like 'Hotels'. Only specific COMPANY names.
       IMPORTANT: Do NOT extract days (e.g. Monday), months (e.g. January), or time references.
       Normalize names: Remove 'Ltd', 'Limited', 'India' suffixes. Use 'Tata Steel' not 'Tata Steel Ltd'.
    2. Rating (Buy, Sell, Hold, Underperform, Outperform) - if not explicitly stated, infer or set "Unknown".
    3. Target Price (Numeric value in INR) - if not stated, set null.
    
    Return the output strictly as a JSON list of objects. 
    Example: 
    [
        {{"stock_name": "Tata Motors", "rating": "Buy", "target_price": 1000.0}}
    ]
    
    If no specific company stock is found, return [].
    Do not add any markdown formatting like ```json ... ```. Just return the raw JSON string.
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
        )
        
        response_content = chat_completion.choices[0].message.content.strip()
        
        # Cleanup in case LLM adds backticks
        response_content = response_content.replace("```json", "").replace("```", "")
        
        data = json.loads(response_content)
        
        ratings = []
        for item in data:
            # Validate essential fields
            if item.get("stock_name") and item.get("stock_name") != "Unknown":
                ratings.append(StockRating(
                    item["stock_name"], 
                    item.get("rating", "Unknown"), 
                    item.get("target_price")
                ))
        return ratings

    except Exception as e:
        print(f"Error analyzing with Groq: {e}")
        return []
