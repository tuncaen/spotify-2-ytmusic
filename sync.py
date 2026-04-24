import csv
import sys
from spotify_client import SpotifyClient
from ytmusic_client import YTMusicClient
from matcher import pick_best_match
from state import State
import config


def build_query(track):
    return f"{' '.join(track['artists'])} {track['name']}"


LIKED_SONGS_SENTINEL_ID = "__LIKED_SONGS__"


def main():
    if not config.PLAYLISTS_TO_SYNC and not getattr(config, "SYNC_LIKED_SONGS", False):
        print("! config.py içinde ne PLAYLISTS_TO_SYNC ne SYNC_LIKED_SONGS aktif.")
        sys.exit(1)

    sp = SpotifyClient()
    yt = YTMusicClient()
    state = State(config.STATE_DB)

    sp_playlists = sp.find_playlists_by_names(config.PLAYLISTS_TO_SYNC)
    found = {p["name"] for p in sp_playlists}
    for name in config.PLAYLISTS_TO_SYNC:
        if name not in found:
            print(f"!  Spotify'da bulunamadı: {name}")

    if getattr(config, "SYNC_LIKED_SONGS", False):
        sp_playlists.append({
            "id": LIKED_SONGS_SENTINEL_ID,
            "name": config.LIKED_SONGS_YT_NAME,
            "_liked": True,
        })

    unmatched_rows = []
    total_added = 0

    for sp_pl in sp_playlists:
        sp_pl_id, sp_pl_name = sp_pl["id"], sp_pl["name"]
        print(f"\n>> {sp_pl_name}")

        yt_pl_id = (state.get_ytmusic_playlist_id(sp_pl_id)
                    or yt.find_playlist_by_name(sp_pl_name))
        if not yt_pl_id:
            yt_pl_id = yt.create_playlist(sp_pl_name,
                                          f"Synced from Spotify: {sp_pl_name}")
            print("   + YT Music'te yeni playlist oluşturuldu")
        state.save_playlist_mapping(sp_pl_id, sp_pl_name, yt_pl_id)

        if sp_pl.get("_liked"):
            tracks = sp.get_liked_songs()
        else:
            tracks = sp.get_playlist_tracks(sp_pl_id)
        new = [t for t in tracks if not state.is_synced(t["id"], sp_pl_id)]
        print(f"   {len(tracks)} şarkı ({len(new)} yeni)")

        for t in new:
            candidates = yt.search_song(build_query(t), limit=5)
            best, score = pick_best_match(t, candidates)

            if best:
                try:
                    yt.add_track_to_playlist(yt_pl_id, best["videoId"])
                    state.record_track(t["id"], sp_pl_id, best["videoId"],
                                       yt_pl_id, score, "added")
                    total_added += 1
                    print(f"   + {t['artists'][0]} — {t['name']}  ({score:.2f})")
                except Exception as e:
                    state.record_track(t["id"], sp_pl_id, best["videoId"],
                                       yt_pl_id, score, "error")
                    print(f"   x eklenemedi ({t['name']}): {e}")
            else:
                state.record_track(t["id"], sp_pl_id, None, yt_pl_id,
                                   score, "unmatched")
                unmatched_rows.append({
                    "playlist":   sp_pl_name,
                    "artist":     ", ".join(t["artists"]),
                    "track":      t["name"],
                    "best_score": f"{score:.2f}",
                    "spotify_id": t["id"],
                })
                print(f"   ? eşleşmedi: {t['artists'][0]} — {t['name']}")

    if unmatched_rows:
        with open(config.UNMATCHED_REPORT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=unmatched_rows[0].keys())
            w.writeheader()
            w.writerows(unmatched_rows)
        print(f"\n{len(unmatched_rows)} eşleşmeyen → {config.UNMATCHED_REPORT}")

    print(f"\nToplam eklendi: {total_added}")


if __name__ == "__main__":
    main()
