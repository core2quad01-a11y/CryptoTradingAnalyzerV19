import tkinter as tk
from tkinter import ttk
from crypto_trading_analyzer_classic import App as ClassicApp
from crypto_trading_analyzer_confluence import App as ConfluenceApp


def launch(app_class):
    root.destroy()
    new_root = tk.Tk()
    app_class(new_root)
    new_root.mainloop()

root = tk.Tk()
root.title('Crypto Trading Analyzer — Escolha da Interface')
root.geometry('620x360')
root.resizable(False, False)

frame = ttk.Frame(root, padding=28)
frame.pack(fill='both', expand=True)

ttk.Label(frame, text='CRYPTO TRADING ANALYZER V19', font=('Arial', 22, 'bold')).pack(pady=(10, 4))
ttk.Label(frame, text='Escolha a interface que deseja utilizar', font=('Arial', 11)).pack(pady=(0, 22))

classic = ttk.LabelFrame(frame, text='Interface 1 — Clássica', padding=16)
classic.pack(fill='x', pady=6)
ttk.Label(classic, text='Interface anterior: ranking, direção estimada, análise histórica,\nBinance + Bybit, monitoramento e alertas.', justify='left').pack(side='left')
ttk.Button(classic, text='ABRIR INTERFACE CLÁSSICA', command=lambda: launch(ClassicApp)).pack(side='right', padx=8)

advanced = ttk.LabelFrame(frame, text='Interface 2 — Confluência', padding=16)
advanced.pack(fill='x', pady=6)
ttk.Label(advanced, text='Interface nova: score 0–100, confluência técnica,\nentrada, stop, 3 alvos, R/R e scanner avançado.', justify='left').pack(side='left')
ttk.Button(advanced, text='ABRIR INTERFACE CONFLUÊNCIA', command=lambda: launch(ConfluenceApp)).pack(side='right', padx=8)

ttk.Label(frame, text='As duas interfaces usam Binance + Bybit e podem ser escolhidas a cada execução.', font=('Arial', 9)).pack(pady=16)

root.mainloop()
