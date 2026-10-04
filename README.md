# GW2 Leaderboard Watcher

Live Guild Wars 2 ranked PvP top 250 (NA and EU): rating charts, who's on fire or cold, peak hours,
rating cutoffs, personal stats with your own API key, a match helper and build guides.

- **Website:** https://sinoenix.github.io/gw2-watcher/
- **How it works:** a GitHub Action (`.github/workflows/watch.yml`) runs `ci_check.py` every few minutes,
  reads the public GW2 API and saves the shared history to the `data` branch. The page loads that history
  and keeps updating live while it is open.
- **API keys** typed on the page stay in the visitor's browser and are only sent to ArenaNet.
- `gw2_leaderboard_watcher.py` is the PC version (Python 3.8+, no installs).

Fan-made, not affiliated with ArenaNet.
