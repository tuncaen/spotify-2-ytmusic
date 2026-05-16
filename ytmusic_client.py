import os
import time
from typing import Any

from ytmusicapi import YTMusic

import config


class YTMusicClient:
    """
    ytmusicapi tabanlı istemci, browser auth (cookie/SAPISID) kullanır.
    Quota yoktur — tüm işlemler music.youtube.com'un internal API'si üzerinden.
    """

    def __init__(self):
        if not os.path.exists(config.YTMUSIC_AUTH_FILE):
            raise FileNotFoundError(
                f"{config.YTMUSIC_AUTH_FILE} yok. README'deki browser auth adımlarına bak."
            )
        self.yt = YTMusic(config.YTMUSIC_AUTH_FILE)

    def get_library_playlists(self) -> list[dict]:
        return self.yt.get_library_playlists(limit=500)

    def find_playlist_by_name(self, name: str) -> str | None:
        for p in self.get_library_playlists():
            if p["title"] == name:
                return p["playlistId"]
        return None

    def create_playlist(self, name: str, description: str = "") -> str:
        return self.yt.create_playlist(
            title=name, description=description, privacy_status="PRIVATE"
        )

    def search_song(self, query: str, limit: int = 5) -> list[dict]:
        # ytmusicapi search: duration_seconds alanını zaten doldurur, ek videos.list gerekmez
        try:
            return self.yt.search(query, filter="songs", limit=limit)
        except Exception:
            return []

    def add_track_to_playlist(self, playlist_id: str, video_id: str) -> Any:
        """YT Music'in rate-limit/transient 409 hatalarına karşı exponential backoff."""
        delays = [2, 5, 10, 20]  # saniye — toplam ~37sn max bekleme
        for attempt, delay in enumerate([0] + delays):
            if delay:
                time.sleep(delay)
            try:
                return self.yt.add_playlist_items(playlist_id, [video_id])
            except Exception as e:
                msg = str(e)
                # 409 Conflict + "Sorry, something went wrong" = transient throttle
                # 4xx/5xx server errors = retry candidate
                transient = "409" in msg or "500" in msg or "502" in msg or "503" in msg or "504" in msg
                if not transient or attempt >= len(delays):
                    raise
                # ileride bir attempt daha var, backoff'a devam
