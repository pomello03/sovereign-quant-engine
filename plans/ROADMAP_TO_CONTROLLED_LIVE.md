# Roadmap verso un live controllato

Ordinata **per dipendenza**, non per facilità. Ogni task ha un done criteria verificabile.
Riferimenti: [`docs/AUDIT_AND_TARGET_ARCHITECTURE.md`](../docs/AUDIT_AND_TARGET_ARCHITECTURE.md) ·
[`docs/VALIDATION_AND_LIVE_GATES.md`](../docs/VALIDATION_AND_LIVE_GATES.md) ·
[`PROJECT_STATE.md`](../PROJECT_STATE.md)

**Regola d'oro:** nessun task di questa lista rende il progetto più vero finché il primo non è fatto.
Rifattorizzare, cancellare codice morto o migliorare la dashboard prima di P0-1 è ottimizzare una finzione.

---

## Stato al 2026-08-03 (commit `0cd1f68`)

| | task | esito |
|---|---|---|
| ✅ | **P0-1** primo array di trade reali | **0 trade.** Vedi [`research/RESULT_P0-1.md`](../research/RESULT_P0-1.md) |
| ✅ | **P0-2** venue e strumento | **Bybit spot.** `routes.py` allineato; lo short non è eseguibile |
| ✅ | **P0-3** il mock non può più produrre un verdetto | `mcp_executor.py` riscritto, 403 → 265 righe, zero percorsi mock |
| ✅ | **P0-4** provenance | su ogni risultato; `validation_passed` richiede `data_source == 'jesse'` |
| ✅ | **P0-5** vettore RCE | chiuso a 3 livelli, 16 test di regressione |
| ✅ | **P0-6** fail-closed sulle metriche | `MissingMetricError`; default `or 100` / `or 1.5` rimossi |
| ✅ | **P0-7** ottimizzatore sospeso | non invocato da nessuna parte; loop inline della dashboard cancellato |
| ✅ | **P1-1** una sola base di rischio | `_stop_distance()` unica sorgente per sizing e stop |
| ✅ | **P1-2** clamp sul nozionale | `MAX_NOTIONAL_PCT` nel template |
| ✅ | **P1-3** schema che rifiuta valori assurdi | `exclusiveMinimum` + sign check nel Supervisor |
| ✅ | **P1-7** logging ed exit code | `run_simulation.py` esce 0/1/2/3 |
| ⬜ | **P1-4** modello di costi | fee reali già applicate nel backtest; manca slippage esplicito e la coppia LORDO/NETTO ovunque |
| ⬜ | **P1-5** Monte Carlo onesto | block bootstrap, gate sul p95 |
| ⬜ | **P1-6** registro esperimenti | `experiments.jsonl` |
| ⬜ | **P2 · P3 · P4** | invariati |

**Due risultati cambiano il seguito.** Primo: la strategia specificata non esiste, quindi P2 non ha
oggetto finché non ne esiste una — e sceglierla guardando i dati è la cosa vietata dal protocollo.
Secondo: il drawdown reale misurato è **−29 %** contro un limite di **2 %**. Il rischio "il limite
DD 2 % è incompatibile col dominio", elencato in fondo a questo documento, **si è verificato**.

---

## P0 — Verità operativa

### P0-1 · Il primo array di trade reali *(nessuna dipendenza)*
Fuori dal pipeline, venv isolato, strategia **scritta a mano**. Fuori dal pipeline aggira sia il
vettore RCE sia l'audit gate, quindi non richiede alcun fix preventivo.

```bash
python -m venv .venv-jesse && source .venv-jesse/Scripts/activate
pip install jesse
jesse import-candles "Binance Perpetual Futures" BTC-USDT 2023-08-01
# poi jesse.research.backtest() su una strategia in un file isolato
```
**Done:** esiste `scratch_real_trades.json` con `n_trades`, `max_drawdown` e l'expectancy netta per trade.
**Test:** nessuno. È una misura, non un'implementazione.
**Rischio aperto:** se `n_trades < 30`, la strategia non esiste e P1/P2 cambiano di significato.
Questo è un **risultato utile**, non un fallimento.

### P0-2 · Decisione umana sul venue e sullo strumento *(parallelo a P0-1)*
`routes.py:5` dice Binance Perpetual, i `docs/` dicono Bybit. E: canary spot o derivati?
**Done:** una riga scritta nel repo. La seconda risposta cambia il costo del layer di esecuzione da
~5 giorni-uomo a ~5 settimane.

