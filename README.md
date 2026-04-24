# Spotify → YouTube Music Sync

Belirli Spotify playlist'lerini YouTube Music'e taşır ve sonraki çalıştırmalarda sadece yeni şarkıları ekler.

## Kurulum

```bash
cd spotify-to-ytmusic
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 1) Spotify auth

1. https://developer.spotify.com/dashboard → **Create App**
2. Redirect URI olarak `http://localhost:8888/callback` ekle
3. `Client ID` ve `Client Secret`'ı al
4. `.env.example` → `.env` olarak kopyala, değerleri doldur

## 2) YT Music auth (browser yöntemi)

```bash
ytmusicapi browser
```

Komut sana ne yapacağını söyleyecek:
- Tarayıcıda `music.youtube.com`'a gir, giriş yap
- Herhangi bir XHR request'e sağ tık → Copy → Copy request headers
- Terminale yapıştır, Enter
- `browser.json` dosyası oluşur (proje kökünde olmalı)

> Headerlar birkaç ay sonra expire olabilir; o zaman aynı komutla yenile.

## 3) Playlist'leri seç

`config.py` içinde `PLAYLISTS_TO_SYNC` listesine Spotify'daki isimleri bire bir yaz:

```python
PLAYLISTS_TO_SYNC = [
    "Chill Vibes",
    "Türkçe Rock",
]
```

## 4) Auth testi

```bash
python test_auth.py
```

İki servis de OK dönerse devam.

## 5) Sync

```bash
python sync.py
```

İlk çalıştırmada Spotify tarayıcı penceresi açılıp yetki isteyecek. Sonraki çalıştırmalarda `.spotify_cache` kullanır.

## Çıktı

- Eklenen şarkılar `state.db`'ye kaydedilir → bir daha aranmaz/eklenmez
- Eşleşmeyen şarkılar `unmatched_report.csv`'ye yazılır (manuel bakabilirsin)

## Eşleştirme ayarları

`config.py`:
- `MATCH_THRESHOLD` (varsayılan 0.70) — daha sıkı eşleşme için yükselt
- `DURATION_TOLERANCE_SEC` (varsayılan 3) — süre toleransı

Skor = %40 başlık benzerliği + %35 sanatçı benzerliği + %25 süre uyumu.

## Yapı

```
spotify_client.py   Spotify API (playlist + track çekme)
ytmusic_client.py   YT Music API (arama + playlist yönetimi)
matcher.py          Eşleştirme skorlaması
state.py            SQLite: neyi ekledik state'i
sync.py             Orkestrasyon
```
