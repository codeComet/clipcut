"""Is a YouTube channel live: yt-dlp (cookies, proxy) answers first, a failed check is never taken for "offline",
and a stream that was not recorded leaves its reason in the creator's log. Nothing is fetched."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-live-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from studio import creators, ctx, live, media, profiles
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)

URL = "https://www.youtube.com/@Someone"
page = {"html": "<html>consent</html>", "asked": 0}
def get(url, *a, **k):
    page["asked"] += 1
    return "text/html", page["html"].encode()
profiles._get = get
def answer(x):
    def f(url):
        if isinstance(x, Exception):
            raise x
        return x
    profiles._ydl_info = f
def now():
    profiles._live.clear()
    return profiles.live_shared("YouTube", URL)
KEY = URL.lower()

answer({"is_live": True, "id": "abcdefghijk", "title": "GTA 6 2026-11-25 17:57", "concurrent_view_count": 5})
r = now()
check("live", r["live"] and r["embed"] == "abcdefghijk" and r["title"] == "GTA 6" and r["viewers"] == 5, r)
answer({"is_live": False, "id": "x"})
check("a finished stream is offline", not now()["live"] and KEY not in profiles._live_err)
answer(RuntimeError("[youtube:tab] @Someone: The channel is not currently live"))
check("offline is not an error", not now()["live"] and KEY not in profiles._live_err)
check("the plain page was not needed", page["asked"] == 0)
answer(RuntimeError("Sign in to confirm you're not a bot"))
check("a refused check is remembered as failed", not now()["live"] and "not a bot" in profiles._live_err.get(KEY, ""), profiles._live_err)
page["html"] = '<link rel="canonical" href="https://www.youtube.com/watch?v=abcdefghijk">"isLiveNow":true'
r = now()
check("the plain page still finds it live", r["live"] and r["embed"] == "abcdefghijk" and KEY not in profiles._live_err, r)

# the recorder
logged, started = [], []
creators.log = lambda cid, msg: logged.append(msg)
live.start_session = lambda c, url: started.append(url)
live.alerts.notify = lambda *a, **k: None
state = {"res": None}
def resolve(url):
    if state["res"]:
        raise live.NotLive(state["res"])
live.resolve = resolve
C = {"id": "c1", "name": "Someone", "channel": URL, "channels": {"youtube": URL}}
def watch():
    with ctx.as_user("u1"):
        profiles._live.clear()
        live._watch_one(C)

answer(RuntimeError("[youtube:tab] @Someone: The channel is not currently live")); watch()
check("offline logs nothing", not logged and not started, logged)
page["html"] = "consent"; answer(RuntimeError("HTTP Error 429: Too Many Requests")); watch(); watch()
check("a failed check is logged once", len(logged) == 1 and "429" in logged[0] and not started, logged)
answer({"is_live": True, "id": "abcdefghijk", "title": "t"})
logged.clear(); state["res"] = "Requested format is not available"; watch(); watch()
check("live but not playable is logged once", len(logged) == 1 and "Requested format" in logged[0] and not started, logged)
logged.clear(); state["res"] = "This channel is not live right now."; watch()
check("ended since the check: not logged", not logged and not started, logged)
logged.clear(); media.youtube_paused = lambda: True; watch()
check("YouTube paused is logged", len(logged) == 1 and "refusing" in logged[0] and not started, logged)
media.youtube_paused = lambda: False; state["res"] = None
logged.clear(); keep = live.config.MAX_LIVE_PER_USER; live.config.MAX_LIVE_PER_USER = 0; watch()
check("a full server is logged", len(logged) == 1 and "busy" in logged[0] and not started, logged)
live.config.MAX_LIVE_PER_USER = keep
logged.clear(); watch()
check("otherwise it records", started == [URL] and "recording started automatically" in logged[0], logged)
sys.exit(1 if fails else 0)
