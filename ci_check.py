"""One leaderboard check for the always-on version (runs on GitHub Actions).

Loads public_snapshot_<region>.json from --dir, fetches the current top 250,
applies the same logic as the PC program and writes the file back.
No API keys and no personal data are involved.
"""
import argparse
import json
import os
import shutil
import sys
import time

import gw2_leaderboard_watcher as w

MAX_GAP = 1200  # seconds credited as "watched" between two checks (peak-hours map)


def load(path, season, region):
    state = w.new_state(season["id"], region)
    if not os.path.exists(path):
        return state, None
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except Exception:
        return state, None
    if saved.get("season") != season["id"] or saved.get("region") != region:
        # new season: keep the old file next to it, start fresh
        old = os.path.join(os.path.dirname(path), f"season_{saved.get('season', 'old')}_{region}.json")
        shutil.copyfile(path, old)
        return state, None
    for k in state:
        if k in saved and k not in ("season", "region"):
            state[k] = saved[k]
    return state, saved.get("updated")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="data")
    p.add_argument("--regions", default="na,eu")
    p.add_argument("--seed-dir", default=".", help="where to look for a starting snapshot the first time")
    args = p.parse_args()
    os.makedirs(args.dir, exist_ok=True)

    season = w.find_active_season()
    if not season:
        print("No ranked season active.")
        return 0
    failed = 0
    for region in [r.strip() for r in args.regions.split(",") if r.strip()]:
        path = os.path.join(args.dir, f"public_snapshot_{region}.json")
        seed = os.path.join(args.seed_dir, f"public_snapshot_{region}.json")
        if not os.path.exists(path) and os.path.exists(seed):
            shutil.copyfile(seed, path)
            print(f"{region}: starting from the uploaded snapshot")
        state, prev = load(path, season, region)
        try:
            new = w.fetch_ladder(season, region)
        except Exception as e:
            print(f"{region}: API error {e}")
            failed += 1
            continue
        if not new:
            print(f"{region}: empty leaderboard")
            continue
        now = time.time()
        watched = min(MAX_GAP, max(0, now - prev)) if prev else 0
        events = w.apply_snapshot(state, new, now_ts=now, interval=watched)
        cwd = os.getcwd()
        os.chdir(args.dir)
        try:
            w.write_public(state, season, region, now_ts=now)
        finally:
            os.chdir(cwd)
        games = sum(e["dw"] + e["dl"] for e in events if e["type"] == "match")
        print(f"{region}: {len(new)} players, {games} new games")
    return 1 if failed and failed == len(args.regions.split(",")) else 0


if __name__ == "__main__":
    sys.exit(main())
