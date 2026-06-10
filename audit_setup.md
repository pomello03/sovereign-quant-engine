# TASK: Implementazione Pipeline Static Audit per SQE

1. Installa le dev-dependencies Python: ruff, radon, xenon, vulture.
2. Crea un file bash in 'bin/sqe-audit.sh' che esegua in sequenza:
   - ruff check strategies/ --select F,E,W,I,U
   - vulture strategies/ --min-confidence 80
   - xenon --max-absolute A --max-modules A --max-absolute B strategies/
3. Rendi lo script eseguibile (chmod +x).
4. Aggiorna le regole di contesto o i file di configurazione dell'orchestratore per forzare l'esecuzione di './bin/sqe-audit.sh' prima di ogni ciclo di backtest su Jesse.
