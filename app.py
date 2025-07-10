# Import necessary libraries
from flask import Flask, jsonify, request
import sqlite3
import os
# NEW: Import the CORS extension
from flask_cors import CORS

# --- Configuration ---
# Get the absolute path of the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Create a full, absolute path to the database file
DB_FILE = os.path.join(BASE_DIR, "scout_memory.db")

# --- Create the Flask Application ---
app = Flask(__name__)
# NEW: Enable CORS for your entire Flask app.
# This will allow your index.html file to make requests to the API.
CORS(app)


# --- Helper Function to Query Database ---
def query_db(query, args=(), one=False):
    """A helper function to query the SQLite database and return results."""
    # Check if the database file exists before trying to connect
    if not os.path.exists(DB_FILE):
        print(f"ERROR: Database file not found at {DB_FILE}")
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query, args)
            rv = cur.fetchall()
            cur.close()
            results = [dict(row) for row in rv]
            return (results[0] if results else None) if one else results
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None


# --- API Endpoints (Search Logic Corrected) ---

@app.route('/api/briefings/search', methods=['GET'])
def search_briefings():
    """
    A flexible API endpoint to search for briefings.
    It can filter by 'competitor', 'product_line', or both.
    """
    competitor = request.args.get('competitor')
    product_line = request.args.get('product_line')

    print(f"Search request received with params: competitor='{competitor}', product_line='{product_line}'")

    query = "SELECT * FROM processed_items WHERE 1=1"
    args = []

    # CORRECTED LOGIC: Use LOWER() for case-insensitive searching.
    if competitor and competitor != 'All':
        query += " AND LOWER(competitor) LIKE LOWER(?)"
        args.append(f"%{competitor}%")

    if product_line:
        query += " AND LOWER(product_line) LIKE LOWER(?)"
        args.append(f"%{product_line}%")

    query += " ORDER BY processed_at DESC"

    briefings = query_db(query, tuple(args))

    if briefings is None:
        return jsonify({"error": "Database query failed or database file not found"}), 500

    return jsonify(briefings)


# --- Main execution block to run the app ---
# --- Main execution block to run the app ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)