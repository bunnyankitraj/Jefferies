import streamlit as st
import pandas as pd
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

st.markdown(f"""
<style>
    /* App Background */
    .stApp {{
        background-color: {main_bg};
        color: {text_color};
    }}
    
    /* Force date column to be single line */
    td:nth-child(1) {{ white-space: nowrap !important; }}
    /* General table styling */
    td {{ vertical-align: middle !important; }}
    
    /* Hide Streamlit Branding - Aggressive */
    #MainMenu {{display: none !important;}}
    footer {{display: none !important;}}
    header {{display: none !important;}}
    
    /* Hide 'Hosted with Streamlit' Badge specifically */
    div[class*="viewerBadge"] {{display: none !important;}}
    .stApp > header {{display: none !important;}}
    .STHeader {{display: none !important;}}
    
    /* Reduce Top Spacing - Aggressive */
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }}
    /* Pull Title Up */
    h1 {{
        margin-top: 0 !important;
        padding-top: 0 !important;
    }}
</style>
""", unsafe_allow_html=True)

# --- HEADER SECTION ---
header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.markdown("<h2 style='margin:0; padding:0;'>Jefferies India Stock Tracker</h2>", unsafe_allow_html=True)
with header_col2:
    if st.button("🔄 Fetch News", help="Updates in background", key="top_fetch", use_container_width=True):
        def bg_task():
            try: run_job()
            except Exception as e: print(f"Bg Job Error: {e}")
        threading.Thread(target=bg_task).start()
        st.toast("Background fetch started! 🏃")

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# Data Loading
db = get_db()

# Sidebar - Simplified
st.sidebar.markdown("### ⚙️ Controls")
if st.sidebar.button("Full Sync", help="Fetch and Reload Page"):
    with st.spinner("Syncing..."):
        try:
            run_job()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# Admin / Setup (For Cloud Deployment)
with st.sidebar.expander("System Status"):
    try:
        if "known_stocks" in db.table_names():
            count = db["known_stocks"].count
        else:
            count = 0
        st.write(f"**Master List:** {count} stocks")
        if count == 0:
            if st.button("Initialize Master List"):
                with st.spinner("Downloading NSE List..."):
                    from fetch_full_list import fetch_and_store_full_list
                    fetch_and_store_full_list()
                    st.rerun()
    except Exception as e:
        st.error(f"Status Error: {e}")

query = """
SELECT 
    r.entry_date,
    r.stock_name,
    r.rating,
    r.target_price,
    a.title,
    a.source,
    a.published_date,
    a.url
FROM stock_ratings r
JOIN news_articles a ON r.article_id = a.id
"""

try:
    df = pd.read_sql_query(query, db.conn)
except Exception:
    df = pd.DataFrame()

