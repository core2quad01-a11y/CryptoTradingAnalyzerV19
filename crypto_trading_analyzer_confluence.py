import tkinter as tk
from tkinter import ttk, messagebox
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import datetime
import json, threading

BASE='https://api.binance.com'
KLINES=BASE+'/api/v3/klines'; INFO=BASE+'/api/v3/exchangeInfo'; TICKERS=BASE+'/api/v3/ticker/24hr'
BYBIT='https://api.bybit.com'; BYBIT_KLINES=BYBIT+'/v5/market/kline'; BYBIT_INFO=BYBIT+'/v5/market/instruments-info'; BYBIT_TICKERS=BYBIT+'/v5/market/tickers'
INTERVALS={'1 minuto':'1m','5 minutos':'5m','15 minutos':'15m','30 minutos':'30m','1 hora':'1h','4 horas':'4h','1 dia':'1d'}
DEFAULT=['BTC/USDT','ETH/USDT','SOL/USDT']


def api(url, params=None):
    if params: url += '?' + urlencode(params)
    r=urlopen(Request(url,headers={'User-Agent':'CryptoTradingAnalyzer/11.0'}),timeout=15)
    return json.loads(r.read().decode())

def ema(v,p):
    if len(v)<p:return [None]*len(v)
    o=[None]*(p-1); x=sum(v[:p])/p; o.append(x); k=2/(p+1)
    for z in v[p:]: x=(z-x)*k+x; o.append(x)
    return o

def rsi(c,p=14):
    o=[None]*len(c)
    if len(c)<=p:return o
    g=[];l=[]
    for i in range(1,p+1):
        d=c[i]-c[i-1];g.append(max(d,0));l.append(max(-d,0))
    ag=sum(g)/p;al=sum(l)/p;o[p]=100 if al==0 else 100-100/(1+ag/al)
    for i in range(p+1,len(c)):
        d=c[i]-c[i-1];ag=(ag*(p-1)+max(d,0))/p;al=(al*(p-1)+max(-d,0))/p
        o[i]=100 if al==0 else 100-100/(1+ag/al)
    return o

def macd(c,fast=12,slow=26,signal=9):
    ef=ema(c,fast); es=ema(c,slow)
    line=[None]*len(c)
    for i in range(len(c)):
        if ef[i] is not None and es[i] is not None: line[i]=ef[i]-es[i]
    vals=[x for x in line if x is not None]
    sigvals=ema(vals,signal)
    sig=[None]*len(c); k=0
    for i,x in enumerate(line):
        if x is not None:
            if k < len(sigvals): sig[i]=sigvals[k]
            k+=1
    return line,sig

def atr(h,l,c,p=14):
    tr=[None]*len(c)
    for i in range(1,len(c)):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    o=[None]*len(c)
    if len(c)<=p:return o
    x=sum(tr[1:p+1])/p;o[p]=x
    for i in range(p+1,len(c)):x=(x*(p-1)+tr[i])/p;o[i]=x
    return o

def avg(v,p):
    o=[None]*len(v)
    for i in range(p-1,len(v)):o[i]=sum(v[i-p+1:i+1])/p
    return o

