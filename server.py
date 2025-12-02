import os
import uuid
import glob
import time
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# Configuration
TEMP_DIR = "temp_downloads"
COOKIES_FILE = "cookies.txt"

# Create temp folder if not exists
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def get_ydl_opts(basic=True):
    """
    Returns yt-dlp options.
    Checks if cookies.txt exists and adds it to options if found.
    """
    opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    # Check for cookies.txt
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
        
    if basic:
        opts['simulate'] = True
        opts['forceurl'] = True
    
    return opts

def clean_old_files():
    """Removes files in temp folder older than 30 minutes"""
    now = time.time()
    for f in glob.glob(os.path.join(TEMP_DIR, "*")):
        try:
            if os.stat(f).st_mtime < now - 1800:
                os.remove(f)
        except Exception:
            pass

@app.route('/')
def home():
    """Serves the Mini App Interface"""
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    clean_old_files()

    # 1. Decision Logic: Direct or Proxy?
    # YouTube usually requires Proxy (Server download) due to IP restrictions.
    # However, we now prioritize Direct links and offer Proxy as a backup.
    is_youtube = "youtube.com" in url or "youtu.be" in url

    # We default to direct, but flag if proxy is available/recommended as backup
    supports_proxy = is_youtube

    opts = get_ydl_opts(basic=True)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return jsonify({
                "success": True,
                "title": info.get('title', 'Video'),
                "thumbnail": info.get('thumbnail'),
                "download_url": info.get('url'), # The direct stream URL
                "platform": info.get('extractor_key'),
                "ext": info.get('ext', 'mp4'),
                "method": "direct",
                "supports_proxy": supports_proxy,
                "original_url": url
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/proxy_download', methods=['GET'])
def proxy_download():
    """
    Downloads video to server, streams to user, then deletes file.
    Used for YouTube or fallback scenarios.
    """
    url = request.args.get('url')
    if not url:
        return "No URL provided", 400

    # Create unique filename
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(TEMP_DIR, filename)

    # Configure download options
    opts = get_ydl_opts(basic=False)
    opts.update({
        'format': 'best[ext=mp4]/best',
        'outtmpl': filepath,
    })

    try:
        # 1. Download to Server
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        # 2. Schedule deletion after sending to user
        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print(f"Error removing temp file: {e}")
            return response

        # 3. Stream file to user
        return send_file(
            filepath,
            as_attachment=True,
            download_name="video.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        return f"Server Error: {str(e)}", 500

if __name__ == '__main__':
    # CHANGED: Default port is now 8000
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port)