import streamlit as st
import pandas as pd
import os
import sys

# Ensure current directory is in sys.path for Cloud imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Robust Imports for Cloud
try:
    from automation.database import get_db
    from automation.job import run_job
except (ImportError, KeyError):
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from automation.database import get_db
    from automation.job import run_job

import time
import threading
import re
from datetime import datetime, timedelta, date
import pytz

ist_tz = pytz.timezone('Asia/Kolkata')

def normalize_name(name):
    # Data is now pre-standardized in DB via Master List. 
    # Just basic cleanup here.
    if not isinstance(name, str):
        return str(name)
    return name.strip()

def clean_url(url):
    if not isinstance(url, str):
        return url
    url = url.split('&ved=')[0].split('&usg=')[0]
    return url

st.set_page_config(page_title="Jefferies India Tracker", layout="wide")

# Theme Variables
main_bg = "#0e1117"
text_color = "#fafafa"
card_bg = "#1E1E1E"
border_color = "#333"
meta_text = "#ccc"

# CSS for Layout
st.markdown(f"""
<style>
    .stApp {{
        background-color: {main_bg};
        color: {text_color};
    }}
    
    /* Clean up the UI without breaking functionality */
    footer {{visibility: hidden !important;}}
    header {{visibility: hidden !important; height: 0px !important;}}
    div[class*="viewerBadge"] {{display: none !important;}}
    
    .block-container {{
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }}
    
    h1 {{
        margin-bottom: 1rem !important;
    }}
</style>
""", unsafe_allow_html=True)

st.title("Jefferies India Stock Tracker")

# Data Loading Initialization
db = get_db()

# Sidebar (Keep it for advanced users)
st.sidebar.header("Controls")
if st.sidebar.button("🔄 Force Refresh"):
    st.rerun()

# --- MAIN CONTENT LOGIC ---

# Check if Database is Empty
is_db_empty = True
try:
    if "known_stocks" in db.table_names() and db["known_stocks"].count > 0:
        is_db_empty = False
except:
    pass

if is_db_empty:
    st.warning("🚀 **Welcome! Let's get your tracker set up.**")
    st.info("The database is currently empty. We need to load the master list of NSE stocks first.")
    
    if st.button("📦 Step 1: Initialize Master List", use_container_width=True):
        with st.spinner("Downloading NSE Equity List..."):
            try:
                from fetch_full_list import fetch_and_store_full_list
                fetch_and_store_full_list()
                st.success("Master List loaded! Now you can fetch news.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Setup Error: {e}")
    
    st.divider()
    st.caption("Commonly used for fresh Streamlit Cloud deployments.")

