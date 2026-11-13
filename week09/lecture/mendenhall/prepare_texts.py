"""Build the plain-text corpora used in mendenhall_shakespeare.ipynb.

Students don't need to run this; the notebook reads the finished files in texts/.
Run it again only to rebuild them:

    python prepare_texts.py            # downloads into raw/ (skipped if already there)
    python prepare_texts.py RAW_DIR    # use a different download folder

Sources
-------
* Shakespeare: Folger Shakespeare TEI XML (https://www.folger.edu/explore/shakespeares-works/download/).
  Folger tags every line of every speech as verse or prose, which is what lets us
  split them. Speaker names and stage directions are outside the spoken text and are dropped.
* Bacon: Project Gutenberg #575 (Essays) and #5500 (The Advancement of Learning),
  two of the three works Mendenhall counted.
* Marlowe: Project Gutenberg #779 (Doctor Faustus), #1094 (Tamburlaine, Part 1),
  #901 (The Jew of Malta). Speaker prefixes, stage directions, footnote markers
  and editorial front/back matter are stripped with simple rules, so the
  result is close to, but not exactly, the spoken text.
"""

import re
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "raw"
OUT = HERE / "texts"

# Plays chosen because they contain plenty of both verse and prose
FOLGER_PLAYS = {
    "Ham": "Hamlet",
    "1H4": "Henry IV, Part 1",
    "2H4": "Henry IV, Part 2",
    "H5_": "Henry V",
    "AYL": "As You Like It",
    "Ado": "Much Ado About Nothing",
    "TN_": "Twelfth Night",
    "Wiv": "The Merry Wives of Windsor",
}
GUTENBERG = {
    575: "bacon_essays",
    5500: "bacon_advancement",
    779: "marlowe_faustus",
    1094: "marlowe_tamburlaine1",
    901: "marlowe_jew_of_malta",
}

TEI = "{http://www.tei-c.org/ns/1.0}"


def download(url, dest):
    if not dest.exists():
        print("downloading", url)
        urllib.request.urlretrieve(url, dest)
    return dest


# ---------------------------------------------------------------- Shakespeare
def folger_verse_and_prose(xml_bytes):
    """Return {'verse': text, 'prose': text} for one Folger TEI play."""
    root = ET.fromstring(xml_bytes)
    lines = {"verse": [], "prose": []}
    state = {"mode": None, "line": []}

    def end_line():
        if state["mode"] and state["line"]:
            lines[state["mode"]].append("".join(state["line"]).strip())
        state["line"] = []

    def walk(el):
        tag = el.tag.replace(TEI, "")
        if tag == "rdg":          # skip textual variants; keep the main reading
            return
        if tag == "milestone" and el.get("unit") == "ftln":
            end_line()
            ana = el.get("ana", "")
            # '#short' marks a short (part-)line of verse
            state["mode"] = "prose" if ana == "#prose" else "verse"
        elif tag in ("w", "c", "pc") and el.text:
            state["line"].append(el.text)
        for child in el:
            walk(child)

    for ab in root.iter(TEI + "ab"):   # <ab> holds the spoken text of a speech
        walk(ab)
        end_line()
    return {mode: "\n".join(ls).replace("’", "'") for mode, ls in lines.items()}


def build_shakespeare():
    verse, prose = [], []
    for code, title in FOLGER_PLAYS.items():
        z = download(f"https://flgr.sh/txtfss{code}xml", RAW / f"folger_{code}.zip")
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist()
                        if n.endswith(".xml") and not n.startswith("__MACOSX"))
            parts = folger_verse_and_prose(zf.read(name))
        print(f"  {title}: {len(parts['verse'].split()):>6} verse words, "
              f"{len(parts['prose'].split()):>6} prose words")
        verse.append(parts["verse"])
        prose.append(parts["prose"])
    (OUT / "shakespeare_verse.txt").write_text("\n\n".join(verse))
    (OUT / "shakespeare_prose.txt").write_text("\n\n".join(prose))


# ---------------------------------------------------------------- Gutenberg
def between(text, start_pattern, end_pattern):
    start = re.search(start_pattern, text, re.M).start()
    end = re.search(end_pattern, text[start:], re.M).start() + start
    return text[start:end]


def clean_bacon(text, book):
    if book == "bacon_essays":
        body = between(text, r"^Of Truth\s*$", r"^\*\*\* END OF")
    else:
        body = between(text, r"^FIRST BOOK OF FRANCIS BACON", r"^FOOTNOTES\.")
    body = re.sub(r"\(\d+\)", "", body)                 # numbered section markers
    body = re.sub(r"\[(Picture|Footnote)[^\]]*\]", "", body)
    return body


def clean_marlowe(text):
    # From the first spoken line ("     NAME. ...") to the editor's footnotes
    body = between(text, r"^ {5}[A-Z][A-Z ]+\. ", r"^(FOOTNOTES|Footnotes):")
    kept = []
    for line in body.splitlines():
        if line.startswith(" " * 10):                   # deeply indented = stage direction
            continue
        stripped = line.strip()
        if re.match(r"^(ACT|SCENE|Enter|Exit|Exeunt)\b", stripped) or stripped.startswith("["):
            continue
        stripped = re.sub(r"^[A-Z][A-Z' -]+\.\s+", "", stripped)   # speaker prefix
        stripped = re.sub(r"\[[^\]]*\]", "", stripped)            # footnote refs, [Aside.]
        kept.append(stripped)
    return "\n".join(kept)


def build_gutenberg():
    bacon, marlowe = [], []
    for num, name in GUTENBERG.items():
        f = download(f"https://www.gutenberg.org/cache/epub/{num}/pg{num}.txt",
                     RAW / f"pg{num}.txt")
        text = f.read_text(encoding="utf-8").replace("’", "'")
        if name.startswith("bacon"):
            bacon.append(clean_bacon(text, name))
        else:
            marlowe.append(clean_marlowe(text))
        print(f"  {name}: {len((bacon + marlowe)[-1].split()):>6} words")
    (OUT / "bacon_prose.txt").write_text("\n\n".join(bacon))
    (OUT / "marlowe_plays.txt").write_text("\n\n".join(marlowe))


if __name__ == "__main__":
    RAW.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    print("Shakespeare (Folger):")
    build_shakespeare()
    print("Bacon and Marlowe (Project Gutenberg):")
    build_gutenberg()
