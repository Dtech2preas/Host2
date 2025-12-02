import os
import time
import threading
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
FILE_HITS = 'hits.txt'        # Fresh accounts
FILE_TEMP = 'temp_used.txt'   # Accounts on 24h cooldown
FILE_FINAL = 'accoun.txt'     # Where they go after 24h
CHECK_INTERVAL = 3600         # Check for recycling every 1 hour (3600 seconds)
COOLDOWN_SECONDS = 86400      # 24 Hours

# --- BACKGROUND TASK: RECYCLER ---
def recycle_worker():
    """Checks temp file periodically and moves old accounts to accoun.txt"""
    while True:
        try:
            print(f"[{datetime.now()}] Checking for accounts to recycle...")
            
            if not os.path.exists(FILE_TEMP):
                open(FILE_TEMP, 'w').close() # Create if missing

            now = time.time()
            remaining_temp = []
            moved_accounts = []

            # Read temp file
            with open(FILE_TEMP, 'r') as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if "|" in line:
                    timestamp_str, account = line.split("|", 1)
                    timestamp = float(timestamp_str)
                    
                    # If 24 hours have passed
                    if now - timestamp >= COOLDOWN_SECONDS:
                        moved_accounts.append(account)
                    else:
                        remaining_temp.append(line)
                else:
                    # Bad line format? keep it to be safe or delete. 
                    # We will keep it in temp to prevent data loss.
                    remaining_temp.append(line)

            # Rewrite temp file with only the ones still waiting
            with open(FILE_TEMP, 'w') as f:
                for line in remaining_temp:
                    f.write(f"{line}\n")

            # Append moved accounts to accoun.txt
            if moved_accounts:
                with open(FILE_FINAL, 'a') as f:
                    for acc in moved_accounts:
                        f.write(f"{acc}\n")
                print(f"[{datetime.now()}] Recycled {len(moved_accounts)} accounts to {FILE_FINAL}")
            else:
                print(f"[{datetime.now()}] No accounts ready for recycling.")

        except Exception as e:
            print(f"Error in recycle worker: {e}")

        # Sleep for 1 hour before checking again
        time.sleep(CHECK_INTERVAL)

# Start the background thread
recycler_thread = threading.Thread(target=recycle_worker, daemon=True)
recycler_thread.start()

# --- WEB SERVER ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get-account', methods=['GET'])
def get_account():
    try:
        # 1. Read hits.txt
        if not os.path.exists(FILE_HITS):
            return jsonify({"success": False, "error": "Database Error"}), 500

        with open(FILE_HITS, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            return jsonify({"success": False, "error": "Out of Stock"}), 404

        # 2. Pick a random account
        selected_account = random.choice(lines)

        # 3. Remove it from hits.txt
        lines.remove(selected_account)
        with open(FILE_HITS, 'w') as f:
            for line in lines:
                f.write(f"{line}\n")

        # 4. Add to temp_used.txt with current Timestamp
        current_ts = time.time()
        with open(FILE_TEMP, 'a') as f:
            f.write(f"{current_ts}|{selected_account}\n")

        # 5. Send to user
        return jsonify({"success": True, "account": selected_account})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Run server
    app.run(host='0.0.0.0', port=5000)