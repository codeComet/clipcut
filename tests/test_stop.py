"""Stopping a video: it stops at its next step, keeps finished clips, and can then be deleted or retried.
Nothing is downloaded: the pipeline, queue and saving are replaced by stand-ins."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-stop-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from studio import jobs, creators
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)

jobs.save = lambda job: None
creators.log = lambda *a, **k: None
class End(BaseException): pass
def run_worker(items):
    it = iter(items)
    def get(_quick=False):
        try:
            return next(it)
        except StopIteration:
            raise End()
    jobs._q.get, jobs._q.done = get, (lambda: None)
    try:
        jobs._worker()
    except End:
        pass

def make(status="running"):
    job = {"id": "j1", "user": "u", "kind": "video", "creator": None, "status": status, "stage": "", "progress": 0.2,
           "dir": tempfile.mkdtemp(), "source": {"type": "url", "url": "https://youtu.be/x"},
           "clips": [{"id": "c1", "status": "done"}, {"id": "c2", "status": "rendering"}]}
    jobs._jobs["j1"] = job
    return job

# a running video: Stop takes effect at its next progress update
job = make()
steps = []
def fake_run(j):
    for i in range(100):
        steps.append(i)
        jobs._set(j, progress=0.2 + i / 1000)
        if i == 3:
            jobs.stop("j1")          # pressed while it is working
jobs._run_job = fake_run
run_worker([("job", "j1", None)])
check("a running video stops at its next step", steps[-1] == 4, steps[-1])
check("...and says it was stopped by you", job["status"] == "error" and job["error"] == "Stopped by you.", job.get("error"))
check("finished clips are kept", job["clips"][0]["status"] == "done")
check("clips being made are marked as cut short", job["clips"][1]["status"] == "error")
check("it can be retried afterwards", (jobs.retry("j1") or True) and job["status"] == "queued" and "stopping" not in job)

# stopped while waiting in line: never starts
job = make(status="queued")
jobs.stop("j1")
started = []
jobs._run_job = lambda j: started.append(1)
run_worker([("job", "j1", None)])
check("a waiting video that was stopped never starts", not started and job["status"] == "error")

# a downloader that wraps our Stopped in its own error still counts as stopped
job = make()
def wrapped(j):
    jobs.stop("j1")
    try:
        jobs._set(j, progress=0.3)
    except jobs.Stopped as e:
        raise RuntimeError("DownloadError: " + str(e))
jobs._run_job = wrapped
run_worker([("job", "j1", None)])
check("a stop inside a download still counts as stopped", job["error"] == "Stopped by you.", job.get("error"))

for st in ("done", "error"):
    make(status=st)
    try:
        jobs.stop("j1"); check(f"a {st} video cannot be stopped", False)
    except ValueError:
        check(f"a {st} video cannot be stopped", True)
sys.exit(1 if fails else 0)
