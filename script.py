import requests, pdfplumber, io, json, os, datetime as dt
from zoneinfo import ZoneInfo

TOPIC = os.environ["NTFY_TOPIC"]  # your private ntfy.sh topic
HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://official.nba.com/"}
STATE = "state.json"

def fetch_latest():
    t = dt.datetime.now(ZoneInfo("America/New_York")).replace(second=0, microsecond=0)
    t -= dt.timedelta(minutes=t.minute % 15)
    for _ in range(8):  # walk back up to 2 hrs
        u = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{t:%Y-%m-%d_%I_%M%p}.pdf"
        r = requests.get(u, headers=HDR, timeout=20)
        if r.ok and r.content[:4] == b"%PDF":
            return r.content
        t -= dt.timedelta(minutes=15)

def parse(pdf):
    out, matchup, team = {}, "", ""
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        for page in p.pages:
            for tbl in page.extract_tables():
                for r in tbl:
                    r = [(c or "").replace("\n", " ").strip() for c in r]
                    if len(r) < 7 or r[0] == "Game Date":
                        continue
                    matchup = r[2] or matchup   # blank = same as row above
                    team = r[3] or team
                    if "PHI" in matchup and r[4]:
                        out[f"{team}|{r[4]}"] = f"{r[5]} ({r[6]})"
    return out

pdf = fetch_latest()
if pdf:
    new = parse(pdf)
    old = json.load(open(STATE)) if os.path.exists(STATE) else None
    if old is not None:
        msgs  = [f"{k.split('|')[1]}: {v}" for k, v in new.items() if old.get(k) != v]
        msgs += [f"{k.split('|')[1]}: off report" for k in old if k not in new]
        if msgs:
            requests.post(f"https://ntfy.sh/{TOPIC}", data="\n".join(msgs).encode(),
                          headers={"Title": "76ers game injury update"})
    json.dump(new, open(STATE, "w"))
