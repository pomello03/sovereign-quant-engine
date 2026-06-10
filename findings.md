# Findings — Analisi Tecnica Pre-Implementazione

## Stato del codice (2026-06-10)

### quant_validator.py (attuale)
- `run_monte_carlo(metrics, num_simulations, drawdown_limit, seed)` — due modalità:
  bootstrap (se `metrics.trade_returns` non vuoto) e log-normale parametrico.
  NON raccoglie traiettorie: solo aggregati (risk_of_ruin, avg/peak drawdown).
- `generate_report(metrics, constraints, num_simulations)` — scrive
  `validation_report.json` + chiama `_generate_html_dashboard`.
- `_generate_html_dashboard` — HTML monolitico ~300 righe inline in f-string Python
  (tema slate/violet, 10 path generati client-side). DA SOSTITUIRE con template esterni.

### optimizer.py (attuale)
- `RiskOptimizer.optimize_risk_parameters(max_iterations)` — loop chiuso:
  dimezza `max_position_sizing_pct` (floor 0.1), poi riduce `stop_loss_value` (×0.8, floor 0.005).
  NON registra lo storico iterazioni. Chiama `validator.generate_report` ad ogni iterazione.

### Vincoli dai test esistenti (NON rompere)
- `test_validator.py::test_generate_report`: asserisce `loaded_report == report`
  → ogni nuovo campo del report deve essere JSON-serializzabile round-trip.
- `test_optimizer.py`: mocka `bridge.generate_strategy_code`, `bridge.execute_closed_loop`,
  `validator.generate_report`. La terminazione del loop DEVE restare basata su
  `report["validation_passed"]` (il mock la controlla). Chiamate extra a metodi reali
  del validator (run_monte_carlo) sono OK ma non devono pilotare la terminazione.
- `mcp_executor.py` salta l'audit quando `PYTEST_CURRENT_TEST` è settato.

### Conteggio test: 61 attuali (test_supervisor, test_bridge, test_executor, test_validator, test_optimizer, test_edge_cases)

## Path Hardcoded (verifica richiesta dal protocollo)
- ✅ Nessun path assoluto estraneo nel codice Python (`grep /home/|/Users/|/root/|C:\\` su *.py: zero hit nel codice;
  `mcp_executor.py` usa una lista di path noti di Git-for-Windows come fallback legittimo multi-candidato).
- ✅ I link `file:///C:/Users/franc/Documents/sovereign-quant-engine/...` in README e docs/ sono già
  uniformi al workspace corrente.
- ⚠️ `docs/Pipeline Deploy IRL Bybit Hetzner.md:63` usa `/root/sovereign-quant-engine`: INTENZIONALE
  (guida deploy su VPS Linux Hetzner), non va toccato.
- `bin/sqe-audit.sh` risolve i path relativamente a se stesso (portabile). OK.

## Node/Vite (richiesta "Eliminazione Runtimes Multipli")
- ✅ NESSUN progetto Node/Vite nel repo: zero `package.json`, zero `vite.config.*`,
  zero componenti React/Express. Niente da rimuovere.
- `web_dashboard/` è un server FastAPI Python (live monitor con SSE), NON Node.
  Referenziato dal README (§5 Monitor & Dashboard Web). Non rimosso: la richiesta
  citava esplicitamente Node/Vite. Se va eliminato anche il runtime FastAPI,
  serve conferma esplicita (azione distruttiva su componente documentato).

## Audit statico
- `bin/sqe-audit.sh` esegue ruff (F,E,W,I,U), vulture (min-confidence 80),
  xenon (max A/A/B) su `jesse_workspace/strategies/`. Eseguito da mcp_executor
  prima di ogni backtest (fuori da pytest) e manualmente come gate finale.

## Iniezione dati dashboard
- Segnaposto concordato (DESIGN_DASHBOARD.md §⚙️):
  `const SQE_REPORT_DATA = /* REPORT_JSON_PLACEHOLDER */;`
- Python sostituisce `/* REPORT_JSON_PLACEHOLDER */` con `json.dumps(report)`.
  Escape di sicurezza: `</` → `<\/` per evitare chiusura prematura del tag script.
