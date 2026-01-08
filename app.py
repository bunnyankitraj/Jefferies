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
    # Fallback for specific Streamlit Cloud path quirks
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from automation.database import get_db
    from automation.job import run_job

import time
import threading
import re
from datetime import datetime, timedelta, date

def normalize_name(name):
    if not isinstance(name, str):
        return str(name)
    # Remove common suffixes
    name = re.sub(r'\s+(?:Ltd\.?|Limited|India|Inds\.?|Industries)\b\.?', '', name, flags=re.IGNORECASE)
    return name.strip()

def clean_url(url):
    if not isinstance(url, str):
        return url
    # Remove Google tracking parameters often appended to news links
    url = url.split('&ved=')[0]
    url = url.split('&usg=')[0]
    return url

st.set_page_config(page_title="Jefferies India Tracker", layout="wide")

# Theme: Force Dark Mode
main_bg = "#0e1117"
text_color = "#fafafa"
card_bg = "#1E1E1E"
border_color = "#333"
meta_text = "#ccc"

# 1. Dynamic CSS (Requires variables)
st.markdown(f"""
<style>
    .stApp {{
        background-color: {main_bg};
        color: {text_color};
    }}
</style>
""", unsafe_allow_html=True)

# 2. Static CSS (Safe from f-string braces)
st.markdown("""
<style>
    /* Force date column to be single line */
    td:nth-child(1) { white-space: nowrap !important; }
    /* General table styling */
    td { vertical-align: middle !important; }
    
    /* Hide Streamlit Branding */
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    header {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    
    /* Reduce Top Spacing */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }
    h1 {
        margin-top: 0 !important;
        padding-top: 0 !important;
        font-size: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("Jefferies India Stock Tracker")

# Layout: Header + Fetch Button
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.empty()
with col_h2:
    if st.button("🔄 Fetch News", help="Updates in background", key="top_fetch", use_container_width=True):
        def bg_task():
            try:
                run_job()
            except Exception as e:
                print(f"Bg Job Error: {e}")
        threading.Thread(target=bg_task).start()
        st.toast("Background fetch started! 🏃")

# Data Loading
db = get_db()

# Sidebar
st.sidebar.header("Controls")
if st.sidebar.button("Fetch Latest News"):
    with st.spinner("Fetching and Analyzing..."):
        try:
            run_job()
            st.success("Update Complete!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# Admin / Setup
with st.sidebar.expander("System Status"):
    try:
        if "known_stocks" in db.table_names():
            count = db["known_stocks"].count
        else:
            count = 0
        st.write(f"**Master List:** {count} stocks")
        if count == 0 or st.button("Initialize Master List"):
            if st.button("Start Download"):
                with st.spinner("Downloading NSE List..."):
                    try:
                        from fetch_full_list import fetch_and_store_full_list
                        fetch_and_store_full_list()
                        st.success("Done!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
    except Exception as e:
        st.error(f"Status Error: {e}")

query = """
SELECT 
    r.entry_date, r.stock_name, r.rating, r.target_price,
    a.title, a.source, a.published_date, a.url
FROM stock_ratings r
JOIN news_articles a ON r.article_id = a.id
"""

try:
    df = pd.read_sql_query(query, db.conn)
except Exception:
    df = pd.DataFrame()

if not df.empty:
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    df = df[~df['stock_name'].isin(DAYS)]
    df['date_dt'] = pd.to_datetime(df['entry_date'], errors='coerce')
    df = df.dropna(subset=['date_dt'])
    df['display_date'] = df['date_dt'].dt.strftime('%d %b %Y')
    df['url'] = df['url'].apply(clean_url)
    df = df.sort_values('date_dt', ascending=False).drop_duplicates(subset=['stock_name', 'title', 'published_date'])

    all_stocks = sorted(df['stock_name'].unique())
    selected_stocks = st.multiselect("🔍 Search Stocks", options=all_stocks)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        ratings = ["All"] + sorted(df['rating'].unique().tolist())
        sel_rating = st.selectbox("Rating", options=ratings)
    with col2:
        min_date = df['date_dt'].min().date()
        max_date = date.today()
        date_range = st.date_input("Date Range", value=(min_date, max_date))

    filtered_df = df.copy()
    if selected_stocks:
        filtered_df = filtered_df[filtered_df['stock_name'].isin(selected_stocks)]
    if sel_rating != "All":
        filtered_df = filtered_df[filtered_df['rating'] == sel_rating]

    if filtered_df.empty:
        st.warning("No matches found.")
    else:
        for stock in sorted(filtered_df['stock_name'].unique()):
            stock_data = filtered_df[filtered_df['stock_name'] == stock]
            latest_row = stock_data.iloc[0]
            rating = latest_row['rating'] or "Unknown"
            target = f"₹{latest_row['target_price']}" if pd.notnull(latest_row['target_price']) else "N/A"
            
            h_color = "gray"
            if "Buy" in rating: h_color = "green"
            elif "Sell" in rating: h_color = "red"
            
            label = f"**{stock}** | Rating: :{h_color}[{rating}] | Target: {target}"
            with st.expander(label, expanded=bool(selected_stocks)):
                for _, row in stock_data.iterrows():
                    st.markdown(f"""
                    <div style="border: 1px solid {border_color}; border-radius: 8px; padding: 16px; margin-bottom: 12px; background-color: {card_bg};">
                        <div style="font-size: 1.1em; font-weight: 600; margin-bottom: 8px;">
                             <a href="{row['url']}" target="_blank" style="text-decoration: none; color: #00d4ff">{row['title']}</a>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    rat = row.get('rating', 'Unknown')
                    bg = "#666"
                    if "Buy" in rat: bg = "#28a745"
                    elif "Sell" in rat: bg = "#dc3545"
                    elif "Hold" in rat: bg = "#ffc107"
                    
                    tc = '#000' if 'Hold' in rat else '#fff'
                    fmt_tp = f"₹{int(row['target_price']):,}" if pd.notnull(row['target_price']) else ""
                    
                    meta = (
                        f"<div style='font-size: 0.9em; color: {meta_text};'>"
                        f"<span style='background:{bg}; color:{tc}; padding:2px 8px; border-radius:12px;'>{rat}</span>"
                        f"<span style='margin-left:8px;'>{fmt_tp}</span>"
                        f" | <span>{row['source']}</span> | <span>{row['display_date']}</span>"
                        f"</div>"
                    )
                    st.markdown(meta, unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
else:
    # Check if DB is initialized to give better guidance
    try:
        if "known_stocks" not in db.table_names() or db["known_stocks"].count == 0:
            st.warning("⚠️ **Setup Required:** Streamlit Cloud starts with an empty database.")
            st.markdown("""
            ### How to fix this:
            1. Open the **"System Status"** expander in the sidebar (left).
            2. Click **"Initialize Master List"** then **"Start Download"**.
            3. Once stocks are loaded, click **"Fetch Latest News"**.
            """)
        else:
            st.info("No ratings found. Click **'Fetch Latest News'** in the sidebar to scan for today's calls.")
    except Exception:
        st.info("No data. Click 'Fetch Latest News' in the sidebar.")
