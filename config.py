import os
from dotenv import load_dotenv

load_dotenv()

# --- Spotify ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
SPOTIFY_SCOPES = "playlist-read-private playlist-read-collaborative"

# --- YT Music ---
# `ytmusicapi browser` komutu ile oluşturulan dosya
YTMUSIC_AUTH_FILE = "browser.json"

# --- Sync hedefi: Spotify'daki playlist isimleri (bire bir) ---
PLAYLISTS_TO_SYNC = [
    # "Chill Vibes",
    # "Türkçe Rock",
]

# --- Eşleştirme ---
MATCH_THRESHOLD = 0.70          # bu skorun altı = unmatched
DURATION_TOLERANCE_SEC = 3      # ±3sn tam eşleşme sayılır

# --- Dosyalar ---
STATE_DB = "state.db"
UNMATCHED_REPORT = "unmatched_report.csv"
