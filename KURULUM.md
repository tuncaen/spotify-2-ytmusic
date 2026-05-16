# Sıfırdan Kurulum Rehberi

Yeni bir bilgisayarda, başka bir Spotify ve YouTube Music hesabıyla bu sync aracını çalıştırmak için adım adım yönerge.

İki büyük adımı içerir:
- **Spotify auth** — mevcut `spolist` app'i (kullanıcı eklenerek) veya sıfırdan kendi app'ini oluşturma
- **YT Music auth** — browser cookie tabanlı (kota yok)

---

## 0. Önkoşullar

- Python 3.11+
- Git
- Firefox (YT Music headers'ı en kolay yakalanan tarayıcı; Chrome da olur ama Firefox önerilir)
- Senkronlamak istediğin Spotify hesabının kullanıcı adı ve şifresi
- Hedef YouTube Music hesabı (Spotify ile **aynı kişiye ait olması gerekmez**)

---

## 1. Repoyu klonla

PowerShell veya terminalde, klonu nereye atmak istiyorsan oraya `cd` ile gir:

```powershell
git clone https://github.com/tuncaen/spotify-2-ytmusic.git
cd spotify-2-ytmusic
```

---

## 2. Python virtual env ve bağımlılıklar

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Eğer PowerShell `Activate.ps1` çalıştırırken "execution policy" hatası verirse, aynı pencerede şunu çalıştır: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, sonra tekrar `Activate.ps1`.

---

## 3. Spotify auth

İki yol var:

### 3A. Mevcut `spolist` app'ini kullan (önerilen — daha az iş)

Bu app `tuncaenes@gmail.com` tarafından oluşturulmuş; `Development` modunda. Yeni bir Spotify hesabıyla kullanmak için **bu hesabın email'i app'in "User Management" listesine eklenmiş olmalı**.

**App sahibinin yapacağı (bir kerelik):**

1. https://developer.spotify.com/dashboard → `spolist` app'i seç
2. Sağ üstte **Settings** → sol menüde **User Management**
3. **Add new user** → yeni hesabın **email adresi** ve **adı** → **Add**

User eklenince yeni hesap aynı `Client ID` ve `Client Secret` ile auth olabilir.

`.env` dosyasını oluştur (`.env.example`'ı kopyala) ve şu değerleri gir:

```
SPOTIFY_CLIENT_ID=<spolist sahibinin client id>
SPOTIFY_CLIENT_SECRET=<spolist sahibinin client secret>
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

> Client Secret değerini app sahibinden iste — Dashboard'da `View client secret`'a tıklayarak görünür.

### 3B. Sıfırdan kendi Spotify app'ini oluştur (bağımsız)

App sahibine erişimin yoksa veya kendi app'in olsun istiyorsan:

1. https://developer.spotify.com/dashboard → hesabınla giriş yap
2. **Create app** → form:
   - **App name**: `spolist-account2` (herhangi bir şey, sadece sana özel)
   - **App description**: `Personal playlist sync`
   - **Redirect URI**: `http://127.0.0.1:8888/callback` → **Add** butonu (kutuda zincir gibi görünmesi lazım)
   - **Which API/SDKs are you planning to use?** → sadece **Web API** işaretli
   - "Developer Terms of Service" kutusunu işaretle → **Save**
3. App detayında `Client ID`'yi kopyala, **View client secret**'a tıklayıp `Client Secret`'i de kopyala
4. `.env`'ye gir:

```
SPOTIFY_CLIENT_ID=<senin client id>
SPOTIFY_CLIENT_SECRET=<senin client secret>
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

> Yeni oluşan app de Development modunda. Yalnız kendi hesabınla kullanacaksan ek bir şey gerekmez. Başkalarına vermek istersen yine User Management'tan ekleme yaparsın.

---

## 4. YT Music browser auth

YT Music için cookie tabanlı auth kullanıyoruz — kota yok, hız sınırı yok.

1. Firefox'ta **incognito (özel) pencere** aç (Ctrl+Shift+P) — clean session olsun, başka Google hesaplarıyla karışmasın
2. `https://music.youtube.com`'a git, **sync için kullanmak istediğin YouTube hesabıyla** giriş yap
3. Önce manuel doğrulama: Library → New playlist butonu ile küçük bir test playlist'i oluşturmayı dene (sonra silersin). Bu, hesabın yazma izninin olduğunu garanti eder
4. F12 (DevTools) → **Network** sekmesi → filtre kutusuna `browse` yaz
5. Sol menüden bir playlist'e tıkla — Network'te `/youtubei/v1/browse` POST isteklerinin geldiğini gör
6. Bu POST isteklerden birine **sağ tık** → **Copy Value** → **Copy Request Headers**
7. VSCode'da proje kökünde [headers.txt](headers.txt) dosyası oluştur, kopyaladığını yapıştır, kaydet (newline'lar korunsun)
8. `browser.json`'u Python ile üret:

```powershell
.venv\Scripts\python -c "from ytmusicapi import setup; setup(filepath='browser.json', headers_raw=open('headers.txt', encoding='utf-8').read())"
```

`browser.json` proje kökünde oluşur, gitignore'da olduğu için commit'lenmez.

> Headers birkaç ay sonra expire olabilir — auth çalışmamaya başlarsa aynı adımlarla yenile.

---

## 5. config.py — sync hedefleri

`config.py` dosyasını aç, **`PLAYLISTS_TO_SYNC`** listesine sync etmek istediğin Spotify playlist isimlerini **birebir** yaz:

```python
PLAYLISTS_TO_SYNC = [
    "Chill Vibes",
    "Türkçe Rock",
]

SYNC_LIKED_SONGS = True
LIKED_SONGS_YT_NAME = "Liked Songs (Spotify)"
```

> İsmi bilmiyorsan, auth tamamlandıktan sonra şu komutla listele:
> ```powershell
> $env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python -c "from spotify_client import SpotifyClient; sp=SpotifyClient(); [print(p['name']) for p in sp.get_user_playlists()]"
> ```

`SYNC_LIKED_SONGS = True` ise Spotify'ın "Beğenilen Şarkılar" özel koleksiyonu da senkronlanır (`LIKED_SONGS_YT_NAME` adında bir YT playlist'i oluşturulur).

