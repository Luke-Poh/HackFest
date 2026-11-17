"""Echo - HOLLOWNET's guide bot.
Offline by default (rules + live data). If ANTHROPIC_API_KEY is set, uses Claude with the same live data."""
import json, os, re, urllib.request

MODEL = os.environ.get("HOLLOWNET_MODEL", "claude-sonnet-5-5")


def enabled(): return bool(os.environ.get("ANTHROPIC_API_KEY"))


def P(i):
    m = re.match(r"L(\d+)N(\d+)", i)
    return f"Level {m[1]} · Block {m[2]}"


# (name, regex, tab, explanation)
G = [
    ("intro", r"what is (this|hollownet|the hollow|the app)|what does this (app )?do|directorate|the hollow\b|story|purpose|2087|explain (this|everything|the app)", "home",
     "**HOLLOWNET** is a control room for a made-up world. It's 2087, the surface is unlivable, and 2 billion people live underground in **the Hollow**. A government called **the Directorate** controls the air, the network and movement. This app watches a simulated Hollow and helps with problems like blackouts, bad water, hidden sickness and getting back to the surface."),
    ("tour", r"demo|tour|walk me|get started|where do i (start|begin)|how do i use|pitch|present", "home",
     "Quick demo:\n1. **Home**: click a map square.\n2. **Power**: see blackout warnings.\n3. Press the red **Simulate network shutdown** button, then open **Stay Connected** and send a message. It still arrives by hopping between neighbors.\n4. **Health & Food**: compare real vs official sickness.\n5. **The Surface**: click Simulate tampering and watch the chain break."),
    ("sim", r"simulat(ion|ed)|fake|made.?up|real data|realistic|where does (the )?data", None,
     "All numbers come from a simulation in server.py that updates every 2 seconds. Deeper levels drift toward worse power, heat, water and sickness, with random events like floods and surges. Nothing is real data, so say that in your pitch: the code is real, the world is pretend."),
    ("blackout", r"blackout|power cut|early warning|predict|lights", "power",
     "**Blackout early warning** (Power tab): it watches how fast each neighborhood's power use is climbing. If it's heading toward 97%, it predicts about how many minutes are left, so people get warned before the lights go out."),
    ("fair", r"fair|unfair|share|short.?changed|ration|ration", "power",
     "**Fair share** (Power tab): compares what each level *needs* (people, depth, heat) with what a government that favors the upper levels would give it. 'Short-changed' means the level gets noticeably less than it should."),
    ("cool", r"\bhot\b|cool|temperature|\bfans?\b|heat", "power",
     "**Cooling monitor** (Power tab): shows which levels are too hot and roughly how many extra fan units they need, so repair crews go where it matters most."),
    ("water", r"water|\btaps?\b|drink|contaminat", "water",
     "**Water watch** (Water & Tunnels tab): sensors test the water everywhere. If it's contaminated, that tap is locked so nobody drinks it."),
    ("flood", r"flood|tunnel|route|sewage|path", "water",
     "**Tunnel safety** (Water & Tunnels tab): lists flooded sections. Pick two places and it finds a route that avoids the flooding, or tells you you're cut off."),
    ("mesh", r"mesh|message|network|chat|shut.?down|relay|\bhops?\b", "comms",
     "**Mesh chat** (Stay Connected tab): normally messages go through the government network, which can read them. If the network is shut down, messages hop neighbor to neighbor instead, like passing a note down a row of people. A blackout can break the chain."),
    ("checkin", r"check.?in|family|relatives|\bsafe\b", "comms",
     "**Family check-in** (Stay Connected tab): after a blackout, families on different levels can't reach each other. Tap 'I'm safe' or 'I need help' and everyone can see it."),
    ("space", r"\bspace\b|\broom\b|crowd|overcrowd", "comms",
     "**Share space** (Stay Connected tab): people with spare floor space offer it, people who need space request it, and the app matches each request to the closest offer that's big enough."),
    ("outbreak", r"outbreak|sick|lung|official|hidden|cases|illness", "health",
     "**Real vs official sickness** (Health & Food tab): residents' reports show the real number of lung-sickness cases. The 'official' number is lower, and the gap is what's being hidden."),
    ("dispatch", r"medicine|\bkits?\b|dispatch|supply", "health",
     "**Medicine dispatch** (Health & Food tab): splits 1,000 medicine kits across levels, giving more to places with the most hidden cases."),
    ("clinic", r"clinic|symptom|triage|doctor", "health",
     "**Symptom check** (Health & Food tab): tick what you feel and get a triage level: rest at home, request a medicine kit, or see a clinic urgently."),
    ("wellness", r"sleep|mood|wellness|light therapy|sunlight", "health",
     "**Sleep & mood tracker** (Health & Food tab): living without sunlight affects sleep and mood. Log how you feel and it suggests a light-therapy session if you're sleeping badly or feeling low."),
    ("farm", r"farm|\bgrow|crop|\bfood\b", "health",
     "**Grow your own food** (Health & Food tab): enter your growing space and group size to see what percent of daily calories you could grow, and how many days of stored food you'd have if cut off."),
    ("ledger", r"ledger|tamper|hash|chain|surface safe|proof|blockchain", "surf",
     "**Tamper-proof surface data** (The Surface tab): each sensor reading is locked to the one before it, like links in a chain. Change any old reading and every lock after it stops matching, so tampering is detected."),
    ("ascent", r"\bsuits?\b|dome|outpost|ascent|go first|first wave", "surf",
     "**Ascent planner** (The Surface tab): scores suits, domes and sealed outposts on cost, safety and capacity, and suggests the healthiest neighborhoods as the first group to go."),
    ("migration", r"migrat|move everyone|how long|years|simulate button", "surf",
     "**Migration simulator** (The Surface tab): enter how many millions want to go up and it estimates how many years the move takes if capacity grows each month."),
]
GUIDE_TEXT = "\n".join(f"- {t}" for *_, t in G)


