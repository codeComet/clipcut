"""The API for scripts: API keys, starting a video, clip details with the transcript, edits, the post queue with
approval. Runs against the code directly, with its own empty data folder; nothing outside it is touched."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-api-")
os.environ.update(DATABASE_URL="", CLIPCUT_ACCOUNTS="0", CLIPCUT_AI_KEY="", CLIPCUT_AI_KEY_FILE="", CLIPCUT_FETCH_MODEL="0",
                  CLIPCUT_PUBLIC_URL="http://127.0.0.1:8765")
sys.path.insert(0, ".")
from fastapi.testclient import TestClient  # noqa: E402

from studio import accounts, apikey, auth, ctx, db, jobs, media, posting, server  # noqa: E402

db.init()
fails = []
BASE = "http://127.0.0.1:8765"
c = TestClient(server.app, base_url=BASE, follow_redirects=False)


def check(name, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   got {got!r}"))
    ok or fails.append(name)


owner = auth.local_user()
key = auth.new_api_key(owner.id, "test")
K = {"Authorization": f"Bearer {key}"}
EVIL = {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}

# ---- keys
check("a wrong key is refused", c.get("/api/jobs", headers={"Authorization": "Bearer cc_nope"}).status_code, 401)
check("a key works", c.get("/api/jobs", headers=K).status_code, 200)
check("a keyed change needs no browser origin", c.put("/api/settings", json={}, headers=K).status_code, 200)
check("without a key, another website is still refused", c.put("/api/settings", json={}, headers=EVIL).status_code, 403)
check("a key never opens the admin area", c.get("/api/admin/overview", headers=K).status_code, 404)
check("a key only opens the API", c.get("/app", headers=K).status_code, 404)
env = Path(os.environ["CLIPCUT_DATA"]) / "x" / ".env"
env.parent.mkdir()
env.write_text("OTHER=1\nCLIPCUT_API_KEY=old\n")
sys.argv = ["apikey", "--env", str(env)]
apikey.main()
saved = env.read_text().splitlines()
check("apikey --env replaces the old key and keeps the rest", (saved[0], len(saved), saved[1].startswith("CLIPCUT_API_KEY=cc_")), ("OTHER=1", 2, True))
check("...and that key works", c.get("/api/jobs", headers={"Authorization": "Bearer " + saved[1].split("=", 1)[1]}).status_code, 200)

# ---- starting a video
media._PREVIEWS["https://www.youtube.com/watch?v=LIVE1234567"] = {"title": "x", "uploader": "y", "duration": 0, "is_live": True, "thumb": ""}
r = c.post("/api/jobs", json={"url": "https://www.youtube.com/watch?v=LIVE1234567"}, headers=K)
check("a live stream is refused with a clear message", (r.status_code, "live stream" in r.json()["detail"]), (400, True))
check("a site that isn't supported is refused", c.post("/api/jobs", json={"url": "https://example.com/v"}, headers=K).status_code, 400)
check("bad options are refused", c.post("/api/jobs", json={"url": "https://youtu.be/abc", "from_min": "soon"}, headers=K).status_code, 400)

with ctx.as_user(owner.id):
    job = jobs.create({"type": "url", "url": "https://www.youtube.com/watch?v=ABCDEFGHIJK&t=5", "name": "v"},
                      {"max_clips": 3}, enqueue=False)
    d = Path(job["dir"])
    (d / "clips").mkdir()
    (d / "clips" / "clip01.mp4").write_bytes(b"x")
    (d / "words.json").write_text(json.dumps([{"w": "before", "s": 1, "e": 2}, {"w": "the", "s": 10, "e": 10.2},
                                              {"w": "opening", "s": 10.3, "e": 11}, {"w": "after", "s": 40, "e": 41}]))
    job.update(status="done", uploader="Some Channel", title="A video", clips=[
        {"id": "clip01", "start": 9.5, "end": 30, "score": 88, "hook": "WAIT", "title": "T", "description": "D",
         "hashtags": ["gta6"], "style": "bounce", "layout": "blur", "status": "done", "file": "clip01.mp4", "cover": "clip01.jpg", "version": 1}])
    jobs.save(job)
    accounts._put({"id": "acc1", "platform": "youtube", "name": "@mypage", "added": time.time()})

jid, cid = job["id"], f"{job['id']}.clip01"
j = c.get(f"/api/jobs/{jid}", headers=K).json()
check("a job answers with job_id, clip_ids and a plain status", (j["job_id"], j["clip_ids"], j["status"]), (jid, [cid], "done"))
check("the same video is found however its link is written",
      [x["job_id"] for x in c.get("/api/jobs", params={"url": "https://youtu.be/ABCDEFGHIJK"}, headers=K).json()], [jid])
check("another video is not", c.get("/api/jobs", params={"url": "https://youtu.be/ZZZZZZZZZZZ"}, headers=K).json(), [])

# ---- clips
k = c.get(f"/api/clips/{cid}", headers=K).json()
check("clip details", (k["score"], k["duration"], k["big_text"], k["source_channel"], k["source_url"].endswith("&t=5")),
      (88, 20.5, "WAIT", "Some Channel", True))
check("the clip's transcript is only what is said in it", k["transcript"], "the opening")
check("the video link works with the key", c.get(k["video_url"].replace(BASE, ""), headers=K).status_code, 200)
check("no such clip", c.get(f"/api/clips/{jid}.clip99", headers=K).status_code, 404)
k = c.patch(f"/api/clips/{cid}", json={"title": "New title"}, headers=K).json()
check("a new title needs no re-make", (k["title"], k["status"]), ("New title", "done"))
saved = []
jobs.request_render, real = (lambda jid_, cid_, ch: saved.append(ch)), jobs.request_render
check("new timing re-makes the clip", (c.patch(f"/api/clips/{cid}", json={"start": 10, "big_text": "NO WAY"}, headers=K).status_code,
                                        saved[-1]), (200, {"start": 10, "hook": "NO WAY"}))
check("remake", (c.post(f"/api/clips/{cid}/remake", headers=K).status_code, saved[-1]), (200, {}))
jobs.request_render = real

# ---- accounts and the post queue
check("accounts list the handle", c.get("/api/accounts", headers=K).json()[0]["handle"], "@mypage")
check("an unknown account is refused", c.post(f"/api/clips/{cid}/queue", json={"account_ids": ["nope"]}, headers=K).status_code, 400)
check("a bad time is refused", c.post(f"/api/clips/{cid}/queue", json={"account_ids": ["acc1"], "scheduled_at": "tomorrow"}, headers=K).status_code, 400)
r = c.post(f"/api/clips/{cid}/queue", json={"account_ids": ["acc1"], "scheduled_at": "2099-01-01T00:00:00Z"}, headers=K)
check("too far ahead is refused", r.status_code, 400)
at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 7200)) + "Z"
r = c.post(f"/api/clips/{cid}/queue", json={"account_ids": ["acc1"], "scheduled_at": at, "caption": "Hi", "approval": True}, headers=K).json()
pid = r["post_ids"][0]
p = r["posts"][0]
check("queued for approval, at the time asked, with the caption", (p["status"], abs(p["due_at"] - time.time() - 7200) < 5, p["caption"]),
      ("approval", True, "Hi"))
check("never twice to the same account", c.post(f"/api/clips/{cid}/queue", json={"account_ids": ["acc1"]}, headers=K).status_code, 400)
check("the queue lists it", [x["post_id"] for x in c.get("/api/queue", headers=K).json()], [pid])
check("the poster skips posts waiting for approval", [x for x in posting._posts if x["status"] == "scheduled"], [])
check("approve", c.post(f"/api/posts/{pid}/approve", headers=K).status_code, 200)
check("...then it is scheduled", next(x for x in posting._posts if x["id"] == pid)["status"], "scheduled")
check("approving twice is refused", c.post(f"/api/posts/{pid}/approve", headers=K).status_code, 400)
st = c.get(f"/api/posts/{pid}/stats", headers=K).json()
check("stats answer even before any numbers came in", (st["post_id"], st["views"], st["likes"]), (pid, None, None))
check("cancel", c.delete(f"/api/queue/{pid}", headers=K).status_code, 200)
check("the queue is empty again", c.get("/api/queue", headers=K).json(), [])
check("...but all=1 still shows it", [x["status"] for x in c.get("/api/queue", params={"all": 1}, headers=K).json()], ["cancelled"])
check("another post's stats are not found", c.get("/api/posts/nope/stats", headers=K).status_code, 404)

print(f"\n{len(fails)} failed" if fails else "\nAll API checks passed")
sys.exit(1 if fails else 0)
