"""Reads public stats for every posted video and saves them. Runs on GitHub Actions."""
import json, csv, os, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
posts = json.load(open(os.path.join(ROOT, "tracker", "posts.json")))
now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
FIELDS = ["view_count", "like_count", "comment_count", "repost_count", "duration"]

def fetch(url):
    try:
        out = subprocess.run(["yt-dlp", "--dump-json", "--skip-download", "--no-warnings", url],
                             capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return {"error": (out.stderr or "failed").strip().splitlines()[-1][:200]}
        j = json.loads(out.stdout)
        return {k: j.get(k) for k in FIELDS}
    except Exception as e:
        return {"error": str(e)[:200]}

latest = {"updated_utc": now, "posts": []}
rows = []
for p in posts:
    entry = {"id": p["id"], "title": p.get("title", "")}
    for platform in ("tiktok", "youtube"):
        if p.get(platform):
            s = fetch(p[platform]); entry[platform] = s
            rows.append([now, p["id"], platform] + [s.get(k, "") for k in FIELDS] + [s.get("error", "")])
    latest["posts"].append(entry)

os.makedirs(os.path.join(ROOT, "stats"), exist_ok=True)
json.dump(latest, open(os.path.join(ROOT, "stats", "latest.json"), "w"), indent=2)
hist = os.path.join(ROOT, "stats", "history.csv")
new = not os.path.exists(hist)
with open(hist, "a", newline="") as f:
    w = csv.writer(f)
    if new: w.writerow(["time_utc", "post", "platform"] + FIELDS + ["error"])
    w.writerows(rows)
print(json.dumps(latest, indent=2))
