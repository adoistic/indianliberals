import os,re,sys,json
STOP=set("the a an of in on and or to for by with at from is are as it its his her their this that not no".split())
def toks(s):
    return {w for w in re.findall(r"[a-z']+", s.lower()) if w not in STOP and len(w)>2}
rows=[]
for fn in sorted(os.listdir('.')):
    if not fn.endswith('.md'): continue
    t=open(fn,encoding='utf-8').read()
    m=re.match(r'^---\n.*?\n---\n(.*)$',t,re.S)
    if not m: continue
    body=m.group(1)
    secs=re.findall(r'^###\s+(.+?)\s*$\n(?:\*By[^\n]*\*\n)?\n?((?:(?!^###\s).*\n?)*)',body,re.M)
    if len(secs)<3: continue
    tested=hit=0
    for head,prose in secs:
        head=re.sub(r'\(.*?\)','',head)
        h=toks(head)
        if len(h)<2: continue
        prose_head=' '.join(prose.split()[:60])
        if not prose_head.strip(): continue
        tested+=1
        if len(h & toks(prose_head))/len(h) >= 0.5: hit+=1
    if tested>=3:
        rows.append((fn[:-3], tested, hit, round(hit/tested,2)))
bad=[r for r in rows if r[3] < 0.4]
print(f"files analysed: {len(rows)}")
print(f"files where <40% of headings match their prose (likely shifted): {len(bad)}")
json.dump([r[0] for r in bad],open('/private/tmp/claude-501/-Users-siraj-Indian-Liberals-Website/24cd46d5-7613-4c28-b7e6-1415026da729/scratchpad/shifted.json','w'))
for r in bad[:25]: print("   ",r[0],f"match {r[2]}/{r[1]}")
