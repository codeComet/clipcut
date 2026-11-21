"""Downloaded clips are named after their title, never their internal name, and never with characters
that file systems refuse."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-dlname-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from studio import account
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)

n = account.clip_name({"title": "Heist crew escapes cops: by jumping/into the river?!"}, "clip01")
check("the title becomes the file name", n == "Heist crew escapes cops by jumping into the river !", n)
n = account.clip_name({"title": "Kai's 'lucky day' twist, GTA 6 (part 2)."}, "c")
check("apostrophes, commas and brackets stay; no dot at the end", n == "Kai's 'lucky day' twist, GTA 6 (part 2)", n)
check("the big text is used when there is no title", account.clip_name({"hook": "WE GOT A PROBLEM"}, "clip04") == "WE GOT A PROBLEM")
check("nothing usable: the clip's own name", account.clip_name({"title": "?/*"}, "clip04") == "clip04")
check("long titles are cut to 60 characters", len(account.clip_name({"title": "x" * 200}, "c")) == 60)
check("other alphabets are kept", account.clip_name({"title": "GTA 6 الكبير"}, "c") == "GTA 6 الكبير")
sys.exit(1 if fails else 0)
