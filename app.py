import streamlit as st
import pandas as pd
from automation.database import get_db
from automation.job import run_job
import time
import re

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

st.markdown("""
<style>
    /* Force date column to be single line */
    td:nth-child(1) { white-space: nowrap !important; }
    /* General table styling */
    td { vertical-align: middle !important; }
</style>
""", unsafe_allow_html=True)

st.title("Jefferies India Stock Tracker")
st.markdown("### Latest Analyst Calls & Targets")

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

# Data Loading
db = get_db()

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
    # 0. Safety Cleanup (Blacklist & Dedupe)
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    MISC = ["Unknown", "Yesterday", "Today", "Tomorrow", "Week", "Year", "Month", "Daily", "Weekly", "Monthly", "Report", "Analysis", "Market"]
    
    BLACKLIST = ["Hotels", "Stocks", "Banks", "Finance", "Power", "Jefferies", "India", "Airports", "Airlines"] + DAYS + MONTHS + MISC
    df = df[~df['stock_name'].isin(BLACKLIST)]
    
    # Filter bad sources
    df = df[~df['source'].str.contains('scanx.trade', case=False, na=False)]
    
    # 0. Clean and Parse Dates (Critical for sorting)
    df['published_datetime'] = pd.to_datetime(df['published_date'], errors='coerce')
    
    # 1. Sort by Latest Date first (So dedupe keeps the newest)
    df = df.sort_values(by='published_datetime', ascending=False)
    
    # 2. Normalize Names & Clean URLs
    df['normalized_name'] = df['stock_name'].apply(normalize_name)
    df['url'] = df['url'].apply(clean_url)
    
    # 3. Strict Deduplication
    df = df.drop_duplicates(subset=['title', 'normalized_name'], keep='first')
    df = df.drop_duplicates(subset=['url', 'normalized_name'], keep='first')
    
    # Format for Display
    df['display_date'] = df['published_datetime'].dt.strftime('%d-%m-%Y %I:%M %p').fillna(df['published_date'])
    df['Article Link'] = df.apply(lambda x: f'<a href="{x["url"]}" target="_blank">{x["title"]}</a>', axis=1)

    # 2. Search Filter (Multi-select for auto-complete feel)
    all_stocks = sorted(df['normalized_name'].unique().tolist())
    selected_stocks = st.multiselect("Search Stock", options=all_stocks, placeholder="Start typing to search (e.g. Tata)...")
    
    if selected_stocks:
        # Filter by selected stocks
        mask = df['normalized_name'].isin(selected_stocks)
        df_filtered = df[mask]
    else:
        # Show all if empty
        df_filtered = df

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
            header_color = "black"
            if "Buy" in rating: header_color = "green"
            elif "Sell" in rating: header_color = "red"
            
            expand_label = f"**{stock}** | Rating: :{header_color}[{rating}] | Target: {target} | *Last Update: {latest_row['display_date']}*"
            
            with st.expander(expand_label, expanded=True if selected_stocks else False):
                # Mobile-Friendly List View (Vertical Stack)
                for _, row in stock_data.iterrows():
                    # 1. Main Title Link (Subheader size for readability)
                    st.markdown(f"[{row['title']}]({row['url']})", unsafe_allow_html=True)
                    
                    # 2. Metadata Line (Badge style using HTML)
                    rat = row['rating']
                    
                    # Manual CSS Badge
                    if "Buy" in rat:
                        # Green
                        bg_color = "#d1fae5" # Light green
                        text_color = "#065f46" # Dark green
                    elif "Sell" in rat:
                        # Red
                        bg_color = "#fee2e2" # Light red
                        text_color = "#991b1b" # Dark red
                    else:
                        # Gray
                        bg_color = "#f3f4f6"
                        text_color = "#1f2937"
                        
                    rat_badge = f"<span style='background-color: {bg_color}; color: {text_color}; padding: 4px 8px; border-radius: 6px; font-size: 0.85em; font-weight: 600;'>{rat}</span>"
                    
                    # Target Formatting
                    target_str = ""
                    if pd.notnull(row['target_price']):
                        tp = row['target_price']
                        fmt_tp = f"{int(tp)}" if tp == int(tp) else f"{tp:.2f}"
                        target_str = f"<span style='margin-left: 8px;'>🎯 <b>₹{fmt_tp}</b></span>"

                    # Source & Date
                    # Note: We use a single string to avoid indentation causing Markdown code-block rendering
                    meta_html = (
                        f"<div style='margin-top: 6px; display: flex; align-items: center; flex-wrap: wrap; font-size: 0.9em; color: #555;'>"
                        f"{rat_badge}"
                        f"{target_str}"
                        f"<span style='margin: 0 10px; color: #ccc;'>|</span>"
                        f"<span>{row['source']}</span>"
                        f"<span style='margin: 0 10px; color: #ccc;'>|</span>"
                        f"<span>{row['display_date']}</span>"
                        f"</div>"
                    )
                    st.markdown(meta_html, unsafe_allow_html=True)
                    
                    st.divider()

else:
    st.info("No data found. Click 'Fetch Latest News' in the sidebar.")
