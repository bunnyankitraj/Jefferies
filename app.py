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
    
    /* Reveal header for Deploy button visibility */
    header {{visibility: visible !important;}}
    
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }}
    
    h1 {{
        margin-bottom: 0.5rem !important;
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
        r.entry_date, r.stock_name, r.rating, r.target_price, r.broker,
        a.title, a.source, a.published_date, a.url, a.fetched_at
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
        
        df['date_dt'] = pd.to_datetime(df['published_date'], errors='coerce')
        
        def to_ist(dt):
            if pd.isnull(dt): return dt
            if isinstance(dt, str):
                dt = pd.to_datetime(dt, errors='coerce')
            if dt is None or pd.isnull(dt): return dt
            
            if dt.tzinfo is None:
                # If naive, we check if it's likely a UTC string or a legacy IST string
                # For safety, standard is UTC storage. 
                # If it's a future time of now, it's definitely double-timezone bug
                dt = pytz.utc.localize(dt)
            return dt.astimezone(ist_tz)
        
        df['date_dt'] = df['date_dt'].apply(to_ist)
        # Apply to_ist to fetched_at as well
        df['fetched_dt'] = pd.to_datetime(df['fetched_at'], errors='coerce').apply(to_ist)
        df = df.dropna(subset=['date_dt'])
        
        # Latest Fetch Time
        latest_fetch = df['fetched_dt'].max()
        if pd.notnull(latest_fetch):
            latest_fetch_ist = latest_fetch.strftime('%d %b, %I:%M %p')
            st.caption(f"⏱️ Latest update processed at: **{latest_fetch_ist}** (IST)")

        df['display_date'] = df['date_dt'].dt.strftime('%d %b %Y, %I:%M %p')
        df['url'] = df['url'].apply(clean_url)
        df = df.sort_values('date_dt', ascending=False).drop_duplicates(subset=['stock_name', 'url', 'broker'])

        # --- FILTERS (Back on Main Page) ---
        with st.expander("🔍 Filter & Search Options", expanded=True):
            all_stocks = sorted(df['stock_name'].unique())
            c_s1, c_s2 = st.columns([1, 4])
            with c_s1:
                all_stocks_toggle = st.checkbox("Select All Stocks", value=False)
            with c_s2:
                default_stocks = all_stocks if all_stocks_toggle else []
                selected_stocks = st.multiselect("Stocks", options=all_stocks, default=default_stocks)
            
            c1, c2 = st.columns(2)
            with c1:
                available_ratings = sorted(df['rating'].fillna("Unknown").unique().tolist())
                all_ratings_toggle = st.checkbox("Select All Ratings", value=not bool(st.session_state.get('sel_ratings')))
                default_ratings = available_ratings if all_ratings_toggle else []
                sel_ratings = st.multiselect("Ratings", options=available_ratings, default=default_ratings)
            with c2:
                available_brokers = sorted(df['broker'].fillna("Jefferies").unique().tolist())
                all_brokers_toggle = st.checkbox("Select All Brokers", value=not bool(st.session_state.get('sel_brokers')))
                default_brokers = available_brokers if all_brokers_toggle else []
                sel_brokers = st.multiselect("Brokers", options=available_brokers, default=default_brokers)
            
            st.divider()
            c3, c4 = st.columns(2)
            with c3:
                date_preset = st.radio("Date Range", ["All Time", "Last 24 Hours", "Last 7 Days", "Custom"], horizontal=True)
            with c4:
                date_range = None
                if date_preset == "Custom":
                    min_d_val = df['date_dt'].min().date()
                    max_d_val = date.today()
                    date_range = st.date_input("Range", value=(min_d_val, max_d_val))

        # Apply Filters
        f_df = df.copy()
        if selected_stocks:
            f_df = f_df[f_df['stock_name'].isin(selected_stocks)]
        if sel_ratings:
            f_df = f_df[f_df['rating'].isin(sel_ratings)]
        if sel_brokers:
            f_df = f_df[f_df['broker'].isin(sel_brokers)]
        
        now_ist = datetime.now(ist_tz)
        if date_preset == "Last 24 Hours":
            f_df = f_df[f_df['date_dt'] >= (now_ist - timedelta(days=1))]
        elif date_preset == "Last 7 Days":
            f_df = f_df[f_df['date_dt'] >= (now_ist - timedelta(days=7))]
        elif date_preset == "Custom" and isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['date_dt'].dt.date >= date_range[0]) & (f_df['date_dt'].dt.date <= date_range[1])]

        if f_df.empty:
            st.warning("No matches found.")
        else:
            # Expansion Control (Main Page)
            col_exp1, col_exp2, col_exp3 = st.columns([2, 5, 2])
            with col_exp1:
                expand_all = st.checkbox("Expand All", value=False)
            with col_exp3:
                # Add Data Export
                csv = f_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"stock_tracker_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv',
                    use_container_width=True
                )
            
            stocks_sorted = f_df.groupby('stock_name')['date_dt'].max().sort_values(ascending=False).index.tolist()
            
            for stock in stocks_sorted:
                s_data = f_df[f_df['stock_name'] == stock]
                # Sort inner results by date descending (latest first)
                s_data = s_data.sort_values('date_dt', ascending=False)
                
                # Get the absolute most recent news time for this stock in IST
                latest_time_str = s_data.iloc[0]['date_dt'].strftime('%d %b, %I:%M %p')
                
                # Check for Combined Signal (Jefferies + JPMC both Buy)
                jefferies_buy = s_data[(s_data['broker'] == 'Jefferies') & (s_data['rating'] == 'Buy')]
                jpm_buy = s_data[(s_data['broker'] == 'JPMC') & (s_data['rating'] == 'Buy')]
                
                is_combined_up = not jefferies_buy.empty and not jpm_buy.empty
                top = s_data.iloc[0]
                
                if is_combined_up:
                    combined_target = min(jefferies_buy['target_price'].min(), jpm_buy['target_price'].min())
                    tp_str = f"₹{combined_target:,.0f}" if pd.notnull(combined_target) else "N/A"
                    label = f"🚀 :blue[**{stock}**] | Rating: :green[**BUY**] | Target: **{tp_str}** | 🕒 {latest_time_str}"
                else:
                    h_c = "gray"
                    if "Buy" in top['rating']: h_c = "green"
                    elif "Sell" in top['rating']: h_c = "red"
                    elif "Hold" in top['rating']: h_c = "orange"
                    
                    tp = f"₹{top['target_price']:,.0f}" if pd.notnull(top['target_price']) else "N/A"
                    label = f":blue[**{stock}**] | Rating: :{h_c}[{top['rating']}] | Target: {tp} ({top['broker']}) | 🕒 {latest_time_str}"
                
                with st.expander(label, expanded=expand_all):
                    if is_combined_up:
                        st.info(f"Both Jefferies and JPMC have issued a **BUY** rating for {stock}. Status is **BUY** and Target is the minimum: **{tp_str}**. (Last updated: {latest_time_str})")
                    
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
                            f"<span style='background:#444; color:#fff; padding:2px 8px; border-radius:12px; margin-right:8px;'>{row['broker']}</span>"
                            f"<span style='background:{bg}; color:{c_tc}; padding:2px 8px; border-radius:12px;'>{rat}</span>"
                            f"<span style='margin-left:8px;'>{fmt_tp}</span>"
                            f" | <span>{row['source']}</span> | <span>{row['display_date']}</span>"
                            f"</div>"
                        )
                        st.markdown(meta_html, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
