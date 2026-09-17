import asyncio,os,time
import numpy as np,pandas as pd
import aiohttp
from datetime import datetime,timezone

T=os.getenv("TG_TOKEN","")
A=os.getenv("PO_ASSET","eurusd")
B=float(os.getenv("PO_BANK",50))
SK=float(os.getenv("PO_STAKE",0.20))
CF=float(os.getenv("PO_CONF",0.76))
MT=int(os.getenv("PO_MAXT",35))
MD=float(os.getenv("PO_MDX",0.25))
VM=float(os.getenv("PO_VOL",12.0))
TF=int(os.getenv("PO_TF",5))
bank=B;n=0;stop=False;cid="";last=0

def rsi(c,p=14):
    if len(c)<p+1:return 50
    d=np.diff(c[-p-1:])
    g=np.where(d>0,d,0);l=np.where(d<0,-d,0)
    a=float(np.mean(g));b=float(np.mean(l))
    return 100 if not b else 100-100/(1+a/b)
def macd(c):
    s=pd.Series(c)
    return float(s.ewm(span=12).mean().iloc[-1]-s.ewm(span=26).mean().iloc[-1])
def boll(c,p=20,k=2):
    s=pd.Series(c);m=float(s.rolling(p).mean().iloc[-1])
    sd=float(s.rolling(p).std().iloc[-1])
    if not sd:return .5
    return max(0,min(1,(float(c[-1])-(m-k*sd))/(2*k*sd)))
def atr(c,h,l,p=14):
    if len(c)<30:return 0
    tr=np.maximum(h[1:]-l[1:],np.maximum(np.abs(h[1:]-c[:-1]),np.abs(l[1:]-c[:-1])))
    a=float(np.mean(tr[-p:]))
    return a/np.mean(c[-30:])*1e4

async def tg(t):
    if not cid:return
    try:
        async with aiohttp.ClientSession() as c:
            await c.post(f"https://api.telegram.org/bot{T}/sendMessage",json={"chat_id":cid,"text":t,"parse_mode":"HTML"})
    except:pass

async def poll():
    global cid,bank,n,stop
    try:
        async with aiohttp.ClientSession() as c:
            j=(await (await c.get(f"https://api.telegram.org/bot{T}/getUpdates")).json()).get("result",[])
            for m in j:
                msg=m["message"]["text"].strip()
                cid=m["chat"]["id"]
                if msg=="/start":
                    bank=B;n=0;stop=False
                    await tg(f"Trader99 ONLINE | bank ${bank:.2f} | {A.upper()} {TF}m | conf>{CF}")
                elif msg=="/ping":
                    await tg(f"pong | bank ${bank:.2f} | {n}/{MT}")
                elif msg=="/balance":
                    await tg(f"bank ${bank:.2f} | {n}/{MT}")
                elif msg=="/stop":
                    stop=True
                    await tg("STOPPED")
                elif msg=="/restart":
                    bank=B;n=0;stop=False
                    await tg(f"RESTARTED | ${bank:.2f}")
    except:pass

async def market():
    global last,bank,n,stop
    if stop or n>=MT or bank<B*(1-MD):return
    now=time.time();s=now//300*300
    if s==last:return
    try:
        async with aiohttp.ClientSession() as c:
            r=await c.get(f"https://ws.pocketoption.com/public/v1/trade/get_history?asset_id={A}&timeframe={TF}&start={s-3600}&end={now}&limit=300",timeout=10)
            j=(await r.json()).get("payload",{}).get("history",{})
            if not j:return
            ks=sorted(j.keys())
            c=[float(j[k]["close"]) for k in ks]
            hh=[float(j[k]["high"]) for k in ks]
            ll=[float(j[k]["low"]) for k in ks]
            if len(c)<60:return
            up=float(np.polyfit(range(len(c[-30:]),np.array(c[-30:])),1)[0])>0
            v=atr(c,hh,ll)
            bl=int(macd(c)>0)+int(rsi(c)>55)+int(boll(c)>.6)
            sl=int(macd(c)<0)+int(rsi(c)<45)+int(boll(c)<.4)
            cf=max(.5,min(1,(bl/3)*(.9 if up else .7)))
            cf2=max(.5,min(1,(sl/3)*(.9 if not up else .7)))
            if bl>=2 and up and cf>=CF and v>VM:
                last=s;n+=1;st=bank*SK
                await tg(f"SIGNAL | CALL | conf {cf:.2f} | vol {v:.1f} | ${st:.2f}")
                bank+=st*.8
                await asyncio.sleep(310)
                await tg(f"DONE | CALL | bank ${bank:.2f} | {n}/{MT}")
            elif sl>=2 and not up and cf2>=CF and v>VM:
                last=s;n+=1;st=bank*SK
                await tg(f"SIGNAL | PUT | conf {cf2:.2f} | vol {v:.1f} | ${st:.2f}")
                bank-=st
                await asyncio.sleep(310)
                await tg(f"DONE | PUT | bank ${bank:.2f} | {n}/{MT}")
    except:pass

async def loop():
    while True:
        await poll()
        if cid:
            await market()
        await asyncio.sleep(15)

if __name__ == "__main__":
    print("BOOTING Trader99")
    asyncio.run(loop())
