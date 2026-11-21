"""Long videos get more clips (one per 8 minutes, up to 20), so there are spares to queue later.
Short videos keep the number that was asked for."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-count-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from studio import jobs
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)
m = 60
check("a 12-minute video keeps 6", jobs.clips_for(12 * m, 6) == 6)
check("a 30-minute video keeps 6", jobs.clips_for(30 * m, 6) == 6)
check("a 1-hour video gets 8", jobs.clips_for(60 * m, 6) == 8, jobs.clips_for(60 * m, 6))
check("a 2-hour video gets 15", jobs.clips_for(120 * m, 6) == 15, jobs.clips_for(120 * m, 6))
check("an 11-hour stream stops at 20", jobs.clips_for(11 * 60 * m, 6) == 20)
check("asking for more than that is kept", jobs.clips_for(60 * m, 12) == 12)
check("asking for 2 on a short video gives 2", jobs.clips_for(10 * m, 2) == 2)
sys.exit(1 if fails else 0)