else:
    # Header Row: Search + Fetch Button
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.empty() # Placeholder for search if we want it top-level
    with col_h2:
        if st.button("🔥 Fetch Latest News", help="Scans for news and analyzes with AI", type="primary", use_container_width=True):
            def bg_task():
                try:
                    run_job()
                    print("Background Job Success")
                except Exception as e:
                    print(f"Bg Job Error: {e}")
            threading.Thread(target=bg_task).start()
            st.toast("AI analysis started in background! 🏃 Stay tuned.")

    # Query Data
    query = """
    SELECT 
        r.entry_date, r.stock_name, r.rating, r.target_price,
        a.title, a.source, a.published_date, a.url
    FROM stock_ratings r
    JOIN news_articles a ON r.article_id = a.id
    """
    
    try:
        df = pd.read_sql_query(query, db.conn)
    except:
        df = pd.DataFrame()

    if df.empty:
        st.info("No stock calls found yet. Click **'Fetch Latest News'** above to start the engine.")
    else:
        # Pre-process Data
        df['stock_name'] = df['stock_name'].apply(normalize_name)
        DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        df = df[~df['stock_name'].isin(DAYS)]
        
        # Use published_date for news time, falling back to entry_date
        df['date_dt'] = pd.to_datetime(df['published_date'], errors='coerce')
        
        def to_ist(dt):
            if pd.isnull(dt): return dt
            if dt.tzinfo is None:
                # Assume UTC if no timezone info from Google News
                dt = pytz.utc.localize(dt)
            return dt.astimezone(ist_tz)
        
        df['date_dt'] = df['date_dt'].apply(to_ist)
        df = df.dropna(subset=['date_dt'])
        
        df['display_date'] = df['date_dt'].dt.strftime('%d %b %Y, %I:%M %p')
        df['url'] = df['url'].apply(clean_url)
        # More aggressive deduplication: Same stock + Same cleansed URL = One entry
        df = df.sort_values('date_dt', ascending=False).drop_duplicates(subset=['stock_name', 'url'])

        # Filter Section
        st.divider()
        all_stocks = sorted(df['stock_name'].unique())
        selected_stocks = st.multiselect("🔍 Search Specific Stocks", options=all_stocks)
        
        c1, c2 = st.columns(2)
        with c1:
            ratings = ["All"] + sorted(df['rating'].unique().tolist())
            sel_rating = st.selectbox("Filter by Rating", options=ratings)
        with c2:
            min_d = df['date_dt'].min().date()
            max_d = date.today()
            date_range = st.date_input("Date Range", value=(min_d, max_d))

        # Apply Filters
        f_df = df.copy()
        if selected_stocks:
            f_df = f_df[f_df['stock_name'].isin(selected_stocks)]
        if sel_rating != "All":
            f_df = f_df[f_df['rating'] == sel_rating]
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['date_dt'].dt.date >= date_range[0]) & (f_df['date_dt'].dt.date <= date_range[1])]

        if f_df.empty:
            st.warning("No matches for current filters.")
        else:
            # Display Cards
            # Sort stocks by their LATEST entry_date (latest first)
            stocks_sorted = f_df.groupby('stock_name')['date_dt'].max().sort_values(ascending=False).index.tolist()
            
            for stock in stocks_sorted:
                s_data = f_df[f_df['stock_name'] == stock]
                # Sort inner results by date descending (latest first)
                s_data = s_data.sort_values('date_dt', ascending=False)
                top = s_data.iloc[0]
                
                h_c = "gray"
                if "Buy" in top['rating']: h_c = "green"
                elif "Sell" in top['rating']: h_c = "red"
                elif "Hold" in top['rating']: h_c = "orange" # Distinct from gray Unknown
                
                tp = f"₹{top['target_price']}" if pd.notnull(top['target_price']) else "N/A"
                # Stock name in cyan/blue to pop
                label = f":blue[**{stock}**] ({top['display_date']}) | Rating: :{h_c}[{top['rating']}] | Target: {tp}"
                
                with st.expander(label, expanded=bool(selected_stocks)):
                    for _, row in s_data.iterrows():
                        st.markdown(f"""
                        <div style="border: 1px solid {border_color}; border-radius: 8px; padding: 16px; margin-bottom: 12px; background-color: {card_bg};">
                            <div style="font-size: 1.1em; font-weight: 600; margin-bottom: 8px;">
                                 <a href="{row['url']}" target="_blank" style="text-decoration: none; color: #00d4ff">{row['title']}</a>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        rat = row.get('rating', 'Unknown')
                        bg = "#666" # Default Gray for Unknown
                        if "Buy" in rat: bg = "#28a745" # Green
                        elif "Sell" in rat: bg = "#dc3545" # Red
                        elif "Hold" in rat: bg = "#fb8c00" # Orange/Amber
                        
                        c_tc = '#fff'
                        fmt_tp = f"₹{int(row['target_price']):,}" if pd.notnull(row['target_price']) else ""
                        
                        meta_html = (
                            f"<div style='font-size: 0.9em; color: {meta_text};'>"
                            f"<span style='background:{bg}; color:{c_tc}; padding:2px 8px; border-radius:12px;'>{rat}</span>"
                            f"<span style='margin-left:8px;'>{fmt_tp}</span>"
                            f" | <span>{row['source']}</span> | <span>{row['display_date']}</span>"
                            f"</div>"
                        )
                        st.markdown(meta_html, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
