import os
from dotenv import load_dotenv

load_dotenv()

# --- Spotify ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SPOTIFY_SCOPES = "playlist-read-private playlist-read-collaborative"

# --- YT Music ---
# `ytmusicapi oauth` ile oluşturulan dosya (OAuth flow — browser'dan daha güvenilir)
YTMUSIC_AUTH_FILE = "oauth.json"
YT_OAUTH_CLIENT_ID = os.getenv("YT_OAUTH_CLIENT_ID")
YT_OAUTH_CLIENT_SECRET = os.getenv("YT_OAUTH_CLIENT_SECRET")

# --- Sync hedefi: Spotify'daki playlist isimleri (bire bir) ---
PLAYLISTS_TO_SYNC = [
    "Radyo'dan Beğenilenler",
    "Sets Singles",
    "E&B T",
    "Working",
    "Radio Epic",
    "Radio Tech",
    "Sorrow Radio",
    "StDeep Radio",
]

# --- Eşleştirme ---
MATCH_THRESHOLD = 0.70          # bu skorun altı = unmatched
DURATION_TOLERANCE_SEC = 3      # ±3sn tam eşleşme sayılır

# --- Dosyalar ---
STATE_DB = "state.db"
UNMATCHED_REPORT = "unmatched_report.csv"
