"""İki servisin auth'ı çalışıyor mu diye hızlı test."""
from spotify_client import SpotifyClient
from ytmusic_client import YTMusicClient


def main():
    print("Spotify auth testi...")
    sp = SpotifyClient()
    me = sp.sp.current_user()
    print(f"  OK: {me['display_name']} ({me['id']})")
    pls = sp.get_user_playlists()
    print(f"  {len(pls)} playlist bulundu.")

    print("\nYT Music auth testi...")
    yt = YTMusicClient()
    yt_pls = yt.get_library_playlists()
    print(f"  OK: {len(yt_pls)} playlist bulundu.")


if __name__ == "__main__":
    main()
