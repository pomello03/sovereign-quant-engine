# PROJECT_STATE

**Aggiornato:** 2026-08-03 · **Branch:** `audit/p0-operational-truth` · **HEAD:** `ee61f32`
**Regola di questo file:** nessuna affermazione non dimostrata. Ogni riga qui è stata eseguita o letta.

---

## Stato corrente in una frase

Il pipeline ha certificato `PASSED`, con `risk_of_ruin: 0.0` e cinque iterazioni di ottimizzazione,
una strategia che su cinque anni di candele reali **non apre nemmeno una posizione** (V10).

## Decisioni prese

| # | Decisione | Data | Conseguenza |
|---|---|---|---|
| D1 | **Venue: Bybit** | 2026-08-03 | `routes.py:5` (`'Binance Perpetual'`) va allineato |
| D2 | **Strumento: spot** | 2026-08-03 | niente leva/liquidazione/funding; `entry_short_conditions` non eseguibile; layer di esecuzione ~5 giorni invece di ~5 settimane; fee 0.1 % per lato |

---

## Risultati verificati in questa sessione

### V1 — Nessun backtest reale è mai stato eseguito
```
python -c "import jesse"     → ModuleNotFoundError: No module named 'jesse'
which jesse                  → (vuoto)
```
`mcp_executor.py:128` verifica `shutil.which("jesse")`; il ramo `:175-181` ritorna
`status: "SUCCESS"` con metriche sintetiche. Verificato eseguendo `MCPJesseRunner.run_backtest()`:
`status = SUCCESS`, `stdout = "Mock execution: Jesse CLI not installed/found in system path."`
Il dict ritornato ha chiavi `['status','metrics','stdout','stderr']` — nessun campo di provenienza.

### V2 — Il verdetto è una funzione dei parametri di rischio, non del mercato
Eseguito variando solo il blueprint, nessuna candela letta:

| pos_size % | max_dd | sharpe | profit_factor | risk_of_ruin | verdetto |
|---|---|---|---|---|---|
| 2.0 | −12.0 | 1.8 | 2.0 | 100.00 % | FAILED |
| 1.0 | −6.0 | 1.8 | 2.0 | 99.60 % | FAILED |
| 0.5 | −3.0 | 1.8 | 2.0 | 65.00 % | FAILED |
| 0.25 | −1.5 | 1.8 | 2.0 | 11.80 % | FAILED |
| 0.125 | −0.75 | 1.8 | 2.0 | 0.10 % | **PASSED** |

Riproduce entro il rumore Monte Carlo l'`optimization_history` committato in
`payload_drop/validation_report.json` (100 / 99.40 / 63.70 / 11.70 / 0.00).
Sharpe e profit factor sono costanti: dipendono solo da `stop_loss_value` (`mcp_executor.py:159, 165`).

### V3 — Il blueprint promosso non è eseguibile su un exchange reale
`payload_drop/strategy_blueprint.json` → `max_position_sizing_pct: 0.125`.
Su 1000 € = 1,25 € di rischio per trade. Il minimo notional di Bybit v5 è 5 USDT
(`minOrderQty=0.001` BTC, `minNotionalValue=5`, verificato via API pubblica da un agente di audit).

### V4 — Il gate anti-falso-positivo ha polarità invertita (P0)
`_parse_jesse_output` (`mcp_executor.py:293-299`) ritorna 5 chiavi e **mai** `trade_returns`.
`run_monte_carlo` (`quant_validator.py:136-138`) senza `trade_returns` → `parametric_lognormal`.
`validate_with_monte_carlo` (`:82-83`) rifiuta tutto ciò che non è `bootstrap`.

Eseguito con uno stdout Jesse plausibile (Sharpe 3.1, DD −1.2 %, 63 trade):
```
simulation_mode          = parametric_lognormal
validate_metrics         = True
validate_with_monte_carlo = False      ← RIFIUTATO
```
Stessi vincoli, metriche mock: `mode = bootstrap`, verdetto `True` ← **ACCETTATO**.

**Un backtest reale non può superare il gate. Solo il mock può.**

### V5 — Il gate statistico è soddisfatto da due costanti
`_mock_trade_returns()` (`mcp_executor.py:18-28`) produce 40 campioni con due soli valori distinti
(`0.00125`, `-0.001375`, verificato sul JSON committato). Il docstring dichiara il movente:
*"so the validator exercises the unbiased bootstrap path"*.
Risultato: `simulation_mode="bootstrap"`, `real_trades_used=40`, `validate_with_monte_carlo=True`.

