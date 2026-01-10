import streamlit as st
import pandas as pd
import os
import sys
import threading
import time

# --- CONFIGURATION FLAGS ---
ENABLE_POWER_TOOLS = False  # Toggle for Watchlist, Deep Search, and Upside Calculator

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

st.set_page_config(page_title="Professional Stock Research Dashboard", layout="wide")

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

st.title("Professional Stock Research Dashboard")

# Data Loading Initialization
db = get_db()

# Sidebar (Keep it for advanced users)
def get_currency_symbol(code):
    if code == "USD": return "$"
    if code == "EUR": return "€"
    if code == "GBP": return "£"
    return "₹" # Default INR

st.sidebar.header("Controls")

if 'focus_stock' not in st.session_state:
    st.session_state.focus_stock = None

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = set()

if st.session_state.focus_stock:
    st.sidebar.info(f"📍 Viewing: **{st.session_state.focus_stock}**")
    if st.sidebar.button("Clear Focus & Show All"):
        st.session_state.focus_stock = None
        st.rerun()

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
        r.entry_date, r.stock_name, r.rating, r.target_price, r.currency, r.broker,
        a.title, a.source, a.published_date, a.url, a.fetched_at, a.raw_content
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
        
        df['date_dt'] = pd.to_datetime(df['published_date'], errors='coerce', format='ISO8601')
        
        def to_ist(dt):
            if pd.isnull(dt): return dt
            if isinstance(dt, str):
                dt = pd.to_datetime(dt, errors='coerce', format='ISO8601')
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

        # Sidebar Monitoring Table
        st.sidebar.markdown("---")
        st.sidebar.subheader("🏢 Broker Activity")
        mon_df = df.groupby('broker')['fetched_dt'].max().reset_index()
        mon_df['Last Update'] = mon_df['fetched_dt'].dt.strftime('%d %b, %I:%M %p')
        st.sidebar.table(mon_df[['broker', 'Last Update']])

        # --- FILTERS (Back on Main Page) ---
        with st.expander("Dashboard Command Center (Filters)", expanded=False):
            st.markdown("#### 🏢 Core Selection")
            all_stocks = sorted(df['stock_name'].unique())
            available_ratings = sorted(df['rating'].fillna("Unknown").unique().tolist())
            available_brokers = sorted(df['broker'].fillna("Jefferies").unique().tolist())

            # Grid Row 1: Stock Selection & Search
            if ENABLE_POWER_TOOLS:
                c_s1, c_s2, c_s3 = st.columns([1, 2, 2])
                with c_s1:
                    all_stocks_toggle = st.checkbox("Select All Stocks", value=False)
                with c_s2:
                    default_stocks = all_stocks if all_stocks_toggle else []
                    selected_stocks = st.multiselect("Pick Stocks", options=all_stocks, default=default_stocks)
                with c_s3:
                    keyword_search = st.text_input("🔍 Catalyst Deep Search", placeholder="e.g. Dividend, Margins, Upgrade", help="Search article titles and descriptions for specific catalysts.")
            else:
                c_s1, c_s2 = st.columns([1, 4])
                with c_s1:
                    all_stocks_toggle = st.checkbox("Select All Stocks", value=False)
                with c_s2:
                    default_stocks = all_stocks if all_stocks_toggle else []
                    selected_stocks = st.multiselect("Pick Stocks", options=all_stocks, default=default_stocks)
                keyword_search = None

            # Grid Row 2: Ratings, Brokers & Watchlist
            if ENABLE_POWER_TOOLS:
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    all_ratings_toggle = st.checkbox("All Ratings", value=False, key="all_rat")
                    default_ratings = available_ratings if all_ratings_toggle else []
                    sel_ratings = st.multiselect("Ratings", options=available_ratings, default=default_ratings)
                with c2:
                    all_brokers_toggle = st.checkbox("All Brokers", value=False, key="all_brok")
                    default_brokers = available_brokers if all_brokers_toggle else []
                    sel_brokers = st.multiselect("Brokers", options=available_brokers, default=default_brokers)
                with c3:
                    st.write("") # Spacer
                    watchlist_only = st.checkbox("⭐ Watchlist Only", value=False, help="Show only stocks you have starred.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    all_ratings_toggle = st.checkbox("All Ratings", value=False, key="all_rat_v2")
                    default_ratings = available_ratings if all_ratings_toggle else []
                    sel_ratings = st.multiselect("Ratings", options=available_ratings, default=default_ratings)
                with c2:
                    all_brokers_toggle = st.checkbox("All Brokers", value=False, key="all_brok_v2")
                    default_brokers = available_brokers if all_brokers_toggle else []
                    sel_brokers = st.multiselect("Brokers", options=available_brokers, default=default_brokers)
                watchlist_only = False
            
            st.divider()
            
            # Row 3: Performance Dials
            st.markdown("#### 🎯 Performance Dials")
            conv_options = {
                "All": 1,
                "Strong (2+)": 2,
                "High (3+)": 3,
                "Universal (4+)": 4
            }
            conv_label = st.radio("Conviction Power (Min. Broker Agreement)", 
                                  options=list(conv_options.keys()), 
                                  horizontal=True,
                                  help="Isolates stocks that have been rated by at least N different brokers.")
            min_brokers = conv_options[conv_label]
            
            p1, p2, p3, p4 = st.columns(4)
            with p1:
                show_only_with_target = st.checkbox("🎯 Targets Only", value=False, help="Show only stocks with explicit numerical price targets.")
            with p2:
                strong_buy_only = st.checkbox("🚀 Strong Buy", value=False, help="Filter for only 'Buy' and 'Outperform' ratings.")
            with p3:
                fresh_today = st.checkbox("⏰ Fresh Today", value=False, help="Show only updates from the last 24 hours.")
            with p4:
                contrarian_radar = st.checkbox("⚖️ Contrarian", value=False, help="Find stocks with conflicting ratings (e.g., Buy vs Sell).")

            st.divider()
            
            # Row 4: Time Horizon
            st.markdown("#### ⏳ Time Horizon")
            ct1, ct2 = st.columns([3, 2])
            with ct1:
                date_preset = st.radio("Lookback Period", ["All Time", "Last 24 Hours", "Last 7 Days", "Custom"], horizontal=True)
            with ct2:
                date_range = None
                if date_preset == "Custom":
                    min_d_val = df['date_dt'].min().date()
                    max_d_val = date.today()
                    date_range = st.date_input("Select Range", value=(min_d_val, max_d_val))

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

        # Apply Focus Mode
        if st.session_state.get('focus_stock'):
            f_df = f_df[f_df['stock_name'] == st.session_state.focus_stock]

        # Apply Conviction Agreement Filter

        # Apply Conviction Agreement Filter
        if min_brokers > 1:
            # Count unique brokers per stock in the current filtered set
            broker_counts = f_df.groupby('stock_name')['broker'].nunique()
            qualified_stocks = broker_counts[broker_counts >= min_brokers].index
            f_df = f_df[f_df['stock_name'].isin(qualified_stocks)]
            
        if show_only_with_target:
            f_df = f_df[pd.notnull(f_df['target_price']) & (f_df['target_price'] > 0)]

        if strong_buy_only:
            f_df = f_df[f_df['rating'].isin(['Buy', 'Outperform'])]

        if fresh_today:
            f_df = f_df[f_df['date_dt'] >= (now_ist - timedelta(hours=24))]

        if contrarian_radar:
            # Find stocks with at least one Buy/Outperform and at least one Sell/Underperform
            buy_ratings = ['Buy', 'Outperform']
            sell_ratings = ['Sell', 'Underperform']
            
            buy_stocks = set(f_df[f_df['rating'].isin(buy_ratings)]['stock_name'])
            sell_stocks = set(f_df[f_df['rating'].isin(sell_ratings)]['stock_name'])
            contrarian_stocks = buy_stocks.intersection(sell_stocks)
            f_df = f_df[f_df['stock_name'].isin(contrarian_stocks)]

        if keyword_search:
            f_df = f_df[
                f_df['title'].str.contains(keyword_search, case=False, na=False) | 
                f_df['raw_content'].str.contains(keyword_search, case=False, na=False)
            ]

        if watchlist_only:
            f_df = f_df[f_df['stock_name'].isin(st.session_state.watchlist)]

        if f_df.empty:
            st.warning("No matches found.")
        else:
            # --- HOTTEST PICKS ---
            buy_only = f_df[f_df['rating'] == 'Buy']
            if not buy_only.empty:
                hot_picks = buy_only['stock_name'].value_counts().head(5)
                with st.expander("🔥 Consensus Hottest Picks (Click to focus)", expanded=False):
                    hp_cols = st.columns(len(hot_picks))
                    for i, (s_name, count) in enumerate(hot_picks.items()):
                        with hp_cols[i]:
                            # Make it a button that sets focus (Toggles: deselects if already selected)
                            if st.button(f"**{s_name}**\n\n{count} Buy Calls", key=f"hp_{s_name}", use_container_width=True):
                                if st.session_state.focus_stock == s_name:
                                    st.session_state.focus_stock = None
                                else:
                                    st.session_state.focus_stock = s_name
                                st.rerun()
                st.divider()

            # Expansion Control (Main Page)
            col_exp1, col_exp2, col_exp3 = st.columns([2, 5, 2])
            with col_exp1:
                # Default to expanded if focusing on a specific stock
                def_exp = True if st.session_state.get('focus_stock') else False
                expand_all = st.checkbox("Expand All", value=def_exp)
            with col_exp2:
                total_unique_stocks = f_df['stock_name'].nunique()
                st.markdown(f"<div style='text-align: center; margin-top: 5px; font-weight: 600;'>Showing {total_unique_stocks} unique stocks</div>", unsafe_allow_html=True)
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
                
                # Check for Combined Signal (Any 2+ brokers both Buy)
                buy_ratings = s_data[s_data['rating'] == 'Buy']
                participating_brokers = sorted(buy_ratings['broker'].unique().tolist())
                
                # Broker Badge System for label
                broker_tags = []
                for b in sorted(s_data['broker'].unique()):
                    b_ratings = s_data[s_data['broker'] == b]['rating'].tolist()
                    main_r = b_ratings[0]
                    color = "gray"
                    if "Buy" in main_r: color = "green"
                    elif "Sell" in main_r: color = "red"
                    elif "Hold" in main_r: color = "orange"
                    broker_tags.append(f":{color}[{b}]")
                
                tags_str = " | ".join(broker_tags)
                
                is_combined_up = len(participating_brokers) >= 2
                top = s_data.iloc[0]
                
                if is_combined_up:
                    combined_target = buy_ratings['target_price'].min()
                    # Use the currency of the first participating broker for the label
                    cur_code = buy_ratings.iloc[0].get('currency', 'INR')
                    sym = get_currency_symbol(cur_code)
                    tp_str = f"{sym}{combined_target:,.0f}" if pd.notnull(combined_target) else "N/A"
                    label = f"🚀 **x{len(participating_brokers)}** :blue[**{stock}**] | {tags_str} | Target: **{tp_str}** | 🕒 {latest_time_str}"
                else:
                    cur_code = top.get('currency', 'INR')
                    sym = get_currency_symbol(cur_code)
                    tp = f"{sym}{top['target_price']:,.0f}" if pd.notnull(top['target_price']) else "N/A"
                    label = f":blue[**{stock}**] | {tags_str} | Target: {tp} | 🕒 {latest_time_str}"
                
                with st.expander(label, expanded=expand_all):
                    # --- POWER TOOLS: WATCHLIST & UPSIDE ---
                    if ENABLE_POWER_TOOLS:
                        pt1, pt2 = st.columns([1, 2])
                        with pt1:
                            is_starred = stock in st.session_state.watchlist
                            star_btn = st.button("⭐ Unstar" if is_starred else "☆ Star", key=f"star_{stock}", use_container_width=True)
                            if star_btn:
                                if is_starred: st.session_state.watchlist.remove(stock)
                                else: st.session_state.watchlist.add(stock)
                                st.rerun()
                        
                        with pt2:
                            target_for_calc = combined_target if is_combined_up else top['target_price']
                            if pd.notnull(target_for_calc) and target_for_calc > 0:
                                calc_cols = st.columns([2, 2])
                                with calc_cols[0]:
                                    cmp = st.number_input("CMP", value=0.0, step=1.0, key=f"cmp_{stock}", label_visibility="collapsed", placeholder="Enter CMP")
                                with calc_cols[1]:
                                    if cmp > 0:
                                        upside = ((target_for_calc / cmp) - 1) * 100
                                        color = "green" if upside > 15 else "white"
                                        st.markdown(f"**{upside:.1f}% Upside**", help=f"Target: {target_for_calc}")
                                    else:
                                        st.caption("Enter Price for %")
                        
                        st.divider()

                    if is_combined_up:
                        brokers_str = ", ".join(participating_brokers)
                        st.info(f"Multiple brokers ({brokers_str}) have issued a **BUY** rating for {stock}. Status is **BUY** and Target is the minimum: **{tp_str}**. (Last updated: {latest_time_str})")
                    
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
                        sym = get_currency_symbol(row.get('currency', 'INR'))
                        fmt_tp = f"{sym}{int(row['target_price']):,}" if pd.notnull(row['target_price']) else ""
                        
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
