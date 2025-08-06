# AI Competition Scout

This project is a Python-based web application designed to automatically scrape competitor websites for new feature announcements, analyze them using a Large Language Model (LLM), and display the insights through a web interface.

## Project Overview

The application consists of two main components:

1.  **`scout.py`**: A Python script that scrapes competitor websites (currently Braze and Iterable), identifies new feature releases, and uses the Gemini API to generate a product management analysis of each new feature. The analysis is then stored in a Supabase PostgreSQL database.
2.  **`app.py`**: A Flask-based API that provides endpoints to search and retrieve the competitive intelligence briefings stored in the database. This allows a front-end application to display the data.

The project is designed to provide a continuous stream of competitive intelligence, helping product teams stay informed about the latest developments in the market.

## Features

*   **Automated Scraping**: The `scout.py` script uses Selenium and BeautifulSoup to scrape competitor release notes.
*   **AI-Powered Analysis**: Leverages the Gemini API to analyze scraped content and generate structured, actionable insights.
*   **Database Storage**: Stores the generated briefings in a PostgreSQL database (hosted on Supabase) for persistence and easy retrieval.
*   **REST API**: A Flask application (`app.py`) provides a simple API to query the database for briefings.
*   **Web Interface**: A basic HTML, CSS, and JavaScript front-end to display the competitive intelligence data.

## Project Structure

```
.
├── .env                # Local environment variables (API keys, database URI)
├── .gitignore          # Files to be ignored by Git
├── app.py              # Flask API for serving briefing data
├── index.html          # Main HTML file for the web interface
├── README.MD           # This file
├── requirements.txt    # Python dependencies
├── scout.py            # Main script for scraping and AI analysis
├── script.js           # JavaScript for the web interface
└── style.css           # CSS for the web interface
```

## Setup and Installation

### Prerequisites

*   Python 3.x
*   A Supabase account for the PostgreSQL database.
*   A Google AI Studio API key for the Gemini API.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd <your-repository-name>
```

### 2. Create a Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up Environment Variables

Create a `.env` file in the root of the project directory and add the following variables:

```
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
SUPABASE_CONNECTION_URI="YOUR_SUPABASE_CONNECTION_URI"
```

*   `GEMINI_API_KEY`: Your API key from Google AI Studio.
*   `SUPABASE_CONNECTION_URI`: The connection string for your Supabase PostgreSQL database.

### 5. Set up the Database

The `scout.py` script expects a table named `briefings` in your Supabase database. You can create this table using the following SQL statement in the Supabase SQL Editor:

```sql
CREATE TABLE briefings (
    id SERIAL PRIMARY KEY,
    processed_identifier TEXT UNIQUE NOT NULL,
    competitor TEXT,
    product_line TEXT,
    feature_update TEXT,
    summary TEXT,
    pm_analysis TEXT,
    source_url TEXT,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);
```

## How to Run

### 1. Run the Scout Script

To populate the database with the latest competitive intelligence, run the `scout.py` script:

```bash
python scout.py
```

This script will scrape the configured competitor websites, analyze the new features, and store the results in your database.

### 2. Run the Flask API

To start the API server, run the `app.py` file:

```bash
python app.py
```

The API will be available at `http://127.0.0.1:5001`.

### 3. View the Web Interface

Open the `index.html` file in your web browser to view the competitive intelligence dashboard. The dashboard will fetch data from the Flask API and display it in a searchable table.

## How it Works

### `scout.py`

1.  **Initialization**: The script loads environment variables and sets up a connection to the Supabase database.
2.  **Scraping**: For each competitor defined in the `competitors` dictionary, the script calls the associated parser function (`parse_braze_page` or `parse_iterable_page`).
3.  **Parsing**: The parser functions use Selenium to load the competitor's release notes page and BeautifulSoup to parse the HTML. They identify new features that have not been processed before by checking the `processed_identifier` in the database.
4.  **AI Analysis**: For each new feature, the `process_single_feature` function constructs a detailed prompt and sends it to the Gemini API. The API returns a JSON object containing the feature analysis.
5.  **Database Insertion**: The structured analysis from the AI is then saved to the `briefings` table in the database.

### `app.py`

1.  **Initialization**: The Flask application is initialized, and CORS is enabled to allow requests from the front-end.
2.  **Database Connection**: The `get_db_connection` function establishes a connection to the Supabase database using the `SUPABASE_CONNECTION_URI` from the environment variables.
3.  **API Endpoint**: The `/api/briefings/search` endpoint allows clients to search for briefings. It accepts `competitor` and `product_line` as query parameters to filter the results.
4.  **JSON Response**: The endpoint queries the database, fetches the matching briefings, and returns them as a JSON response.
