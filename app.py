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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Inter', sans-serif;
        background-color: {main_bg};
        color: {text_color};
    }}

    /* Global Transitions */
    * {{ transition: all 0.2s ease-in-out; }}

    /* Hide Streamlit Branding */
    #MainMenu, footer, header, div[class*="viewerBadge"], .stApp > header, .STHeader {{
        display: none !important;
    }}

    /* Layout Spacing */
    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1200px;
    }}

    /* Header Styling */
    h2 {{
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #00d4ff !important;
        margin-bottom: 1rem !important;
    }}

    /* Glassmorphism Cards & Inputs */
    .stMultiSelect, .stDateInput, div[data-testid="stExpander"] {{
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
    }}

    /* Premium Button Styling */
    .stButton > button {{
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(0, 212, 255, 0.05)) !important;
        color: #00d4ff !important;
        border: 1px solid rgba(0, 212, 255, 0.3) !important;
        border-radius: 10px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.75rem !important;
    }}

    .stButton > button:hover {{
        background: rgba(0, 212, 255, 0.2) !important;
        border-color: #00d4ff !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.2) !important;
        transform: translateY(-2px);
    }}

    /* Inputs Focus & Selection */
    .stMultiSelect [data-baseweb="tag"] {{
        background-color: #00d4ff !important;
        color: #000 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}

    /* Custom Scrollbar */
    ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
    ::-webkit-scrollbar-track {{ background: rgba(255, 255, 255, 0.02); }}
    ::-webkit-scrollbar-thumb {{ background: rgba(0, 212, 255, 0.2); border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(0, 212, 255, 0.4); }}
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
    a.url,
    p.close as current_price,
    p.date as price_date
FROM stock_ratings r
JOIN news_articles a ON r.article_id = a.id
LEFT JOIN known_stocks k ON r.stock_name = k.company_name
LEFT JOIN (
    SELECT symbol, close, date
    FROM stock_prices
    WHERE id IN (SELECT MAX(id) FROM stock_prices GROUP BY symbol)
) p ON k.symbol = p.symbol
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
        # Collapsible Date Filter for Mobile-Friendly UI
        with st.expander("📅 Date Range", expanded=False):
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
            
            date_range = st.date_input("Select Date Range", min_value=min_date, max_value=max_date, key="date_range_val", label_visibility="collapsed")
            
            # Quick Presets in horizontal layout
            st.markdown("<div style='margin-top: 10px; margin-bottom: 5px; font-size: 0.9em; color: #ccc;'>Quick Select:</div>", unsafe_allow_html=True)
            p_col1, p_col2, p_col3, p_col4 = st.columns(4)
            p_col1.button("1D", on_click=lambda: set_date_state((today_date, today_date)), help="Today", key="p_1d")
            p_col2.button("7D", on_click=lambda: set_date_state((today_date - timedelta(days=7), today_date)), help="Last 7 Days", key="p_7d")
            p_col3.button("1M", on_click=lambda: set_date_state((today_date - timedelta(days=30), today_date)), help="Last Month", key="p_1m")
            p_col4.button("✖", on_click=lambda: set_date_state((min_date, max_date)), help="Reset to All", key="p_reset")

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
            
            # Price Info
            curr_price = f"₹{latest_row['current_price']}" if pd.notnull(latest_row['current_price']) else ""
            price_segment = f" | Price: **{curr_price}**" if curr_price else ""
            
            # Use blue color for stock name to make it stand out
            expand_label = f":blue[**{stock}**]{price_segment} | Rating: :{header_color}[{rating}] | Target: {target} | *Last Update: {latest_row['display_date']}*"
            
            with st.expander(expand_label, expanded=True if selected_stocks else False):
                # Mobile-Friendly List View (Vertical Stack)
                for _, row in stock_data.iterrows():
                    # Card Container Start - Modern glassmorphic card
                    st.markdown(f"""
                    <div style="
                        background: rgba(255, 255, 255, 0.02);
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-left: 4px solid #00d4ff;
                        border-radius: 12px;
                        padding: 1.25rem;
                        margin-bottom: 1rem;
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    ">
                        <div style="font-size: 1.05rem; font-weight: 600; line-height: 1.4; margin-bottom: 0.75rem;">
                             <a href="{row['url']}" target="_blank" style="text-decoration: none; color: #00d4ff; transition: color 0.2s;">{row['title']}</a>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Sentiment-aware Badge Styling
                    rat = row.get('rating', 'Unknown')
                    bg_badge = "rgba(100, 100, 100, 0.2)"
                    text_color_badge = "#ccc"
                    if "Buy" in rat: 
                        bg_badge = "rgba(40, 167, 69, 0.15)"
                        text_color_badge = "#28a745"
                    elif "Sell" in rat: 
                        bg_badge = "rgba(220, 53, 69, 0.15)"
                        text_color_badge = "#dc3545"
                    elif "Hold" in rat: 
                        bg_badge = "rgba(255, 193, 7, 0.15)"
                        text_color_badge = "#ffc107"
                    
                    rat_badge = f"<span style='background: {bg_badge}; color: {text_color_badge}; padding: 4px 10px; border-radius: 8px; font-size: 0.75rem; font-weight: 600; border: 1px solid {bg_badge};'>{rat}</span>"

                    target_str = ""
                    if pd.notnull(row['target_price']) and row['target_price'] > 0:
                        fmt_tp = f"{int(row['target_price']):,}"
                        target_str = f"<span style='margin-left: 12px; font-size: 0.85rem; color: {text_color}; opacity: 0.9;'>🎯 <b>₹{fmt_tp}</b></span>"

                    # Metadata Row
                    meta_html = (
                        f"<div style='display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 0.5rem;'>"
                        f"{rat_badge}"
                        f"{target_str}"
                        f"<div style='flex-grow: 1;'></div>"
                        f"<div style='font-size: 0.75rem; color: {meta_text}; opacity: 0.7;'>{row['source']} • {row['display_date']}</div>"
                        f"</div>"
                    )
                    st.markdown(meta_html, unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("No data found. Click 'Fetch Latest News' in the sidebar.")

