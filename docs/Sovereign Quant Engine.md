# Sovereign Quant Engine

Benvenuto nella nota centrale del **Sovereign Quant Engine**. Questa cartella raccoglie tutta la documentazione strutturata e le guide operative del tuo motore di trading automatico.

## 🗺️ Mappa della Documentazione
Naviga tra le varie guide ed i manuali operativi cliccando sui link sottostanti:

*   [[Sovereign Quant Engine Manual]]: La guida completa di riferimento per l'operatore umano del quant engine.
*   [[Guida Semplicissima]]: Spiegazione intuitiva dell'architettura multi-agente e delle metriche finanziarie tramite la metafora del ristorante (adatta a principianti).
*   [[Guida Master Completa]]: Il manuale operativo master con i dettagli di implementazione tecnica avanzata (AST, Double Monte Carlo, ecc.).
*   [[Architecture Bible]]: Le regole assolute e le invarianti di condotta dell'agente Developer (da non violare mai).
*   [[Analisi Efficacia Sovereign Quant Engine]]: Report di analisi dell'efficacia dell'infrastruttura contro il rischio di rovina.
*   [[Pipeline Deploy IRL Bybit Hetzner]]: Istruzioni fisiche dettagliate per il deployment sicuro su VPS Hetzner e broker Bybit.
*   [[Guida al Deploy IRL Sicuro]]: Sintesi in 3 fasi della scaletta di deploy reale a basso rischio.

---

## 🛠️ Struttura del Progetto (Workspace)
La repository locale è situata in `C:\Users\franc\Documents\sovereign-quant-engine` ed è sincronizzata in una repository privata su GitHub:
*   **Repository Remota:** [GitHub pomello03/sovereign-quant-engine](https://github.com/pomello03/sovereign-quant-engine)

### Elementi Chiave del Workspace:
*   `core_engine/`: Contiene la logica del Supervisor, dell'Executor Jesse, del Developer Bridge (con AST Parser e Regime Switching) e del Validator Monte Carlo (Bootstrap e Log-normal).
*   `schemas/`: I contratti dati JSON Schema immutabili della Fase 1.
*   `payload_drop/`: Cartella di scambio dati in cui il Supervisor esporta il blueprint e in cui si trova la [Dashboard Grafica Interattiva locale](file:///C:/Users/franc/Documents/sovereign-quant-engine/payload_drop/validation_dashboard.html).
*   `jesse_workspace/`: Cartella nativa di Jesse in cui l'agente Developer compila il codice della strategia.

---

## 🚀 Come iniziare subito:
1. Avvia i container con `docker-compose up -d` nella cartella del progetto.
2. Inserisci i file di specifica in `payload_drop/`.
3. Avvia la simulazione completa con `python run_simulation.py`.
4. Visualizza i grafici Monte Carlo aprendo il file `validation_dashboard.html`.
