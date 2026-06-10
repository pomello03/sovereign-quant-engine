# Progress Log — Dashboard Redesign

## 2026-06-10

### Fase 1 — Setup ✅
- Letti DESIGN_DASHBOARD.md, quant_validator.py, optimizer.py, test_validator.py, test_optimizer.py, mcp_executor.py.
- Verifica path: nessun path estraneo nel codice (dettagli in findings.md).
- Verifica Node/Vite: assente dal repo, nulla da rimuovere (web_dashboard/ è FastAPI, lasciato intatto).
- Creati task_plan.md, findings.md, progress.md.

### Fase 2 — Backend ✅
- `run_monte_carlo`: aggiunto `collect_trajectories` (default 0) → `equity_trajectories` + `drawdown_trajectories` nel risultato (punti arrotondati, max N traiettorie).
- `generate_report`: nuovi param opzionali `optimization_history`, `strategy_code`, `blueprint`, `mc_results`; report arricchito con `optimization_history`, `strategy_code`, `strategy_blueprint`, `backtest_equity_curve`, `backtest_drawdown_curve`.
- `_generate_html_dashboard`: riscritto — legge `core_engine/templates/dashboard.html`, inietta JSON sul segnaposto, scrive HTML + copia `dashboard_app.js` in payload_drop.
- `optimizer.py`: storico iterazioni registrato (params, metriche, MC, verdict); MC eseguito una sola volta per iterazione e passato a generate_report via `mc_results`; legge il codice strategia generato per il drawer.
- `run_simulation.py`: passa `blueprint` e `strategy_code` a generate_report.

### Fase 3 — Frontend ✅
- Creato `core_engine/templates/dashboard.html` (guscio statico zinc-950 glassmorphic, sidebar, bento grid, 2 canvas, code drawer, CDN: Tailwind/Chart.js/Lucide/Google Fonts).
- Creato `core_engine/templates/dashboard_app.js` (render metriche/verdict/params, stepper interattivo con vista per iterazione, grafici equity+drawdown con traiettorie backend, fallback parametrico client-side, syntax highlighting base).

### Fase 4 — Test isolati ✅
- `pytest -p no:anyio tests/test_validator.py` → 14/14 PASS (10 esistenti + 4 nuovi).
- `pytest -p no:anyio tests/test_optimizer.py` → 6/6 PASS (5 esistenti + 1 nuovo).
- Nuovi test: traiettorie MC (count/lunghezza/range), report con history/code/blueprint, artefatti HTML+JS generati con dati iniettati, history registrata dall'optimizer.

### Fase 5 — Gate finale ✅
- Suite completa `pytest -p no:anyio -v`: **66/66 PASS** (61 preesistenti + 5 nuovi).
- Audit statico `./bin/sqe-audit.sh`: **PASSED** (ruff/vulture/xenon OK).
- `python run_simulation.py`: pipeline E2E OK — optimizer converge (iterazione 4, pos size 0.25%),
  dashboard generata con 50 traiettorie + stepper a 4 nodi. Artefatti verificati in payload_drop/.

## 2026-06-10 — Hardening Debug 5 Vulnerabilità ✅

- **Vuln 1** (stale signal): `state_io.py` → `atomic_write_json` (tmp+os.replace+fsync) e
  `read_json_fresh(max_age_seconds)` con `StaleStateError`. Supervisor: param `max_spec_age_seconds`
  (freshness su alpha_spec), scrittura blueprint atomica. Validator: scrittura report atomica.
- **Vuln 2** (NaN/None getter): template strategia → helper `_safe_indicator`/`_coerce_number`/
  `_is_valid_number` (valida lunghezza candele, rifiuta NaN/inf, fallback per famiglia:
  rsi=50, atr=price*0.01, altri=price). `_position_qty` con guardia qty NaN/<=0.
- **Vuln 3** (concorrenza/DB): `state_io.file_lock` cross-platform (fcntl/msvcrt su sidecar `.lock`);
  `db_pool.py` → `PostgresConnectionPool` thread-safe, context manager transazionale (commit/rollback,
  scarto connessione rotta), retry con exponential backoff su SQLSTATE 40001/40P01, factory iniettabile.
- **Vuln 4** (trailing stop): riscritto in helper piccoli (`_trail_side`/`_update_peak`/`_trailing_sl`/
  `_is_new_extreme`/`_is_favorable_move`/`_should_resend_stop`): picco storico, movimento unidirezionale,
  re-invio ordine solo se variazione ≥ `TRAIL_MIN_MOVE_PCT` (0.2%).
- **Vuln 5** (look-ahead/empty trades): rimosso scaling parametrico da `abs_max_dd`; aggiunto
  `real_trades_used`; `validate_with_monte_carlo` ora richiede `simulation_mode=='bootstrap'` e
  `real_trades_used >= MIN_REAL_TRADES (30)` → strategie inattive/senza campione reale falliscono.
  Mock executor emette ≥30 `trade_returns` scalati con la position size (pipeline esercita il bootstrap).

### Gate finale
- Suite: **91/91 PASS** (66 → +25 nuovi: 9 state_io, 9 db_pool, 3 bridge, 2 supervisor freshness, 2 validator Vuln5).
- `./bin/sqe-audit.sh`: **PASSED** (ruff/vulture/xenon — incl. codice generato, refactor per rank A).
- `run_simulation.py`: converge a iter.5 (pos 0.125%), bootstrap MC, RoR 0.20%, verdict PASSED.

## Errori & Decisioni
- Decisione: template sorgente in `core_engine/templates/` (versionati), artefatti generati in `payload_drop/`. Evita che la rigenerazione cancelli il sorgente e mantiene il decoupling token-saving.
- Decisione: terminazione loop optimizer invariata (basata su `report["validation_passed"]`) per compatibilità con i mock dei test esistenti.
- Fix preesistente 1: `payload_drop/risk_constraints.json` aveva `max_drawdown_limit_pct: 3.0` che violava lo schema (max 2.0) e bloccava run_simulation al Step 1 → corretto a 2.0.
- Fix preesistente 2: l'audit ruff falliva sul codice generato (W293 righe vuote con spazi, E501 in params.py, I001 ordine import) → `developer_bridge.py`: pformat width=70, import in ordine canonico + 2 righe vuote prima della classe, helper `_strip_trailing_whitespace`.
- Node/Vite: assente dal repo (nessun package.json/vite.config) — nulla da rimuovere. `web_dashboard/` è FastAPI/Python, lasciato intatto in attesa di conferma esplicita per l'eventuale rimozione.
