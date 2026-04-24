import os
from ytmusicapi import YTMusic
import config


class YTMusicClient:
    def __init__(self):
        if not os.path.exists(config.YTMUSIC_AUTH_FILE):
            raise FileNotFoundError(
                f"{config.YTMUSIC_AUTH_FILE} yok. "
                "Önce `ytmusicapi browser` komutunu çalıştır (README'ye bak)."
            )
        self.yt = YTMusic(config.YTMUSIC_AUTH_FILE)

    def get_library_playlists(self):
        return self.yt.get_library_playlists(limit=500)

    def find_playlist_by_name(self, name):
        for p in self.get_library_playlists():
            if p["title"] == name:
                return p["playlistId"]
        return None

    def create_playlist(self, name, description=""):
        return self.yt.create_playlist(
            title=name, description=description, privacy_status="PRIVATE"
        )

    def search_song(self, query, limit=5):
        # filter='songs' → resmi track'lar video'lara tercih edilir
        try:
            return self.yt.search(query, filter="songs", limit=limit)
        except Exception:
            return []

    def add_track_to_playlist(self, playlist_id, video_id):
        return self.yt.add_playlist_items(playlist_id, [video_id])
