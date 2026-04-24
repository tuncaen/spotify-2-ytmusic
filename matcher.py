from rapidfuzz import fuzz
import config


def _norm(s):
    return (s or "").lower().strip()


def _duration_seconds(candidate):
    if candidate.get("duration_seconds"):
        return candidate["duration_seconds"]
    dur = candidate.get("duration") or ""
    parts = dur.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0


def score_candidate(spotify_track, cand):
    sp_title   = _norm(spotify_track["name"])
    sp_artists = " ".join(_norm(a) for a in spotify_track["artists"])
    sp_dur     = spotify_track["duration_ms"] / 1000

    yt_title   = _norm(cand.get("title", ""))
    yt_artists = " ".join(_norm(a["name"]) for a in cand.get("artists", []))
    yt_dur     = _duration_seconds(cand)

    title_s  = fuzz.token_set_ratio(sp_title, yt_title) / 100
    artist_s = fuzz.token_set_ratio(sp_artists, yt_artists) / 100

    if yt_dur == 0:
        dur_s = 0.5
    else:
        diff = abs(sp_dur - yt_dur)
        dur_s = 1.0 if diff <= config.DURATION_TOLERANCE_SEC \
               else 0.5 if diff <= 10 else 0.0

    return 0.40 * title_s + 0.35 * artist_s + 0.25 * dur_s


def pick_best_match(spotify_track, candidates):
    if not candidates:
        return None, 0.0
    scored = [(c, score_candidate(spotify_track, c)) for c in candidates]
    best, score = max(scored, key=lambda x: x[1])
    if score >= config.MATCH_THRESHOLD:
        return best, score
    return None, score   # eşik altı — unmatched
