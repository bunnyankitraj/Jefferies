import os
import json
import re
from groq import Groq
from openai import OpenAI
from dotenv import load_dotenv

# Load env
load_dotenv()

class StockRating:
    def __init__(self, stock_name, rating, target_price):
        self.stock_name = stock_name
        self.rating = rating
        self.target_price = target_price
        
    def __repr__(self):
        return f"<StockRating {self.stock_name} {self.rating} {self.target_price}>"

def get_prompt(text, broker_name):
    return f"""
    You are a financial news analyzer specializing in '{broker_name}' equity research. 
    Analyze the following news snippet and extract structured data about stock ratings/recommendations.
    
    News Snippet:
    {text}
    
    Extract the following for each stock mentioned:
    1. Stock Name: Only specific COMPANY names (e.g. 'Tata Motors', 'Zomato'). 
       - DO NOT extract sector names (e.g. 'Auto', 'Banks', 'Hotels').
       - DO NOT extract time/days (e.g. 'Monday', 'January').
       - Normalize: Remove 'Ltd', 'Limited', 'India' suffixes.
    2. Rating: This is the CORE task. 
       - Look for words like 'Buy', 'Sell', 'Hold', 'Accumulate' (map to Buy), 'Underperform' (map to Sell), 'Outperform' (map to Buy).
       - BIFURCATE DECISIVELY: If the article discusses a "Top Pick", "Favorite", or "Upgrade", mark as 'Buy'. If it discusses "Downgrade" or "Caution", mark as 'Sell'.
       - Only use 'Unknown' if there is absolutely no sentiment or recommendation expressed.
    3. Target Price: Numeric per-share value in INR. 
       - IMPORTANT: Do NOT extract total valuation or market cap figures (e.g. '1 lakh crore', '50 billion').
       - If the price seems like a total monetary value rather than a per-share target, set null.
       - If not stated, set null.
    
    Return ONLY a raw JSON list of objects. No preamble, no markdown.
    Example: 
    [
        {{"stock_name": "Tata Motors", "rating": "Buy", "target_price": 1200.0}}
    ]
    """

def analyze_with_groq(text, broker_name):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": get_prompt(text, broker_name)}],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            print("Groq Rate Limit Reached.")
        else:
            print(f"Groq Error: {e}")
        return None

def analyze_with_openai(text, broker_name):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found.")
        return None
        
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Using mini for efficiency as fallback
            messages=[{"role": "user", "content": get_prompt(text, broker_name)}],
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None

def analyze_article(article_data, broker_name="Jefferies"):
    """
    Uses Groq LLM to analyze the article text, falling back to OpenAI if Groq fails.
    """
    text = f"Title: {article_data['title']}\nDescription: {article_data.get('desc', '')}"
    
    # Try Groq First
    response_content = analyze_with_groq(text, broker_name)
    
    # Fallback to OpenAI
    if not response_content:
        print(f"Falling back to OpenAI for {broker_name} analysis...")
        response_content = analyze_with_openai(text, broker_name)
        
    if not response_content:
        return []
    
    try:
        # Cleanup in case LLM adds backticks
        response_content = response_content.replace("```json", "").replace("```", "")
        data = json.loads(response_content)
        
        # Deduplicate results from the LLM based on stock_name
        seen_stocks = set()
        ratings = []
        for item in data:
            s_name = item.get("stock_name")
            if s_name and s_name != "Unknown" and s_name not in seen_stocks:
                seen_stocks.add(s_name)
                ratings.append(StockRating(
                    s_name, 
                    item.get("rating", "Unknown"), 
                    item.get("target_price")
                ))
        return ratings
    except Exception as e:
        print(f"Error parsing AI response: {e}")
        return []
