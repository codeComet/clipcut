"""Moving a clip's start or end on a long video. Only a piece around each clip is downloaded, so moving it
outside that piece must fetch a new piece (not be ignored), and live clips must say why they cannot move.
Nothing is downloaded: the queue and saving are replaced by stand-ins, and the sound is made up."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-retrim-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
import numpy as np
from studio import jobs
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)

queued = []
jobs.save = lambda job: None
jobs._q.put = lambda item, **k: queued.append(item)

def make(kind="video", typ="url"):
    clip = {"id": "c1", "start": 110.0, "end": 140.0, "src": "/nowhere.mp4", "src_offset": 100.0, "src_end": 150.0,
            "status": "done", "style": jobs.DEFAULTS["style"], "layout": jobs.DEFAULTS["layout"]}
    job = {"id": "j1", "kind": kind, "source": {"type": typ, "url": "https://example.com/v"}, "duration": 7200,
           "clips": [clip], "options": {"quality": 720}}
    jobs._jobs["j1"] = job
    return clip

clip = make()
jobs.request_render("j1", "c1", {"start": 80, "end": 140})
check("a long video's clip can move earlier than its saved piece", clip["start"] == 80, clip["start"])
check("...and a new piece is fetched for it", clip.get("refetch") is True)
check("...and the clip is queued to be made again", queued[-1] == ("clip", "j1", "c1"))

clip = make()
jobs.request_render("j1", "c1", {"start": 105, "end": 145})
check("moving inside the saved piece needs no new download", "refetch" not in clip and clip["start"] == 105)

clip = make()
jobs.request_render("j1", "c1", {"start": 7150, "end": 7250})
check("the end never goes past the end of the video", clip["end"] == 7200, clip["end"])

clip = make(kind="live")
try:
    jobs.request_render("j1", "c1", {"start": 80, "end": 140})
    check("a live clip outside its saved piece is refused with a reason", False)
except ValueError as e:
    check("a live clip outside its saved piece is refused with a reason", "100 to 150" in str(e), str(e))
check("...and is left as it was", clip["start"] == 110 and clip["status"] == "done")

# where a new piece really begins, found by matching sound with the old piece
rng = np.random.default_rng(1)
full = (rng.standard_normal(200 * 16000) * 3000).astype(np.int16)
cut = lambda a, b: full[int(a * 16000): int(b * 16000)]
old = cut(100, 150)
got = jobs.piece_offset(old, 100.0, cut(91.3, 160), 90.0)    # asked for 90, the keyframe gave 91.3
check("a new piece that starts earlier is placed by its sound", abs(got - 91.3) < 0.05, got)
got = jobs.piece_offset(old, 100.0, cut(120.6, 170), 120.0)
check("a new piece that starts later is placed by its sound", abs(got - 120.6) < 0.05, got)

sys.exit(1 if fails else 0)