### V6 — `validate_metrics` è fail-open, e un test lo sancisce
Con tutte le metriche `None` e vincoli severi (Sharpe ≥ 3.0, PF ≥ 5.0) ritorna `True`.
Ogni gate è `if X is not None` (`quant_validator.py:34-55`).
Test che lo certifica: `tests/test_edge_cases.py::test_validate_metrics_none_values_pass`.

### V7 — Esecuzione di codice arbitrario da `alpha_spec.json` (P0)
PoC eseguito, marcatore benigno creato nello scratchpad:
```
indicators[0].params = {"period": "14, __x=open(r'...','w').write('RCE ...')"}
1. jsonschema.validate                   → PASSA  (nessun pattern/additionalProperties)
2. riga generata: lambda: ta.rsi(self.candles, period=14, __x=open(...)...)
3. il file generato è Python VALIDO      → SI
4. import del modulo                     → ok
5. accesso alla property rsi             → 50.0   ← valore normale
   MARCATORE CREATO: True
```
Il payload esegue al **primo accesso all'indicatore** (in un backtest: la prima candela),
non all'import. `_safe_indicator` avvolge la lambda in `try/except`, quindi la property
restituisce il fallback e **nulla appare nei log**. Il vettore è `developer_bridge.py:262-263`,
f-string grezza; il parser AST (`:183-235`) protegge solo `entry_*_conditions`, non gli indicatori.

**Non è sfruttabile oggi** perché nessuno importa il modulo generato (Jesse assente).
Diventa attivo al primo `pip install jesse`.

### V8 — Un tool di sviluppo mancante è indistinguibile da un bug di codice
Prima run, senza `ruff` installato:
```
STATUS: COMPILATION_ERROR
STDERR: No module named ruff / vulture / xenon
```
`mcp_executor.py:120-125` mappa qualunque exit ≠ 0 dell'audit su `COMPILATION_ERROR`.
`execute_closed_loop` rigenera e ritenta 3 volte codice perfettamente valido, poi fallisce.

### V12 — Il codice generato non poteva girare in Jesse. Mai.
Due difetti fatali, entrambi invisibili finché nessuno eseguiva davvero:

1. **Collisione di nomi con il framework.** La strategia generata definiva
   `hyperparameters` come `@property` che ritorna un dict. `Strategy.hyperparameters()`
   è un **metodo** di Jesse, invocato durante il setup della route:
   `TypeError: 'dict' object is not callable`, prima ancora della prima candela.
   Rinominato in `regime_params`.
2. **Ordini di uscita nel posto sbagliato.** `self.take_profit` dentro `go_long()`
   è rifiutato su spot da Jesse (`InvalidStrategy`). Spostati in `on_open_position()`,
   e prezzati sull'entry **eseguito** invece che su quello inteso.

Il pipeline ha generato per mesi codice che non poteva essere eseguito, e ha
riportato `SUCCESS` ogni volta — perché il percorso mock non lo eseguiva.

### V11 — Le commissioni si mangiano l'edge (controllo su 120 trade reali)
`ControlStrategy` (stessa struttura di rischio, condizione che si attiva) su
1.402.560 candele a 1 minuto, `sha256:252993559a78e464…`, 2024-01-01 → 2026-07-01:

| | |
|---|---|
| PnL lordo | **+2081.64** |
| commissioni | **−2559.88** |
| PnL netto | **−478.24** |
| commissioni / edge lordo | **1.23** |
| max drawdown | **−29.00 %** (limite dichiarato: 2.0 %) |
| nozionale massimo | **125.08 %** dell'equity, su spot senza leva |

Serve anche come controllo dello strumento: 120 trade contro 0 di `SpecStrategy`,
stesso simulatore, stesse candele. **L'harness funziona; la differenza è la strategia.**

### V10 — La strategia certificata PASSED non apre nessuna posizione (P0-1)
Primo dato di mercato mai entrato nel progetto: **11.115 candele Bybit spot BTCUSDT 4h**,
2021-07-05 → 2026-07-31, completezza 100 %, 0 gap, 0 righe OHLC invalide,
`sha256:42a8f62fd9f5236e…` (`research/data/bybit_spot_BTCUSDT_240.meta.json`).

