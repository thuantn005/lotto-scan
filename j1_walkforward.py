#!/usr/bin/env python3
"""Leakage-safe walk-forward J1 evaluator for Vietlott Lotto 5/35.
Produces per-origin predictions and an honest exact-J1 audit. This cannot predict randomness; it measures historical performance.
"""
import argparse,csv,json,random,math
from collections import Counter
from pathlib import Path

N=35

def load_draws(path):
    out=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            try:
                j=json.loads(r['result_json']); main=sorted(set(map(int,j['numbers']))); sp=list(map(int,j.get('special_numbers',[])))
                if len(main)==5 and all(1<=x<=35 for x in main) and sp:
                    out.append({'id':str(r.get('draw_id','')).zfill(5),'date':r.get('draw_date',''),'main':main,'special':sp[0]})
            except (ValueError,KeyError,TypeError,json.JSONDecodeError): continue
    out.sort(key=lambda x:int(x['id']))
    return out

def rank_predict(history, window=100, alpha=1.0):
    hist=history[-window:]
    freq=Counter(x for d in hist for x in d['main'])
    # Laplace smoothing; deterministic tie-breaking avoids tuning on future outcomes.
    ranked=sorted(range(1,36),key=lambda x:(-(freq[x]+alpha),x))
    sf=Counter(d['special'] for d in hist)
    special=sorted(range(1,36),key=lambda x:(-(sf[x]+alpha),x))[0]
    return ranked[:5],special

def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',default='data/all.csv');p.add_argument('--out',default='j1_walkforward');p.add_argument('--min-train',type=int,default=100);p.add_argument('--window',type=int,default=100);p.add_argument('--tickets',type=int,default=1);p.add_argument('--seed',type=int,default=535)
    a=p.parse_args(); draws=load_draws(a.csv)
    if len(draws)<=a.min_train: raise SystemExit(f'Not enough valid draws: {len(draws)}')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True); rows=[]; j1=0;main5=0;sp=0;hits=Counter()
    rng=random.Random(a.seed)
    for i in range(a.min_train,len(draws)):
        hist=draws[:i]; target=draws[i]
        pred,special=rank_predict(hist,a.window)
        # Generate fixed number of distinct 5-number tickets from historical frequency ranking.
        tickets=[pred]
        pool=sorted(range(1,36),key=lambda x:(-Counter(n for d in hist[-a.window:] for n in d['main'])[x],x))
        while len(tickets)<a.tickets:
            t=sorted(rng.sample(pool,5))
            if t not in tickets:tickets.append(t)
        best=max(len(set(t)&set(target['main'])) for t in tickets)
        for t in tickets:
            k=len(set(t)&set(target['main']));hits[k]+=1
            if k==5 and special in target['special'] if isinstance(target['special'],list) else k==5 and special==target['special']: j1+=1
        if best==5: main5+=1
        if special==target['special']:sp+=1
        rows.append({'target_draw_id':target['id'],'date':target['date'],'train_draws':i,'tickets':json.dumps(tickets),'predicted_special':special,'actual_main':json.dumps(target['main']),'actual_special':target['special'],'best_main_hits':best,'special_hit':int(special==target['special']),'j1_any_ticket':int(any(set(t)==set(target['main']) for t in tickets) and special==target['special'])})
    with open(out/'j1_walkforward.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    total=len(rows); ticket_count=total*a.tickets
    report=f'''# J1 Walk-forward report\n\n- Valid historical draws: {len(draws)}\n- Evaluated target draws: {total}\n- Training window: last {a.window} draws (minimum initial training {a.min_train})\n- Tickets per target draw: {a.tickets}\n- Main 5/5 ticket occurrences (ticket-level): {hits[5]} / {ticket_count}\n- Exact J1 occurrences across all tickets: {j1} / {ticket_count}\n- Draws with at least one 5/5 main match: {main5} / {total}\n- Special-number hits: {sp} / {total}\n\n## Interpretation\nThis is a retrospective, leakage-safe evaluation, not evidence of future predictability. Exact J1 is extremely rare; zero hits does not establish impossibility, and any observed hit is not proof of a repeatable edge. Compare against random tickets with the same ticket count and evaluate on a future holdout before making claims. The rank model is a transparent baseline, not a guaranteed improvement.\n'''
    (out/'report.md').write_text(report,encoding='utf-8')
    print(report)
if __name__=='__main__':main()
