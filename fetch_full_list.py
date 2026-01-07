import pandas as pd
from automation.database import get_db
import requests
import io

# URL for Full Equity List
EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

def fetch_and_store_full_list():
    print("Fetching Full Equity list (EQUITY_L.csv)...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(EQUITY_URL, headers=headers)
        response.raise_for_status()
        
        # Read CSV
        df = pd.read_csv(io.StringIO(response.text))
        
        # Print columns to debug
        print("Columns found:", df.columns.tolist())
        
        # Columns often have trailing spaces in EQUITY_L.csv
        df.columns = [c.strip() for c in df.columns]
        
        # We need SYMBOL and NAME OF COMPANY
        df_clean = df[['SYMBOL', 'NAME OF COMPANY', 'ISIN NUMBER']].rename(columns={
            'SYMBOL': 'symbol',
            'NAME OF COMPANY': 'company_name',
            'ISIN NUMBER': 'isin'
        })
        
        print(f"Fetched {len(df_clean)} stocks.")
        
        # Store in DB
        db = get_db()
        # Using replace=True to overwrite old Nifty 500 list
        db["known_stocks"].insert_all(df_clean.to_dict('records'), pk="symbol", replace=True, batch_size=100)
        
        # Ensure FTS is enabled
        try:
             db["known_stocks"].enable_fts(["symbol", "company_name"], create_triggers=True, replace=True)
        except:
            pass

        print("Full Master list stored in database successfully.")
        
    except Exception as e:
        print(f"Error fetching master list: {e}")

if __name__ == "__main__":
    fetch_and_store_full_list()
