"""Deleting clips, videos, creators and accounts, bulk actions and the zip download. Runs against the code directly,
with its own empty data folder: nothing outside it is touched."""
import json, os, sys, tempfile, zipfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-del-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from pathlib import Path
import sqlalchemy as sa
from studio import account, auth, config, creators, ctx, db, jobs, posting
db.init()
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x else "")); ok or fails.append(n)
a, _ = auth._create("a@example.com", "A", password_hash="x"); b, _ = auth._create("b@example.com", "B", password_hash="x")
def video(creator=None, n=3, status="done"):
    j = jobs.create({"type": "file", "path": "", "name": "v.mp4"}, {}, enqueue=False, creator=creator)
    (Path(j["dir"]) / "clips").mkdir(parents=True, exist_ok=True)
    for i in range(n):
        cid = f"clip{i+1:02d}"
        for ext in ("mp4", "jpg"): (Path(j["dir"]) / "clips" / f"{cid}.{ext}").write_bytes(b"x" * 1000)
        j["clips"].append({"id": cid, "status": "done", "file": f"{cid}.mp4", "cover": f"{cid}.jpg", "title": "Same title", "start": 0, "end": 10})
    j["status"] = status; jobs.save(j); return j
with ctx.as_user(a.id):
    c = creators.create({"name": "Streamer"})
    j1, j2, j3 = video(), video(c["id"]), video(status="running")
    check("one clip is deleted with its files", account.delete_clip(j1["id"], "clip01") and not (Path(j1["dir"]) / "clips" / "clip01.mp4").exists() and len(jobs.get(j1["id"])["clips"]) == 2)
    z = account.zip_clips([(j1["id"], "clip02"), (j1["id"], "clip03"), (j2["id"], "clip01"), ("nope", "x")])
    names = zipfile.ZipFile(z).namelist()
    check("several clips download as one zip with distinct names", len(names) == 3 and len(set(names)) == 3, str(names))
    def post(j, cid, status, user=a.id):
        p = {"id": f"p{len(posting._posts)}", "user": user, "job": j["id"], "clip": cid, "status": status, "error": None}
        posting._posts.append(p); return p
    jp = video()
    one, two, sent, other = post(jp, "clip01", "approval"), post(jp, "clip02", "scheduled"), post(jp, "clip02", "posted"), post(j2, "clip03", "approval")
    theirs = post(jp, "clip02", "approval", b.id)
    account.delete_clip(jp["id"], "clip01")
    check("deleting a clip takes only its own posts out of the queue", [one["status"], two["status"]] == ["cancelled", "scheduled"], str([one, two]))
    jobs.delete(jp["id"])
    check("deleting a video takes its waiting posts out of the queue", two["status"] == "cancelled" and two["error"])
    check("what is already posted, other videos and other people are left alone", [sent["status"], other["status"], theirs["status"]] == ["posted", "approval", "approval"])
    check("and that is saved", [p["status"] for p in json.loads(posting._FILE.read_text())][:2] == ["cancelled", "cancelled"])
    jb = video(); bulk = post(jb, "clip01", "scheduled"); account.delete_many([jb["id"]], [])
    check("bulk delete does too", bulk["status"] == "cancelled")
    r = account.delete_many([j1["id"], j3["id"]], [(j2["id"], "clip01"), (j1["id"], "clip02")])
    check("bulk delete removes videos and clips, leaves work in progress alone", r == {"videos": 1, "clips": 1, "skipped": 1}, str(r))
    check("the deleted video's folder is gone", not Path(j1["dir"]).exists())
with ctx.as_user(b.id):
    check("someone else cannot delete my clip", not account.delete_clip(j2["id"], "clip02"))
    try:
        account.zip_clips([(j2["id"], "clip02")]); ok = False
    except ValueError: ok = True
    check("someone else cannot download my clips", ok)
    check("someone else cannot delete my creator", account.delete_creator(c["id"]) == {"ok": False})
with ctx.as_user(a.id):
    r = account.delete_creator(c["id"])
    check("deleting a creator removes their videos and folder", r["ok"] and r["videos"] == 1 and not jobs.get(j2["id"]) and not creators.get(c["id"]) and not creators.root(c["id"]).exists(), str(r))
    try:
        account.delete_account(a.id); ok = False
    except account.Busy: ok = True
    check("an account with a video in progress is not deleted", ok)
    j = jobs.get(j3["id"]); j["status"] = "done"; jobs.save(j)
udir = config.user_dir(a.id)
check("the account is deleted", account.delete_account(a.id)["ok"] and auth.get_user(a.id) is None and not udir.exists())
with db.engine.connect() as cn:
    left = {t.name: cn.execute(sa.select(sa.func.count()).select_from(t).where(t.c.user_id == a.id)).scalar() for t in db.meta.sorted_tables if "user_id" in t.c}
check("nothing of theirs is left in the database", not any(left.values()), str(left))
check("the other account is untouched", auth.get_user(b.id) is not None and config.user_dir(b.id).exists())
a2, _ = auth._create("A@example.com", "A again", password_hash="x")
check("the same email can sign up again afterwards, as a new account", a2.id != a.id)
print("ALL PASSED" if not fails else f"{len(fails)} failed")
import shutil; shutil.rmtree(os.environ["CLIPCUT_DATA"], ignore_errors=True)
sys.exit(1 if fails else 0)
