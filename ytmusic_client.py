import json
import os
import time
from typing import Any

import requests

import config

YT_DATA_API = "https://www.googleapis.com/youtube/v3"
YT_MUSIC_API = "https://music.youtube.com/youtubei/v1"
# YT Music'in TVHTML5 client'ı unauthenticated search için sabit format
TV_CONTEXT = {
    "client": {
        "clientName": "TVHTML5",
        "clientVersion": "7.20250101.04.00",
        "hl": "en",
    }
}


class YTMusicClient:
    """
    Hibrit istemci:
      - Arama: YT Music'in public /search endpoint'i (auth yok, quota yok)
      - Playlist işlemleri: YouTube Data API v3 + OAuth Bearer token

    Sebep: Google, custom OAuth client'lara YT Music internal write endpoint'lerine
    izin vermiyor (401). Data API v3 ise resmi yol, quota'sı var (10000/gün default).
    """

    def __init__(self):
        if not os.path.exists(config.YTMUSIC_AUTH_FILE):
            raise FileNotFoundError(
                f"{config.YTMUSIC_AUTH_FILE} yok. "
                "Önce `ytmusicapi oauth --file oauth.json --client-id ... --client-secret ...` çalıştır."
            )
        if not (config.YT_OAUTH_CLIENT_ID and config.YT_OAUTH_CLIENT_SECRET):
            raise RuntimeError(
                ".env içinde YT_OAUTH_CLIENT_ID ve YT_OAUTH_CLIENT_SECRET eksik."
            )
        with open(config.YTMUSIC_AUTH_FILE) as f:
            self._token = json.load(f)

    # ---------- OAuth token yönetimi ----------

    def _refresh_if_needed(self) -> None:
        if int(time.time()) < self._token.get("expires_at", 0) - 60:
            return
        r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config.YT_OAUTH_CLIENT_ID,
                "client_secret": config.YT_OAUTH_CLIENT_SECRET,
                "refresh_token": self._token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()
        fresh = r.json()
        self._token["access_token"] = fresh["access_token"]
        self._token["expires_in"] = fresh["expires_in"]
        self._token["expires_at"] = int(time.time()) + fresh["expires_in"]
        with open(config.YTMUSIC_AUTH_FILE, "w") as f:
            json.dump(self._token, f, indent=2)

    def _auth_headers(self) -> dict:
        self._refresh_if_needed()
        return {"Authorization": f"Bearer {self._token['access_token']}"}

    # ---------- Data API v3 (yazma) ----------

    def get_library_playlists(self) -> list[dict]:
        """Kullanıcının tüm playlist'lerini Data API v3 ile döner."""
        playlists, token = [], None
        while True:
            params = {"part": "id,snippet", "mine": "true", "maxResults": 50}
            if token:
                params["pageToken"] = token
            r = requests.get(f"{YT_DATA_API}/playlists", headers=self._auth_headers(), params=params)
            r.raise_for_status()
            d = r.json()
            for it in d.get("items", []):
                playlists.append({"playlistId": it["id"], "title": it["snippet"]["title"]})
            token = d.get("nextPageToken")
            if not token:
                break
        return playlists

    def find_playlist_by_name(self, name: str) -> str | None:
        for p in self.get_library_playlists():
            if p["title"] == name:
                return p["playlistId"]
        return None

    def create_playlist(self, name: str, description: str = "") -> str:
        r = requests.post(
            f"{YT_DATA_API}/playlists",
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            params={"part": "snippet,status"},
            json={
                "snippet": {"title": name, "description": description},
                "status": {"privacyStatus": "private"},
            },
        )
        r.raise_for_status()
        return r.json()["id"]

    def add_track_to_playlist(self, playlist_id: str, video_id: str) -> Any:
        r = requests.post(
            f"{YT_DATA_API}/playlistItems",
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            params={"part": "snippet"},
            json={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
        r.raise_for_status()
        return r.json()

    # ---------- YT Music public search (arama) ----------

    def search_song(self, query: str, limit: int = 5) -> list[dict]:
        """
        YT Music arama — auth'suz public endpoint.
        Dönen format matcher.score_candidate'ın beklediği şekle uyarlanır:
            [{ "videoId": ..., "title": ..., "artists": [{"name": ...}], "duration_seconds": ... }]
        """
        body = {"query": query, "params": "EgWKAQIIAWoMEAMQBBAJEA4QChAF", "context": TV_CONTEXT}
        try:
            r = requests.post(f"{YT_MUSIC_API}/search?alt=json", json=body, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []

        return list(_extract_song_candidates(data))[:limit]


def _extract_song_candidates(data: dict):
    """TVHTML5 search response'u tileRenderer'lardan oluşur — her biri bir sonuç."""
    seen_video_ids = set()
    for tile in _iter_tile_renderers(data):
        video_id = (((tile.get("onSelectCommand") or {}).get("watchEndpoint") or {}).get("videoId"))
        if not video_id or len(video_id) != 11 or video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        meta = (tile.get("metadata") or {}).get("tileMetadataRenderer") or {}
        title = _text_of(meta.get("title"))
        if not title:
            continue
        artists = _extract_artists(meta.get("lines") or [])
        yield {
            "videoId": video_id,
            "title": title,
            "artists": artists,
            "duration_seconds": 0,  # TVHTML5 search'te duration yok — matcher eksiği 0.5 puanla handle ediyor
        }


def _iter_tile_renderers(node):
    if isinstance(node, dict):
        if "tileRenderer" in node and isinstance(node["tileRenderer"], dict):
            yield node["tileRenderer"]
            return
        for v in node.values():
            yield from _iter_tile_renderers(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_tile_renderers(v)


def _text_of(node) -> str:
    if not isinstance(node, dict):
        return ""
    if isinstance(node.get("simpleText"), str):
        return node["simpleText"]
    runs = node.get("runs")
    if isinstance(runs, list) and runs and isinstance(runs[0], dict):
        return runs[0].get("text", "")
    return ""


def _extract_artists(lines: list) -> list[dict]:
    # Genelde ilk satır sanatçı(lar), sonraki satırlar views/duration/tarih metadata'sı
    if not lines:
        return []
    items = ((lines[0].get("lineRenderer") or {}).get("items") or [])
    artists = []
    for it in items:
        txt = _text_of((it.get("lineItemRenderer") or {}).get("text"))
        if not txt or _is_separator(txt):
            continue
        # Virgül/& ile ayrılmış çoklu sanatçıları böl
        for part in _split_artists(txt):
            if part and not _is_separator(part):
                artists.append({"name": part})
    return artists[:5]


def _split_artists(s: str) -> list[str]:
    out = [s]
    for sep in (", ", " & ", " and ", ","):
        out = [p.strip() for chunk in out for p in chunk.split(sep)]
    return [p for p in out if p]


def _is_separator(s: str) -> bool:
    s_low = s.strip().lower()
    return s_low in {"", "•", "-", "·"}
