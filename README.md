# Crypto Trading Analyzer V19 — Windows EXE

Este pacote gera automaticamente o executável Windows `CryptoTradingAnalyzerV19.exe` a partir do código Python V19.

## Como gerar no GitHub

1. Crie um repositório no GitHub.
2. Envie **todos os arquivos desta pasta** para o repositório.
3. No GitHub, abra **Actions**.
4. Selecione **Build Windows EXE**.
5. Clique em **Run workflow**.
6. Aguarde a conclusão.
7. Abra a execução concluída e, em **Artifacts**, baixe `CryptoTradingAnalyzerV19-Windows`.
8. Dentro do ZIP estará `CryptoTradingAnalyzerV19.exe`.

O `.exe` não exige Python instalado no computador Windows.

## Execução local no Linux

Para testar o código-fonte:

```bash
python3 crypto_trading_analyzer.py
```

## Observação

O aplicativo acessa APIs públicas da Binance e da Bybit pela internet. O executável não contém credenciais de API.
