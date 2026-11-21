"""Retrying a failed video: it goes back in the queue and picks up where it stopped, keeping finished clips.
Nothing is downloaded: the queue and saving are replaced by stand-ins."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-retry-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from studio import jobs
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)

queued = []
jobs.save = lambda job: None
jobs._q.put = lambda item, **k: queued.append(item)

def make(status="error", kind="video", source=None):
    job = {"id": "j1", "user": "u", "kind": kind, "status": status, "error": "ERROR: [youtube] refused",
           "source": source or {"type": "url", "url": "https://youtu.be/x"},
           "clips": [{"id": "c1", "status": "done"}, {"id": "c2", "status": "error", "error": jobs.STOPPED},
                     {"id": "c3", "status": "error", "error": "Could not fetch this part"}]}
    jobs._jobs["j1"] = job
    return job

job = make()
jobs.retry("j1")
check("a failed video goes back in the queue", job["status"] == "queued" and queued[-1] == ("job", "j1", None))
check("...with its error cleared", job["error"] is None)
check("...and picks up where it stopped", job.get("resume") is True)
check("finished clips are kept", job["clips"][0]["status"] == "done")
check("clips cut short by the failure are made again", job["clips"][1]["status"] == "queued")
check("clips that failed on their own stay failed", job["clips"][2]["status"] == "error")

for name, j in [("a video that did not fail", make(status="done")), ("a live recording", make(kind="live")),
                ("an upload whose file is gone", make(source={"type": "file", "path": "/nowhere.mp4"}))]:
    try:
        jobs.retry("j1")
        check(f"{name} cannot be retried", False)
    except ValueError:
        check(f"{name} cannot be retried", j["status"] in ("done", "error"))

sys.exit(1 if fails else 0)