```
rsi(14) < 30                 561 barre  (5.07 %)
close > sma(50)             5609 barre  (50.69 %)
rsi(14) < 30 AND close>sma     0 barre  ← la condizione d'ingresso effettiva
```

Strutturale, non una questione di soglia: RSI minimo osservato con `close > sma` = **36.59**
(serve < 30); `close/sma` massimo osservato con `RSI < 30` = **0.9811** (serve > 1.00);
**corr(RSI, close/sma) = +0.870** — le due condizioni misurano la stessa cosa.
Se fossero indipendenti ci si aspetterebbero ~284 barre; se ne osservano 0.

`payload_drop/validation_report.json` certifica questa strategia `PASSED` con
`risk_of_ruin: 0.0` e cinque iterazioni di ottimizzazione.
Dettaglio in [`research/RESULT_P0-1.md`](research/RESULT_P0-1.md).

### V9 — Baseline dei test
`pytest -p no:anyio -q` → **91 passed in 2.59s**. I test esercitano un percorso di metriche
diverso da quello di produzione: `PYTEST_CURRENT_TEST` disattiva audit e formattazione
(`mcp_executor.py:50, 144`, `developer_bridge.py:68`).
La CI (`.github/workflows/sqe_audit.yml`) esegue **solo** `bin/sqe-audit.sh`, nessun pytest.

---

## Comandi eseguiti

```bash
git checkout -b audit/p0-operational-truth        # branch di lavoro, main intatto
pip install pytest jsonschema ruff vulture xenon  # nessuno era installato
pytest -p no:anyio -q                             # 91 passed
python -m graphify ...                            # graphify-out/ (865 nodi, 1344 archi)
```
Più tre script di verifica nello scratchpad (non nel repo): `proof_p0.py`, `verify_r01_r02.py`.

**Nessun file del repository è stato modificato.** `git status` → solo `.claude/` e `graphify-out/` untracked.

---

## Blocchi

| # | Blocco | Natura | Sblocco |
|---|---|---|---|
| B1 | Jesse non installato, zero candele reali nel DB | **Ambiente** | `pip install jesse` in venv isolato + `jesse import-candles` |
| B2 | Nessun dato di mercato mai osservato dal progetto | **Conoscenza** | dipende da B1 |
| B3 | Nessuna decisione presa sul venue di esecuzione (`routes.py:5` = Binance Perpetual, i `docs/` dicono Bybit) | **Decisione umana** | una riga di risposta dall'owner |
| B4 | Nessuna decisione su spot vs derivati per il canary | **Decisione umana** | cambia il costo del layer di esecuzione da ~5 giorni a ~5 settimane |

B1 non è stato risolto in questa sessione perché installare Jesse nel venv principale è
una modifica d'ambiente irreversibile con effetti collaterali noti (pinna `pytest~=6.2.5`,
trascina Postgres/Redis/Ray) e **attiva il vettore V7**.

---

## Prossimo passo preciso

Ottenere il primo array di trade reali del progetto, **fuori dal pipeline**, in venv isolato,
con una strategia scritta a mano. Fuori dal pipeline aggira sia V7 sia l'audit gate,
quindi non richiede alcun fix preventivo.

```bash
python -m venv .venv-jesse && source .venv-jesse/Scripts/activate
pip install jesse
jesse import-candles "Binance Perpetual Futures" BTC-USDT 2023-08-01
# poi jesse.research.backtest() su una strategia scritta a mano
```

Tre numeri decidono il resto del progetto:
`n_trades` (< 30 → non c'è nulla da validare), `max_drawdown` a sizing 1-2 %
(un ordine di grandezza sopra il 2 % → il mandato è incompatibile col dominio),
expectancy netta per trade (< 0.02 % → la strategia vive dentro le fee).

---

## Cosa NON è stato verificato

- Le regex di `_parse_jesse_output` contro l'output reale di Jesse. Mai confrontate con una tabella vera.
- Il comportamento del plugin live di Jesse (wheel binario chiuso, non leggibile).
- Qualunque affermazione sulla performance della strategia. Non esiste un solo dato di mercato.
- Se `rsi < 30 AND close > sma` produca ≥ 30 trade su BTC 4h. Ignoto.