### P0-3 · Il mock non può più produrre un verdetto *(dipende da P0-1)*
Sostituire `mcp_executor.py` con la chiamata in-process a `jesse.research.backtest()`.
I quattro rami mock ritornano `NO_DATA`, mai `SUCCESS`. Il mock e le fixture si spostano nei test.
**Done:** un ambiente senza Jesse produce `NO_DATA`; `grep -rn "SUCCESS" core_engine/` non trova
alcun percorso che la ritorni senza dati.
**Test:** `test_no_jesse_produces_no_data`, `test_missing_candles_is_not_success`.
Risolve **R-02, R-03, R-04** insieme, e cancella 403 righe.

### P0-4 · Provenance del risultato *(dipende da P0-3)*
`data_source: 'jesse'|'mock'`, `data_fingerprint`, commit della strategia, versione framework,
costi modellati, seed, config — propagati fino alla UI.
`validation_passed = True` **rifiutato** se `data_source != 'jesse'`.
**Done:** un report senza fingerprint è invalido; la dashboard mostra lo stato del dato in cima, non un badge.
**Test:** `test_report_without_fingerprint_is_rejected`.

### P0-5 · Chiudere il vettore RCE *(deve stare nello stesso commit che porta Jesse nel venv principale)*
`pattern` su `indicators[].name`, `additionalProperties: {type: number}` su `params`,
`visit_Name` che solleva su nomi non whitelisted, `ast.parse()` sul file generato prima di scriverlo.
**Done:** il PoC di `PROJECT_STATE.md` V7 fallisce alla validazione dello schema.
**Test:** il PoC stesso, come test di regressione.

### P0-6 · Fail-closed sulle metriche *(dipende da P0-3)*
`validate_metrics` solleva su metrica mancante invece di saltare il gate.
Rimuovere i default `or 100` / `or 1.5` in `run_monte_carlo`.
Cancellare `test_validate_metrics_none_values_pass`.
**Done:** `validate_metrics({})` solleva.
**Attenzione all'ordine:** senza questo, correggere R-02 **promuove** una strategia mai misurata.

### P0-7 · Sospendere l'ottimizzatore
Non correggerlo: sospenderlo. Risolve un'equazione che si è scritto da solo, e su dati reali
l'euristica non ha alcuna garanzia. Torna in gioco solo dopo che P1-1 avrà misurato se il drawdown
reale è lineare nel sizing.
**Done:** `run_simulation.py` non lo invoca; il loop inline in `web_dashboard/main.py:141-190` è cancellato
(sparisce anche R-09).

---

## P1 — Il rischio dichiarato è il rischio reale

### P1-1 · Una sola base di rischio *(dipende da P0-1)*
`developer_bridge.py:369` e `:384` devono usare la stessa distanza di stop. **Nel template**, non nel
file generato — il prossimo run lo sovrascrive.
**Done:** il rapporto rischio effettivo / dichiarato è 1.0 su tutta la griglia di ATR.
**Test:** parametrizzato su `_position_qty` con `{atr: NaN, atr: 0, pos=0, pos<0, price: 0, chiave assente}`,
asserendo `notional ≤ capital · cap`.

### P1-2 · Clamp sul nozionale *(dipende da P1-1)*
`qty ≤ capital · cap_notional / price`. **Il fix di P1-1 da solo non chiude l'esposizione**: il percorso
normale produce comunque `capital/price`. Verificato dal verificatore Execution.
**Done:** con `pos_pct=2.0` e ATR 0.5 %, il notional non supera il cap. Oggi è il 200 % del capitale.

### P1-3 · Schema che rifiuta valori assurdi
`exclusiveMinimum` su `stop_loss_value` e `max_position_sizing_pct`.
Oggi `stop_loss_value = -0.02` è **approvato**: i segni si cancellano in `tp/sl` (`supervisor.py:126`).
**Done:** `-0.02` e `0` sollevano.

### P1-4 · Modello di costi *(dipende da P0-1)*
Fee taker letta a runtime, slippage ≥ 2 bps, funding compensato a posteriori
(Jesse restituisce 0 in backtest, verificato nel sorgente).
Ogni metrica in coppia LORDO / NETTO.
**Done:** nessuna decisione viene presa su una metrica lorda.
**Perché è P1 e non P2:** con fee 0.11 % il `risk_of_ruin = 0.0` del report committato diventa 98.9 %.

