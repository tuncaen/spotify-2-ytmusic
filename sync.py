import csv
import os
import re
import sys

from spotify_client import SpotifyClient
from ytmusic_client import YTMusicClient
from matcher import pick_best_match
from state import State
import config


LIKED_SONGS_SENTINEL_ID = "__LIKED_SONGS__"
LIKED_PLAN_FILE = "liked_plan.csv"


def build_query(track):
    return f"{' '.join(track['artists'])} {track['name']}"


def parse_videoid(s):
    """11-char videoId, music.youtube.com URL, youtu.be link veya watch?v=... formatından videoId çıkar."""
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    m = re.search(r"(?:v=|youtu\.be/|/watch\?v=)([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Liked Songs: iki fazlı plan/apply
# --------------------------------------------------------------------------

def handle_liked_songs(sp, yt, state):
    """
    Plan dosyası varsa: validate + apply (clean rebuild ile doğru sıralama).
    Yoksa: yeni Spotify tracks varsa hepsini matchle. Unmatched yoksa
    incremental append, varsa plan dosyası yaz ve çık.
    """
    sp_id = LIKED_SONGS_SENTINEL_ID
    yt_pl_name = config.LIKED_SONGS_YT_NAME

    # 1) Plan dosyası mevcutsa apply
    if os.path.exists(LIKED_PLAN_FILE):
        rows = _read_plan(LIKED_PLAN_FILE)
        invalid = []
        for r in rows:
            vid = parse_videoid(r.get("ytmusic_video_id", ""))
            if not vid:
                invalid.append(r)
            else:
                r["ytmusic_video_id"] = vid
        if invalid:
            print(f"!! {LIKED_PLAN_FILE}: {len(invalid)} satırda ytmusic_video_id eksik/geçersiz.")
            for r in invalid[:5]:
                print(f"   {r.get('artist','')} — {r.get('track','')}  (spotify_id={r.get('spotify_id','')})")
            print(f"   Dosyayı editleyip eksikleri doldur, sonra tekrar sync.py çalıştır.")
            return
        success = _apply_liked_plan(sp, yt, state, rows)
        if success:
            os.remove(LIKED_PLAN_FILE)
            print(f"   {LIKED_PLAN_FILE} silindi.")
        else:
            print(f"   {LIKED_PLAN_FILE} korundu — düzeltip tekrar sync.py çalıştırırsan kaldığı yerden devam edecek.")
        return

    # 2) Plan yok — yeni track'leri matchle
    print(f"\n>> {yt_pl_name}")
    spotify_liked = sp.get_liked_songs()
    state_synced = state.get_added_ids(sp_id)
    new_tracks = [t for t in spotify_liked if t["id"] not in state_synced]

    if not new_tracks:
        print(f"   Spotify'da {len(spotify_liked)} liked song, hepsi state'te. Yeni yok.")
        return

    print(f"   {len(spotify_liked)} liked song, {len(new_tracks)} yeni — match deniyor...")
    matched = {}    # spotify_id -> {"videoId":..., "score":...}
    unmatched = {}  # spotify_id -> score
    for t in new_tracks:
        candidates = yt.search_song(build_query(t), limit=5)
        best, score = pick_best_match(t, candidates)
        if best:
            matched[t["id"]] = {"videoId": best["videoId"], "score": score}
        else:
            unmatched[t["id"]] = score

    print(f"   matched: {len(matched)}, needs_review: {len(unmatched)}")

    # 3) Hepsi matched → incremental append (basit, hızlı, sıra korunur)
    if not unmatched:
        _incremental_append(sp, yt, state, sp_id, yt_pl_name, new_tracks, matched)
        return

    # 4) Unmatched var → tüm playlist için plan yaz, kullanıcı doldurup tekrar koşacak
    print(f"   Unmatched var. Sıralamayı korumak için clean rebuild gerekecek.")
    print(f"   Plan dosyası yazılıyor: {LIKED_PLAN_FILE}")
    _write_full_plan(state, sp_id, spotify_liked, matched, unmatched)
    print(f"\n   ! {LIKED_PLAN_FILE} oluşturuldu.")
    print(f"   ! 'needs_review' satırlarındaki ytmusic_video_id kolonunu doldur (videoId, URL kabul).")
    print(f"   ! Sonra tekrar `python sync.py` çalıştır — playlist sıfırdan oluşturulup tüm tracks")
    print(f"     added_at sırasında eklenecek (Date added DESC view'de Spotify ile birebir).")


def _incremental_append(sp, yt, state, sp_id, yt_pl_name, new_tracks, matched):
    yt_pl_id = state.get_ytmusic_playlist_id(sp_id) or yt.find_playlist_by_name(yt_pl_name)
    if not yt_pl_id:
        yt_pl_id = yt.create_playlist(yt_pl_name, "Synced from Spotify: Liked Songs")
        print(f"   + YT Music'te yeni playlist oluşturuldu")
    state.save_playlist_mapping(sp_id, yt_pl_name, yt_pl_id)

    # Spotify newest-first döner; reverse ile oldest-first iterate
    # → last appended (newest from Spotify) en yüksek publishedAt → Date added DESC view'de en üstte
    for t in reversed(new_tracks):
        m = matched.get(t["id"])
        if not m:
            continue
        try:
            yt.add_track_to_playlist(yt_pl_id, m["videoId"])
            state.record_track(t["id"], sp_id, m["videoId"], yt_pl_id, m["score"], "added")
            print(f"   + {t['artists'][0]} — {t['name']}  ({m['score']:.2f})")
        except Exception as e:
            state.record_track(t["id"], sp_id, m["videoId"], yt_pl_id, m["score"], "error")
            print(f"   x eklenemedi ({t['name']}): {e}")


def _write_full_plan(state, sp_id, spotify_liked, new_matched, new_unmatched):
    """Plan'a Spotify'daki TÜM liked songs'u yaz — already-synced'leri de
    dahil ederiz ki apply'da clean rebuild olsun."""
    existing = state.get_added_video_map(sp_id)
    rows = []
    for t in spotify_liked:
        sid = t["id"]
        if sid in existing:
            row = {
                "spotify_id": sid,
                "added_at": t.get("added_at", ""),
                "artist": ", ".join(t["artists"]),
                "track": t["name"],
                "ytmusic_video_id": existing[sid],
                "match_score": "",
                "status": "matched_existing",
            }
        elif sid in new_matched:
            m = new_matched[sid]
            row = {
                "spotify_id": sid,
                "added_at": t.get("added_at", ""),
                "artist": ", ".join(t["artists"]),
                "track": t["name"],
                "ytmusic_video_id": m["videoId"],
                "match_score": f"{m['score']:.2f}",
                "status": "matched_new",
            }
        elif sid in new_unmatched:
            row = {
                "spotify_id": sid,
                "added_at": t.get("added_at", ""),
                "artist": ", ".join(t["artists"]),
                "track": t["name"],
                "ytmusic_video_id": "",
                "match_score": f"{new_unmatched[sid]:.2f}",
                "status": "needs_review",
            }
        else:
            # Spotify Liked'da ama state'te yok ve match denenmedi (?) — temkinli davran
            row = {
                "spotify_id": sid,
                "added_at": t.get("added_at", ""),
                "artist": ", ".join(t["artists"]),
                "track": t["name"],
                "ytmusic_video_id": "",
                "match_score": "",
                "status": "needs_review",
            }
        rows.append(row)
    _write_plan(LIKED_PLAN_FILE, rows)


def _apply_liked_plan(sp, yt, state, rows):
    """
    Plan rows'u uygula. Mod:
      - FRESH (state'te 'added' yok): YT playlist sil + yeni oluştur, hepsini sırayla ekle
      - RESUME (state'te 'added' var): mevcut YT playlist'i koru, state'te olanları skip et,
        kalanları added_at sırasında ekle

    Fail-fast: ilk hatada durur (state'e 'error' kaydeder), False döner.
    Tüm başarılı tamamlanırsa True döner.
    """
    sp_id = LIKED_SONGS_SENTINEL_ID
    yt_pl_name = config.LIKED_SONGS_YT_NAME

    already_synced = state.get_added_ids(sp_id)
    is_resume = bool(already_synced)

    if is_resume:
        yt_pl_id = state.get_ytmusic_playlist_id(sp_id)
        print(f"\n>> {yt_pl_name} RESUME — {len(already_synced)} zaten eklenmiş, kaldığı yerden devam")
        if not yt_pl_id:
            print(f"   !! state'te 'added' var ama playlist mapping yok — RESUME mümkün değil")
            return False
    else:
        print(f"\n>> {yt_pl_name} FRESH apply ({len(rows)} track)")
        # Mevcut aynı isimli YT playlist'i (varsa) sil
        old_pl_id = yt.find_playlist_by_name(yt_pl_name)
        if old_pl_id:
            print(f"   eski playlist siliniyor: {old_pl_id}")
            try:
                yt.yt.delete_playlist(old_pl_id)
            except Exception as e:
                print(f"   delete err (devam): {e}")
        # Yeni playlist
        yt_pl_id = yt.create_playlist(yt_pl_name, "Synced from Spotify: Liked Songs")
        state.save_playlist_mapping(sp_id, yt_pl_name, yt_pl_id)
        print(f"   yeni playlist: {yt_pl_id}")

    # added_at oldest-first sırala
    rows_sorted = sorted(rows, key=lambda r: r.get("added_at", "") or "")
    pending = [r for r in rows_sorted if r["spotify_id"] not in already_synced]
    print(f"   {len(pending)}/{len(rows_sorted)} track eklenecek")

    total = 0
    for r in pending:
        vid = r["ytmusic_video_id"]
        score = float(r["match_score"]) if r.get("match_score") else 1.0
        try:
            yt.add_track_to_playlist(yt_pl_id, vid)
            state.record_track(r["spotify_id"], sp_id, vid, yt_pl_id, score, "added")
            total += 1
            print(f"   + {r['artist']} — {r['track']}")
        except Exception as e:
            # FAIL-FAST: state'e error olarak yaz, dur, çık
            state.record_track(r["spotify_id"], sp_id, vid, yt_pl_id, score, "error")
            print(f"\n   x DURDU: {r['artist']} — {r['track']}")
            print(f"     spotify_id: {r['spotify_id']}")
            print(f"     videoId:    {vid}")
            print(f"     hata:       {e}")
            print(f"   Bu noktaya kadar {total} track eklendi.")
            print(f"   {LIKED_PLAN_FILE}'de bu satırın ytmusic_video_id'sini düzelt")
            print(f"   (veya satırı tamamen sil), sonra `python sync.py` — RESUME modda devam eder.")
            return False

    print(f"\n   apply tamam: {total} yeni eklendi (toplam {len(rows_sorted)}).")
    return True


def _read_plan(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_plan(path, rows):
    fieldnames = ["spotify_id", "added_at", "artist", "track",
                  "ytmusic_video_id", "match_score", "status"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------------
# Regular playlists (sync.py'ın eski davranışı)
# --------------------------------------------------------------------------

def handle_regular_playlist(sp, yt, state, sp_pl, unmatched_rows):
    sp_pl_id, sp_pl_name = sp_pl["id"], sp_pl["name"]
    print(f"\n>> {sp_pl_name}")

    yt_pl_id = (state.get_ytmusic_playlist_id(sp_pl_id)
                or yt.find_playlist_by_name(sp_pl_name))
    if not yt_pl_id:
        yt_pl_id = yt.create_playlist(sp_pl_name,
                                      f"Synced from Spotify: {sp_pl_name}")
        print("   + YT Music'te yeni playlist oluşturuldu")
    state.save_playlist_mapping(sp_pl_id, sp_pl_name, yt_pl_id)

    tracks = sp.get_playlist_tracks(sp_pl_id)
    new = [t for t in tracks if not state.is_synced(t["id"], sp_pl_id)]
    print(f"   {len(tracks)} şarkı ({len(new)} yeni)")

    added = 0
    for t in new:
        candidates = yt.search_song(build_query(t), limit=5)
        best, score = pick_best_match(t, candidates)

        if best:
            try:
                yt.add_track_to_playlist(yt_pl_id, best["videoId"])
                state.record_track(t["id"], sp_pl_id, best["videoId"],
                                   yt_pl_id, score, "added")
                added += 1
                print(f"   + {t['artists'][0]} — {t['name']}  ({score:.2f})")
            except Exception as e:
                state.record_track(t["id"], sp_pl_id, best["videoId"],
                                   yt_pl_id, score, "error")
                print(f"   x eklenemedi ({t['name']}): {e}")
        else:
            state.record_track(t["id"], sp_pl_id, None, yt_pl_id, score, "unmatched")
            unmatched_rows.append({
                "playlist":   sp_pl_name,
                "artist":     ", ".join(t["artists"]),
                "track":      t["name"],
                "best_score": f"{score:.2f}",
                "spotify_id": t["id"],
            })
            print(f"   ? eşleşmedi: {t['artists'][0]} — {t['name']}")
    return added


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    if not config.PLAYLISTS_TO_SYNC and not getattr(config, "SYNC_LIKED_SONGS", False):
        print("! config.py içinde ne PLAYLISTS_TO_SYNC ne SYNC_LIKED_SONGS aktif.")
        sys.exit(1)

    sp = SpotifyClient()
    yt = YTMusicClient()
    state = State(config.STATE_DB)

    # Regular playlists
    unmatched_rows = []
    total_added = 0
    if config.PLAYLISTS_TO_SYNC:
        sp_playlists = sp.find_playlists_by_names(config.PLAYLISTS_TO_SYNC)
        found = {p["name"] for p in sp_playlists}
        for name in config.PLAYLISTS_TO_SYNC:
            if name not in found:
                print(f"!  Spotify'da bulunamadı: {name}")

        for sp_pl in sp_playlists:
            total_added += handle_regular_playlist(sp, yt, state, sp_pl, unmatched_rows)

        if unmatched_rows:
            with open(config.UNMATCHED_REPORT, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=unmatched_rows[0].keys())
                w.writeheader()
                w.writerows(unmatched_rows)
            print(f"\n{len(unmatched_rows)} eşleşmeyen → {config.UNMATCHED_REPORT}")

    # Liked Songs
    if getattr(config, "SYNC_LIKED_SONGS", False):
        handle_liked_songs(sp, yt, state)

    print(f"\nRegular playlists'e eklenen: {total_added}")


if __name__ == "__main__":
    main()
