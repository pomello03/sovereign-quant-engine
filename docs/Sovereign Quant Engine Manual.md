# Sovereign Quant Engine Manual
## Guida per l'Operatore Umano

Questo manuale guida l'operatore umano nella comprensione, configurazione ed esecuzione quotidiana del Sovereign Quant Engine.

## 1. Filosofia del Sistema

Il sistema si basa sulla separazione rigorosa delle responsabilità. Invece di affidare a un unico agente AI la scrittura e la validazione del codice, abbiamo implementato tre ruoli specialistici indipendenti:
- **Alpha Generator**: Cerca le inefficienze dei mercati.
- **Risk Analyst**: Protegge la cassa impostando vincoli rigidi.
- **Context Monitor**: Rileva la volatilità e lo stato macro del mercato.

Lo **Chef Supervisor** analizza le loro raccomandazioni e applica il **Bias di Rovina**: se la strategia presenta una probabilità stocastica di superare il drawdown massimo impostato, la proposta viene bloccata immediatamente.

## 2. Il Flusso dei Dati (I file JSON)

I contratti formali tra gli agenti sono definiti dai file JSON contenuti in `payload_drop/`:
- **`alpha_spec.json`**: Contiene la definizione dei segnali tecnici e le condizioni d'ingresso/uscita della strategia.
- **`risk_constraints.json`**: Contiene le regole di money management (drawdown massimo, stop loss, take profit e sizing).
- **`context_regime.json`**: Contiene i dati dello stato del mercato (trend bullish/bearish, volatilità, volume).
- **`strategy_blueprint.json`**: Il documento finale emesso dal Supervisor che unisce le tre specifiche e riceve lo stato `APPROVED`.

## 3. Setup e Accensione dell'Infrastruttura

Per eseguire il motore e salvare lo storico candele per il backtesting, PostgreSQL deve essere online.

### Passo 1: Avviare i container Docker
Esegui questo comando nella cartella principale del progetto:
```bash
cd C:\Users\franc\Documents\sovereign-quant-engine
docker-compose up -d
```

### Passo 2: Verificare lo stato dei servizi
Assicurati che il database Postgres sia correttamente in esecuzione:
```bash
docker ps
```
*(Dovresti vedere `postgres:15-alpine` nello stato `Up`).*

## 4. Eseguire la Pipeline di Validazione

Puoi testare l'intera pipeline logica ed eseguire i test Monte Carlo con un singolo comando:
```bash
python run_simulation.py
```
**Sotto il cofano:**
1. Il Supervisor legge ed esegue il parsing sintattico delle condizioni.
2. Se approvato, il Developer Bridge scrive il codice Python in `jesse_workspace/strategies/SovereignStrategy/`.
3. Il Validator lancia il backtest Jesse e avvia lo stress test Monte Carlo a 1.000 iterazioni.

## 5. Visualizzare i Riscontri Grafici

### Opzione A: Dashboard di Validazione Interattiva (Inclusa)
Fai doppio clic sul file sul tuo computer per aprirlo in un browser:
[validation_dashboard.html](file:///C:/Users/franc/Documents/sovereign-quant-engine/payload_drop/validation_dashboard.html)

La dashboard ti mostrerà:
- **L'Equity Curve Media** attesa.
- **10 percorsi Monte Carlo casuali** per stimare la dispersione.
- **Risk of Ruin**: la probabilità di fallimento.

### Opzione B: Connessione Grafica con Jesse Trade Dashboard
Per visualizzare l'interfaccia interattiva ufficiale di Jesse:
```bash
cd jesse_workspace
jesse make-ip
```
Inserisci l'IP e il token generato in [https://jesse.trade/dashboard](https://jesse.trade/dashboard).

## 6. Glossario Essenziale delle Metriche

- **Sharpe Ratio:** Rapporto rendimento/rischio. Target reale: $\ge 1.5$.
- **Max Drawdown (DD):** Massima perdita registrata dal picco. Limitato al $2.0\%$ per sicurezza estrema.
- **Profit Factor:** Guadagno lordo / perdita lorda. Target reale: $> 1.3$.
- **Risk of Ruin:** La probabilità stimata tramite Monte Carlo che la strategia superi il drawdown limite impostato.
