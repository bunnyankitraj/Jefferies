# Jefferies India Stock Tracker 📈

A sophisticated AI-powered stock tracking dashboard that aggregates, analyzes, and visualizes analyst calls and targets for Indian stocks from Jefferies.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

## 🌟 Features

### 🖥️ User Interface (Streamlit)

- **Mobile-First Design**: Optimized layout with hidden branding and top-level controls.
- **Dark Mode**: Enforced dark theme for a premium look.
- **Smart Filtering**:
  - **Multi-Select Search**: Filter by multiple specific stocks.
  - **Rating Filter**: Filter by Buy, Sell, Hold, or Unknown.
  - **Date Range**: Custom date picker with quick presets (Today, 7D, 1M).
- **Live Updates**: "Fetch News" button running asynchronously in the background.

### 🤖 Automation & AI

- **News Aggregation**: Fetches latest news via Google News RSS.
- **AI Analysis**: Uses **Groq LLM** to parse article content, extract sentiment, assign ratings (Buy/Sell/Hold), and identify target prices.
- **Deduplication**: Smart URL and title matching to prevent duplicate entries.
- **Cron Job Ready**: Includes `daily_run.sh` for automated scheduling.

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Jefferies.git
cd Jefferies
```

### 2. Set up Environment

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API Keys

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Initialize Database

The app auto-initializes `data/stocks.db` on first run. To manually fetch the NSE Equity list:

```bash
python fetch_full_list.py
```

---

## 🏃‍♂️ Usage

### Run the Web App

```bash
streamlit run app.py
```

Access the app at `http://localhost:8501`.

### Run Manual News Fetch

To trigger the news fetcher manually (CLI):

```bash
python -m automation.job
```

### Automate with Cron

Use the provided script to run daily updates:

```bash
# Add to crontab (e.g., Run every hour)
0 * * * * /path/to/Jefferies/daily_run.sh
```

---

## 📂 Project Structure

```
Jefferies/
├── app.py                 # Main Streamlit Application
├── automation/
│   ├── news_fetcher.py    # RSS Feed Parsing
│   ├── analyzer.py        # Groq AI Logic
│   ├── database.py        # SQLite Operations
│   ├── job.py             # Orchestration Script
│   └── ...
├── data/
│   └── stocks.db          # SQLite Database
├── daily_run.sh           # Automation Script
└── requirements.txt       # Dependencies
```

---

## 🛠️ Tech Stack

- **Frontend**: Streamlit
- **Backend Logic**: Python
- **Database**: SQLite
- **AI Model**: Groq (LLM)
- **Data Source**: Google News RSS

---

## 📜 License

MIT License.
