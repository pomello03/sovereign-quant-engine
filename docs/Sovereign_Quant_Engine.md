---
type: project
tags: [trading, quant, ai, jesse, python, mcp]
created: 2026-06-07
status: active
---

# Sovereign Quant Engine

## Descrizione
**Sovereign Quant Engine** è un framework di trading algoritmico autonomo a ciclo chiuso (closed-loop) basato su un'architettura multi-agente antagonista. Il sistema automatizza la scrittura, il backtesting, l'ottimizzazione stocastica e la validazione empirica di strategie quantitative di trading utilizzando il **Jesse Framework** e il protocollo **Model Context Protocol (MCP)** guidato da modelli Gemini 3.5.

---

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

## Caratteristiche Principali
- **Dibattito Antagonista Isolato**: Tre nodi specialisti lavorano in totale isolamento (Alpha Generator, Risk Analyst, Context Monitor) per eliminare i bias cognitivi dell'IA ed evitare l'overfitting (curve-fitting).
- **Arbitrato Conservativo (Supervisor)**: Un agente Supervisor unisce i report JSON degli specialisti dando priorità assoluta alla gestione del rischio (drawdown massimo limitato a <2% di rovina).
- **Integrazione Nativa Jesse (MCP)**: Esecuzione automatica dei backtest localmente tramite comandi CLI ed estrazione delle metriche chiave (Sharpe, Sortino, Drawdown, Profit Factor).
- **Stress-Testing Stocastico (Quant Validator)**: Validazione avanzata delle strategie tramite test di permutazione Monte Carlo e iniezione di slippage/spread aggressivi prima di qualsiasi deployment.
- **Ciclo di Autocorrezione**: Un loop closed-loop rileva eventuali errori a runtime o errori di compilazione e forza il Developer ad auto-correggersi.

---

## Stack Tecnologico
- **Orchestratore e Modelli**: Gemini 3.5 + Antigravity CLI.
- **Interfaccia e Protocollo**: Model Context Protocol (MCP).
- **Linguaggio e Framework**: Python 3.12, Jesse Framework.
- **Validazione Stocastica**: Python (SciPy / NumPy / Pandas per Monte Carlo).

---

## Architettura Multi-Agente
1. **Alpha Generator**: Cerca inefficienze e segnali d'ingresso. Output: `alpha_spec.json`.
2. **Risk Analyst**: Definisce stop loss, trailing e money management. Output: `risk_constraints.json`.
3. **Context Monitor**: Rileva regime, volume e volatilità. Output: `context_regime.json`.
4. **Supervisor**: Arbitra le specifiche e produce `Strategy_Blueprint.json`.
5. **Developer AI**: Scrive il codice Python Jesse compatibile.
6. **MCP Jesse Runner**: Esegue `jesse backtest` e restituisce i log delle metriche.
7. **Quant Validator**: Esegue stress test Monte Carlo e convalida/reinietta.

---

## 🛠️ Struttura del Progetto (Workspace)
La repository locale è situata in `C:\Users\franc\Documents\sovereign-quant-engine` ed è sincronizzata in una repository privata su GitHub:
*   **Repository Remota:** [GitHub pomello03/sovereign-quant-engine](https://github.com/pomello03/sovereign-quant-engine)

### Elementi Chiave del Workspace:
- `core_engine/`: Contiene la logica del Supervisor, dell'Executor Jesse, del Developer Bridge (con AST Parser e Regime Switching) e del Validator Monte Carlo (Bootstrap e Log-normal).
- `schemas/`: I contratti dati JSON Schema immutabili della Fase 1.
- `payload_drop/`: Cartella di scambio dati in cui il Supervisor esporta il blueprint e in cui si trova la [Dashboard Grafica Interattiva locale](file:///C:/Users/franc/Documents/sovereign-quant-engine/payload_drop/validation_dashboard.html).
- `jesse_workspace/`: Cartella nativa di Jesse in cui l'agente Developer compila il codice della strategia.
