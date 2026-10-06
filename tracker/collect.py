"""Reads public stats for every posted video and saves them. Runs on GitHub Actions.
YouTube: official YouTube Data API (needs repo secret YT_API_KEY), else public mirrors.
TikTok: public stats lookup (tikwm), else yt-dlp."""
import json, csv, os, re, subprocess, datetime, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
posts = json.load(open(os.path.join(ROOT, "tracker", "posts.json")))
now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
FIELDS = ["views", "likes", "comments", "shares", "source"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

def get_json(url, data=None):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def youtube(url):
    vid = re.search(r"(?:shorts/|v=|youtu\.be/)([\w-]{11})", url).group(1)
    key = os.environ.get("YT_API_KEY")
    errors = []
    if key:
        try:
            j = get_json(f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={vid}&key={key}")
            st = j["items"][0]["statistics"]
            return {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                    "comments": int(st.get("commentCount", 0)), "shares": "", "source": "youtube-api"}
        except Exception as e: errors.append(f"api: {e}")
    for base in ("https://pipedapi.kavin.rocks", "https://pipedapi.adminforge.de", "https://api.piped.private.coffee"):
        try:
            j = get_json(f"{base}/streams/{vid}")
            return {"views": j.get("views"), "likes": j.get("likes"), "comments": "", "shares": "", "source": base}
        except Exception as e: errors.append(f"{base}: {str(e)[:60]}")
    return {"error": " | ".join(errors)[:300]}

def tiktok(url):
    errors = []
    try:
        j = get_json("https://www.tikwm.com/api/", data=urllib.parse.urlencode({"url": url, "hd": 0}).encode())
        d = j.get("data") or {}
        if d:
            return {"views": d.get("play_count"), "likes": d.get("digg_count"), "comments": d.get("comment_count"),
                    "shares": d.get("share_count"), "source": "tikwm"}
        errors.append(f"tikwm: {j.get('msg')}")
    except Exception as e: errors.append(f"tikwm: {str(e)[:80]}")
    try:
        out = subprocess.run(["yt-dlp", "--dump-json", "--skip-download", "--no-warnings", url], capture_output=True, text=True, timeout=120)
        if out.returncode == 0:
            j = json.loads(out.stdout)
            return {"views": j.get("view_count"), "likes": j.get("like_count"), "comments": j.get("comment_count"),
                    "shares": j.get("repost_count"), "source": "yt-dlp"}
        errors.append("yt-dlp: " + (out.stderr.strip().splitlines() or ["failed"])[-1][:80])
    except Exception as e: errors.append(f"yt-dlp: {e}")
    return {"error": " | ".join(errors)[:300]}

latest = {"updated_utc": now, "posts": []}
rows = []
for p in posts:
    entry = {"id": p["id"], "title": p.get("title", "")}
    for platform, fn in (("tiktok", tiktok), ("youtube", youtube)):
        if p.get(platform):
            s = fn(p[platform]); entry[platform] = s
            rows.append([now, p["id"], platform] + [s.get(k, "") for k in FIELDS] + [s.get("error", "")])
    latest["posts"].append(entry)

os.makedirs(os.path.join(ROOT, "stats"), exist_ok=True)
json.dump(latest, open(os.path.join(ROOT, "stats", "latest.json"), "w"), indent=2)
hist = os.path.join(ROOT, "stats", "history.csv")
new = not os.path.exists(hist) or open(hist).readline().strip() != ",".join(["time_utc", "post", "platform"] + FIELDS + ["error"])
with open(hist, "w" if new else "a", newline="") as f:
    w = csv.writer(f)
    if new: w.writerow(["time_utc", "post", "platform"] + FIELDS + ["error"])
    w.writerows(rows)
print(json.dumps(latest, indent=2))