def live(n, s):
    N = s["nodes"]
    if n == "blackout":
        b = [x for x in N if x["black"]]; w = [x for x in N if x["warn"]]
        return f"Right now: {len(b)} blackout(s) and {len(w)} warning(s)" + (f", e.g. {P(b[0]['id'])}." if b else ".")
    if n == "water":
        u = [x for x in N if x["unsafe"]]
        return f"Right now: {len(u)} unsafe tap(s)" + (f", e.g. {P(u[0]['id'])}." if u else ".")
    if n == "flood":
        f = [x for x in N if x["flood"]]
        return f"Right now: {len(f)} flooded area(s)" + (f", e.g. {P(f[0]['id'])}." if f else ".")
    if n == "outbreak":
        real = sum(l["ill"] for l in s["levels"]); off = sum(l["off"] for l in s["levels"])
        return f"Right now: {real} real cases vs {off} official, so {real - off} are hidden."
    if n == "cool":
        c = s["cooling"]
        return f"Hottest right now: Level {c[0]['lvl']} at {c[0]['temp']}°C." if c else "All levels are at a safe temperature right now."
    if n == "ledger":
        return "The chain is intact." if s["ledger_bad"] < 0 else f"Tampering is detected at reading #{s['ledger_bad']}."
    if n == "mesh":
        return "The government network is ON, so messages go through it (and can be read)." if s["net"] else "The government network is SHUT DOWN, so messages hop neighbor to neighbor."
    if n == "fair":
        w = max(s["fair"], key=lambda f: f["gap"])
        return f"Most short-changed right now: Level {w['lvl']} (should get {w['fair']}%, would get {w['directorate']}%)."
    return ""


def summary(s):
    N = s["nodes"]; c = lambda k: sum(1 for x in N if x["sev"] == k)
    return f"{c('green')} OK, {c('amber')} warnings, {c('red')} emergencies. Unsafe taps: {sum(x['unsafe'] for x in N)}. Flooded: {sum(x['flood'] for x in N)}."


def data(low, s):
    N = s["nodes"]
    m = re.search(r"(?:level|lvl|l)\s*(\d+)\s*[,·\-]?\s*(?:block|blk|b|n)\s*(\d+)", low)
    if m:
        x = next((n for n in N if n["id"] == f"L{m[1]}N{m[2]}"), None)
        if not x: return "That place doesn't exist. Levels go from 1 to 10 and blocks from 1 to 5.", "home"
        st = {"green": "all OK", "amber": "a warning", "red": "an emergency"}[x["sev"]]
        return (f"**{P(x['id'])}** ({x['pop']:,} people): {st}. Power use {x['power']}%{' (BLACKOUT)' if x['black'] else ''}, {x['temp']}°C, "
                f"water {'UNSAFE' if x['unsafe'] else 'safe'}, {x['food']} days of food, {x['ill']} sick{', tunnel flooded' if x['flood'] else ''}."), "home"
    m = re.search(r"(?:level|lvl)\s*(\d+)", low)
    if m and 1 <= int(m[1]) <= 10:
        lv = int(m[1]); g = [x for x in N if x["lvl"] == lv]; r = sum(x["sev"] == "red" for x in g); a = sum(x["sev"] == "amber" for x in g)
        L, f = s["levels"][lv - 1], s["fair"][lv - 1]
        return (f"**Level {lv}**: {r} emergency, {a} warning, {5 - r - a} OK blocks. Average {L['temp']}°C. {L['ill']} real sick vs {L['off']} official. "
                f"It should get {f['fair']}% of power but would get {f['directorate']}%."), "home"
    if re.search(r"worst|hardest hit|most (dangerous|affected)|which level|safest|best level", low):
        sc = {l: sum({"red": 2, "amber": 1}.get(x["sev"], 0) for x in N if x["lvl"] == l) for l in range(1, 11)}
        w, b = max(sc, key=lambda l: (sc[l], l)), min(sc, key=lambda l: (sc[l], l))
        return f"Worst off right now: **Level {w}** (problem score {sc[w]}). Safest: **Level {b}** (score {sc[b]}). Deeper levels usually do worse.", "home"
    if re.search(r"wrong|right now|happening|status|summary|problems?|emergenc|alerts?|overview|how bad|current", low):
        top = "\n".join(f"• {P(a[1])}: {a[2]}" for a in sorted(s["alerts"], key=lambda a: a[0] != "red")[:3])
        return f"**Right now:** {summary(s)}" + (f"\nTop issues:\n{top}" if top else "\nEverything looks calm."), "home"
    return None


