"""Run: python test_hollownet.py   (starts its own server on port 8765)"""
import json, os, subprocess, sys, time, urllib.request as u, urllib.error
import server

fails = []
def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok: fails.append(name)

# 1) Simulation invariants over 3000 ticks (about 100 simulated minutes)
for _ in range(3000): server.tick()
check("sim stays in valid ranges for 3000 ticks", server.selfcheck() == [])
check("ledger chain valid and capped", server.verify() == -1 and len(server.ledger) <= server.CAP)
check("50 neighborhoods", len(server.nodes) == 50)


# 3) Echo bot (offline mode)
import bot
os.environ.pop("ANTHROPIC_API_KEY", None)
s = server.snap()
for q, key in [("what is this app?", "HOLLOWNET"), ("Level 8 Block 2", "Level 8"), ("level 3", "Level 3"), ("which level is worst", "Worst"),
               ("how many cases are hidden", "hidden"), ("is any water unsafe", "unsafe"), ("what's going wrong right now", "Right now"),
               ("show me a demo", "Quick demo"), ("tell me about tampering", "chain"), ("L99N9", "doesn't exist"), ("asdkjh qwe", "not sure")]:
    r = bot.ask(q, [], s)
    check(f"bot answers: {q!r}", key.lower() in r["reply"].lower() and r["mode"] == "offline" and r["suggestions"])

# 2) HTTP hardening
env = dict(os.environ, PORT="8765")
p = subprocess.Popen([sys.executable, "server.py"], env=env, stdout=subprocess.DEVNULL); time.sleep(1.5)
URL = "http://127.0.0.1:8765"
def call(path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    try:
        r = u.urlopen(u.Request(URL + path, data=data, headers={"Content-Type": "application/json"}), timeout=5)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
try:
    ok = lambda r: r[0] == 200
    bad = lambda r: r[0] == 400 and "error" in r[1]
    check("state loads, health empty", ok(call("/api/state")) and call("/api/state")[1]["health"] == [])
    check("unknown place rejected", bad(call("/api/checkin", {"name": "a", "node": "L99N9"})))
    check("empty name rejected", bad(call("/api/checkin", {"name": "  ", "node": "L1N1"})))
    check("malformed JSON rejected", bad(call("/api/net", raw=b"{nope")))
    check("JSON array body rejected", bad(call("/api/net", raw=b"[1]")))
    check("oversized body rejected", bad(call("/api/message", raw=b"x" * 20000)))
    check("negative space rejected", bad(call("/api/space", {"node": "L1N1", "m2": -5, "kind": "offer"})))
    check("sleep 99h rejected", bad(call("/api/wellness", {"node": "L1N1", "sleep": 99, "mood": 3})))
    check("mood 9 rejected", bad(call("/api/wellness", {"node": "L1N1", "sleep": 7, "mood": 9})))
    check("NaN population rejected", bad(call("/api/migrate?pop=nan")))
    check("huge population rejected", bad(call("/api/migrate?pop=1e30")))
    check("text population rejected", bad(call("/api/migrate?pop=abc")))
    check("farm negative area rejected", bad(call("/api/farm?node=L1N1&m2=-1&people=5")))
    check("clinic needs a symptom", bad(call("/api/clinic", {"symptoms": [], "node": "L1N1"})))
    check("same-place message rejected", bad(call("/api/message", {"src": "L1N1", "dst": "L1N1", "text": "hi"})))
    check("same-place route rejected", bad(call("/api/route?a=L1N1&b=L1N1")))
    check("valid migrate works", ok(call("/api/migrate?pop=500")))
    check("valid clinic works", call("/api/clinic", {"symptoms": ["cough", "blood"], "node": "L3N3"})[1]["triage"] == "URGENT")
    st, r = call("/api/message", {"src": "L2N1", "dst": "L2N3", "text": "hello"}); check("message via network", ok((st, r)) and r["hops"] == 1)
    call("/api/net", {}); st, r = call("/api/message", {"src": "L2N1", "dst": "L2N3", "text": "hello"})
    check("mesh hops when network off (or clean failure)", ok((st, r)) and (r["delivered"] is False or r["hops"] >= 2))
    call("/api/ledger/tamper", {}); check("tamper detected", call("/api/state")[1]["ledger_bad"] >= 0)
    call("/api/ledger/reset", {}); check("reset repairs chain", call("/api/state")[1]["ledger_bad"] == -1)
    st, r = call("/api/chat", {"message": "which level is worst?"}); check("chat endpoint works", ok((st, r)) and "reply" in r)
    check("chat rejects empty", bad(call("/api/chat", {"message": "  "})))
    check("chat survives junk history", ok(call("/api/chat", {"message": "hi", "history": [1, {"role": "x"}, "a"]})))
    check("server still alive after abuse", ok(call("/api/state")))
finally:
    p.terminate()
print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
