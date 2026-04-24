import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config


class SpotifyClient:
    def __init__(self):
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=config.SPOTIFY_CLIENT_ID,
            client_secret=config.SPOTIFY_CLIENT_SECRET,
            redirect_uri=config.SPOTIFY_REDIRECT_URI,
            scope=config.SPOTIFY_SCOPES,
            cache_path=".spotify_cache",
            open_browser=True,
        ))

    def get_user_playlists(self):
        playlists, results = [], self.sp.current_user_playlists(limit=50)
        while results:
            playlists.extend(results["items"])
            results = self.sp.next(results) if results.get("next") else None
        return playlists

    def find_playlists_by_names(self, names):
        wanted = set(names)
        return [p for p in self.get_user_playlists() if p["name"] in wanted]

    def get_playlist_tracks(self, playlist_id):
        tracks = []
        results = self.sp.playlist_items(
            playlist_id, limit=100, additional_types=("track",)
        )
        while results:
            for item in results["items"]:
                # Spotify API yeni sürümde track'i "item" altında döndürüyor, eskiden "track"
                t = item.get("track") or item.get("item")
                if not t or not t.get("id"):   # local/unavailable -> skip
                    continue
                tracks.append(_to_track(t))
            results = self.sp.next(results) if results.get("next") else None
        return tracks

    def get_liked_songs(self):
        """Spotify'ın 'Liked Songs' koleksiyonu — playlist değil, özel /me/tracks endpoint'i."""
        tracks = []
        results = self.sp.current_user_saved_tracks(limit=50)
        while results:
            for item in results["items"]:
                t = item.get("track")
                if not t or not t.get("id"):
                    continue
                tracks.append(_to_track(t))
            results = self.sp.next(results) if results.get("next") else None
        return tracks


def _to_track(t):
    return {
        "id": t["id"],
        "name": t["name"],
        "artists": [a["name"] for a in t["artists"]],
        "album": t["album"]["name"],
        "duration_ms": t["duration_ms"],
        "isrc": t.get("external_ids", {}).get("isrc"),
    }
