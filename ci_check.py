"""One leaderboard check for the always-on version (runs on GitHub Actions).

Loads public_snapshot_<region>.json from --dir, fetches the current top 250,
applies the same logic as the PC program and writes the file back.

If the GW2_API_KEY secret is set, it also keeps the owner's own ranked games and
rating in me.json (the key itself is never written anywhere).
"""
import argparse
import json
import os
import shutil
import sys
import time

import gw2_leaderboard_watcher as w

MAX_SPREAD = 6 * 3600  # gaps up to this long are spread over the hours they cover (peak-hours map)


def spread_gap(state, prev, now, games):
    """Credits the time between two checks, and the games found, to every hour it covers.

    apply_snapshot() was called with interval=0, so it put all `games` in the current
    hour and credited no watching time. GitHub can skip scheduled runs for a while; without
    this, one late check would dump hours of games into a single hour.
    """
    bucket_now = w.hour_bucket(now)
    state["hour_counts"][bucket_now] = state["hour_counts"].get(bucket_now, 0) - games
    if state["hour_counts"][bucket_now] <= 0:
        state["hour_counts"].pop(bucket_now, None)
    if not prev or now <= prev or now - prev > MAX_SPREAD:
        return  # first check, or a gap too long to trust: count nothing for peak hours
    span = now - prev
    t = prev
    while t < now:
        start = int(t // 3600 * 3600)
        end = min(now, start + 3600)
        part = end - t
        b = str(start)
        state["observed_hours"][b] = min(3600, state["observed_hours"].get(b, 0) + part)
        share = games * part / span
        if share:
            state["hour_counts"][b] = round(state["hour_counts"].get(b, 0) + share, 2)
        t = end


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


def update_me(dirpath, season):
    """Saves the key owner's recent games and rating to me.json (GitHub secret GW2_API_KEY)."""
    key = os.environ.get("GW2_API_KEY", "").strip()
    if not key:
        return
    path = os.path.join(dirpath, "me.json")
    store = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                store = json.load(f)
        except Exception:
            store = {}
    state = {"maps": store.pop("maps", {}) or {}}
    store.pop("updated", None)
    try:
        fresh = w.fetch_player(state, store, key, season["id"])
    except w.AuthError:
        print("me: the API key was rejected (needs account + pvp)")
        return
    except Exception as e:
        print(f"me: could not update ({e})")
        return
    store["maps"] = state["maps"]
    store["updated"] = time.time()
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(store, f, separators=(",", ":"))
    os.replace(path + ".tmp", path)
    print(f"me: {store.get('account')} rating {store.get('rating')} ({len(fresh)} new games, {len(store['games'])} saved)")


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
        events = w.apply_snapshot(state, new, now_ts=now, interval=0)
        games = sum(e["dw"] + e["dl"] for e in events if e["type"] == "match")
        if prev:
            spread_gap(state, prev, now, games)
        cwd = os.getcwd()
        os.chdir(args.dir)
        try:
            w.write_public(state, season, region, now_ts=now)
        finally:
            os.chdir(cwd)
        print(f"{region}: {len(new)} players, {games} new games")
    update_me(args.dir, season)
    return 1 if failed and failed == len(args.regions.split(",")) else 0


if __name__ == "__main__":
    sys.exit(main())
