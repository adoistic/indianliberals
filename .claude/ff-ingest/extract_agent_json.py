#!/usr/bin/env python3
"""Extract the JSON result object from an async-agent .output JSONL transcript.
Usage: extract_agent_json.py <output_file> <marker_key> <dest.json>
Finds the longest text block containing <marker_key>, pulls the balanced {...}
that contains it, writes clean JSON to dest. Prints a one-line confirmation."""
import json, sys
out, marker, dest = sys.argv[1], sys.argv[2], sys.argv[3]
texts = []
def walk(o):
    if isinstance(o, str):
        if marker in o: texts.append(o)
    elif isinstance(o, dict):
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
for line in open(out, encoding="utf-8"):
    line = line.strip()
    if not line: continue
    try: walk(json.loads(line))
    except json.JSONDecodeError: pass
if not texts:
    print(f"FAIL: no text block with {marker!r} in {out}"); sys.exit(1)
t = max(texts, key=len)
mk = '"' + marker + '"'
idx = t.find(mk)
if idx == -1: idx = t.find(marker)
start = t.rfind('{', 0, idx)
depth = 0; instr = False; esc = False; end = None
for i in range(start, len(t)):
    c = t[i]
    if esc: esc = False; continue
    if c == '\\' and instr: esc = True; continue
    if c == '"': instr = not instr; continue
    if instr: continue
    if c == '{': depth += 1
    elif c == '}':
        depth -= 1
        if depth == 0: end = i + 1; break
try:
    obj = json.loads(t[start:end])
except Exception as e:
    print(f"FAIL: JSON parse error in {out}: {e}"); sys.exit(1)
json.dump(obj, open(dest, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"OK {dest}  keys={list(obj.keys())[:6]}")
