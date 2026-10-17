# AI Data Analyst Agent

A local business analytics application for analysing Excel-based KPIs, detecting anomalies, and generating AI-powered business insights.

---

## Quick Start (Windows)

### 1. Prerequisites

- Python 3.11 or 3.12
- Git (optional)

### 2. Set up the environment

```powershell
# Navigate to the project folder
cd "ai-data-analyst agent"

# Create and activate a virtual environment (recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
copy .env.example .env
notepad .env
```

Edit `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Optional | Enables AI-generated insights. Get one at [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `SMTP_HOST` | Optional | Email alerts (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | Optional | Usually `587` |
| `SMTP_USER` | Optional | Your email address |
| `SMTP_PASSWORD` | Optional | App password (not your login password) |
| `APP_SECRET_KEY` | Recommended | Random string for session security |
| `ADMIN_PASSWORD_HASH` | Recommended | bcrypt hash of your admin password (see below) |

### 4. Set an admin password (recommended for any shared machine)

```powershell
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

Copy the output into `ADMIN_PASSWORD_HASH` in your `.env` file.  
Leave `ADMIN_PASSWORD_HASH` empty for fully local, single-user use (no login required).

### 5. Generate the sample dataset

```powershell
python generate_sample_data.py
```

This creates `data/sample_business_data.xlsx` with 3 years of monthly data and injected anomalies.

### 6. Start the application

```powershell
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

### 7. Start the background scheduler (optional)

In a **separate terminal window**:

```powershell
.\venv\Scripts\Activate.ps1
python run_scheduler.py
```

> **Note:** Scheduled analysis only runs while this process is active and your computer is on. It is not cloud-based.

---

## Using the Application

1. **Business Settings** — Enter your business name, industry, and metric descriptions.
2. **Upload Data** — Upload your Excel file, select the worksheet, date column, and KPI columns.
3. **KPI Analysis** — View aggregated trends and period-over-period comparisons.
4. **Anomaly Detection** — Review flagged anomalies with severity and explanations.
5. **AI Insights** — Generate an AI business summary (requires Gemini API key).
6. **Alert Settings** — Configure email recipients and severity thresholds.
7. **History** — View all past analysis runs.

---

## Running Tests

```powershell
pytest tests/ -v
```

With coverage:

```powershell
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Project Structure

```
ai-data-analyst-agent/
├── app.py                        # Streamlit application entry point
├── run_scheduler.py              # Standalone background scheduler
├── generate_sample_data.py       # Creates a test dataset
├── requirements.txt
├── .env.example                  # Environment variable template
├── .gitignore
├── config/
│   └── settings.py               # Centralised configuration
├── data/
│   ├── uploads/                  # Uploaded files (gitignored)
│   ├── processed/                # Processed outputs
│   └── reports/
├── src/
│   ├── ingestion/
│   │   ├── excel_reader.py       # Safe file reading and hashing
│   │   └── validator.py          # Data validation and profiling
│   ├── analytics/
│   │   ├── metrics.py            # KPI calculations
│   │   ├── profiler.py           # Report builder
│   │   └── time_series.py        # Gap detection, baselines
│   ├── detection/
│   │   ├── baseline.py           # Baseline strategies
│   │   ├── detector.py           # Multi-method anomaly detection
│   │   └── severity.py           # Severity scoring
│   ├── agent/
│   │   ├── analyst.py            # AI analyst (Gemini API)
│   │   ├── business_context.py   # Context formatting
│   │   └── prompts.py            # Prompt templates
│   ├── alerts/
│   │   ├── deduplication.py      # Alert dedup keys
│   │   ├── email_service.py      # SMTP sender
│   │   └── rules.py              # Alert rule engine
│   ├── database/
│   │   ├── db.py                 # Engine and session
│   │   ├── models.py             # ORM models
│   │   └── repository.py         # Data access layer
│   ├── scheduler/
│   │   └── jobs.py               # Scheduled job definitions
│   └── dashboard/
│       ├── charts.py             # Plotly chart builders
│       └── components.py         # Streamlit UI components
└── tests/
    ├── conftest.py
    ├── expected_anomalies.py     # Ground-truth labels (not in dataset)
    ├── test_excel_reader.py
    ├── test_metrics.py
    ├── test_detector.py
    ├── test_database.py
    └── test_alerts.py
```

---

## Security

- API keys and SMTP passwords are loaded from environment variables only — never hardcoded, stored in the database, or logged.
- Uploaded file names are sanitised before writing to disk.
- File extension and size are validated before processing.
- Duplicate file hashes are rejected to prevent re-processing identical data.
- All database operations use SQLAlchemy parameterised queries — no raw SQL string interpolation.
- User inputs are sanitised with `bleach` before storage.
- Admin password is stored as a bcrypt hash — the plain text is never retained.
- SQLite WAL mode and foreign-key enforcement are enabled on every connection.
- The Streamlit `menu_items` remove the default "Made with Streamlit" link.

---

## Known Limitations

- The scheduler only runs while `run_scheduler.py` is active on the local machine.
- The application is designed for single-user local use. For multi-user deployment, add a reverse proxy (e.g. Nginx) and HTTPS.
- AI insights require a Gemini API key with available quota. The application functions fully without it.
- Very large Excel files (many thousands of rows) may be slow on the first upload due to validation overhead.
- XLS format support depends on the `xlrd` library (2.x only supports BIFF8 `.xls`, not XLSB or XLSM).

---

## Licence

For internal business use. No warranty is provided.
