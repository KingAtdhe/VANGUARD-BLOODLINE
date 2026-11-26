import re,sys,collections
log=sys.argv[1]; thr=float(sys.argv[2]) if len(sys.argv)>2 else 1.5
d=collections.OrderedDict()
for l in open(log):
    if not l.startswith("KEYED "): continue
    p=l.split(); name=p[1]; f=int(p[2])
    nums=re.findall(r"\(([-\d. ]+)\)",l)
    pts=[tuple(map(float,n.split())) for n in nums[:4]]
    head=float(re.search(r"head ([\d.]+)",l).group(1))
    d.setdefault(name,[]).append((f,pts,head))
for name,fr in d.items():
    runs=[];cur=[]
    for a,b in zip(fr,fr[1:]):
        m=max(sum((x-y)**2 for x,y in zip(p,q))**.5 for p,q in zip(a[1],b[1]))*100
        m=max(m,abs(a[2]-b[2])*100)
        if m<=thr: cur.append(b[0])
        else:
            if len(cur)>=4: runs.append((cur[0],cur[-1]))
            cur=[]
    if len(cur)>=4: runs.append((cur[0],cur[-1]))
    print(name.replace("KAIRO_",""), len(fr), "still(<=%.1fcm):"%thr, runs)
