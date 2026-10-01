import tkinter as tk
from tkinter import ttk, messagebox
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import datetime
import json, threading

BASE='https://api.binance.com'; KLINES=BASE+'/api/v3/klines'; INFO=BASE+'/api/v3/exchangeInfo'; TICKERS=BASE+'/api/v3/ticker/24hr'
BYBIT='https://api.bybit.com'; BYBIT_KLINES=BYBIT+'/v5/market/kline'; BYBIT_INFO=BYBIT+'/v5/market/instruments-info'; BYBIT_TICKERS=BYBIT+'/v5/market/tickers'
INTERVALS={'1 minuto':'1m','5 minutos':'5m','15 minutos':'15m','30 minutos':'30m','1 hora':'1h','4 horas':'4h','1 dia':'1d'}
DEFAULT=['BTC/USDT','ETH/USDT','SOL/USDT']

def api(url, params=None):
    if params: url += '?' + urlencode(params)
    r=urlopen(Request(url,headers={'User-Agent':'CryptoTradingAnalyzerV5/1.0'}),timeout=15)
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

class App:
    def __init__(self,root):
        self.root=root;self.alert_popup=None;root.title('Crypto Trading Analyzer V8');root.geometry('1120x820');self.assets=[f'BINANCE:{x}' for x in DEFAULT];self.c=[];self.d={};self.last=None;self.monitor=False;self.chart_job=None;self.chart_busy=False;self.selected_setup=None;self.chart_zoom=80;self.ranked_results=[];self.ranked_symbols=[]
        self.ui();self.refresh()
    def ui(self):
        top=ttk.Frame(self.root,padding=15);top.pack(fill='x');ttk.Label(top,text='CRYPTO TRADING ANALYZER V9 — BINANCE + BYBIT',font=('Arial',21,'bold')).pack(anchor='w');ttk.Label(top,text='Direção estimada + alertas + estatística histórica',font=('Arial',10)).pack(anchor='w')
        f=ttk.LabelFrame(self.root,text='Mercado',padding=10);f.pack(fill='x',padx=15,pady=5)
        ttk.Label(f,text='Ativo:').grid(row=0,column=0);self.asset=tk.StringVar(value='BTC/USDT');self.combo=ttk.Combobox(f,textvariable=self.asset,values=self.assets,width=20);self.combo.grid(row=0,column=1,padx=5);ttk.Button(f,text='↻ Atualizar ativos',command=self.refresh).grid(row=0,column=2,padx=5)
        ttk.Label(f,text='Pesquisar:').grid(row=0,column=3,padx=8);self.search=tk.StringVar();e=ttk.Entry(f,textvariable=self.search,width=16);e.grid(row=0,column=4);self.search.trace_add('write',self.filter)
        ttk.Label(f,text='Timeframe:').grid(row=1,column=0,pady=6);self.interval=tk.StringVar(value='15 minutos');ttk.Combobox(f,textvariable=self.interval,values=list(INTERVALS),state='readonly',width=18).grid(row=1,column=1)
        ttk.Label(f,text='Alerta >=').grid(row=1,column=2);self.threshold=tk.StringVar(value='70');ttk.Entry(f,textvariable=self.threshold,width=7).grid(row=1,column=3,sticky='w');self.alerts=tk.BooleanVar(value=True);ttk.Checkbutton(f,text='🔔 Alertas',variable=self.alerts).grid(row=1,column=4,sticky='w');self.auto=tk.BooleanVar();ttk.Checkbutton(f,text='Monitorar',variable=self.auto,command=self.toggle).grid(row=1,column=5)
        a=ttk.Frame(self.root,padding=8);a.pack(fill='x',padx=15);ttk.Button(a,text='ANALISAR AGORA',command=self.async_analyze).pack(side='left',padx=4);ttk.Button(a,text='🔎 PESQUISAR MELHOR RISCO × RETORNO',command=self.async_scan).pack(side='left',padx=4);ttk.Button(a,text='🔄 ATUALIZAR OPERAÇÃO',command=self.async_refresh_operation).pack(side='left',padx=4);ttk.Button(a,text='TESTAR ALERTA',command=lambda:self.alert('Teste','Alerta funcionando.')).pack(side='left',padx=4);ttk.Button(a,text='LIMPAR',command=self.clear).pack(side='left',padx=4)
        r=ttk.LabelFrame(self.root,text='ATIVOS ENCONTRADOS PELO RANKING',padding=10);r.pack(fill='x',padx=15,pady=5)
        ttk.Label(r,text='Escolher do ranking:').grid(row=0,column=0,padx=5)
        self.ranked_choice=tk.StringVar(value='Nenhum ranking disponível')
        self.ranked_combo=ttk.Combobox(r,textvariable=self.ranked_choice,values=['Nenhum ranking disponível'],state='readonly',width=52)
        self.ranked_combo.grid(row=0,column=1,padx=5,sticky='ew')
        self.ranked_combo.bind('<<ComboboxSelected>>',self.select_ranked)
        ttk.Button(r,text='🎯 USAR ATIVO SELECIONADO',command=self.use_ranked).grid(row=0,column=2,padx=5)
        ttk.Button(r,text='🔄 ATUALIZAR ATIVOS PELO RANKING',command=self.async_scan).grid(row=0,column=3,padx=5)
        r.columnconfigure(1,weight=1)
        self.ranked_status=tk.StringVar(value='Faça uma pesquisa de risco × retorno para preencher esta lista.')
        ttk.Label(r,textvariable=self.ranked_status).grid(row=1,column=0,columnspan=4,sticky='w',padx=5,pady=5)
        p=ttk.LabelFrame(self.root,text='DIREÇÃO ESTIMADA DO MERCADO',padding=12);p.pack(fill='x',padx=15,pady=5);self.direction=tk.StringVar(value='AGUARDAR');self.probs=tk.StringVar(value='Alta 0% | Baixa 0% | Lateral 0%');self.base=tk.StringVar(value='Base histórica: -');ttk.Label(p,textvariable=self.direction,font=('Arial',22,'bold')).pack();ttk.Label(p,textvariable=self.probs,font=('Arial',14)).pack(pady=3);ttk.Label(p,textvariable=self.base).pack()
        self.mtf_status=tk.StringVar(value='MTF: aguardando leitura 4H / 1H / timeframe atual');ttk.Label(p,textvariable=self.mtf_status,font=('Arial',10,'bold')).pack(pady=(4,0))
        q=ttk.LabelFrame(self.root,text='Detalhes + Gráfico em tempo real',padding=8);q.pack(fill='both',expand=True,padx=15,pady=5);q.columnconfigure(0,weight=1);q.columnconfigure(1,weight=2);q.rowconfigure(0,weight=1);left=ttk.Frame(q);left.grid(row=0,column=0,sticky='nsew',padx=(0,8));self.out=tk.Text(left,font=('Consolas',10),wrap='word',state='disabled');self.out.pack(fill='both',expand=True);right=ttk.Frame(q);right.grid(row=0,column=1,sticky='nsew');zc=ttk.Frame(right);zc.pack(fill='x',pady=(0,4));ttk.Label(zc,text='Zoom:').pack(side='left',padx=(2,4));ttk.Button(zc,text='−',width=3,command=lambda:self.change_zoom(-10)).pack(side='left',padx=2);self.zoom_label=tk.StringVar(value='80 candles');ttk.Label(zc,textvariable=self.zoom_label,width=11,anchor='center').pack(side='left');ttk.Button(zc,text='+',width=3,command=lambda:self.change_zoom(10)).pack(side='left',padx=2);ttk.Button(zc,text='↺',width=3,command=lambda:self.set_zoom(80)).pack(side='left',padx=2);self.levels_label=tk.StringVar(value='Entrada: —  |  Stop: —  |  Saídas: —');ttk.Label(zc,textvariable=self.levels_label,anchor='w',font=('Arial',8)).pack(side='left',fill='x',expand=True,padx=(8,0));self.chart_canvas=tk.Canvas(right,background='#111827',highlightthickness=0);self.chart_canvas.pack(fill='both',expand=True);self.chart_canvas.bind('<Configure>',lambda e:self.draw_chart());self.chart_canvas.bind('<MouseWheel>',self._wheel_zoom);self.chart_canvas.bind('<Button-4>',lambda e:self.change_zoom(10));self.chart_canvas.bind('<Button-5>',lambda e:self.change_zoom(-10));self.status=tk.StringVar(value='Pronto.');ttk.Label(self.root,textvariable=self.status,padding=7).pack(fill='x',padx=15);self.start_realtime_chart()
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

    def refresh(self):
        self.status.set('Atualizando ativos...');threading.Thread(target=self._refresh,daemon=True).start()
    def _refresh(self):
        try:
            d=api(INFO); ba=sorted({f'BINANCE:{s["baseAsset"]}/USDT' for s in d['symbols'] if s.get('status')=='TRADING' and s.get('quoteAsset')=='USDT'})
        except Exception: ba=[]
        try:
            d=api(BYBIT_INFO,{'category':'linear','limit':1000}); bb=sorted({f'BYBIT:{s["baseCoin"]}/USDT' for s in d.get('result',{}).get('list',[]) if s.get('status')=='Trading' and s.get('quoteCoin')=='USDT'})
        except Exception: bb=[]
        a=ba+bb
        self.root.after(0,lambda:self.setassets(a))
    def setassets(self,a):
        self.assets=a or self.assets;self.combo['values']=self.assets;self.status.set(f'{len(self.assets)} pares USDT disponíveis: Binance + Bybit.')
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
        q=self.search.get().upper();v=[x for x in self.assets if q in x];self.combo['values']=v or self.assets
    def candles(self):
        ex,sym=self.asset.get().split(':',1) if ':' in self.asset.get() else ('BINANCE',self.asset.get())
        symbol=sym.replace('/',''); interval=INTERVALS[self.interval.get()]
        if ex=='BYBIT':
            rows=api(BYBIT_KLINES,{'category':'linear','symbol':symbol,'interval':{'1m':'1','5m':'5','15m':'15','30m':'30','1h':'60','4h':'240','1d':'D'}[interval],'limit':1000}).get('result',{}).get('list',[])
            rows=list(reversed(rows));return [{'time':datetime.fromtimestamp(int(r[0])/1000),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5])} for r in rows]
        rows=api(KLINES,{'symbol':symbol,'interval':interval,'limit':1000});return [{'time':datetime.fromtimestamp(r[0]/1000),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5])} for r in rows]
    def indicators(self,c):
        cl=[x['close'] for x in c];hi=[x['high'] for x in c];lo=[x['low'] for x in c];vo=[x['volume'] for x in c];e9=ema(cl,9);e21=ema(cl,21);e50=ema(cl,50);e200=ema(cl,200);rr=rsi(cl);aa=atr(hi,lo,cl);e12=ema(cl,12);e26=ema(cl,26);m=[None if e12[i] is None or e26[i] is None else e12[i]-e26[i] for i in range(len(cl))];v=[x for x in m if x is not None];sv=ema(v,9);ms=[None]*len(cl);j=0
        for i,x in enumerate(m):
            if x is not None:
                if sv[j] is not None:ms[i]=sv[j]
                j+=1
        va=[None]*len(vo)
        for i in range(19,len(vo)):va[i]=sum(vo[i-19:i+1])/20
        return dict(e9=e9,e21=e21,e50=e50,e200=e200,rsi=rr,atr=aa,macd=m,ms=ms,va=va)
    def signal(self,i):
        d=self.d;c=self.c[i];keys=('e9','e21','e50','e200','rsi','atr','macd','ms','va');x=[d[k][i] for k in keys]
        if any(z is None for z in x):return 'AGUARDAR',0,[]
        e9,e21,e50,e200,r,a,m,ms,va=x;lp=sp=0;rs=[]
        if c['close']>e50:lp+=1;rs.append('preço acima da EMA50')
        else:sp+=1;rs.append('preço abaixo da EMA50')
        if e50>e200:lp+=2;rs.append('EMA50 acima da EMA200')
        else:sp+=2;rs.append('EMA50 abaixo da EMA200')
        if e9>e21:lp+=2;rs.append('EMA9 acima da EMA21')
        else:sp+=2;rs.append('EMA9 abaixo da EMA21')
        if 50<=r<=68:lp+=2;rs.append('RSI favorável à alta')
        elif 32<=r<50:sp+=2;rs.append('RSI favorável à baixa')
        if m>ms:lp+=2;rs.append('MACD acima do sinal')
        else:sp+=2;rs.append('MACD abaixo do sinal')
        if c['volume']>va:
            if lp>sp:lp+=1;rs.append('volume acima da média')
            elif sp>lp:sp+=1;rs.append('volume acima da média')
        if lp>=7 and lp>sp:return 'LONG',min(100,lp*10),rs
        if sp>=7 and sp>lp:return 'SHORT',min(100,sp*10),rs
        return 'AGUARDAR',max(lp,sp)*10,rs
    def probabilities(self):
        if len(self.c)<260:return 0,0,0,0
        samples=[];cur=self.signal(len(self.c)-1)[0]
        for i in range(220,len(self.c)-6):
            s,_,_=self.signal(i)
            if s=='AGUARDAR':continue
            ret=(self.c[i+6]['close']/self.c[i]['close']-1)*100;at=self.d['atr'][i];thr=max(.25,at/self.c[i]['close']*100*.75)
            samples.append((s,'ALTA' if ret>=thr else 'BAIXA' if ret<=-thr else 'LATERAL'))
        r=[o for s,o in samples if s==cur] if cur!='AGUARDAR' else []
        if len(r)<15:r=[o for _,o in samples]
        n=len(r);return ((r.count('ALTA')/n*100,r.count('BAIXA')/n*100,r.count('LATERAL')/n*100,n) if n else (0,0,100,0))
    def async_scan(self):
        threading.Thread(target=self.scan_market,daemon=True).start()

    def trade_plan(self, signal, price, atr_value):
        # Plano técnico baseado em ATR; não é ordem automática.
        if not atr_value or atr_value <= 0 or signal not in ('LONG','SHORT'):
            return None
        risk=max(atr_value*1.2, price*0.002)
        if signal=='LONG':
            stop=price-risk; t1=price+risk*1.5; t2=price+risk*2.5; t3=price+risk*3.5
        else:
            stop=price+risk; t1=price-risk*1.5; t2=price-risk*2.5; t3=price-risk*3.5
        return {'entry':price,'stop':stop,'t1':t1,'t2':t2,'t3':t3,'risk_pct':risk/price*100,'rr1':1.5,'rr2':2.5,'rr3':3.5}

    def scan_market(self):
        try:
            self.root.after(0,lambda:self.status.set('Escaneando mercado: selecionando ativos líquidos...'))
            candidates=[]
            try:
                bt=api(TICKERS); candidates += [('BINANCE',x['symbol'],float(x.get('quoteVolume',0) or 0)) for x in bt if x.get('symbol','').endswith('USDT') and float(x.get('quoteVolume',0) or 0)>0]
            except Exception: pass
            try:
                yt=api(BYBIT_TICKERS,{'category':'linear'}).get('result',{}).get('list',[]); candidates += [('BYBIT',x['symbol'],float(x.get('turnover24h',0) or 0)) for x in yt if x.get('symbol','').endswith('USDT') and float(x.get('turnover24h',0) or 0)>0]
            except Exception: pass
            candidates=sorted(candidates,key=lambda x:x[2],reverse=True)[:60]
            results=[]
            interval=INTERVALS[self.interval.get()]
            for n,(exchange,symbol,volume24) in enumerate(candidates,1):
                try:
                    if exchange=='BYBIT':
                        rows=api(BYBIT_KLINES,{'category':'linear','symbol':symbol,'interval':{'1m':'1','5m':'5','15m':'15','30m':'30','1h':'60','4h':'240','1d':'D'}[interval],'limit':500}).get('result',{}).get('list',[]); rows=list(reversed(rows))
                    else:
                        rows=api(KLINES,{'symbol':symbol,'interval':interval,'limit':500})
                    c=[{'time':datetime.fromtimestamp(int(r[0])/1000),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5])} for r in rows]
                    if len(c)<260: continue
                    d=self.indicators(c); i=len(c)-1
                    oldc,oldd,oldcself=self.c,self.d,self.asset.get()
                    self.c,self.d=c,d
                    sig,score,reasons=self.signal(i); up,down,side,samples=self.probabilities()
                    self.c,self.d=oldc,oldd
                    direction='ALTA' if up>=down and up>=side else 'BAIXA' if down>=up and down>=side else 'LATERAL'
                    prob={'ALTA':up,'BAIXA':down,'LATERAL':side}[direction]
                    if sig not in ('LONG','SHORT') or prob<55: continue
                    plan=self.trade_plan(sig,c[i]['close'],d['atr'][i])
                    if not plan: continue
                    # Score de ranking: combina histórico, qualidade técnica e R/R, normalizado em 0-100.
                    rr_score=min(plan['rr3']/3.5,1.0)*100
                    rank_score=prob*0.55 + score*0.25 + rr_score*0.20
                    results.append({'symbol':symbol,'exchange':exchange,'signal':sig,'prob':prob,'score':score,'price':c[i]['close'],'plan':plan,'samples':samples,'reasons':reasons,'direction':direction,'rank':rank_score,'volume':volume24})
                    self.root.after(0,lambda n=n:self.status.set(f'Escaneando mercado... {n}/{len(usdt)}'))
                except Exception:
                    continue
            results.sort(key=lambda x:x['rank'],reverse=True)
            # Classificação final: do maior score de oportunidade para o menor.
            for idx, item in enumerate(results, 1): item['position']=idx
            self.root.after(0,lambda:self.show_scan(results[:10]))
        except Exception as e:
            self.root.after(0,lambda:messagebox.showerror('Erro no scanner',str(e)))

    def select_ranked(self,*_):
        value=self.ranked_choice.get()
        for r in self.ranked_results:
            if value.startswith(f'{r["position"]}º'):
                self.selected_setup=r
                self.ranked_status.set(f'Selecionado: {r["exchange"]}:{r["symbol"]} | {r["signal"]} | Score {r["rank"]:.1f}/100')
                break

    def use_ranked(self):
        r=self.selected_setup
        if not r or 'symbol' not in r:
            messagebox.showinfo('Ranking','Primeiro faça uma pesquisa e selecione um ativo do ranking.')
            return
        self.asset.set(f"{r['exchange']}:{r['symbol'].replace('USDT','/USDT')}")
        self.search.set('')
        self.status.set(f'Ativo selecionado: {self.asset.get()}. Clique em ANALISAR AGORA ou ATUALIZAR OPERAÇÃO.')
        self.show_operation(r)

    def show_scan(self,results):
        self.ranked_results=results
        self.ranked_symbols=[f'{r["position"]}º — {r["exchange"]}:{r["symbol"]} — {r["signal"]} — Score {r["rank"]:.1f} | Hist. {r["prob"]:.1f}% | R/R 1:{r["plan"]["rr3"]:.1f}' for r in results]
        self.ranked_combo['values']=self.ranked_symbols or ['Nenhum ranking disponível']
        if results:
            self.ranked_choice.set(self.ranked_symbols[0])
            self.selected_setup=results[0]
            self.ranked_status.set(f'{len(results)} ativos classificados. A lista está ordenada do melhor para o pior.')
        else:
            self.ranked_choice.set('Nenhum ranking disponível')
            self.ranked_status.set('Nenhum ativo passou nos filtros da análise.')
        self.selected_setup=results[0] if results else None
        if not results:
            self.status.set('Nenhum setup encontrou os filtros mínimos.')
            messagebox.showinfo('Scanner','Nenhum ativo encontrou simultaneamente sinal técnico e estimativa histórica mínima.')
            return
        def f(x):
            if abs(x)>=1000:return f'{x:,.2f}'
            if abs(x)>=1:return f'{x:.4f}'
            return f'{x:.8f}'
        lines=['','='*100,'🏆 RANKING — MELHOR → PIOR OPORTUNIDADE','='*100,'','A classificação é ordenada pelo SCORE DE OPORTUNIDADE, do maior para o menor.','Score = histórico + força técnica + risco/retorno. Não é garantia de resultado.','']
        for pos,r in enumerate(results,1):
            p=r['plan']; medal='🥇' if pos==1 else '🥈' if pos==2 else '🥉' if pos==3 else f'{pos:02d}º'
            lines += [f'{medal}  {r["exchange"]}:{r["symbol"]}   {r["signal"]}   | SCORE OPORTUNIDADE: {r["rank"]:.1f}/100', f'    Prob. histórica: {r["prob"]:.1f}% | Score técnico: {r["score"]}/100 | R/R Alvo 3: 1:{p["rr3"]:.1f} | Risco: {p["risk_pct"]:.2f}%', '-'*100, f'    Entrada:     {f(p["entry"])}', f'    Stop Loss:   {f(p["stop"])}', f'    Alvo 1:      {f(p["t1"])}   | R/R 1:{p["rr1"]:.1f}', f'    Alvo 2:      {f(p["t2"])}   | R/R 1:{p["rr2"]:.1f}', f'    Alvo 3:      {f(p["t3"])}   | R/R 1:{p["rr3"]:.1f}', f'    Direção histórica: {r["direction"]} | Amostra: {r["samples"]} sinais | Volume 24h: USDT {r["volume"]:,.0f}', '    Motivos: '+('; '.join(r['reasons'])), '']
        self.out.config(state='normal');self.out.delete('1.0','end');self.out.insert('end','\n'.join(lines));self.out.config(state='disabled');self.direction.set(f'{results[0]["exchange"]}:{results[0]["symbol"]} — {results[0]["signal"]}');self.probs.set(f'🥇 1º {results[0]["exchange"]}:{results[0]["symbol"]} | Score oportunidade: {results[0]["rank"]:.1f}/100 | Histórico: {results[0]["prob"]:.1f}% | R/R 1:{results[0]["plan"]["rr3"]:.1f}');self.base.set(f'Ranking ordenado: 1º → {len(results)}º | timeframe: {self.interval.get()}');self.status.set(f'Scanner concluído. {len(results)} setups encontrados.')

    def async_refresh_operation(self):
        threading.Thread(target=self.refresh_operation,daemon=True).start()

    def refresh_operation(self):
        try:
            self.root.after(0,lambda:self.status.set('Atualizando operação com dados mais recentes...'))
            ex,sym=self.asset.get().split(':',1) if ':' in self.asset.get() else ('BINANCE',self.asset.get())
            symbol=sym.replace('/','')
            interval=INTERVALS[self.interval.get()]
            if ex=='BYBIT':
                rows=api(BYBIT_KLINES,{'category':'linear','symbol':symbol,'interval':{'1m':'1','5m':'5','15m':'15','30m':'30','1h':'60','4h':'240','1d':'D'}[interval],'limit':500}).get('result',{}).get('list',[]); rows=list(reversed(rows))
            else:
                rows=api(KLINES,{'symbol':symbol,'interval':interval,'limit':500})
            c=[{'time':datetime.fromtimestamp(int(r[0])/1000),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5])} for r in rows]
            d=self.indicators(c); i=len(c)-1; self.c,self.d=c,d
            sig,score,reasons=self.signal(i); up,down,side,n=self.probabilities()
            direction='ALTA' if up>=down and up>=side else 'BAIXA' if down>=up and down>=side else 'LATERAL'
            prob={'ALTA':up,'BAIXA':down,'LATERAL':side}[direction]
            plan=self.trade_plan(sig,c[i]['close'],d['atr'][i])
            if sig not in ('LONG','SHORT') or not plan:
                self.root.after(0,lambda:self.show_no_operation(sig,score,up,down,side,n,direction,prob,reasons)); return
            setup={'symbol':symbol,'exchange':exchange,'signal':sig,'prob':prob,'score':score,'direction':direction,'samples':n,'plan':plan,'reasons':reasons,'time':c[i]['time'],'price':c[i]['close'],'rsi':d['rsi'][i],'atr':d['atr'][i],'mtf':mtf}
            self.selected_setup=setup
            self.root.after(0,lambda:self.show_operation(setup))
        except Exception as e:
            self.root.after(0,lambda:messagebox.showerror('Erro ao atualizar operação',str(e)))

    def show_no_operation(self,sig,score,up,down,side,n,direction,prob,reasons):
        self.direction.set(f'{direction} — {prob:.1f}%')
        self.probs.set(f'🟢 Alta {up:.1f}%    🔴 Baixa {down:.1f}%    🟡 Lateral {side:.1f}%')
        self.base.set(f'Atualização: {n} sinais históricos | Sinal atual: {sig} | Score: {score}/100')
        txt='\n'.join([
            '', '='*72, 'SEM OPERAÇÃO ATIVA', '='*72, '',
            'O mercado foi atualizado, mas o modelo não encontrou uma configuração LONG/SHORT suficientemente definida.',
            '', f'Direção histórica predominante: {direction}', f'Estimativa histórica: {prob:.1f}%',
            f'Sinal técnico: {sig}', f'Score técnico: {score}/100', '', 'Fatores observados:',
            *['• '+x for x in reasons], '', 'Ação do modelo: AGUARDAR.', '='*72])
        self.out.config(state='normal');self.out.delete('1.0','end');self.out.insert('end',txt);self.out.config(state='disabled');self.status.set('Atualização concluída: sem setup operacional.')

    def show_operation(self,r):
        p=r['plan']
        def f(x):
            if abs(x)>=1000:return f'{x:,.2f}'
            if abs(x)>=1:return f'{x:.4f}'
            return f'{x:.8f}'
        if r['signal']=='LONG':
            t1pct=(p['t1']/p['entry']-1)*100; t2pct=(p['t2']/p['entry']-1)*100; t3pct=(p['t3']/p['entry']-1)*100
        else:
            t1pct=(1-p['t1']/p['entry'])*100; t2pct=(1-p['t2']/p['entry'])*100; t3pct=(1-p['t3']/p['entry'])*100
        lines=['', '='*72, f'🎯 OPERAÇÃO COMPLETA — {r["symbol"]}', '='*72, '',
            f'DIREÇÃO:                 {r["signal"]}', f'DIREÇÃO HISTÓRICA:      {r["direction"]} — {r["prob"]:.1f}%',
            f'SCORE TÉCNICO:          {r["score"]}/100', f'AMOSTRA HISTÓRICA:      {r["samples"]} sinais',
            f'TIMEFRAME:              {self.interval.get()}', f'ATUALIZADO EM:          {r["time"].strftime("%d/%m/%Y %H:%M")}', '',
            '─'*72, '📍 ENTRADA / SAÍDA', '─'*72, f'Entrada:                 {f(p["entry"])}',
            f'Stop Loss:               {f(p["stop"])}', f'Risco até o Stop:       {p["risk_pct"]:.2f}%', '',
            f'Alvo 1:                  {f(p["t1"])}   (+{t1pct:.2f}%)   R/R 1:{p["rr1"]:.1f}',
            f'Alvo 2:                  {f(p["t2"])}   (+{t2pct:.2f}%)   R/R 1:{p["rr2"]:.1f}',
            f'Alvo 3:                  {f(p["t3"])}   (+{t3pct:.2f}%)   R/R 1:{p["rr3"]:.1f}', '',
            '─'*72, '📊 INDICADORES', '─'*72, f'Preço:                   {f(r["price"])}', f'RSI:                     {r["rsi"]:.2f}', f'ATR:                     {f(r["atr"])}', '',
            '─'*72, '🔎 MOTIVOS DO SETUP', '─'*72, *['• '+x for x in r['reasons']], '',
            '─'*72, '⚠️ COMO INTERPRETAR', '─'*72,
            f'A estimativa de {r["prob"]:.1f}% é baseada em ocorrências históricas do setup e não é garantia.',
            'Entrada, stop e alvos são níveis técnicos calculados pelo modelo.',
            'O botão ATUALIZAR OPERAÇÃO recalcula os níveis com candles novos.',
            'O sistema não envia ordens automaticamente.', '='*72]
        txt='\n'.join(lines)
        self.direction.set(f'{r["symbol"]} — {r["signal"]} — {r["prob"]:.1f}%')
        self.probs.set(f'Entrada {f(p["entry"])} | Stop {f(p["stop"])} | R/R Alvo 3: 1:{p["rr3"]:.1f}')
        self.base.set(f'Operação atualizada | {self.interval.get()} | Risco {p["risk_pct"]:.2f}% | Alvo 3 +{t3pct:.2f}%')
        self.out.config(state='normal');self.out.delete('1.0','end');self.out.insert('end',txt);self.out.config(state='disabled');self.status.set('Operação atualizada com dados recentes.')

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
            self.root.after(0,lambda:self.status.set('Buscando dados reais...'));self.c=self.candles();self.d=self.indicators(self.c);i=len(self.c)-1;s,score,reasons=self.signal(i);up,down,side,n=self.probabilities();direction='ALTA' if up>=down and up>=side else 'BAIXA' if down>=up and down>=side else 'LATERAL';prob={'ALTA':up,'BAIXA':down,'LATERAL':side}[direction];self.root.after(0,lambda:self.show(s,score,reasons,up,down,side,n,direction,prob))
            try:t=float(self.threshold.get().replace(',','.'))
            except:t=70
            if self.alerts.get() and s in ('LONG','SHORT') and prob>=t:
                marker=f'{self.asset.get()}|{self.interval.get()}|{s}|{round(prob)}'
                if marker!=self.last:
                    self.last=marker
                    plan=self.trade_plan(self.c,self.d)
                    def abrir_alerta():
                        self.alert(f'{s} — {self.asset.get()}',
                                   f'Direção histórica estimada: {direction}\n'
                                   f'Probabilidade estimada: {prob:.1f}%\n'
                                   f'Score técnico: {score}/100\n\n'
                                   f'ENTRADA: {plan["entry"]:.8g}\n'
                                   f'STOP: {plan["stop"]:.8g}\n'
                                   f'ALVO 1: {plan["t1"]:.8g}\n'
                                   f'ALVO 2: {plan["t2"]:.8g}\n'
                                   f'ALVO 3: {plan["t3"]:.8g}\n\n'
                                   f'Risco: {plan["risk_pct"]:.2f}%\n'
                                   f'R/R Alvo 1: 1:{plan["rr1"]:.1f}\n'
                                   f'R/R Alvo 2: 1:{plan["rr2"]:.1f}\n'
                                   f'R/R Alvo 3: 1:{plan["rr3"]:.1f}')
                    self.root.after(0,abrir_alerta)
        except Exception as e:self.root.after(0,lambda:messagebox.showerror('Erro',str(e)))
    def show(self,s,score,reasons,up,down,side,n,direction,prob):
        self.direction.set(f'{direction} — {prob:.1f}%');self.probs.set(f'🟢 Alta {up:.1f}%    🔴 Baixa {down:.1f}%    🟡 Lateral {side:.1f}%');self.base.set(f'Base histórica: {n} sinais | Sinal atual: {s} | Score: {score}/100');i=len(self.c)-1;d=self.d;c=self.c[i]
        def f(x):return '-' if x is None else f'{x:,.2f}' if abs(x)>=1000 else f'{x:.4f}' if abs(x)>=1 else f'{x:.8f}'
        txt=f'''\n============================================================\n{self.asset.get()} — DIREÇÃO ESTIMADA\n============================================================\n\nDireção predominante:   {direction}\nProbabilidade estimada: {prob:.1f}%\n\nALTA: {up:.1f}%   BAIXA: {down:.1f}%   LATERAL: {side:.1f}%\nAmostra histórica: {n} sinais\n\nSINAL TÉCNICO ATUAL\n------------------------------------------------------------\nSinal: {s}\nScore: {score}/100\nPreço: {f(c['close'])}\nCandle: {c['time'].strftime('%d/%m/%Y %H:%M')}\n\nINDICADORES\n------------------------------------------------------------\nEMA9: {f(d['e9'][i])}\nEMA21: {f(d['e21'][i])}\nEMA50: {f(d['e50'][i])}\nEMA200: {f(d['e200'][i])}\nRSI: {d['rsi'][i]:.2f}\nMACD: {d['macd'][i]:.6f}\nMACD Signal: {d['ms'][i]:.6f}\nATR: {f(d['atr'][i])}\n\nFATORES\n------------------------------------------------------------\n'''+''.join('• '+r+'\n' for r in reasons)+'''\n------------------------------------------------------------\nA probabilidade é uma estatística histórica do modelo, não uma\ngarantia para o próximo movimento. Use backtest e controle de risco.\n============================================================\n''';self.out.config(state='normal');self.out.delete('1.0','end');self.out.insert('end',txt);self.out.config(state='disabled');self.status.set('Análise concluída.')
    def alert(self,t,m):
        # Garante que apenas um popup de alerta fique aberto por vez.
        if self.alert_popup is not None:
            try:
                if self.alert_popup.winfo_exists():
                    self.alert_popup.destroy()
            except Exception:
                pass
            self.alert_popup=None
        self.root.bell()
        popup=tk.Toplevel(self.root)
        self.alert_popup=popup
        popup.title(t)
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False,False)
        frame=ttk.Frame(popup,padding=18)
        frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=t,font=('Arial',14,'bold')).pack(pady=(0,10))
        ttk.Label(frame,text=m,justify='left',wraplength=420).pack(pady=(0,15))
        def fechar():
            if self.alert_popup is popup:
                self.alert_popup=None
            try:
                popup.grab_release()
            except Exception:
                pass
            popup.destroy()
        ttk.Button(frame,text='OK',command=fechar).pack()
        popup.protocol('WM_DELETE_WINDOW',fechar)
        popup.update_idletasks()
        x=self.root.winfo_rootx()+(self.root.winfo_width()-popup.winfo_width())//2
        y=self.root.winfo_rooty()+(self.root.winfo_height()-popup.winfo_height())//2
        popup.geometry(f'+{max(0,x)}+{max(0,y)}')
        popup.lift()
        popup.focus_force()
    def toggle(self):
        self.monitor=self.auto.get()
        if self.monitor:self.loop()
    def loop(self):
        if self.monitor:self.async_analyze();self.root.after(60000,self.loop)
    def clear(self):self.out.config(state='normal');self.out.delete('1.0','end');self.out.config(state='disabled');self.direction.set('AGUARDAR');self.probs.set('Alta 0% | Baixa 0% | Lateral 0%');self.base.set('Base histórica: -')

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