---

## 6. Auth doğrulama

```powershell
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python test_auth.py
```

İlk çalıştırmada Spotify tarayıcı penceresi açıp yetki ister — izin ver, browser cache'i `.spotify_cache` olarak oluşur.

Beklenen çıktı:
```
Spotify auth testi...
  OK: <isim> (<spotify_user_id>)
  N playlist bulundu.

YT Music auth testi...
  OK: M playlist bulundu.
```

İkisi de **OK** dönerse sıradakine geç. Hata alırsan "Sorun Giderme" bölümüne bak.

---

## 7. İlk sync

```powershell
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python sync.py
```

- Her Spotify playlist için aynı isimde bir YT Music playlist'i oluşturulur (private)
- Şarkılar matchlenmeye çalışılır, başarılı eşleşmeler eklenir
- Eşleşmeyenler `unmatched_report.csv`'ye yazılır
- `state.db`'de neyin eklendiği kaydedilir → tekrar çalıştırınca aynı şarkılar tekrar denenmez

Spotify'a yeni şarkı eklediğin zaman aynı komutu tekrar çalıştır — yalnızca yeni eklenenler senkronlanır.

---

## Sorun Giderme

### Spotify 403 / "Access blocked"
- App'in `User Management`'ında bu hesabın eklenmiş olduğundan emin ol (3A senaryosu)
- Veya kendi app'ini oluştur (3B)

### Spotify redirect URI mismatch
- App ayarlarında **Redirect URI** olarak `http://127.0.0.1:8888/callback` (bire bir, `localhost` değil) ekli olmalı

### YT Music auth `KeyError: 'cookie'` veya benzeri
- Headers'ı yanlış capture etmiş olabilirsin. `headers.txt`'i sil, yeni bir `/browse` POST isteğinden Copy Request Headers yap, tekrar dene
- Eğer terminal'e yapıştırıyorsan newline'lar kayboluyor — VSCode dosyaya yapıştır

### "Bu YT account'u manuel playlist oluşturamıyor"
- Hesap YT Music'e tam erişimi yoksa (örneğin family üyesi, brand account vb.) write işlemleri 401/403 olur
- Önce music.youtube.com'da UI'dan bir playlist oluşturmayı dene; çalışırsa header capture aynı oturumdan yap

### `state.db` bozulduysa / temiz başlamak istiyorsan
```powershell
Remove-Item state.db, unmatched_report.csv -ErrorAction SilentlyContinue
```
Sonra `python sync.py` — tüm playlist'leri tekrar tarar, ama YT Music'te mevcut playlist'ler korunur (state.db olmadığı için, sync.py find_playlist_by_name ile isimden bulur ve mapping'i yeniden yazar).

### Headers expire oldu (birkaç ay sonra)
YT Music sürekli çalışmıyorsa: `headers.txt`'i yenile (incognito Firefox → music.youtube.com → DevTools → Copy Request Headers), sonra `setup(...)` komutunu tekrar çalıştır.

---

## Yapı

```
.env                    Spotify credentials (gitignored)
browser.json            YT Music cookie auth (gitignored)
.spotify_cache          Spotify OAuth token cache (gitignored)
state.db                SQLite: synclanan tracks ve playlist mapping'i (gitignored)
unmatched_report.csv    Eşleşmeyenlerin raporu (gitignored)
config.py               Playlist isimleri, threshold, dosya path'leri
spotify_client.py       Spotify API wrapper
ytmusic_client.py       YT Music API wrapper (ytmusicapi + browser auth)
matcher.py              Track eşleştirme skorlaması
sync.py                 Ana orkestrasyon
test_auth.py            Auth doğrulama testi
```
