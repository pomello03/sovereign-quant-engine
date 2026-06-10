# Task Plan — Hardening Debug 5 Vulnerabilità

> Protocollo: memoria su disco. Aggiornare ad ogni fase, non spiegare in chat.
> (Il redesign dashboard precedente è completato — vedi sezione storica in progress.md.)

## Obiettivo
Risolvere 5 vulnerabilità di propagazione errori, concorrenza, lifecycle Jesse e deriva statistica.

## Mapping Vulnerabilità → Codice → Soluzione

### Vuln 1 — Silent State Propagation (alpha_spec stale)
- Dove: lettura di `alpha_spec.json` (Supervisor) + scrittura blueprint/report.
- Fix: `core_engine/state_io.py` → `atomic_write_json` (tmp + os.replace) e
  `read_json_fresh(path, max_age_seconds=60)` con `StaleStateError`.
- Wire: Supervisor opzione `max_spec_age_seconds` (enforce freshness su alpha_spec);
  scritture blueprint/report passano ad atomic write.

### Vuln 2 — NaN/None Propagation (getter indicatori)
- Dove: template strategia in `developer_bridge.py` (getter `rsi`/`sma`/`atr`, go_long/go_short).
- Fix: getter robusti `_safe_indicator` con validazione lunghezza candele + fallback costante;
  guardia su qty NaN/<=0 in go_long/go_short.

### Vuln 3 — Race Conditions & DB Pool
- Dove: stato condiviso (blueprint/report) senza lock; nessun pool DB.
- Fix: `state_io.file_lock(path, exclusive=True/False)` cross-platform (fcntl POSIX / msvcrt Windows,
  su sidecar `.lock`); `core_engine/db_pool.py` → `PostgresConnectionPool` thread-safe con
  context manager transazionale + exponential backoff su deadlock. (DB reale = Postgres, vedi docker-compose.)

### Vuln 4 — Trailing Stop Spamming & violazione unidirezionalità
- Dove: `_update_trailing_stop` nel template.
- Fix: memorizza picco storico (`_trail_peak`), movimento solo unidirezionale,
  chiamata API solo se variazione > soglia minima (0.2%).

### Vuln 5 — Look-ahead Bias & Empty Trades Bypass
- Dove: `quant_validator.py` run_monte_carlo / validate_with_monte_carlo.
- Fix: soglia minima trade reali (≥30); parametrico calibrato SOLO su `trade_returns` reali
  (no scaling da max_drawdown aggregato = no look-ahead); strategie inattive → validation FAIL.

## Fasi
- [x] Fase A: state_io.py + test (9 test)
- [x] Fase B: db_pool.py + test (9 test)
- [x] Fase C: template getter robusti (Vuln 2) + trailing stop (Vuln 4) + test (3 test bridge)
- [x] Fase D: quant_validator Vuln 5 + test (real_trades_used, gate bootstrap+≥30)
- [x] Fase E: wire atomic write + freshness in supervisor + atomic write report in validator
- [x] Fase F: gate finale — 91/91 test, sqe-audit PASSED, run_simulation OK (converge iter.5, bootstrap)

## Decisioni
- `fcntl` è solo POSIX (deploy Hetzner Linux). Per girare i test su Windows uso lock
  cross-platform: fcntl su POSIX, msvcrt su Windows, su file sidecar `.lock`.
- DB: Postgres (psycopg2) con import lazy + factory iniettabile → testabile senza DB reale.
- Freshness enforcement opt-in (`max_spec_age_seconds`, default None) per non rompere
  run_simulation/demo che legge spec committate; abilitabile in produzione.
