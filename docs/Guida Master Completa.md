# Guida Master Completa all'Infrastruttura

Benvenuto nel manuale operativo master del **Sovereign Quant Engine**. Questo documento fornisce la guida tecnica completa per lo sviluppo, la configurazione e il deploy sicuro del motore di trading a ciclo chiuso.

## 1. Panoramica del Sistema e Architettura

Il **Sovereign Quant Engine** è un'infrastruttura integrata a ciclo chiuso (Closed-Loop) per il design sicuro, la generazione di codice, il backtesting automatizzato e lo stress testing quantitativo di strategie algoritmiche destinate al mercato delle criptovalute.

| Componente (Nodo) | Funzione Principale | Sicurezza & Validazione |
| :--- | :--- | :--- |
| **Supervisor** | Valida i file in ingresso (payload) ed emette il blueprint strutturato. | Verifica schemi JSON formali. |
| **Developer Bridge** | Traduce le specifiche logiche in classi Python conformi a Jesse. | AST parser whitelist. Rifiuta esecuzione di comandi o letture arbitrarie. |
| **Quant Validator** | Esegue test Monte Carlo (bootstrap e log-normale) e controlla i limiti di rischio. | Blocca strategie che superano la probabilità critica di rovina. |

## 2. Dispositivi di Sicurezza Implementati

### 2.1 AST Condition Parser
Per prevenire attacchi di iniezione di codice (Code Injection) attraverso parametri non fidati, le stringhe delle condizioni tecniche (es. `RSI < 30`) non vengono mai valutate direttamente tramite `eval()` o `exec()`. Il motore utilizza un **Abstract Syntax Tree (AST) Parser** che analizza formalmente l'espressione prima della traduzione in codice Python. Qualsiasi operazione non esplicitamente autorizzata (chiamate a funzioni, importazioni di librerie, o letture di attributi di sistema) solleva immediatamente un'eccezione di sicurezza.

### 2.2 Stress Testing Monte Carlo Avanzato
Il modulo di validazione quantitativa implementa un doppio motore Monte Carlo per calcolare la probabilità di rovina (*Risk of Ruin*):

- **A. Bootstrap Non-Parametrico (Empirico):** Se il report del backtest contiene i rendimenti trade-by-trade reali, l'algoritmo esegue un ricampionamento con reinserimento preservando fedelmente la distribuzione di probabilità originaria e catturando asimmetrie ed eventi reali.
- **B. Modello Parametrico Mixture Log-Normale (Fallback):** Qualora i dati dei singoli trade non fossero disponibili, il sistema simula i rendimenti generando campioni casuali da una distribuzione asimmetrica log-normale tarata sui parametri macro (Sharpe Ratio, Win Rate, Profit Factor, numero totale di operazioni), garantendo una stima accurata della coda di rischio.

## 3. Configurazione dell'Infrastruttura

### 3.1 Blueprint del Payload (`strategy_blueprint.json`)
Il file blueprint contiene la struttura logica della strategia da testare. Esempio di schema autorizzato:
```json
{
  "strategy_name": "SovereignStrategy",
  "indicators": [
    {"name": "RSI", "params": {"period": 14}}
  ],
  "rules": {
    "entry_long": "RSI < 30",
    "exit_long": "RSI > 70"
  },
  "context": {
    "market_regime": "trending_bullish"
  }
}
```

### 3.2 Vincoli di Rischio (`risk_constraints.json`)
Questo file definisce le metriche massime tollerate dal validatore quantitativo:
```json
{
  "max_allowed_drawdown": 15.0,
  "max_risk_of_ruin": 0.05,
  "min_sharpe_ratio": 1.2
}
```

## 4. Istruzioni Operative Step-by-Step

### 4.1 Setup Iniziale
Clonare il repository e configurare l'ambiente virtuale Python:
```bash
git clone https://github.com/pomello03/sovereign-quant-engine.git
cd sovereign-quant-engine
pip install -r requirements.txt
```

### 4.2 Esecuzione dei Test Unitari
Prima di ogni deployment, validare tutti i meccanismi di sicurezza dell'AST e del validatore quantitativo:
```bash
pytest -v
```

### 4.3 Lancio della Simulazione di Pipeline
Eseguire la simulazione end-to-end (dalla generazione automatica del codice al report quantitativo Monte Carlo):
```bash
python run_simulation.py
```
Questo script genera automaticamente i file della strategia dentro `jesse_workspace/strategies/SovereignStrategy/` ed esporta i risultati quantitativi in `payload_drop/validation_report.json`.

### 4.4 Visualizzazione del Dashboard Grafico
Aprire il file `payload_drop/validation_dashboard.html` in qualsiasi browser web per visualizzare l'interfaccia interattiva con le curve di stress test Monte Carlo e il responso finale del validatore.
