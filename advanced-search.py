import argparse
import os
from datetime import datetime, timedelta, timezone
from tqdm import tqdm
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import shutil
import textwrap
from wcwidth import wcswidth

end_date = datetime.now(timezone.utc)

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope="user-library-read"))

def pad_cell(text, width):
    text_width = wcswidth(text)
    pad_len = max(0, width - text_width)
    return text + " " * pad_len

def print_verbose_table(tracks, verbosity=1):
    base_headers = ["Song", "Artist(s)", "Album", "Released"]
    extended_headers = ["Added", "Play Count"] if verbosity >= 2 else []
    headers = base_headers + extended_headers

    term_width = shutil.get_terminal_size().columns
    min_col_widths = [10] * len(headers)
    col_ratios = [0.25, 0.25, 0.20, 0.10] + ([0.10, 0.10] if verbosity >= 2 else [])
    max_total_width = term_width - (len(headers) + 1) * 3 - 1
    col_widths = [
        max(min_w, int(max_total_width * ratio)) for min_w, ratio in zip(min_col_widths, col_ratios)
    ]

    def wrap_row(row):
        wrapped = [textwrap.wrap(col, width) or [''] for col, width in zip(row, col_widths)]
        max_lines = max(len(col) for col in wrapped)
        return [
            [col[i] if i < len(col) else '' for col in wrapped]
            for i in range(max_lines)
        ]

    def draw_border():
        line = '+'
        for width in col_widths:
            line += '-' * (width + 2) + '+'
        print(line)

    def draw_row(cells):
        for row in wrap_row(cells):
            line = '|'
            for i, cell in enumerate(row):
                line += ' ' + pad_cell(cell, col_widths[i]) + ' |'
            print(line)


    draw_border()
    draw_row(headers)
    draw_border()

    for item in tracks:
        track = item["track"]
        row = [
            track["name"],
            ", ".join(a["name"] for a in track["artists"]),
            track["album"]["name"],
            track["album"]["release_date"]
        ]
        if verbosity >= 2:
            added = item.get("added_at", "-").split("T")[0] if "added_at" in item else "-"
            play_count = '-'  # Placeholder
            row += [added, str(play_count)]
        draw_row(row)
        draw_border()

def parse_args():
    parser = argparse.ArgumentParser(description="Advanced Spotify Song Search")
    parser.add_argument("-l", "--liked", action="store_true", help="Limit to liked songs")
    parser.add_argument("--added-start", type=str, help="Start date (YYYY-MM-DD) for when track was added")
    parser.add_argument("--added-end", type=str, help="End date (YYYY-MM-DD) for when track was added")
    parser.add_argument("-r", "--recently-added", type=int, help="Tracks added in the last N months")
    parser.add_argument("-v", "--verbose", type=int, default=0, help="Verbosity level (0 = names only, 1 = table)")
    return parser.parse_args()

def get_liked_tracks(start_date=None, end_date=None):
    results = []
    limit = 50
    offset = 0

    with tqdm(desc="Filtering liked songs") as pbar:
        while True:
            batch = sp.current_user_saved_tracks(limit=limit, offset=offset)
            items = batch["items"]
            if not items:
                break

            for item in items:
                added_at = datetime.strptime(item["added_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                # Stop if we’ve gone past the start_date
                if start_date and added_at < start_date:
                    return results

                if start_date and added_at < start_date:
                    continue
                if end_date and added_at > end_date:
                    continue

                results.append(item)
                pbar.update(1)

            if batch["next"] is None:
                break

            offset += limit

    return results


def filter_by_date(tracks, start=None, end=None):
    filtered = []
    for item in tracks:
        added_at = datetime.strptime(item["added_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if start and added_at < start:
            continue
        if end and added_at > end:
            continue
        filtered.append(item)
    return filtered

def main():
    args = parse_args()
    start_date = None
    end_date = None

    if args.recently_added:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30 * args.recently_added)
    else:
        if args.added_start:
            start_date = datetime.strptime(args.added_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if args.added_end:
            end_date = datetime.strptime(args.added_end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    if args.liked:
        tracks = get_liked_tracks(start_date=start_date, end_date=end_date)

        if args.verbose == 0:
            for item in tracks:
                print(item["track"]["name"])
        else:
            print_verbose_table(tracks, verbosity=args.verbose)

    else:
        print("Search beyond liked songs not implemented yet.")

if __name__ == "__main__":
    main()