# Visualization Logic
if not df.empty:
    # ... (Maintenance lists same as before)
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    MISC = ["Unknown", "Yesterday", "Today", "Tomorrow", "Week", "Year", "Month", "Daily", "Weekly", "Monthly", "Report", "Analysis", "Market"]
    BLACKLIST = ["Hotels", "Stocks", "Banks", "Finance", "Power", "Jefferies", "India", "Airports", "Airlines"] + DAYS + MONTHS + MISC
    
    df = df[~df['stock_name'].isin(BLACKLIST)]
    df = df[~df['source'].str.contains('scanx.trade', case=False, na=False)]
    df['published_datetime'] = pd.to_datetime(df['published_date'], errors='coerce')
    df = df.sort_values(by='published_datetime', ascending=False)
    df['normalized_name'] = df['stock_name'].apply(normalize_name)
    df['url'] = df['url'].apply(clean_url)
    df = df.drop_duplicates(subset=['title', 'normalized_name'], keep='first')
    df = df.drop_duplicates(subset=['url', 'normalized_name'], keep='first')
    df['display_date'] = df['published_datetime'].dt.strftime('%d-%m-%Y %I:%M %p').fillna(df['published_date'])

    # --- FILTER ROW ---
    f_col1, f_col2, f_col3 = st.columns([2.5, 1.2, 1.5])
    
    with f_col1:
        all_stocks = sorted(df['normalized_name'].unique().tolist())
        selected_stocks = st.multiselect("🔍 Search Stocks", options=all_stocks, placeholder="e.g. Reliance, Tata...")
    
    with f_col2:
        standard_ratings = ["Buy", "Sell", "Hold", "Unknown"]
        selected_ratings = st.multiselect("📊 Rating", options=standard_ratings)

    with f_col3:
        # Determine valid range
        min_date = df['published_datetime'].min().date() if pd.notnull(df['published_datetime'].min()) else date.today()
        db_max = df['published_datetime'].max().date() if pd.notnull(df['published_datetime'].max()) else date.today()
        today_date = date.today()
        max_date = max(db_max, today_date)

        if "date_range_val" not in st.session_state:
            st.session_state.date_range_val = (min_date, max_date)

        def set_date_state(val):
            s, e = val
            s = max(min_date, min(s, max_date))
            e = max(min_date, min(e, max_date))
            if s > e: s = e
            st.session_state.date_range_val = (s, e)
        
        st.write("**📅 Date Range**")
        date_range = st.date_input("Date Range", min_value=min_date, max_value=max_date, key="date_range_val", label_visibility="collapsed")
        
        # Micro-Presets
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        p_col1.button("1D", on_click=lambda: set_date_state((today_date, today_date)), help="Today", key="p_1d")
        p_col2.button("7D", on_click=lambda: set_date_state((today_date - timedelta(days=7), today_date)), help="7 Days", key="p_7d")
        p_col3.button("1M", on_click=lambda: set_date_state((today_date - timedelta(days=30), today_date)), help="1 Month", key="p_1m")
        p_col4.button("✖", on_click=lambda: set_date_state((min_date, max_date)), help="Reset", key="p_reset")

        p_col4.button("✖", on_click=lambda: set_date_state((min_date, max_date)), help="Reset", key="p_reset")

    # Apply Filters
    df_filtered = df.copy()
    
    if selected_stocks:
        df_filtered = df_filtered[df_filtered['normalized_name'].isin(selected_stocks)]
        
    if selected_ratings:
        # create a regex pattern to match any selected rating
        pattern = '|'.join(selected_ratings)
        df_filtered = df_filtered[df_filtered['rating'].str.contains(pattern, case=False, na=False)]
        
    if date_range and isinstance(date_range, tuple):
        if len(date_range) == 2:
            start_d, end_d = date_range
            df_filtered = df_filtered[
                (df_filtered['published_datetime'].dt.date >= start_d) & 
                (df_filtered['published_datetime'].dt.date <= end_d)
            ]
        elif len(date_range) == 1:
            # Handle single date selection edge case
            start_d = date_range[0]
            df_filtered = df_filtered[df_filtered['published_datetime'].dt.date >= start_d]

    # 3. Group Display
    if df_filtered.empty:
        st.info("No stocks found matching your search.")
    else:
        # Get unique stocks from the already sorted dataframe
        unique_stocks = df_filtered['normalized_name'].unique()
        
        st.write(f"Showing {len(unique_stocks)} stocks")
        
        for stock in unique_stocks:
            stock_data = df_filtered[df_filtered['normalized_name'] == stock]
            latest_row = stock_data.iloc[0] # Because it is sorted
            
            # Header Info
            rating = latest_row['rating'] if latest_row['rating'] else "N/A"
            target = f"₹{latest_row['target_price']}" if pd.notnull(latest_row['target_price']) else "N/A"
            
            # Color code header
            header_color = "gray"
            if "Buy" in rating: header_color = "green"
            elif "Sell" in rating: header_color = "red"
            
            # Use blue color for stock name to make it stand out
            expand_label = f":blue[**{stock}**] | Rating: :{header_color}[{rating}] | Target: {target} | *Last Update: {latest_row['display_date']}*"
            
            with st.expander(expand_label, expanded=True if selected_stocks else False):
                # Mobile-Friendly List View (Vertical Stack)
                for _, row in stock_data.iterrows():
                    # Card Container Start - Added colorful accent border-left
                    st.markdown(f"""
                    <div style="
                        border: 1px solid {border_color};
                        border-left: 4px solid #00d4ff;
                        border-radius: 8px;
                        padding: 16px;
                        margin-bottom: 12px;
                        background-color: {card_bg};
                        transition: transform 0.2s;
                    ">
                        <div style="font-size: 1.1em; font-weight: 600; margin-bottom: 8px;">
                             <a href="{row['url']}" target="_blank" style="text-decoration: none; color: #00d4ff">{row['title']}</a>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Logic for Rating Badge
                    rat = row.get('rating', 'Unknown')
                    bg_badge = "#666"
                    if "Buy" in rat: bg_badge = "#28a745"
                    elif "Sell" in rat: bg_badge = "#dc3545"
                    elif "Hold" in rat: bg_badge = "#ffc107"
                    
                    text_badge = '#000' if 'Hold' in rat else '#fff'
                    rat_badge = f"<span style='background-color: {bg_badge}; color: {text_badge}; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 8px;'>{rat}</span>"

                    target_str = ""
                    if pd.notnull(row['target_price']) and row['target_price'] > 0:
                        fmt_tp = f"{int(row['target_price']):,}"
                        target_str = f"<span style='margin-left: 8px; color: {text_color};'>🎯 <b>₹{fmt_tp}</b></span>"

                    # Metadata Line
                    meta_html = (
                        f"<div style='margin-top: 6px; display: flex; align-items: center; flex-wrap: wrap; font-size: 0.9em; color: {meta_text};'>"
                        f"{rat_badge}"
                        f"{target_str}"
                        f"<span style='margin: 0 10px; opacity: 0.5;'>|</span>"
                        f"<span>{row['source']}</span>"
                        f"<span style='margin: 0 10px; opacity: 0.5;'>|</span>"
                        f"<span>{row['display_date']}</span>"
                        f"</div>"
                    )
                    st.markdown(meta_html, unsafe_allow_html=True)
                    
                    # Close Card
                    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("No data found. Click 'Fetch Latest News' in the sidebar.")

