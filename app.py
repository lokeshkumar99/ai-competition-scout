import os
import psycopg2
from flask import Flask, jsonify, request
from psycopg2.extras import RealDictCursor
from flask_cors import CORS
# NEW: Import dotenv to load local environment variables
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This will load the variables from your .env file for local development
load_dotenv()

# --- Initialize Flask App ---
app = Flask(__name__)
# Enable CORS to allow your frontend to communicate with this API
CORS(app)

# --- Configuration ---
# Get the database URL from environment variables. Works locally and on Render.
DATABASE_URL = os.getenv('SUPABASE_CONNECTION_URI')


def get_db_connection():
    """Establishes a connection to the Supabase database."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


@app.route('/api/briefings/search')
def search_briefings():
    """
    API endpoint to search for briefings with filters for competitor and product_line.
    """
    # Get query parameters from the request URL
    competitor = request.args.get('competitor')
    product_line = request.args.get('product_line')

    conn = None
    try:
        conn = get_db_connection()
        # Use RealDictCursor to get results as dictionaries (easily converted to JSON)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Start building the SQL query
        base_query = "SELECT * FROM briefings"
        filters = []
        params = []

        if competitor:
            filters.append("competitor = %s")
            params.append(competitor)
        if product_line:
            filters.append("product_line = %s")
            params.append(product_line)

        # Add filters to the base query if any exist
        if filters:
            base_query += " WHERE " + " AND ".join(filters)

        # Add ordering to always show the newest first
        base_query += " ORDER BY processed_at DESC"

        cursor.execute(base_query, tuple(params))
        briefings = cursor.fetchall()

        return jsonify(briefings)

    except Exception as e:
        # Log the error to the console for debugging
        print(f"An error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()


# A simple root route to confirm the API is running
@app.route('/')
def index():
    return "AI Competition Scout API is running."


# Main execution block to run the app
if __name__ == '__main__':
    # Check if the essential database URL is present
    if not DATABASE_URL:
        print("FATAL ERROR: SUPABASE_CONNECTION_URI is not set in your .env file.")
    else:
        print("Starting Flask server...")
        app.run(host='0.0.0.0', port=5001, debug=True)
