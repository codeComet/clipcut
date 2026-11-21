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

# a video YouTube calls English, where its captions misheard a song into made-up words
song = ">> We're not giving up. >> Okay, Don't draw Myo Harikiru Kyo, Dione Goyo, Helm Tosogan Kojo, Diona Guo Hadrikroke Bure Pajiman Chinchako, Turitara Nagam Tail"
out = brain.english_captions(ws(song), "en", youtube_english=lambda: (_ for _ in ()).throw(AssertionError("asked YouTube again")))
check("nonsense on an 'English' video is not kept as it was heard", asked[-1] == "Caption translation", asked[-1])
check("YouTube's speaker marks (>>) never reach the captions", all(w["w"] != ">>" for w in out))
out = brain.english_captions(ws(samples["English slang"][0] + " >> yeah"), "en")
check("a real English video still only gets tidied", asked[-1] == "Caption wording fix" and all(w["w"] != ">>" for w in out))
brain.ask_ai = lambda prompt, schema, purpose="": ([""] * int(prompt.rsplit("(", 1)[1].split(")")[0]), "m", {})
check("a clip of only a song gets no captions rather than nonsense", brain.translate_caption_words(ws(song)) == [])

sys.exit(1 if fails else 0)
