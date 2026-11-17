#!/usr/bin/env python3
"""HOLLOWNET - one platform for the Hollow. Stdlib only. Run: python3 server.py  -> http://localhost:8000"""
import json, random, time, hashlib, threading, os, math
import bot
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import deque

L, N, LOCK, CAP = 10, 5, threading.Lock(), 200
nodes = {}
for l in range(1, L + 1):
    for n in range(1, N + 1):
        i = f"L{l}N{n}"
        nodes[i] = dict(id=i, lvl=l, n=n, pop=random.randint(8000, 12000) * (1 + l // 4), power=55 + l * 2.5, hist=[],
                        temp=22 + l * 1.8, water=0.4 * l, air=95 - l * 2.2, food=14 - l * 0.6, ill=l * 3.0,
                        flood=False, black=0)
net = {"on": True}
msgs, checkins, wellness, ledger = [], {}, [], []
space = {"offers": [{"node": "L2N3", "m2": 40}, {"node": "L6N1", "m2": 25}],
         "requests": [{"node": "L7N2", "m2": 20}, {"node": "L9N5", "m2": 30}]}
tickn = [0]


class Bad(Exception): pass


SYM = ("cough", "fever", "breathless", "blood", "fatigue")


def node(v):
    if not isinstance(v, str) or v not in nodes: raise Bad("Please pick a place from the list (Level 1-10, Block 1-5).")
    return v


def num(v, lo, hi, name):
    try: f = float(v)
    except (TypeError, ValueError): raise Bad(f"{name} must be a number.")
    if math.isnan(f) or math.isinf(f) or not lo <= f <= hi: raise Bad(f"{name} must be between {lo:g} and {hi:g}.")
    return f


def txt(v, n, name):
    if not isinstance(v, str) or not v.strip(): raise Bad(f"{name} can't be empty.")
    return v.strip()[:n]


def trim(a, n=CAP): del a[:-n]


def selfcheck():
    bad = []
    if len(nodes) != L * N: bad.append("wrong number of neighborhoods")
    for x in nodes.values():
        for k, lo, hi in (("power", 0, 100), ("temp", 10, 60), ("air", 0, 100), ("food", 0, 20), ("ill", 0, 200), ("water", 0, 1e4)):
            if not lo <= x[k] <= hi: bad.append(f"{x['id']} {k} out of range")
    return bad


def adj(i):
    x = nodes[i]; r = []
    for dl, dn in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        j = f"L{x['lvl'] + dl}N{x['n'] + dn}"
        if j in nodes: r.append(j)
    return r


def bfs(a, b, ok):
    if a not in nodes or b not in nodes or not ok(a) or not ok(b): return None
    prev, q = {a: None}, deque([a])
    while q:
        c = q.popleft()
        if c == b:
            p = []
            while c: p.append(c); c = prev[c]
            return p[::-1]
        for j in adj(c):
            if j not in prev and ok(j): prev[j] = c; q.append(j)
    return None


def block(data):
    prev = ledger[-1]["hash"] if ledger else "0" * 64
    h = hashlib.sha256((prev + json.dumps(data, sort_keys=True)).encode()).hexdigest()
    ledger.append({"i": ledger[-1]["i"] + 1 if ledger else 0, "data": data, "prev": prev, "hash": h})
    if len(ledger) > CAP: del ledger[0]


def verify():
    prev = ledger[0]["prev"] if ledger else "0" * 64
    for b in ledger:
        h = hashlib.sha256((prev + json.dumps(b["data"], sort_keys=True)).encode()).hexdigest()
        if b["prev"] != prev or b["hash"] != h: return b["i"]
        prev = b["hash"]
    return -1


def tick():
    tickn[0] += 1
    for x in nodes.values():
        d = x["lvl"]; g = random.gauss
        if x["black"] > 0:
            x["black"] -= 1
            if x["black"] == 0: x["power"], x["hist"] = 65, []
        else:
            x["power"] += (60 + d * 2.5 - x["power"]) * 0.05 + g(0.4 + d * 0.05, 2.2)
            if random.random() < 0.01 * d: x["power"] += 15
            if x["power"] >= 100: x["power"], x["black"] = 100, 4
        x["hist"] = (x["hist"] + [x["power"]])[-6:]
        x["temp"] += (22 + d * 1.8 + (8 if x["black"] else 0) - x["temp"]) * 0.1 + g(0, 0.2)
        x["water"] = max(0, x["water"] + (0.4 * d - x["water"]) * 0.1 + g(0, 0.3) + (6 if random.random() < 0.02 * d else 0))
        x["air"] = min(100, x["air"] + (95 - d * 2.2 - x["air"]) * 0.1 + g(0, 0.5))
        if not x["flood"] and random.random() < 0.004 * d: x["flood"] = True
        elif x["flood"] and random.random() < 0.05: x["flood"] = False
        tgt = 14 - 0.6 * d
        x["food"] = max(0, x["food"] - 0.05) if x["flood"] else x["food"] + (tgt - x["food"]) * 0.02
        x["ill"] = max(0, min(200, x["ill"] + g(0.1 * (d - 3), 1)))
        x["temp"] = max(10, min(60, x["temp"])); x["food"] = max(0, min(20, x["food"])); x["power"] = max(0, min(100, x["power"]))
    if tickn[0] % 5 == 0:
        block({"t": int(time.time()), "pm25": round(random.gauss(8, 1.5), 1), "o2": round(random.gauss(20.8, .1), 2),
               "rad_uSv": round(random.gauss(0.12, 0.01), 3), "temp_c": round(random.gauss(14, 2), 1), "sensor": "S-%d" % random.randint(1, 4)})


def loop():
    while True:
        time.sleep(2)
        with LOCK: tick()


def pub(x):
    h = x["hist"]; sl = (h[-1] - h[0]) / (len(h) - 1) if len(h) > 1 else 0
    eta = round((97 - x["power"]) / sl) if sl > 0.3 and x["black"] == 0 and x["power"] < 97 else None
    warn = eta is not None and eta <= 12
    unsafe = x["water"] > 5
    sev = "red" if (x["black"] or x["flood"]) else "amber" if (warn or unsafe or x["temp"] > 34 or x["air"] < 70) else "green"
    return dict(id=x["id"], lvl=x["lvl"], n=x["n"], pop=x["pop"], power=round(x["power"], 1), temp=round(x["temp"], 1),
                water=round(x["water"], 1), air=round(x["air"], 1), food=round(x["food"], 1), ill=round(x["ill"]),
                off=int(x["ill"] * 0.4), flood=x["flood"], black=x["black"], warn=warn, eta=eta, unsafe=unsafe, sev=sev)


def snap():
    ns = [pub(x) for x in nodes.values()]
    al = []
    for x in ns:
        if x["black"]: al.append(["red", x["id"], "BLACKOUT in progress"])
        elif x["warn"]: al.append(["amber", x["id"], f"Blackout likely in ~{x['eta']} ticks (load {x['power']}%)"])
        if x["unsafe"]: al.append(["amber", x["id"], f"Unsafe water ({x['water']} ppm) - tap locked"])
        if x["flood"]: al.append(["red", x["id"], "Tunnel flooded - neighborhood cut off"])
        if x["food"] < 4: al.append(["red", x["id"], f"Only {x['food']} days of food left"])
    # fair share (problem 2): need-weighted vs Directorate split favouring upper levels
    S = sum(x["pop"] for x in ns) * 0.8
    need = {x["id"]: x["pop"] * (1 + .08 * (x["lvl"] - 1)) * (1 + max(0, x["temp"] - 30) * .03) for x in ns}
    dirw = {x["id"]: x["pop"] * max(.2, 1.6 - .1 * x["lvl"] * 1.2) for x in ns}
    tn, td = sum(need.values()), sum(dirw.values())
    fair = []
    for l in range(1, L + 1):
        ids = [x["id"] for x in ns if x["lvl"] == l]
        f, d = sum(need[i] for i in ids) / tn * 100, sum(dirw[i] for i in ids) / td * 100
        fair.append(dict(lvl=l, fair=round(f, 1), directorate=round(d, 1), gap=round(f - d, 1)))
    lv = []
    for l in range(1, L + 1):
        g = [x for x in ns if x["lvl"] == l]
        lv.append(dict(lvl=l, temp=round(sum(x["temp"] for x in g) / N, 1), ill=sum(x["ill"] for x in g), off=sum(x["off"] for x in g),
                       fans=max(0, round((sum(x["temp"] for x in g) / N - 30) * 12))))
    cool = sorted([v for v in lv if v["temp"] > 30], key=lambda v: -v["temp"])
    gaps = {v["lvl"]: max(0, v["ill"] - v["off"]) for v in lv}
    tg = sum(gaps.values()) or 1
    disp = sorted([dict(lvl=l, kits=round(1000 * g / tg)) for l, g in gaps.items()], key=lambda d: -d["kits"])[:5]
    clusters = sorted([x for x in ns if x["ill"] > 40], key=lambda x: -x["ill"])[:5]
    # space matching (problem 6)
    used, match = set(), []
    for r in space["requests"]:
        best = None
        for k, o in enumerate(space["offers"]):
            if k in used or o["m2"] < r["m2"]: continue
            a, b = nodes[o["node"]], nodes[r["node"]]
            dist = abs(a["lvl"] - b["lvl"]) + abs(a["n"] - b["n"])
            if best is None or dist < best[0]: best = (dist, k)
        if best: used.add(best[1]); match.append(dict(request=r["node"], offer=space["offers"][best[1]]["node"], m2=r["m2"], dist=best[0]))
    return dict(tick=tickn[0], net=net["on"], nodes=ns, alerts=al[:40], fair=fair, levels=lv, cooling=cool, dispatch=disp,
                clusters=[dict(id=c["id"], ill=c["ill"], off=c["off"]) for c in clusters], space=space, matches=match,
                checkins=checkins, msgs=msgs[-8:], wellness=wellness[-5:], ledger=ledger[-6:], ledger_len=len(ledger), ledger_bad=verify(), health=selfcheck(), ai=bot.enabled())


def ascent():
    opts = {"Pressure suit": (.2, .85, .01), "Portable dome": (.5, .8, .1), "Sealed outpost": (.8, .95, .4)}
    rows = [dict(option=k, cost=c, safety=s, capacity=cap, score=round(s * .5 + cap * .3 + (1 - c) * .2, 2)) for k, (c, s, cap) in opts.items()]
    ns = [pub(x) for x in nodes.values()]
    first = sorted(ns, key=lambda x: (x["ill"] / x["pop"] * 1000, -x["lvl"]))[:5]
    return dict(options=sorted(rows, key=lambda r: -r["score"]), first_wave=[x["id"] for x in first])


def migrate(pop):
    cap, m, done, series = 0.2, 0, 0, []
    while done < pop and m < 1200:
        done += cap; cap *= 1.04; m += 1
        if m % 12 == 0: series.append(round(min(done, pop) / pop * 100))
    series.append(100)
    return dict(months=m, years=round(m / 12, 1), pct_by_year=series)


CROPS = {"algae": (60, .4), "sweet potato": (25, .3), "soy": (18, .2), "lettuce": (6, .1)}


def farm(node, m2, people):
    need = people * 2000; prod = {c: round(m2 * mix * k) for c, (k, mix) in CROPS.items()}
    tot = sum(prod.values()); x = nodes.get(node)
    return dict(kcal_needed=need, produced=prod, coverage_pct=round(tot / need * 100) if need else 0,
                local_food_days=round(x["food"], 1) if x else None)


def clinic(sym, node):
    w = {"cough": 1, "fever": 2, "breathless": 3, "blood": 4, "fatigue": 1}
    s = sum(w.get(k, 0) for k in sym)
    if node in nodes and s >= 2: nodes[node]["ill"] += 1
    if s >= 4: return dict(score=s, triage="URGENT", advice="Go to nearest clinic or request an escort. Keep upright, avoid exertion.")
    if s >= 2: return dict(score=s, triage="MEDICINE KIT", advice="Request a lung kit via Supply Dispatch. Rest, use filtered air, recheck in 12h.")
    return dict(score=s, triage="SELF-CARE", advice="Hydrate with verified-safe water and rest.")


INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, obj, code=200):
        html = isinstance(obj, bytes)
        b = obj if html else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def run(self, fn):
        try:
            with LOCK: r = fn()
            self.send(r)
        except Bad as e: self.send({"error": str(e)}, 400)
        except (BrokenPipeError, ConnectionError): pass
        except Exception: self.send({"error": "Something went wrong on the server."}, 500)

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.run(lambda: self.get(u.path, q))

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 <= n <= 10000: raise Bad("Request too large.")
            b = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(b, dict): raise ValueError
        except Bad as e: return self.send({"error": str(e)}, 400)
        except ValueError: return self.send({"error": "Bad request."}, 400)
        if urlparse(self.path).path == "/api/chat":
            try:
                msg = txt(b.get("message"), 300, "Message")
                hist = [{"role": m["role"], "content": m["content"][:600]} for m in (b.get("history") if isinstance(b.get("history"), list) else [])[-6:]
                        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
                with LOCK: st = snap()
                return self.send(bot.ask(msg, hist, st))
            except Bad as e: return self.send({"error": str(e)}, 400)
            except (BrokenPipeError, ConnectionError): return
            except Exception: return self.send({"error": "Echo had a hiccup. Try again."}, 500)
        self.run(lambda: self.post(urlparse(self.path).path, b))

    def get(self, p, q):
        if p == "/": return open(INDEX, "rb").read()
        if p == "/api/state": return snap()
        if p == "/api/route":
            a, b = node(q.get("a")), node(q.get("b"))
            if a == b: raise Bad("Pick two different places.")
            path = bfs(a, b, lambda i: not nodes[i]["flood"])
            return dict(path=path, ok=path is not None, blocked=[i for i in (a, b) if nodes[i]["flood"]])
        if p == "/api/ascent": return ascent()
        if p == "/api/migrate": return migrate(num(q.get("pop"), 0.1, 2000, "Population (millions)"))
        if p == "/api/farm":
            return farm(node(q.get("node")), num(q.get("m2"), 1, 1e6, "Growing space"), int(num(q.get("people"), 1, 1e6, "People")))
        raise Bad("Not found.")

    def post(self, p, b):
        if p == "/api/net": net["on"] = not net["on"]; return {"net": net["on"]}
        if p == "/api/message":
            s, d = node(b.get("src")), node(b.get("dst"))
            if s == d: raise Bad("Pick two different places.")
            text = txt(b.get("text"), 200, "Message")
            path = bfs(s, d, lambda i: nodes[i]["black"] == 0)
            if net["on"]: r = dict(via="Directorate network (logged & monitored)", hops=1, delivered=True)
            elif path: r = dict(via="mesh relay", hops=len(path) - 1, path=path, delivered=True)
            else: r = dict(via="no mesh path - a blackout is breaking the chain of relays", delivered=False)
            msgs.append(dict(src=s, dst=d, text=text, **r)); trim(msgs); return r
        if p == "/api/checkin":
            name, n = txt(b.get("name"), 30, "Name"), node(b.get("node"))
            if name not in checkins and len(checkins) >= CAP: raise Bad("The check-in list is full.")
            checkins[name] = dict(node=n, safe=b.get("safe") is True, t=time.strftime("%H:%M:%S")); return {"ok": True}
        if p == "/api/space":
            n, m2, k = node(b.get("node")), num(b.get("m2"), 1, 500, "Space (m2)"), b.get("kind")
            if k not in ("offer", "request"): raise Bad("Choose offer or request.")
            lst = space[k + "s"]
            if len(lst) >= CAP: raise Bad("That list is full.")
            lst.append(dict(node=n, m2=m2)); return {"ok": True}
        if p == "/api/clinic":
            sy = b.get("symptoms"); n = node(b.get("node"))
            sy = [x for x in sy if x in SYM] if isinstance(sy, list) else []
            if not sy: raise Bad("Tick at least one symptom.")
            return clinic(sy, n)
        if p == "/api/wellness":
            n, sl, md = node(b.get("node")), num(b.get("sleep"), 0, 24, "Hours slept"), int(num(b.get("mood"), 1, 5, "Mood"))
            mins = (30 + 3 * nodes[n]["lvl"]) if (sl < 6 or md <= 2) else 0
            wellness.append(dict(node=n, sleep=sl, mood=md, light_min=mins)); trim(wellness)
            return dict(light_min=mins)
        if p == "/api/ledger/tamper":
            if len(ledger) < 3: raise Bad("Wait a few seconds for readings to arrive first.")
            ledger[1]["data"]["pm25"] = 999; return {"ok": True}
        if p == "/api/ledger/reset":
            ledger.clear()
            for _ in range(3): block({"t": int(time.time()), "pm25": 8.0, "o2": 20.8, "rad_uSv": .12, "temp_c": 14, "sensor": "S-1"})
            return {"ok": True}
        raise Bad("Not found.")


if __name__ == "__main__":
    for _ in range(15): tick()
    threading.Thread(target=loop, daemon=True).start()
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", 8000))
    print(f"HOLLOWNET running on http://localhost:{port}  (Ctrl+C to stop)")
    ThreadingHTTPServer((host, port), H).serve_forever()
