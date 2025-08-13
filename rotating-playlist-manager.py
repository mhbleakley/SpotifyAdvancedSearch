import time
import os
from datetime import datetime, timedelta, UTC
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

SCOPE = "user-library-read playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"
MONTHS_BACK = 12
PLURAL = 's' if MONTHS_BACK > 1 else ''
ROTATION_NAME = f"Rotation: Last {MONTHS_BACK} Month{PLURAL}"

def init_spotify_client():
    return Spotify(auth_manager=SpotifyOAuth(
        scope=SCOPE,
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        redirect_uri=os.getenv("REDIRECT_URI"),
        cache_path=".cache_rotation"
    ))

def fetch_liked_tracks(sp, months=12):
    cutoff = datetime.now(UTC) - timedelta(days=months*30)
    results = []
    offset = 0

    while True:
        items = sp.current_user_saved_tracks(limit=50, offset=offset)["items"]
        if not items:
            break
        for item in items:
            added_at = datetime.strptime(item["added_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            if added_at >= cutoff:
                results.append(item["track"]["id"])
            else:
                return results  # Spotify returns most recent first, so we can stop
        offset += len(items)
    return results


def get_all_user_playlists(sp) -> list[dict]:
    playlists = []
    offset = 0

    while True:
        response = sp.current_user_playlists(limit=50, offset=offset)
        items = response.get('items', [])
        if not items:
            break
        playlists.extend(items)
        offset += len(items)

    return playlists


def find_or_create_playlist(sp, user_id, name):
    offset = 0
    while True:
        resp = sp.current_user_playlists(limit=50, offset=offset)
        for pl in resp.get("items", []):
            if pl["name"] == name and pl["owner"]["id"] == user_id:
                return pl["id"]
        if resp["next"] is None:
            break
        offset += 50

    new_pl = sp.user_playlist_create(user=user_id, name=name, public=False)
    return new_pl["id"]

def get_playlist_track_ids(sp, playlist_id):
    ids = []
    offset = 0
    while True:
        resp = sp.playlist_items(playlist_id, fields="items.track.id,next", limit=100, offset=offset)
        items = resp.get("items", [])
        if not items:
            break
        ids.extend(track["track"]["id"] for track in items if track["track"])
        offset += len(items)
    return ids

def update_playlist_if_needed(sp, playlist_id, new_track_ids):
    existing_ids = get_playlist_track_ids(sp, playlist_id)

    if set(existing_ids) == set(new_track_ids):
        print("Playlist is already up to date.")
        return

    # Clear and re-add (Spotify API does not support replace in one call)
    sp.playlist_replace_items(playlist_id, new_track_ids[:100])
    for i in range(100, len(new_track_ids), 100):
        sp.playlist_add_items(playlist_id, new_track_ids[i:i+100])

    print(f"Updated playlist with {len(new_track_ids)} tracks.")

def main():
    sp = init_spotify_client()
    user_id = sp.current_user()["id"]

    track_ids = fetch_liked_tracks(sp, months=MONTHS_BACK)
    print(f"Found {len(track_ids)} liked tracks from last {MONTHS_BACK} months.")

    print(f'Target Playlist: {ROTATION_NAME}')

    playlists = get_all_user_playlists(sp)

    skip_generation = False
    if len(playlists) < 1:
        print('No playlists found. Likely an error/rate limit, skipping playlist generation to avoid duplicates')
        skip_generation = True

    if not skip_generation:

        print(f'Searching user playlists...')

        target_playlist = None
        for pl in playlists:
            print(f"\t-{pl['name']}") #  ({pl['id']}) - {pl['tracks']['total']} tracks
            if pl['name'] == ROTATION_NAME:
                print('Match found')
                target_playlist = pl['id']
                break

        if target_playlist == None:
            print("Target playlist not found, creating new playlist...")
            target_playlist = find_or_create_playlist(sp, user_id, ROTATION_NAME)
            update_playlist_if_needed(sp, target_playlist, track_ids)
        else:
            print("Target playlist found, checking for updates...")
            update_playlist_if_needed(sp, target_playlist, track_ids)


if __name__ == "__main__":
    main()
