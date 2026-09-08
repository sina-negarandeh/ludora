#!/usr/bin/env bash
# Capture the iOS decoding-test fixtures from a running backend.
#
# These are real API responses, never hand-written, because that is the
# whole point: three clients now read one API contract and nothing
# type-checks Swift against Python. Refresh these after a backend schema
# change and `make ios-test` fails with the field named, instead of the app
# failing on screen.
#
# Requires `make up` (Postgres) and `make backend` (FastAPI on :8000).
set -euo pipefail

BASE="${LUDORA_API:-http://localhost:8000}"
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/ios/LudoraKit/Tests/LudoraKitTests/Fixtures"

if ! curl -sf "$BASE/health" >/dev/null; then
    echo "error: no backend at $BASE. Run 'make up' then 'make backend' first." >&2
    exit 1
fi
if ! curl -sf "$BASE/api/games/?limit=1" >/dev/null; then
    echo "error: $BASE is up but has no data. Is Postgres running and seeded?" >&2
    exit 1
fi

mkdir -p "$OUT"
BGG=$(curl -sf "$BASE/api/games/?limit=1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["bgg_id"])')

curl -sf "$BASE/api/games/?limit=3"                  -o "$OUT/games_list.json"
curl -sf "$BASE/api/games/$BGG"                      -o "$OUT/game_detail.json"
curl -sf "$BASE/api/games/$BGG/reviews?page=1&page_size=3" -o "$OUT/reviews.json"
curl -sf "$BASE/api/subdomains"                      -o "$OUT/subdomains.json"
curl -sf "$BASE/api/categories"                      -o "$OUT/categories.json"
curl -sf "$BASE/api/themes"                          -o "$OUT/themes.json"
curl -sf "$BASE/api/families"                        -o "$OUT/families.json"
curl -sf -X POST "$BASE/api/search/" -H "Content-Type: application/json" \
     -d '{"q":"industrial revolution economic","mode":"hybrid"}' -o "$OUT/search_results.json"

# A deliberately sparse game, pinned by id rather than searched for.
#
# The catalog is scraped and incomplete, so the fixtures have to include a
# row with real nulls and an empty tag array, or the optionality in the
# Swift models is asserted but never exercised. This one has a null
# subdomain_ranks and an empty subdomains array.
#
# Pinned, not chosen by a "most null fields" heuristic: the test asserts
# this exact bgg_id, so a heuristic that picked a different game on a later
# run would break the test for no real reason. If this game ever leaves the
# catalog, pick another sparse one and update the test together with it.
SPARSE_BGG=199401
if curl -sf "$BASE/api/games/$SPARSE_BGG" -o "$OUT/game_sparse.json"; then
    python3 - "$OUT/game_sparse.json" <<'CHECK'
import json, sys
game = json.load(open(sys.argv[1]))
missing = []
if game.get("subdomain_ranks") is not None:
    missing.append("subdomain_ranks is no longer null")
if game.get("subdomains") != []:
    missing.append("subdomains is no longer empty")
if missing:
    print("warning: the pinned sparse game no longer exercises optionality:", file=sys.stderr)
    for m in missing:
        print(f"  - {m}", file=sys.stderr)
    print("  pick another sparse game and update DecodingTests together.", file=sys.stderr)
CHECK
else
    echo "warning: could not fetch the pinned sparse game ($SPARSE_BGG)." >&2
fi

# Trim the two responses that are large enough to bloat the repo. Keeping
# every branch of the decoder exercised matters; keeping 388KB of family
# namespaces in git does not.
python3 - "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])

def rewrite(name, fn):
    path = out / name
    data = json.loads(path.read_text())
    path.write_text(json.dumps(fn(data), indent=2))

rewrite("families.json", lambda d: [{"group": g["group"], "values": g["values"][:3]} for g in d[:3]])
rewrite("themes.json", lambda d: d[:5])
rewrite("categories.json", lambda d: d[:10])
rewrite("search_results.json", lambda d: {**d, "items": d["items"][:2]})
PY

echo "captured $(ls -1 "$OUT"/*.json | wc -l | tr -d ' ') fixtures into ios/LudoraKit/Tests/LudoraKitTests/Fixtures ($(du -sh "$OUT" | cut -f1))"
echo "run 'make ios-test' to check them against the Swift models"