### P1-5 · Monte Carlo onesto *(dipende da P0-1, P1-4)*
Block bootstrap sui rendimenti per barra, orizzonte = trade attesi nel deployment, gate sul **p95**.
**Done:** il report riporta mediana / p95 / p99 e la lunghezza dei blocchi stimata dall'ACF.
**Test:** su serie IID sintetica, block e IID devono coincidere; su serie con clustering, divergere.

### P1-6 · Registro esperimenti append-only
`experiments.jsonl`, incluse le varianti abbandonate a metà.
**Done:** ogni backtest scrive una riga. **Registro prima, DSR dopo.**
**Perché ora e non dopo:** un DSR calcolato su un registro incompleto è un bollino di rigore su un
numero non corretto.

### P1-7 · Logging strutturato ed exit code
`logging` invece di `print`; `sys.exit(1)` su FAILED.
**Done:** `run_simulation.py; echo $?` distingue PASSED da FAILED da crash. Oggi esce sempre 0.

---

## P2 — Il protocollo statistico (Gate B–C)

Applicare per intero la Parte 1 di `VALIDATION_AND_LIVE_GATES.md`.
Ordine: **baseline B2 per prima** (è la più informativa e la più economica: se non la batte, tutto il
resto è inutile), poi sensibilità parametrica, poi walk-forward, poi DSR.

Il TEST si apre **una sola volta**. Prima di aprirlo, tutto il resto deve essere passato.

---

## P3 — Layer di esecuzione (Gate D)

**Non iniziare prima che il Gate C sia superato.** Costruire il layer di esecuzione per una strategia
senza edge dimostrato è il modo più costoso di non fare nulla.

Ordine: journal SQLite → `clientOrderId` deterministici → boot paranoico → risoluzione del retry
ambiguo per lookup → controlli sulle candele → riconciliazione → risk governor come **processo
separato** → kill switch (eseguito almeno una volta con posizione aperta) → console operativa.

Test proporzionati: chaos test SIGKILL 200 cicli, fault injection sul timeout in 3 varianti,
replay test su candele mutate.

---

## P4 — Igiene (in coda, deliberatamente)

Nessuna di queste voci rende il progetto più vero. Vanno fatte, ma dopo.

`db_pool.py` + `test_db_pool.py` (335 righe, zero importatori) · `file_lock` (~60 righe, zero call site) ·
artefatti generati in `.gitignore` · 6 PDF che duplicano 6 `.md` · `.cursorrules` identico a
`.antigravity_rules.md` · `findings.md`/`progress.md`/`task_plan.md`/`audit_setup.md` ·
`bin/sqe-audit.sh` + la caccia a `sh.exe` (~83 righe, il fallback `python -m` fa già la stessa cosa) ·
`simulate_compilation_error_on_first_try` (scaffolding di test nel percorso di produzione) ·
date hardcoded in 4 punti · la deriva 2 % / 15 % / 1.5 nella documentazione ·
`simulateParametric` in `dashboard_app.js` · pytest nella CI.

Totale stimato: **−1478 righe, −1 dipendenza, −1.1 MB**.

---

## Rischi aperti della roadmap

| Rischio | Perché |
|---|---|
| **P0-1 rivela che non c'è nulla da validare** (`n_trades < 30`) | È l'esito più probabile e va accolto come informazione, non aggirato allentando i filtri |
| **Il generatore di codice sopravvive alla riscrittura** | Il modo più probabile in cui il progetto fallisce: si conserva il layer di generazione sopra il nuovo backend e si ricrea lo stesso teatro con candele vere sotto |
| **P1-1 cambia le metriche e brucia il Gate C** | Il sizing corretto **cambierà** i risultati del backtest. Se il Gate C è già stato superato, va rifatto su una finestra nuova. Motivo per cui P1-1 sta prima di P2 |
| **Il limite DD 2 % è incompatibile col dominio** | Se il maxDD reale a sizing operabile è ≥ 10× il limite, va rinegoziato il mandato — non stretto il sizing |
| **Il canary su derivati invece che spot** | Moltiplica per ~5 il costo di P3 e attiva failure mode (liquidazione, funding, reduce-only) su cui riscrivere da zero è irresponsabile |
