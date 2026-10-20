"""Shadow run: call Jev on 3 fixture postings and append receipts. Changes no rankings.

Usage (TYPESAFE_API_KEY must be set in your own shell):
    PYTHONPATH=src python scripts/jev_shadow.py
"""
import json, os, sys, time
from job_app_finder.jev_fit import decide, judge

SUMMARY = "Student software engineer. Python, SQL, distributed systems. Seeking backend internships."
CASES = {
    "obvious": ("Backend Software Engineering Intern", "Acme", "Build Python services and SQL pipelines. Open to students."),
    "ambiguous": ("Software Engineer II", "Globex", "Backend work in Go or Python. 1-3 years preferred; strong new grads considered."),
    "must_escalate": ("Staff Security Engineer", "Initech", "Requires active TS/SCI clearance and 10+ years experience."),
}

if not os.environ.get("TYPESAFE_API_KEY"):
    sys.exit("TYPESAFE_API_KEY not set; nothing was called.")
with open("data/jev_receipts.jsonl", "a") as f:
    for name, (t, c, d) in CASES.items():
        r = judge(SUMMARY, t, c, d)
        dec = decide(r)
        f.write(json.dumps({"ts": time.time(), "case": name, "model": r.get("model"),
                            "route": dec.route, "fit": dec.fit, "answers": dec.answers,
                            "usage": dec.usage, "latency_s": r["_latency_s"]}) + "\n")
        print(name, "->", dec.route, dec.fit, r["_latency_s"], "s")