SUG = {None: ["What is this app?", "What's going wrong right now?", "Which level is worst?", "Show me a demo"],
       "home": ["Which level is worst?", "How do I use the map?", "Show me a demo"],
       "power": ["Is power shared fairly?", "Where is it too hot?", "What's going wrong right now?"],
       "water": ["Is any water unsafe?", "Are any tunnels flooded?", "What is mesh chat?"],
       "comms": ["How does mesh chat work?", "What is family check-in?", "How do I share space?"],
       "health": ["How many cases are hidden?", "Where should medicine go?", "How do I grow food?"],
       "surf": ["What is the ledger?", "How does tampering get caught?", "How long would moving take?"]}


def llm(msg, hist, s):
    ctx = f"Overall: {summary(s)} Network: {'ON' if s['net'] else 'SHUT DOWN'}. " + live("outbreak", s) + " " + live("ledger", s) + "\nTop alerts: " + "; ".join(f"{P(a[1])} {a[2]}" for a in s["alerts"][:8])
    ctx += "\nLevels (temp, real sick, official): " + "; ".join(f"L{l['lvl']} {l['temp']}C {l['ill']}/{l['off']}" for l in s["levels"])
    sysm = ("You are Echo, the friendly guide inside HOLLOWNET, a hackathon demo for the 'Life Underground' theme. Explain things to complete beginners in plain, short language (under 110 words). "
            "Use only the app guide and live data below. If unsure, say so and point to the right tab. Never invent numbers. You may use **bold**.\n\nAPP GUIDE:\n" + GUIDE_TEXT + "\n\nLIVE DATA:\n" + ctx)
    h = [m for m in hist if m["role"] in ("user", "assistant")]
    while h and h[0]["role"] != "user": h.pop(0)
    body = json.dumps({"model": MODEL, "max_tokens": 400, "system": sysm, "messages": h + [{"role": "user", "content": msg}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body, {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r: d = json.load(r)
    out = "".join(c.get("text", "") for c in d["content"] if c.get("type") == "text").strip()
    if not out: raise ValueError("empty")
    return out


def ask(msg, hist, s):
    low = msg.lower()
    if enabled():
        try:
            tab = next((t for n, rx, t, _ in G if t and re.search(rx, low)), None)
            return dict(reply=llm(msg, hist, s), tab=tab, suggestions=SUG[tab], mode="ai")
        except Exception:
            pass
    if re.match(r"\s*(hi|hello|hey|yo|sup)\b", low): return dict(reply="Hi! I'm **Echo**. Ask me about anything you see in the app, or about the live numbers.", tab=None, suggestions=SUG[None], mode="offline")
    if re.search(r"thank|thx|cool, thanks", low): return dict(reply="You're welcome! Ask me anything else.", tab=None, suggestions=SUG[None], mode="offline")
    d = data(low, s)
    if d: return dict(reply=d[0], tab=d[1], suggestions=SUG[d[1]], mode="offline")
    for n, rx, tab, text in G:
        if re.search(rx, low):
            lv = live(n, s)
            return dict(reply=text + (f"\n\n📊 {lv}" if lv else ""), tab=tab, suggestions=SUG[tab], mode="offline")
    return dict(reply="I'm not sure I got that. I can explain any tab, answer questions about the live data (try 'Level 8 Block 2' or 'which level is worst'), or give you a demo walkthrough.", tab=None, suggestions=SUG[None], mode="offline")
