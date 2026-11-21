"""Captions are English even when the language was never reported (uploads, live recordings, YouTube videos
without a transcript): non-English speech is spotted from the words and translated. The AI is a stand-in."""
import os, sys, tempfile
os.environ["CLIPCUT_DATA"] = tempfile.mkdtemp(prefix="pc-lang-"); os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
from studio import brain
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n + (f"  {x}" if x and not ok else "")); ok or fails.append(n)
def ws(text):
    return [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3} for i, w in enumerate(text.split())]

samples = {
    "English": ("Oh my god bro, look at that guy. He just jumped off the roof and I can't believe it, what is he doing", True),
    "English slang": ("Yo chat, we going in, nah nah he's cooked, wait wait look, bro got clipped by the cop car", True),
    "Spanish": ("No puede ser, mira lo que hizo este tipo, se tiró del techo y no lo puedo creer, qué está haciendo", False),
    "German": ("Was macht der denn da, guck mal, der ist einfach vom Dach gesprungen, ich kann das nicht glauben", False),
    "Portuguese": ("Mano olha isso, o cara pulou do telhado, eu não acredito, o que ele está fazendo, que loucura", False),
    "French": ("Regarde ce mec, il a sauté du toit, je ne peux pas le croire, qu'est-ce qu'il fait là, c'est fou", False),
}
for name, (text, english) in samples.items():
    check(f"{name} speech is {'kept' if english else 'spotted as not English'}", brain.looks_english(ws(text)) == english)
check("a few words are left alone", brain.looks_english(ws("Hola amigo qué tal")))

asked = []
def fake_ai(prompt, schema, purpose=""):
    asked.append(purpose)
    n = int(prompt.rsplit("(", 1)[1].split(")")[0])
    return (["Translated line"] * n if purpose == "Caption translation" else [l.split(": ", 1)[1] for l in prompt.splitlines()[-n:]]), "m", {}
brain.ask_ai = fake_ai
out = brain.english_captions(ws(samples["Spanish"][0]), "")
check("Spanish with no language given is translated", asked[-1] == "Caption translation" and "Translated" in out[0]["w"], asked)
out = brain.english_captions(ws(samples["English"][0]), "")
check("English with no language given is not translated", asked[-1] == "Caption wording fix", asked)
brain.english_captions(ws(samples["Spanish"][0]), "es")
check("a language YouTube reported still decides", asked[-1] == "Caption translation")

sys.exit(1 if fails else 0)
