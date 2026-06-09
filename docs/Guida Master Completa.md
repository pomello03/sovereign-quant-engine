# Guida Master Completa all'Infrastruttura

Benvenuto nel manuale operativo master del **Sovereign Quant Engine**. Questo documento fornisce la guida tecnica completa per lo sviluppo, la configurazione, l'esecuzione locale e la gestione del motore di trading a ciclo chiuso.

---

## 1. Panoramica del Sistema e Architettura

Il **Sovereign Quant Engine** è un'infrastruttura integrata a ciclo chiuso (Closed-Loop) per il design sicuro, la generazione di codice, il backtesting automatizzato e lo stress testing quantitativo di strategie algoritmiche destinate al mercato delle criptovalute.

| Componente | Funzione Principale | Sicurezza & Validazione |
| :--- | :--- | :--- |
| **Supervisor** | Valida i file in ingresso ed emette il blueprint strutturato. | Verifica schemi JSON formali. |
| **Developer Bridge** | Traduce le specifiche logiche in classi Python conformi a Jesse. | AST parser whitelist. Rifiuta esecuzione di comandi o letture arbitrarie. |
| **Quant Validator** | Esegue test Monte Carlo (bootstrap e log-normale) e controlla i limiti di rischio. | Blocca strategie che superano la probabilità critica di rovina. |
| **Risk Optimizer** | Ottimizza ricorsivamente stop loss e position sizing se i limiti sono violati. | Ciclo chiuso di correzione. |

---

## 2. Dispositivi di Sicurezza Implementati

### 2.1 AST Condition Parser
Per prevenire attacchi di iniezione di codice (Code Injection) attraverso parametri non fidati, le stringhe delle condizioni tecniche (es. `RSI < 30`) non vengono mai valutate direttamente tramite `eval()` o `exec()`. Il motore utilizza un **Abstract Syntax Tree (AST) Parser** che analizza formalmente l'espressione prima della traduzione in codice Python. Qualsiasi operazione non esplicitamente autorizzata (chiamate a funzioni, importazioni di librerie, o letture di attributi di sistema) solleva immediatamente un'eccezione di sicurezza.

### 2.2 Stress Testing Monte Carlo Avanzato
Il modulo di validazione quantitativa implementa un doppio motore Monte Carlo per calcolare la probabilità di rovina (*Risk of Ruin*):
- **A. Bootstrap Non-Parametrico (Empirico):** Se il report del backtest contiene i rendimenti trade-by-trade reali, l'algoritmo esegue un ricampionamento con reinserimento preservando fedelmente la distribuzione di probabilità originaria e catturando asimmetrie ed eventi reali.
- **B. Modello Parametrico Mixture Log-Normale (Fallback):** Qualora i dati dei singoli trade non fossero disponibili, il sistema simula i rendimenti generando campioni casuali da una distribuzione asimmetrica log-normale tarata sui parametri macro (Sharpe Ratio, Win Rate, Profit Factor, numero totale di operazioni).

---

## 3. Configurazione e Avvio Operativo

### 3.1 Avvio del Database Postgres (Docker)
Per raccogliere lo storico delle candele ed eseguire i backtest di Jesse, PostgreSQL deve essere online.
1. Apri il terminale nella cartella principale del progetto:
   ```powershell
   cd "C:\Users\francesco.bonino\Documents\SQE branch"
   ```
2. Avvia i container definiti in `docker-compose.yml`:
   ```powershell
   docker-compose up -d
   ```
3. Verifica che il database sia attivo:
   ```powershell
   docker ps
   ```

### 3.2 Esecuzione della Pipeline CLI
Puoi testare l'intera pipeline logica ed eseguire i test Monte Carlo con un singolo comando:
```powershell
python run_simulation.py
```
**Cosa succede sotto il cofano:**
1. Il **Supervisor** legge le specifiche in `payload_drop/` e valida lo schema JSON.
2. Se approvato, il **Developer Bridge** genera il codice Python della strategia in `jesse_workspace/strategies/SovereignStrategy/`.
3. Il **Validator** esegue il backtest tramite Jesse ed estrae le metriche di performance.
4. Se i limiti sono violati, il **Risk Optimizer** effettua regolazioni ricorsive ed esegue nuovamente i backtest.
5. Vengono generate le simulazioni stocastiche Monte Carlo salvando i risultati in `payload_drop/validation_report.json`.

---

## 4. Visualizzazione dei Risultati

### Opzione A: Dashboard Web in Tempo Reale (FastAPI)
Per visualizzare l'interfaccia interattiva del stepper del processo, log del terminale, grafici dell'ottimizzatore:
- Fai doppio clic su `run_dashboard.bat` nella cartella principale del progetto.
- Accedi dal browser all'indirizzo `http://127.0.0.1:8000`.

### Opzione B: File Dashboard di Validazione Locale
Puoi anche aprire direttamente il file HTML statico generato sul tuo browser:
[validation_dashboard.html](file:///C:/Users/francesco.bonino/Documents/SQE%20branch/payload_drop/validation_dashboard.html)

---

## 5. Glossario delle Metriche Quantitative

- **Sharpe Ratio:** Rapporto tra il rendimento medio e la deviazione standard del rendimento. Misura l'efficienza della strategia. (Target consigliato: $\ge 1.2$).
- **Max Drawdown (DD):** La perdita massima cumulata registrata dal picco di equity. (Vincolo di sicurezza impostato nel progetto: $\le 15.0\%$).
- **Profit Factor:** Rapporto tra profitti lordi e perdite lorde. (Target minimo: $> 1.3$).
- **Risk of Ruin:** La probabilità percentuale calcolata tramite simulazione Monte Carlo che l'equity curve della strategia scenda al di sotto della soglia critica stabilita. (Soglia massima consentita: $\le 5.0\%$).