class App:
    def __init__(self,root):
        self.root=root; self.alert_popup=None; self.monitor=False; self.last_alert=None; self.chart_zoom=80
        self.assets=[f'BINANCE:{x}' for x in DEFAULT]; self.c=[]; self.d={}; self.ranked_results=[]; self.selected=None
        root.title('Crypto Trading Analyzer V11'); root.geometry('1180x850')
        self.ui(); self.refresh()

    def ui(self):
        top=ttk.Frame(self.root,padding=14);top.pack(fill='x')
        ttk.Label(top,text='CRYPTO TRADING ANALYZER V11',font=('Arial',22,'bold')).pack(anchor='w')
        ttk.Label(top,text='Scanner de confluência técnica • Binance + Bybit • Entrada / Stop / Alvos',font=('Arial',10)).pack(anchor='w')

        f=ttk.LabelFrame(self.root,text='Mercado',padding=10);f.pack(fill='x',padx=14,pady=5)
        ttk.Label(f,text='Ativo:').grid(row=0,column=0); self.asset=tk.StringVar(value='BINANCE:BTC/USDT')
        self.combo=ttk.Combobox(f,textvariable=self.asset,values=self.assets,width=25);self.combo.grid(row=0,column=1,padx=5)
        ttk.Button(f,text='↻ Atualizar ativos',command=self.refresh).grid(row=0,column=2,padx=5)
        ttk.Label(f,text='Pesquisar:').grid(row=0,column=3,padx=8);self.search=tk.StringVar();e=ttk.Entry(f,textvariable=self.search,width=16);e.grid(row=0,column=4);self.search.trace_add('write',self.filter)
        ttk.Label(f,text='Timeframe:').grid(row=1,column=0,pady=6);self.interval=tk.StringVar(value='15 minutos')
        ttk.Combobox(f,textvariable=self.interval,values=list(INTERVALS),state='readonly',width=22).grid(row=1,column=1)
        ttk.Label(f,text='Alerta mínimo:').grid(row=1,column=2);self.threshold=tk.StringVar(value='70');ttk.Entry(f,textvariable=self.threshold,width=7).grid(row=1,column=3,sticky='w')
        self.alerts=tk.BooleanVar(value=True);ttk.Checkbutton(f,text='🔔 Alertas',variable=self.alerts).grid(row=1,column=4,sticky='w');self.auto=tk.BooleanVar(value=False);ttk.Checkbutton(f,text='Monitorar',variable=self.auto,command=self.toggle).grid(row=1,column=5,sticky='w')

        a=ttk.Frame(self.root,padding=8);a.pack(fill='x',padx=14)
        ttk.Button(a,text='ANALISAR',command=self.async_analyze).pack(side='left',padx=3)
        ttk.Button(a,text='🔎 SCANNER',command=self.async_scan).pack(side='left',padx=3)
        ttk.Button(a,text='🔄 ATUALIZAR OPERAÇÃO',command=self.async_refresh).pack(side='left',padx=3)
        ttk.Button(a,text='TESTAR ALERTA',command=lambda:self.alert('ALERTA — TESTE','Alerta funcionando.')).pack(side='left',padx=3)
        ttk.Button(a,text='LIMPAR',command=self.clear).pack(side='left',padx=3)

        r=ttk.LabelFrame(self.root,text='RANKING DE OPORTUNIDADES',padding=10);r.pack(fill='x',padx=14,pady=5)
        self.rank=tk.StringVar(value='Nenhum resultado');self.rankcombo=ttk.Combobox(r,textvariable=self.rank,values=['Nenhum resultado'],state='readonly',width=85);self.rankcombo.grid(row=0,column=0,padx=5,sticky='ew');self.rankcombo.bind('<<ComboboxSelected>>',self.select_rank)
        ttk.Button(r,text='🎯 USAR SELECIONADO',command=self.use_rank).grid(row=0,column=1,padx=5);r.columnconfigure(0,weight=1)
        self.rankstatus=tk.StringVar(value='Clique em SCANNER para procurar oportunidades.');ttk.Label(r,textvariable=self.rankstatus).grid(row=1,column=0,columnspan=2,sticky='w',pady=5)

        p=ttk.LabelFrame(self.root,text='SINAL',padding=12);p.pack(fill='x',padx=14,pady=5)
        self.direction=tk.StringVar(value='AGUARDAR');self.strength=tk.StringVar(value='Força: 0/100');self.probs=tk.StringVar(value='Alta 0% | Baixa 0% | Lateral 0%')
        ttk.Label(p,textvariable=self.direction,font=('Arial',20,'bold')).pack();ttk.Label(p,textvariable=self.strength,font=('Arial',15,'bold')).pack(pady=2);ttk.Label(p,textvariable=self.probs).pack()

        q=ttk.LabelFrame(self.root,text='Detalhes + Gráfico em tempo real',padding=8);q.pack(fill='both',expand=True,padx=14,pady=5);q.columnconfigure(0,weight=1);q.columnconfigure(1,weight=2);q.rowconfigure(0,weight=1);left=ttk.Frame(q);left.grid(row=0,column=0,sticky='nsew',padx=(0,8));self.out=tk.Text(left,font=('Consolas',10),wrap='word',state='disabled');self.out.pack(fill='both',expand=True);right=ttk.Frame(q);right.grid(row=0,column=1,sticky='nsew');zc=ttk.Frame(right);zc.pack(fill='x',pady=(0,4));ttk.Label(zc,text='Zoom:').pack(side='left',padx=(2,4));ttk.Button(zc,text='−',width=3,command=lambda:self.change_zoom(-10)).pack(side='left',padx=2);self.zoom_label=tk.StringVar(value='80 candles');ttk.Label(zc,textvariable=self.zoom_label,width=11,anchor='center').pack(side='left');ttk.Button(zc,text='+',width=3,command=lambda:self.change_zoom(10)).pack(side='left',padx=2);ttk.Button(zc,text='↺',width=3,command=lambda:self.set_zoom(80)).pack(side='left',padx=2);self.levels_label=tk.StringVar(value='Entrada: —  |  Stop: —  |  Saídas: —');ttk.Label(zc,textvariable=self.levels_label,anchor='w',font=('Arial',8)).pack(side='left',fill='x',expand=True,padx=(8,0));self.chart_canvas=tk.Canvas(right,background='#111827',highlightthickness=0);self.chart_canvas.pack(fill='both',expand=True);self.chart_canvas.bind('<Configure>',lambda e:self.draw_chart());self.chart_canvas.bind('<MouseWheel>',self._wheel_zoom);self.chart_canvas.bind('<Button-4>',lambda e:self.change_zoom(10));self.chart_canvas.bind('<Button-5>',lambda e:self.change_zoom(-10));self.start_realtime_chart()
        self.status=tk.StringVar(value='Pronto.');ttk.Label(self.root,textvariable=self.status,padding=7).pack(fill='x',padx=14)

    def set_zoom(self, value):
        self.chart_zoom=max(30,min(160,int(value)))
        if hasattr(self,'zoom_label'): self.zoom_label.set(f'{self.chart_zoom} candles')
        if hasattr(self,'chart_source'): self.chart_data=self.chart_source[-self.chart_zoom:]
        self.draw_chart()

    def change_zoom(self, delta):
        self.set_zoom(self.chart_zoom + delta)

    def _wheel_zoom(self, event):
        delta=10 if getattr(event,'delta',0)>0 else -10
        self.change_zoom(delta)

    def start_realtime_chart(self):
        self.update_chart_async()

    def update_chart_async(self):
        if getattr(self,'chart_busy',False):
            self.chart_job=self.root.after(10000,self.update_chart_async)
            return
        self.chart_busy=True
        threading.Thread(target=self._load_chart_data,daemon=True).start()
        self.chart_job=self.root.after(10000,self.update_chart_async)

    def _load_chart_data(self):
        try:
            c=self.candles() if hasattr(self,'candles') else self.candles_for()
            self.root.after(0,lambda:self._set_chart_data(c))
        except Exception:
            self.root.after(0,lambda:self._set_chart_busy(False))

    def _set_chart_busy(self,v):
        self.chart_busy=v

    def _set_chart_data(self,c):
        self.chart_busy=False
        self.chart_source=c[-160:]
        self.chart_data=self.chart_source[-self.chart_zoom:]
        self.draw_chart()

    def draw_chart(self):
        if not hasattr(self,'chart_canvas'): return
        self.chart_canvas.delete('all')
        c=getattr(self,'chart_data',[])
        w=max(self.chart_canvas.winfo_width(),460); h=max(self.chart_canvas.winfo_height(),340)
        if len(c)<30:
            self.chart_canvas.create_text(w//2,h//2,text='Aguardando dados do mercado...',fill='white',font=('Arial',12)); return
        # Área principal + dois indicadores compactos
        gap=6; price_h=int(h*0.68); rsi_h=int(h*0.13); macd_h=h-price_h-rsi_h-gap*3
        pad_l,pad_r=55,15; x0=pad_l; x1=w-pad_r
        closes=[x['close'] for x in c]
        hi=max(x['high'] for x in c); lo=min(x['low'] for x in c); span=hi-lo or hi*0.001 or 1
        def py(v): return 8+(hi-v)/span*(price_h-25)
        cw=(x1-x0)/len(c); body=max(2,min(9,cw*.62))
        # preço/candles
        for j in range(4):
            y=8+j*(price_h-25)/3; val=hi-j*span/3
            self.chart_canvas.create_line(x0,y,x1,y,fill='#263244')
            self.chart_canvas.create_text(x0-5,y,text=f'{val:.6g}',fill='#9ca3af',anchor='e',font=('Arial',8))
        for i,x in enumerate(c):
            xx=x0+(i+.5)*cw; yo=py(x['open']); yc=py(x['close']); yh=py(x['high']); yl=py(x['low'])
            col='#22c55e' if x['close']>=x['open'] else '#ef4444'
            self.chart_canvas.create_line(xx,yh,xx,yl,fill=col,width=1)
            self.chart_canvas.create_rectangle(xx-body/2,min(yo,yc),xx+body/2,max(yo,yc)+1,fill=col,outline=col)
        # Médias móveis do gráfico:
        # EMA 9 = verde-claro (média atual), EMA 12 = azul-marinho, EMA 200 = rosa.
        # Mantidas discretas para não poluir a leitura dos candles.
        ma_specs=[
            (9, '#86efac', 2.2, 'EMA 9'),
            (12, '#1e3a8a', 1.8, 'EMA 12'),
            (200, '#f472b6', 1.8, 'EMA 200'),
        ]
        for period,color,width,label in ma_specs:
            vals=ema(closes,period); pts=[]
            for i,v in enumerate(vals):
                if v is not None:
                    pts.extend([x0+(i+.5)*cw,py(v)])
            if len(pts)>=4:
                self.chart_canvas.create_line(*pts,fill=color,width=width,smooth=True)
        # Legenda compacta
        lx=x0+78; ly=6
        for period,color,width,label in ma_specs:
            self.chart_canvas.create_line(lx,ly+5,lx+18,ly+5,fill=color,width=max(2,int(width)))
            self.chart_canvas.create_text(lx+22,ly+5,text=label,fill=color,anchor='w',font=('Arial',7,'bold'))
            lx += 62 if period != 200 else 0
        # Marcações do plano técnico selecionado: entrada, stop e saídas (alvos)
        setup = getattr(self, "selected_setup", None) if hasattr(self, "selected_setup") else getattr(self, "selected", None)
        if setup and setup.get("plan"):
            plan = setup["plan"]
            direction = setup.get("signal", "")
            # As marcações seguem a direção do setup:
            # LONG -> entrada/saídas apontam para cima; stop aponta para baixo.
            # SHORT -> entrada/saídas apontam para baixo; stop aponta para cima.
            is_long = direction == "LONG"
            entry_arrow = "▲" if is_long else "▼"
            stop_arrow = "▼" if is_long else "▲"
            exit_arrow = "▲" if is_long else "▼"
            if hasattr(self, "levels_label"):
                self.levels_label.set(
                    f"{'LONG ↑' if is_long else 'SHORT ↓'}  |  Entrada: {plan.get('entry', 0):.8g}  |  Stop: {plan.get('stop', 0):.8g}  |  Saídas: {plan.get('t1', 0):.8g} / {plan.get('t2', 0):.8g} / {plan.get('t3', 0):.8g}"
                )
            levels = [(f"ENTRADA {entry_arrow}", plan.get("entry"), "#facc15", "--"),
                      (f"STOP {stop_arrow}", plan.get("stop"), "#ef4444", "--"),
                      (f"SAÍDA 1 {exit_arrow}", plan.get("t1"), "#22c55e", "--"),
                      (f"SAÍDA 2 {exit_arrow}", plan.get("t2"), "#4ade80", "--"),
                      (f"SAÍDA 3 {exit_arrow}", plan.get("t3"), "#86efac", "--")]
            for label, value, color, dash in levels:
                if value is None or value < lo or value > hi:
                    continue
                yy = py(value)
                self.chart_canvas.create_line(x0, yy, x1, yy, fill=color, width=1, dash=(7, 4))
            # marcador visual da entrada na vela mais recente
            entry = plan.get("entry")
            if entry is not None and lo <= entry <= hi:
                ex = x0 + (len(c)-.5)*cw
                ey = py(entry)
                up = direction == "LONG"
                pts = [(ex, ey-11), (ex-7, ey+2), (ex+7, ey+2)] if up else [(ex, ey+11), (ex-7, ey-2), (ex+7, ey-2)]
                self.chart_canvas.create_polygon(pts, fill="#facc15", outline="#facc15")
                self.chart_canvas.create_text(ex, ey + (-17 if up else 17), text=("LONG ↑" if up else "SHORT ↓"), fill="#facc15", anchor="s" if up else "n", font=("Arial", 8, "bold"))
        elif hasattr(self, "levels_label"):
            self.levels_label.set("Entrada: —  |  Stop: —  |  Saídas: —")
        last=c[-1]
        self.chart_canvas.create_text(x0+6,5,text=f"{self.asset.get()}  {self.interval.get()} | Preço: {last['close']:.8g}",fill='white',anchor='nw',font=('Arial',10,'bold'))
        # RSI miniatura
        rsi_y0=price_h+gap; rsi_y1=rsi_y0+rsi_h
        self.chart_canvas.create_rectangle(x0,rsi_y0,x1,rsi_y1,outline='#263244')
        self.chart_canvas.create_text(x0+5,rsi_y0+3,text='RSI 14',fill='#cbd5e1',anchor='nw',font=('Arial',8,'bold'))
        def ry(v): return rsi_y1-5-(v/100)*(rsi_h-10)
        for level in (70,50,30):
            y=ry(level); self.chart_canvas.create_line(x0,y,x1,y,fill='#263244',dash=(3,3)); self.chart_canvas.create_text(x0-4,y,text=str(level),fill='#6b7280',anchor='e',font=('Arial',7))
        rv=rsi(closes,14); pts=[]
        for i,v in enumerate(rv):
            if v is not None: pts.extend([x0+(i+.5)*cw,ry(v)])
        if len(pts)>=4: self.chart_canvas.create_line(*pts,fill='#38bdf8',width=1.5,smooth=True)
        rvlast=next((v for v in reversed(rv) if v is not None),None)
        if rvlast is not None: self.chart_canvas.create_text(x1-4,rsi_y0+3,text=f'{rvlast:.1f}',fill='#38bdf8',anchor='ne',font=('Arial',8,'bold'))
        # MACD miniatura
        my0=rsi_y1+gap; my1=h-18
        self.chart_canvas.create_rectangle(x0,my0,x1,my1,outline='#263244')
        self.chart_canvas.create_text(x0+5,my0+3,text='MACD 12,26,9',fill='#cbd5e1',anchor='nw',font=('Arial',8,'bold'))
        ml,ms=macd(closes); valid=[v for v in ml+ms if v is not None]
        if valid:
            mh=max(abs(v) for v in valid) or 1; mid=(my0+my1)/2
            self.chart_canvas.create_line(x0,mid,x1,mid,fill='#263244')
            def my(v): return mid-(v/mh)*(my1-my0-10)/2
            for i,v in enumerate(ml):
                if v is not None:
                    xx=x0+(i+.5)*cw; y=my(v); y0=mid
                    self.chart_canvas.create_line(xx,y0,xx,y,fill=('#55d68a' if v >= 0 else '#ef5350'),width=max(1,int(cw*.7)))
            pts1=[]; pts2=[]
            for i,v in enumerate(ml):
                if v is not None: pts1.extend([x0+(i+.5)*cw,my(v)])
            for i,v in enumerate(ms):
                if v is not None: pts2.extend([x0+(i+.5)*cw,my(v)])
            if len(pts1)>=4:self.chart_canvas.create_line(*pts1,fill='#a78bfa',width=1.3,smooth=True)
            if len(pts2)>=4:self.chart_canvas.create_line(*pts2,fill='#fbbf24',width=1.1,smooth=True)
            lv=next((v for v in reversed(ml) if v is not None),None); sv=next((v for v in reversed(ms) if v is not None),None)
            if lv is not None and sv is not None:self.chart_canvas.create_text(x1-4,my0+3,text=f'M {lv:.3g} | S {sv:.3g}',fill=('#55d68a' if lv >= 0 else '#ef5350'),anchor='ne',font=('Arial',7))
        self.chart_canvas.create_text(x1,h-6,text=last['time'].strftime('%H:%M:%S'),fill='#9ca3af',anchor='se',font=('Arial',8))

    def refresh(self): self.status.set('Atualizando ativos Binance + Bybit...');threading.Thread(target=self._refresh,daemon=True).start()
    def _refresh(self):
        try:
            d=api(INFO); ba=sorted({f'BINANCE:{s["baseAsset"]}/USDT' for s in d['symbols'] if s.get('status')=='TRADING' and s.get('quoteAsset')=='USDT'})
        except Exception: ba=[]
        try:
            d=api(BYBIT_INFO,{'category':'linear','limit':1000});bb=sorted({f'BYBIT:{s["baseCoin"]}/USDT' for s in d.get('result',{}).get('list',[]) if s.get('status')=='Trading' and s.get('quoteCoin')=='USDT'})
        except Exception: bb=[]
        self.root.after(0,lambda:self.setassets(ba+bb))
    def setassets(self,a):
        self.assets=a or self.assets;self.combo['values']=self.assets;self.status.set(f'{len(self.assets)} pares USDT disponíveis.')
    def search_asset(self):
        q=self.search.get().strip().upper()
        if not q:
            self.filter()
            self.status.set('Digite um ativo para pesquisar.')
            return
        vals=[x for x in self.assets if q in x.upper()]
        self.combo['values']=vals or self.assets
        if vals:
            self.asset.set(vals[0])
            self.status.set(f'Pesquisa: {len(vals)} ativo(s) encontrado(s). Selecionado: {vals[0]}')
        else:
            self.status.set(f'Nenhum ativo encontrado para: {q}')

    def filter(self,*_):
        q=self.search.get().upper();self.combo['values']=[x for x in self.assets if q in x] or self.assets

    def candles_for(self,asset=None,limit=1000):
        value=asset or self.asset.get();ex,sym=value.split(':',1) if ':' in value else ('BINANCE',value);symbol=sym.replace('/','');interval=INTERVALS[self.interval.get()]
        if ex=='BYBIT':
            rows=api(BYBIT_KLINES,{'category':'linear','symbol':symbol,'interval':{'1m':'1','5m':'5','15m':'15','30m':'30','1h':'60','4h':'240','1d':'D'}[interval],'limit':limit}).get('result',{}).get('list',[]);rows=list(reversed(rows))
            return [self.row(r,True) for r in rows]
        rows=api(KLINES,{'symbol':symbol,'interval':interval,'limit':limit});return [self.row(r,False) for r in rows]
    def row(self,r,bybit):
        return {'time':datetime.fromtimestamp(int(r[0])/1000),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5])}

    def indicators(self,c):
        cl=[x['close'] for x in c];hi=[x['high'] for x in c];lo=[x['low'] for x in c];vo=[x['volume'] for x in c]
        e9,e21,e50,e200=ema(cl,9),ema(cl,21),ema(cl,50),ema(cl,200);rr=rsi(cl);aa=atr(hi,lo,cl);e12,e26=ema(cl,12),ema(cl,26)
        mac=[None if e12[i] is None or e26[i] is None else e12[i]-e26[i] for i in range(len(cl))]; sv=ema([x for x in mac if x is not None],9);ms=[None]*len(cl);j=0
        for i,x in enumerate(mac):
            if x is not None:
                if sv[j] is not None:ms[i]=sv[j]
                j+=1
        return {'e9':e9,'e21':e21,'e50':e50,'e200':e200,'rsi':rr,'atr':aa,'macd':mac,'ms':ms,'vavg':avg(vo,20),'h20':self.rollmax(hi,20),'l20':self.rollmin(lo,20)}
    def rollmax(self,v,p):
        return [None if i<p else max(v[i-p:i]) for i in range(len(v))]
    def rollmin(self,v,p):
        return [None if i<p else min(v[i-p:i]) for i in range(len(v))]

    def confluence_signal(self,c,d,i):
        if i<210:return 'AGUARDAR',0,[],{}
        x={k:d[k][i] for k in ('e9','e21','e50','e200','rsi','atr','macd','ms','vavg','h20','l20')};
        if any(v is None for v in x.values()):return 'AGUARDAR',0,[],x
        p=c[i]['close']; prev=c[i-1]['close'];v=c[i]['volume'];scoreL=scoreS=0;reasons=[]
        # Trend: 25 points
        if p>x['e50']:scoreL+=8;reasons.append('preço acima da EMA50')
        else:scoreS+=8;reasons.append('preço abaixo da EMA50')
        if x['e50']>x['e200']:scoreL+=9;reasons.append('EMA50 acima da EMA200')
        else:scoreS+=9;reasons.append('EMA50 abaixo da EMA200')
        if x['e9']>x['e21']:scoreL+=8;reasons.append('EMA9 acima da EMA21')
        else:scoreS+=8;reasons.append('EMA9 abaixo da EMA21')
        # Momentum: 20
        if 52<=x['rsi']<=68:scoreL+=10;reasons.append('RSI em zona de momentum comprador')
        elif 32<=x['rsi']<=48:scoreS+=10;reasons.append('RSI em zona de momentum vendedor')
        elif x['rsi']>70:scoreS+=4;reasons.append('RSI elevado: risco de exaustão')
        elif x['rsi']<30:scoreL+=4;reasons.append('RSI baixo: possível reação')
        if x['macd']>x['ms']:scoreL+=10;reasons.append('MACD acima do sinal')
        else:scoreS+=10;reasons.append('MACD abaixo do sinal')
        # Volume: 15
        if x['vavg'] and v>x['vavg']*1.20:
            if scoreL>scoreS:scoreL+=15;reasons.append('volume forte acima da média')
            elif scoreS>scoreL:scoreS+=15;reasons.append('volume forte acima da média')
        elif x['vavg'] and v>x['vavg']:
            if scoreL>scoreS:scoreL+=8;reasons.append('volume acima da média')
            elif scoreS>scoreL:scoreS+=8;reasons.append('volume acima da média')
        # Structure/breakout: 20
        if x['h20'] and p>x['h20']:scoreL+=12;reasons.append('rompimento da máxima recente')
        elif x['l20'] and p<x['l20']:scoreS+=12;reasons.append('rompimento da mínima recente')
        else:
            if p>prev and scoreL>scoreS:scoreL+=5;reasons.append('candle atual confirma pressão compradora')
            elif p<prev and scoreS>scoreL:scoreS+=5;reasons.append('candle atual confirma pressão vendedora')
        if x['atr']/p*100<8:
            if scoreL>scoreS:scoreL+=3;reasons.append('volatilidade relativamente controlada')
            elif scoreS>scoreL:scoreS+=3;reasons.append('volatilidade relativamente controlada')
        # Normalize: maximum nominal is 103; cap at 100.
        if scoreL>=60 and scoreL>scoreS: return 'LONG',min(100,scoreL),reasons,x
        if scoreS>=60 and scoreS>scoreL: return 'SHORT',min(100,scoreS),reasons,x
        return 'AGUARDAR',min(100,max(scoreL,scoreS)),reasons,x

    def probabilities(self,c,d,current):
        if len(c)<280:return 0,0,0,0
        samples=[]
        for i in range(220,len(c)-7):
            s,sc,_,x=self.confluence_signal(c,d,i)
            if s not in ('LONG','SHORT'):continue
            ret=(c[i+6]['close']/c[i]['close']-1)*100;thr=max(.25,x['atr']/c[i]['close']*100*.75)
            outcome='ALTA' if ret>=thr else 'BAIXA' if ret<=-thr else 'LATERAL';samples.append((s,outcome))
        use=[o for s,o in samples if s==current]
        if len(use)<15:use=[o for _,o in samples]
        n=len(use)
        if not n:return 0,0,100,0
        return use.count('ALTA')/n*100,use.count('BAIXA')/n*100,use.count('LATERAL')/n*100,n

    def plan(self,s,p,a):
        if s not in ('LONG','SHORT') or not a:return None
        risk=max(a*1.2,p*.002)
        if s=='LONG':stop=p-risk;t1=p+risk*1.5;t2=p+risk*2.5;t3=p+risk*3.5
        else:stop=p+risk;t1=p-risk*1.5;t2=p-risk*2.5;t3=p-risk*3.5
        return {'entry':p,'stop':stop,'t1':t1,'t2':t2,'t3':t3,'risk_pct':risk/p*100,'rr1':1.5,'rr2':2.5,'rr3':3.5}

    def _mtf_read(self, symbol, exchange, current_interval):
        """Leitura multi-timeframe: 4H = tendência, 1H = confirmação, atual = gatilho."""
        mapping={'1m':'1','5m':'5','15m':'15','30m':'30','1h':'60','4h':'240','1d':'D'}
        def getc(interval, limit=500):
            if exchange=='BYBIT':
                rows=api(BYBIT_KLINES,{'category':'linear','symbol':symbol,'interval':mapping[interval],'limit':limit}).get('result',{}).get('list',[])
                rows=list(reversed(rows))
                return [self.row(r,True) for r in rows]
            rows=api(KLINES,{'symbol':symbol,'interval':interval,'limit':limit})
            return [self.row(r,False) for r in rows]
        def one(interval):
            c=getc(interval)
            if len(c)<220:return {'signal':'AGUARDAR','score':0,'price':c[-1]['close'] if c else None}
            d=self.indicators(c); i=len(c)-1
            if hasattr(self,'confluence_signal'):
                sig,score,_,_=self.confluence_signal(c,d,i)
            else:
                oldc,oldd=self.c,self.d; self.c,self.d=c,d
                sig,score,_=self.signal(i)
                self.c,self.d=oldc,oldd
            return {'signal':sig,'score':score,'price':c[i]['close']}
        tf_cur=current_interval
        r4=one('4h')
        r1=one('1h')
        rc=one(tf_cur)
        # Confirmação: o sinal atual ganha status confirmado quando 4H e 1H apontam para a mesma direção.
        cur=rc['signal']
        if cur in ('LONG','SHORT') and r4['signal']==cur and r1['signal']==cur:
            status=f'MTF CONFIRMADO: 4H {cur} | 1H {cur} | {self.interval.get()} {cur}'
        elif cur in ('LONG','SHORT') and (r4['signal']==cur or r1['signal']==cur):
            status=f'MTF PARCIAL: 4H {r4["signal"]} | 1H {r1["signal"]} | {self.interval.get()} {cur}'
        else:
            status=f'MTF DIVERGENTE: 4H {r4["signal"]} | 1H {r1["signal"]} | {self.interval.get()} {cur}'
        return {'4h':r4,'1h':r1,'current':rc,'status':status}

    def async_analyze(self):threading.Thread(target=self.analyze,daemon=True).start()
    def analyze(self):
        try:
            c=self.candles_for();d=self.indicators(c);i=len(c)-1;s,score,reasons,x=self.confluence_signal(c,d,i);up,down,side,n=self.probabilities(c,d,s);direction='ALTA' if up>=down and up>=side else 'BAIXA' if down>=up and down>=side else 'LATERAL';prob={'ALTA':up,'BAIXA':down,'LATERAL':side}[direction];p=self.plan(s,c[i]['close'],x.get('atr'));self.c,self.d=c,d; ex,sym=(self.asset.get().split(':',1) if ':' in self.asset.get() else ('BINANCE',self.asset.get())); mtf=self._mtf_read(sym.replace('/',''),ex,INTERVALS[self.interval.get()])
            result={'asset':self.asset.get(),'symbol':self.asset.get().split(':')[-1],'signal':s,'score':score,'reasons':reasons,'direction':direction,'prob':prob,'up':up,'down':down,'side':side,'samples':n,'plan':p,'time':c[i]['time'],'price':c[i]['close'],'rsi':x.get('rsi'),'atr':x.get('atr'),'mtf':mtf}
            self.selected=result;self.root.after(0,lambda:self.show(result))
            try:t=float(self.threshold.get().replace(',','.'))
            except:t=70
            if self.alerts.get() and s in ('LONG','SHORT') and score>=t:
                marker=f'{self.asset.get()}|{self.interval.get()}|{s}'
                if marker!=self.last_alert:
                    self.last_alert=marker
                    self.root.after(0,lambda r=result:self.alert_result(r))
        except Exception as e:self.root.after(0,lambda:messagebox.showerror('Erro',str(e)))

    def alert_result(self,r):
        p=r['plan'];
        if not p:return
        msg=(f'Sinal: {r["signal"]}\nScore: {r["score"]}/100\n'
             f'Probabilidade histórica: {r["prob"]:.1f}%\n\n'
             f'ENTRADA: {self.fmt(p["entry"])}\nSTOP: {self.fmt(p["stop"])}\n\n'
             f'🎯 ALVO 1: {self.fmt(p["t1"])}   R/R 1:{p["rr1"]:.1f}\n'
             f'🎯 ALVO 2: {self.fmt(p["t2"])}   R/R 1:{p["rr2"]:.1f}\n'
             f'🎯 ALVO 3: {self.fmt(p["t3"])}   R/R 1:{p["rr3"]:.1f}\n\n'
             f'Risco até o stop: {p["risk_pct"]:.2f}%\nTimeframe: {self.interval.get()}')
        self.alert(f'ALERTA — {r["asset"]}',msg)

    def show(self,r):
        p=r['plan'];self.direction.set(f'{r["signal"]} — {r["direction"]}');self.strength.set(f'Força: {r["score"]}/100');self.probs.set(f'Histórico: Alta {r["up"]:.1f}% | Baixa {r["down"]:.1f}% | Lateral {r["side"]:.1f}%')
        lines=['','='*76,f'INDICADOR DE CONFLUÊNCIA — {r["symbol"]}','='*76,'',f'SINAL:                 {r["signal"]}',f'SCORE:                  {r["score"]}/100',f'DIREÇÃO HISTÓRICA:      {r["direction"]} — {r["prob"]:.1f}%',f'AMOSTRA:               {r["samples"]} ocorrências',f'TIMEFRAME:             {self.interval.get()}',f'ATUALIZADO:             {r["time"].strftime("%d/%m/%Y %H:%M")}', '']
        if p:
            lines += ['─'*76,'📍 PLANO TÉCNICO','─'*76,f'Entrada:                {self.fmt(p["entry"])}',f'Stop:                   {self.fmt(p["stop"])}',f'Risco:                  {p["risk_pct"]:.2f}%',f'Alvo 1:                 {self.fmt(p["t1"])}  | R/R 1:{p["rr1"]:.1f}',f'Alvo 2:                 {self.fmt(p["t2"])}  | R/R 1:{p["rr2"]:.1f}',f'Alvo 3:                 {self.fmt(p["t3"])}  | R/R 1:{p["rr3"]:.1f}','']
        m=r.get('mtf',{}); lines += ['─'*76,'🧭 LEITURA MULTI-TIMEFRAME','─'*76,f'4H — tendência:       {m.get("4h",{}).get("signal","-")} | Score {m.get("4h",{}).get("score",0)}/100',f'1H — confirmação:      {m.get("1h",{}).get("signal","-")} | Score {m.get("1h",{}).get("score",0)}/100',f'{self.interval.get()} — gatilho:   {m.get("current",{}).get("signal","-")} | Score {m.get("current",{}).get("score",0)}/100',m.get('status',''),'','─'*76,'📊 INDICADORES','─'*76,f'Preço:                  {self.fmt(r["price"])}',f'RSI:                    {r["rsi"]:.2f}',f'ATR:                    {self.fmt(r["atr"])}','', '─'*76,'🔎 CONFLUÊNCIAS','─'*76,*['• '+x for x in r['reasons']], '', 'Atenção: este indicador usa um modelo técnico próprio de confluência; as probabilidades são históricas e não garantem resultado.','='*76]
        self.write('\n'.join(lines));self.mtf_status.set(r['mtf']['status']);self.status.set('Análise Confluência concluída.')

    def fmt(self,x):
        if x is None:return '-'
        if abs(x)>=1000:return f'{x:,.2f}'
        if abs(x)>=1:return f'{x:.4f}'
        return f'{x:.8f}'
    def write(self,txt):self.out.config(state='normal');self.out.delete('1.0','end');self.out.insert('end',txt);self.out.config(state='disabled')

    def async_scan(self):threading.Thread(target=self.scan,daemon=True).start()
    def scan(self):
        try:
            self.root.after(0,lambda:self.status.set('Scanner: coletando ativos líquidos...'));cands=[]
            try:
                bt=api(TICKERS);cands += [('BINANCE',x['symbol'],float(x.get('quoteVolume',0) or 0)) for x in bt if x.get('symbol','').endswith('USDT') and float(x.get('quoteVolume',0) or 0)>0]
            except:pass
            try:
                yt=api(BYBIT_TICKERS,{'category':'linear'}).get('result',{}).get('list',[]);cands += [('BYBIT',x['symbol'],float(x.get('turnover24h',0) or 0)) for x in yt if x.get('symbol','').endswith('USDT') and float(x.get('turnover24h',0) or 0)>0]
            except:pass
            cands=sorted(cands,key=lambda x:x[2],reverse=True)[:60];res=[]
            for n,(ex,sym,vol) in enumerate(cands,1):
                try:
                    asset=f'{ex}:{sym.replace("USDT","/USDT")}';c=self.candles_for(asset,500)
                    if len(c)<280:continue
                    d=self.indicators(c);i=len(c)-1;s,score,reasons,x=self.confluence_signal(c,d,i);up,down,side,samples=self.probabilities(c,d,s);direction='ALTA' if up>=down and up>=side else 'BAIXA' if down>=up and down>=side else 'LATERAL';prob={'ALTA':up,'BAIXA':down,'LATERAL':side}[direction];p=self.plan(s,c[i]['close'],x.get('atr'))
                    if s not in ('LONG','SHORT') or score<50 or not p:continue
                    rank=score*.65+prob*.35;res.append({'position':0,'asset':asset,'symbol':sym,'exchange':ex,'signal':s,'score':score,'prob':prob,'direction':direction,'plan':p,'reasons':reasons,'samples':samples,'price':c[i]['close'],'rsi':x['rsi'],'atr':x['atr'],'time':c[i]['time'],'volume':vol,'rank':rank})
                    self.root.after(0,lambda n=n:self.status.set(f'Scanner... {n}/{len(cands)}'))
                except Exception:continue
            res.sort(key=lambda z:z['rank'],reverse=True)
            for i,r in enumerate(res,1):r['position']=i
            self.root.after(0,lambda:self.show_scan(res[:15]))
        except Exception as e:self.root.after(0,lambda:messagebox.showerror('Erro no scanner',str(e)))
    def show_scan(self,res):
        self.ranked_results=res;vals=[f'{r["position"]}º {r["asset"]} — {r["signal"]} — {r["score"]}/100 — Hist {r["prob"]:.1f}% — R/R 1:{r["plan"]["rr3"]:.1f}' for r in res];self.rankcombo['values']=vals or ['Nenhum resultado'];self.rank.set(vals[0] if vals else 'Nenhum resultado');self.rankstatus.set(f'{len(res)} oportunidades encontradas e ordenadas por score composto.' if res else 'Nenhuma configuração passou pelos filtros.');self.status.set('Scanner concluído.')
    def select_rank(self,*_):
        v=self.rank.get()
        for r in self.ranked_results:
            if v.startswith(f'{r["position"]}º'):self.selected=r;break
    def use_rank(self):
        if not self.selected:return
        self.asset.set(self.selected['asset']);self.show(self.selected);self.status.set(f'Ativo selecionado: {self.asset.get()}')
    def async_refresh(self):threading.Thread(target=self.refresh_operation,daemon=True).start()
    def refresh_operation(self):
        try:
            c=self.candles_for();d=self.indicators(c);i=len(c)-1;s,score,reasons,x=self.confluence_signal(c,d,i);up,down,side,n=self.probabilities(c,d,s);direction='ALTA' if up>=down and up>=side else 'BAIXA' if down>=up and down>=side else 'LATERAL';prob={'ALTA':up,'BAIXA':down,'LATERAL':side}[direction];r={'asset':self.asset.get(),'symbol':self.asset.get().split(':')[-1],'signal':s,'score':score,'reasons':reasons,'direction':direction,'prob':prob,'up':up,'down':down,'side':side,'samples':n,'plan':self.plan(s,c[i]['close'],x.get('atr')),'time':c[i]['time'],'price':c[i]['close'],'rsi':x['rsi'],'atr':x['atr']};self.c,self.d=c,d;self.selected=r;self.root.after(0,lambda:self.show(r))
        except Exception as e:self.root.after(0,lambda:messagebox.showerror('Erro','Não foi possível atualizar a operação: '+str(e)))
    def alert(self,title,msg):
        if self.alert_popup is not None:
            try:self.alert_popup.destroy()
            except:pass
            self.alert_popup=None
        self.root.bell();p=tk.Toplevel(self.root);self.alert_popup=p;p.title(title);p.transient(self.root);p.grab_set();p.resizable(False,False)
        fr=ttk.Frame(p,padding=18);fr.pack(fill='both',expand=True);ttk.Label(fr,text=title,font=('Arial',15,'bold')).pack(pady=(0,10));ttk.Label(fr,text=msg,justify='left',wraplength=480).pack(pady=(0,15))
        def close():
            if self.alert_popup is p:self.alert_popup=None
            try:p.grab_release()
            except:pass
            p.destroy()
        ttk.Button(fr,text='OK',command=close).pack();p.protocol('WM_DELETE_WINDOW',close);p.update_idletasks();x=self.root.winfo_rootx()+(self.root.winfo_width()-p.winfo_width())//2;y=self.root.winfo_rooty()+(self.root.winfo_height()-p.winfo_height())//2;p.geometry(f'+{max(0,x)}+{max(0,y)}');p.lift();p.focus_force()
    def toggle(self):
        self.monitor=self.auto.get()
        if self.monitor:self.loop()
    def loop(self):
        if self.monitor:self.async_analyze();self.root.after(60000,self.loop)
    def clear(self):self.write('');self.direction.set('AGUARDAR');self.strength.set('Força: 0/100');self.probs.set('Alta 0% | Baixa 0% | Lateral 0%')

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
