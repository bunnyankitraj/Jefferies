import yfinance as yf
from .database import get_db
import pandas as pd
from datetime import datetime
import time

def fetch_eod_prices():
    """
    Fetches the latest EOD prices for all known stocks and saves them to the DB.
    """
    db = get_db()
    if "known_stocks" not in db.table_names():
        print("No known stocks found. Run master list initialization first.")
        return

    known_stocks = list(db["known_stocks"].rows)
    total = len(known_stocks)
    print(f"Starting EOD price fetch for {total} stocks...")

    count = 0
    for stock in known_stocks:
        symbol = stock["symbol"]
        # yfinance uses .NS for NSE and .BO for BSE
        ticker_symbol = f"{symbol}.NS"
        
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Get latest day's data
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                latest = hist.iloc[-1]
                entry_date = hist.index[-1].strftime('%Y-%m-%d')
                
                db["stock_prices"].insert({
                    "symbol": symbol,
                    "date": entry_date,
                    "open": float(latest["Open"]),
                    "high": float(latest["High"]),
                    "low": float(latest["Low"]),
                    "close": float(latest["Close"]),
                    "volume": int(latest["Volume"])
                }, replace=True) # Using replace=True to handle existing date entries
                
                count += 1
                if count % 10 == 0:
                    print(f"Fetched {count}/{total}...")
            else:
                print(f"No history found for {ticker_symbol}")
                
        except Exception as e:
            print(f"Error fetching {ticker_symbol}: {e}")
        
        # Be nice to the API
        time.sleep(0.5)

    print(f"Completed! Fetched prices for {count} stocks.")

if __name__ == "__main__":
    fetch_eod_prices()
