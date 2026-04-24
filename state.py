import sqlite3
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS synced_tracks (
    spotify_track_id     TEXT NOT NULL,
    spotify_playlist_id  TEXT NOT NULL,
    ytmusic_video_id     TEXT,
    ytmusic_playlist_id  TEXT,
    match_score          REAL,
    status               TEXT NOT NULL,   -- added | unmatched | error
    synced_at            TEXT NOT NULL,
    PRIMARY KEY (spotify_track_id, spotify_playlist_id)
);

CREATE TABLE IF NOT EXISTS playlist_mapping (
    spotify_playlist_id    TEXT PRIMARY KEY,
    spotify_playlist_name  TEXT NOT NULL,
    ytmusic_playlist_id    TEXT NOT NULL,
    created_at             TEXT NOT NULL
);
"""


class State:
    def __init__(self, db_path):
        self.db_path = db_path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def is_synced(self, spotify_track_id, spotify_playlist_id):
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM synced_tracks "
                "WHERE spotify_track_id=? AND spotify_playlist_id=? AND status='added'",
                (spotify_track_id, spotify_playlist_id),
            ).fetchone()
        return row is not None

    def record_track(self, spotify_track_id, spotify_playlist_id,
                     ytmusic_video_id, ytmusic_playlist_id, match_score, status):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO synced_tracks VALUES (?,?,?,?,?,?,?)",
                (spotify_track_id, spotify_playlist_id, ytmusic_video_id,
                 ytmusic_playlist_id, match_score, status,
                 datetime.utcnow().isoformat()),
            )

    def get_ytmusic_playlist_id(self, spotify_playlist_id):
        with self._conn() as c:
            row = c.execute(
                "SELECT ytmusic_playlist_id FROM playlist_mapping "
                "WHERE spotify_playlist_id=?",
                (spotify_playlist_id,),
            ).fetchone()
        return row["ytmusic_playlist_id"] if row else None

    def save_playlist_mapping(self, sp_pl_id, sp_pl_name, yt_pl_id):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO playlist_mapping VALUES (?,?,?,?)",
                (sp_pl_id, sp_pl_name, yt_pl_id, datetime.utcnow().isoformat()),
            )
