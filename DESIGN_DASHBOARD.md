# 🎨 Specifica di Design: Premium Glassmorphic Dashboard

Questo documento contiene le specifiche di design e l'architettura tecnica concordata per il redesign della dashboard stocastica del **Sovereign Quant Engine**.

---

## 🏗️ Architettura Modulare per il Risparmio dei Token
Per evitare che l'agente debba leggere e riscrivere un unico enorme file HTML + JS (sprecando migliaia di token a ogni ciclo di modifica), separiamo la dashboard in due file distinti in `payload_drop/`:
1. **`validation_dashboard.html`**: Il guscio HTML statico contenente la struttura del layout, la sidebar, i container bento-grid per le metriche e il caricamento delle librerie esterne.
2. **`dashboard_app.js`**: La logica JavaScript pura. Gestisce l'inizializzazione dei grafici Chart.js, il rendering dei dati stocastici di Monte Carlo, il controller dello stepper dell'ottimizzatore, e il caricamento dei parametri.

---

## 🎨 Layout & Stile (Premium Dark Glassmorphism)
*   **Tema Scuro**: Sfondo principale zinc-950 (`#09090b`), superfici card in zinc-900 (`#18181b`) con trasparenza (`/70` o `/80`).
*   **Stile Glassmorphic**: Bordi sottili semi-trasparenti (`border border-zinc-800/50`) ed effetto di sfocatura dello sfondo (`backdrop-blur-md`).
*   **Tipografia & Icone**: Font Outfit o Inter caricati da Google Fonts, icone Lucide caricate da CDN.
*   **Badge Semantici**: Il Verdict finale della validazione deve essere chiaramente visibile con un badge semaforico (es: `APPROVED` verde smeraldo con lieve bagliore, `REJECTED` rosso corallo).

---

## 📊 Componenti & Funzionalità

### 1. Sidebar Fissa (Sinistra)
*   **Parametri Strategia**: Elenco strutturato in card degli indicatori attivi e dei vincoli di rischio.
*   **Ottimizzatore (Stepper)**: Timeline verticale interattiva dello storico dei tentativi falliti ed approvati del `RiskOptimizer` (es: `Step 1: 2.0% size (Fallito ❌) -> Step 4: 0.25% size (Passato  )`).
*   **Interattività**: Facendo clic su un nodo della timeline, l'interfaccia deve aggiornare metriche e grafici mostrando le performance di quella specifica iterazione.

### 2. Bento Grid delle Metriche (Centro Superiore)
*   Card con layout moderno per: Sharpe Ratio, Max Drawdown storico/simulato, Profit Factor e Monte Carlo Risk of Ruin.

### 3. Grafici Stocastici (Centro Medio e Inferiore)
*   **Grafico Equity**: Curve stocastiche di Monte Carlo. Visualizza la curva di equity del backtest reale (linea spessa indaco/bianca) sovrapposta a 50 traiettorie simulate sottili e semi-trasparenti.
*   **Grafico Drawdown**: Grafico inferiore allineato per visualizzare le traiettorie dei drawdown storici e simulati.

### 4. Strategy Code Drawer (A comparsa)
*   Pannello espandibile contenente il codice Python generato per la strategia con syntax highlighting base.

---

## ⚙️ Modifiche Python Backend Richieste
1. **`core_engine/quant_validator.py`**:
   - Modificare la simulazione Monte Carlo per raccogliere 50 traiettorie di equity/drawdown simulate rappresentative.
   - Salvare in `validation_report.json` lo storico delle iterazioni di ottimizzazione (ricevuto dall'ottimizzatore).
   - Inserire il file `validation_report.json` come oggetto globale in `validation_dashboard.html` tramite iniezione sul segnaposto:
     `const SQE_REPORT_DATA = /* REPORT_JSON_PLACEHOLDER */;`
2. **`core_engine/optimizer.py`**:
   - Registrare le performance e i parametri testati ad ogni iterazione per passarli a `QuantValidator`.
