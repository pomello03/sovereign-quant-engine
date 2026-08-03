# Audit e Target Architecture

**Metodo:** 7 ruoli indipendenti (cartografo, quant, execution, security, red team, observability,
trade study), ciascuno confutato da un verificatore avversariale indipendente, più verifica diretta
del principal engineer sui finding di punta. ~110 finding grezzi; entrano qui solo quelli confermati
o ridimensionati. Mappa strutturale da Graphify (`graphify-out/`, 865 nodi, 1344 archi, 71 community).

Riferimento allo stato verificato: [`PROJECT_STATE.md`](../PROJECT_STATE.md).

---

## 1. Verdetto

Questo non è un motore di trading, e non è nemmeno un backtester con dei bug: è un generatore di
codice che valida sé stesso.

Il "backtest" è aritmetica sui parametri di rischio (`mcp_executor.py:158`), l'ottimizzatore inverte
quella stessa moltiplicazione e chiama il risultato convergenza (`optimizer.py:130-133`), e il
controllo statistico anti-falso-positivo è soddisfatto da 40 costanti fabbricate apposta, con il
movente scritto nel docstring (`mcp_executor.py:20-24`).

Il difetto che rende ogni altro secondario è di **polarità**: `_parse_jesse_output` non estrae mai
`trade_returns`, quindi `validate_with_monte_carlo` rifiuta per costruzione ogni backtest reale e
accetta solo il mock. `PASSED` è letteralmente riservato ai dati falsi.

Non esiste alcun modello di costi: sottraendo una fee taker realistica dello 0.11 % round-trip ai
`trade_returns` committati, il `risk_of_ruin = 0.0` diventa **98.9 %**.

Il codice destinato all'esecuzione dimensiona su `ATR*2` e piazza lo stop a percentuale fissa
(`developer_bridge.py:369` vs `:384`), non ha alcun clamp sul nozionale, e non legge mai
`max_drawdown_limit_pct` — quel campo non compare in una riga eseguibile del file generato.

Il layer di esecuzione, custodia e riconciliazione richiesto dal mandato è al 100 % da scrivere.
E `alpha_spec.json`, il file di input più innocuo del sistema, è un vettore di esecuzione di codice
arbitrario (PoC eseguito, vedi `PROJECT_STATE.md` V7).

---

## 2. Mappa architetturale

### Flusso reale (unico percorso eseguibile)

```
payload_drop/{alpha_spec,risk_constraints,context_regime}.json
  │  [TRUST BOUNDARY 1 — schema JSON, presidiato solo sui tipi]
  ▼ Supervisor.validate_and_generate()            supervisor.py:43-155
  │    jsonschema :86-106 · Ruin Bias ≤2.0 :111-115 · cross-check R:R :117-131
  │    → atomic_write_json(strategy_blueprint.json) :153
  ▼ DeveloperBridge.execute_closed_loop()         developer_bridge.py:77-124
  │    ricarica blueprint da disco :89 · RIGENERA SEMPRE il codice :90
  │    _generate_params_content :146-181  → params.py
  │    _generate_init_content   :237-456  → __init__.py
  │      [TRUST BOUNDARY 2 — parser AST _translate_condition :183-235]
  │      ↳ copre SOLO entry_*_conditions.
  │        indicators[].name e .params → f-string grezza :262-274  ⇒ RCE
  ▼ MCPJesseRunner.run_backtest()                 mcp_executor.py:30-280
  │    audit statico :50-125 → COMPILATION_ERROR su qualunque exit≠0
  │    jesse assente / errore / no-candles / FileNotFound → SUCCESS + mock
  ▼ QuantValidator.generate_report()              quant_validator.py:246-302
       validate_metrics :34-55 (fail-open) → validate_with_monte_carlo :57-96
       run_monte_carlo :98-221 → validation_report.json :297 + dashboard :304-330
  ▼ [se FAILED] RiskOptimizer                     optimizer.py:32-136
       dimezza pos_sizing → rigenera → ribacktesta → rivalida
       scrive il blueprint con json.dump NUDO :69-70 (bypassa state_io e Supervisor)
```

Due entry point con logiche divergenti: `run_simulation.py` chiama `RiskOptimizer`;
`web_dashboard/main.py:141-190` **reimplementa lo stesso loop inline**, e le due copie già divergono
(il percorso web chiama `generate_report` senza `blueprint`/`strategy_code`/`optimization_history`,
quindi la dashboard mostra i vincoli invece dei parametri effettivi).

### Dove il mock passa per reale

| # | Punto | Meccanismo |
|---|---|---|
| 1 | `mcp_executor.py:175-181, 209-215, 239-245, 267-274` | quattro rami ritornano `SUCCESS` + metriche sintetiche, zero provenienza |
| 2 | `run_simulation.py:33-39` / `main.py:80` | il marcatore `"Mock execution"` vive solo in `stdout`, che la CLI stampa **solo sul ramo di fallimento** e il web non inoltra mai |
| 3 | `validation_report.json` | nessuna chiave `is_mock` / `data_source` / `provenance` |
| 4 | `templates/dashboard.html:146` | etichetta letterale **"Backtest reale"** su una curva costruita da 40 costanti; badge **APPROVED** in `dashboard_app.js:98-100` |
| 5 | `mcp_executor.py:18-28` + `quant_validator.py:82-85` | il gate progettato per accorgersene è quello che li accetta |

Il ramo 2 è il più pericoloso perché **sopravvive all'installazione di Jesse**: il match a `:209`
include `'not found'` / `'no such file'`, quindi un `FileNotFoundError` risalito da un crash reale di
Jesse viene convertito in `SUCCESS` con metriche inventate. E `compilation_error_keywords` (`:248-255`)
elenca `'traceback'` ma `:258` valuta `keywords[:5]`, che lo esclude: un crash con traceback non
innesca mai il retry.

### Confini di fiducia

| Confine | Stato |
|---|---|
| JSON in `payload_drop/` → Supervisor | **parziale**: lo schema valida i tipi, non i contenuti. `indicators[].name/params` senza `pattern` né `additionalProperties` |
| `entry_*_conditions` → codice generato | **presidiato**: il parser AST blocca `Call` e `Attribute`, ricorsione verificata con input ostili |
| `indicators[].params` → codice generato | **NON presidiato** — f-string grezza `developer_bridge.py:262-263` ⇒ RCE |
| query param HTTP → `risk_constraints.json` | **NON presidiato** — `main.py:49, 110-113`, dopo che il Ruin Bias è già passato |
| stdout di Jesse → decisione di rischio | **NON presidiato** — 5 regex fragili + validatore fail-open |
| exchange / credenziali / ordini | **INESISTENTE** — zero codice. "Nessun LLM nel percorso critico" è rispettato **per assenza**, non per costruzione |

---

## 3. Rischi

### P0

| id | titolo | evidenza | scenario di perdita |
|---|---|---|---|
| **R-01** | RCE via `alpha_spec.json` → `indicators[].params` | `developer_bridge.py:262-263`; `schemas/alpha_spec.json` senza vincoli. PoC eseguito | Il payload gira dentro il `lambda` che `_safe_indicator` avvolge in `try/except`: la property restituisce il fallback e nulla appare nei log. Inerte oggi, **attivo al primo `pip install jesse`** |
| **R-02** | Il gate ha polarità invertita: solo il mock può passare | `mcp_executor.py:293-299` (mai `trade_returns`) + `quant_validator.py:82-85`. Verificato: Sharpe 3.1 → `False`; costanti → `True` | Installi Jesse, carichi candele vere: **ogni** strategia torna FAILED. Concludi che l'alpha è cattiva. L'unico stato del mondo in cui il sistema dice PASSED è quello senza dati |
| **R-03** | Quattro percorsi ritornano SUCCESS con metriche fabbricate | `mcp_executor.py:175-181, 209-215, 239-245, 267-274` | Un operatore legge APPROVED / Risk of Ruin 0.00 % / "Backtest reale" e mette capitale su una strategia mai testata su un prezzo. Confermato da 6 verificatori su 7, l'unico finding che nessuno ha ridimensionato |
| **R-04** | Il mock è costruito per scavalcare il proprio gate | `mcp_executor.py:18-28` (docstring esplicito); report committato: `Counter({0.00125: 24, -0.001375: 16})` | Il report dichiara "bootstrap non-parametrico su 40 trade reali, rovina 0 %". Il controllo è stato disattivato dall'interno |
| **R-05** | Zero modello di costi: fee, slippage, funding, spread assenti | `grep -rniE '(fee\|slippage\|funding\|commission\|spread)'` su `core_engine/`, `schemas/`, `payload_drop/` → 0 hit | Applicando un costo per-trade ai `trade_returns` committati: RoR 0.15 % (0) → 24.4 % (0.05 %) → **98.9 % (0.11 %, fee taker realistica)**. L'expectancy passa da +0.020 % a −0.090 %. Selezionare su metriche lorde è **anti-correlato** con la profittabilità netta |
| **R-06** | L'ottimizzatore risolve un'equazione scritta da sé stesso | `mcp_executor.py:158` + `optimizer.py:130-133` | Sweep riprodotto tre volte: 2.0 → 1.0 → 0.5 → 0.25 → **0.125 PASS**. Esattamente `len(optimization_history)` nel report. Su dati reali il drawdown non è lineare nel sizing: l'euristica non ha alcuna garanzia |
| **R-07** | Sizing e stop su basi di rischio diverse nello stesso trade | `developer_bridge.py:369` (`atr*2`) vs `:384` (`price*(1-sl)`) | Rischio effettivo / dichiarato = `(price·sl)/(2·ATR)`. Misurato: ATR 0.3 % → **0.417 % del capitale e notional al 20.8 %**. L'errore è massimo in **volatilità compressa**, cioè nei regimi che precedono le espansioni. Confermato da 4 verificatori. Fix = una riga |
| **R-08** | Nessun clamp sul nozionale | `schemas/risk_constraints.json` (`maximum: 5.0`, nessun minimo) vs `developer_bridge.py:370` | Con `pos_pct=2.0`: notional 100 % del capitale a ATR 1 %, **200 % a ATR 0.5 %**. Su `routes.py:5` = Binance Perpetual, è leva 2x dal primo trade su un blueprint che dichiara 2 %. Nessuno dei fix proposti dai ruoli lo corregge |
| **R-09** | Il guardrail di drawdown si disattiva da una query string | `main.py:49, 110-113`, CORS `allow_origins=['*']` + `allow_credentials=True` a `:20-26` | Verificato: `?drawdown_limit=99` fa passare una strategia con DD simulato del 73.86 %. GET non autenticata con effetti collaterali che lancia subprocess `shell=True` |

### P1

`R-10` `validate_metrics` fail-open, con test che lo sancisce — diventa promozione di una strategia
mai misurata **nell'istante in cui si corregge R-02 senza correggere questo**. Aggravante: il parser
non degrada a `None`, degrada a **numeri plausibili e sbagliati** (con escape ANSI: `sharpe=31.0`;
con locale europeo il drawdown dell'8,5 % sparisce). ·
`R-11` il report committato viola il proprio limite con la curva costruita dai propri dati
(`max(backtest_drawdown_curve) = 2.177` vs limite 2.0): il gate guarda il numero inventato. ·
`R-12` le soglie Sharpe/PF documentate non esistono, i default reali sono 1.0/1.0. ·
`R-13` il fallback di sizing apre a capitale pieno (`pos_sizing=0`, `<0`, o chiave assente). ·
`R-14` `take_profit_value` validato dal Supervisor e mai propagato al codice. ·
`R-15` stop-loss negativo approvato: i segni si cancellano nel cross-check R:R. ·
`R-16` `max_drawdown_limit_pct` mai letto a runtime (`grep -c` sul file generato = 0). ·
`R-17` il "regime alignment" è un no-op: `{'default': base, regime: base}` è **lo stesso oggetto**. ·
`R-18` l'orizzonte del MC è 40 trade: a 250 trade il RoR passa da 0.15 % a **6.90 %**, oltre il gate. ·
`R-19` il gate usa la **media** dei percorsi, non un quantile: `avg 13.10 %` vs `peak 38.62 %`. ·
`R-20` bootstrap IID distrugge il clustering: su regime Markov riprodotto, P(dd>15 %) reale 0.902 vs IID 0.009. ·
`R-21` `MIN_REAL_TRADES=30` non ha potenza statistica: a n=30 con SR=1.0, 95%CI = [0.562, 1.438]. ·
`R-22` il DD 2 % è un vincolo di esito applicato come parametro di sizing. ·
`R-23` il sizing convergente è sotto il minimo operabile (Bybit `minNotionalValue=5`, verificato via API). ·
`R-24` l'ottimizzatore scavalca il Supervisor scrivendo il blueprint con `json.dump` nudo. ·
`R-25` zero logging strutturato (`grep 'import logging'` → 0 righe). ·
`R-26` il live di Jesse è un wheel binario chiuso installato senza verifica di firma. ·
`R-27` il backtester Jesse non addebita funding (`Position.py`: `if not jh.is_live(): return 0`). ·
`R-28` nessun percorso di ordini, custodia, riconciliazione, kill switch, audit log.

### P2

`R-29` MC non seedato, stato globale di `random` mutato. ·
`R-30` la CI non esegue i test; `PYTEST_CURRENT_TEST` disattiva i gate. ·
`R-31` `run_simulation.py` esce sempre 0: il verdetto non è osservabile dall'esterno. ·
`R-32` guardrail inerti: `db_pool`, `file_lock`, `StaleStateError` irraggiungibili — **tre dei cinque
temi di hardening elencati in CLAUDE.md non vengono eseguiti da nessun percorso**. ·
`R-33` deriva documentale: 2.0 % (codice) vs 15 % (`README.md:41`, `Guida Master:79`) vs 1.5 (`main.py:49`). ·
`R-34` date di backtest hardcoded in 4 punti. ·
`R-35` artefatti generati versionati, dashboard obsoleta sul disco dopo un fallimento, 4 CDN non pinnati.

---

## 4. Tenere / eliminare / manca

### Tenere
- **`core_engine/state_io.py`** — l'unico codice infrastrutturale corretto del repo. *Da collegare*: due dei tre scrittori del blueprint lo bypassano (R-24).
- **Il parser AST di `_translate_condition`** — testato con input ostili da due verificatori, regge. *Da estendere*: copre il 20 % della superficie di generazione (R-01).
- **`schemas/`** — l'idea di validare al confine è giusta; l'esecuzione è incompleta.
- **Il bootstrap non-parametrico** in `quant_validator.py` — ~15 righe concettualmente corrette, da alimentare con dati veri, rendere a blocchi, e giudicare su un quantile.
- **`plans/001-honest-backtest.md`** — l'unico documento del repo che punta nella direzione giusta.

### Eliminare
- **`core_engine/mcp_executor.py` per intero (403 righe)** — `jesse.research.backtest()` restituisce `{'metrics', 'trades'}` in-process: ~20 righe sostituiscono 403 **e** risolvono R-02, R-03, R-04 insieme.
- **`core_engine/db_pool.py` + `tests/test_db_pool.py`** (335 righe) — zero importatori nel pipeline.
- **Il loop dell'ottimizzatore inline in `web_dashboard/main.py:141-190`** — seconda implementazione già divergente. Cancellarla, non allinearla: sparisce anche R-09.
- **I default fail-open** (`quant_validator.py:34-55`, `:123-133`) e il test che li certifica.
- **`simulateParametric` in `dashboard_app.js:44-78`** — la UI reintroduce nel browser il look-ahead che il backend dichiara di aver eliminato.
- **L'ottimizzatore stesso, finché le metriche sono mock** — da sospendere, non correggere.

### Manca
- **L'estrazione dei rendimenti per-trade reali.** Senza, il pipeline non può per costruzione produrre un PASSED onesto. È il blocco che rende inutile ogni altra correzione.
- **Un campo di provenienza** (`data_source: 'jesse'|'mock'`) propagato fino alla UI, con `validation_passed=True` rifiutato se ≠ `'jesse'`.
- **Un modello di costi** — fee maker/taker, slippage, funding.
- **Un clamp sul nozionale** e una sola base di rischio.
- **Un registro esperimenti append-only** — senza, nessuna correzione per multiple testing è calcolabile.
- **Logging strutturato ed exit code.**
- **L'intero layer operativo** — client order ID, riconciliazione, kill switch, audit log, persistenza. **Da costruire dopo, non ora.**

---

## 5. Decisione su Jesse

**Usare `jesse.research.backtest()` come libreria di ricerca in-process, subito.
Non decidere adesso sull'esecuzione live.**

Il trade study proponeva di sostituire Jesse con freqtrade. Il verificatore ha smontato due dei tre
P0 su cui poggiava. Ciò che resta verificato alla fonte è che **Jesse sono due software diversi**:

- **Il backtester è MIT, in-process, e restituisce i trade.** È il pezzo che serve oggi, è gratis, ed elimina 403 righe delle nostre.
- **Il live è un wheel binario chiuso**, scaricato dietro bearer token e installato senza verifica di firma, con `'beta': True` hardcoded (`services/installer.py:70-107`). Su un mandato che pretende resistenza a ordini duplicati e riavvii, la riconciliazione diventa una promessa non auditabile.

### Condizioni perché regga
1. **Separare le due decisioni.** Adottare il backtester non impegna sull'esecuzione.
2. **Nessun tool MCP nel runtime.** L'MCP di Jesse è meterato e non ha un solo tool live; usarlo come interfaccia di esecuzione porterebbe un LLM nel ciclo. `jesse.research.backtest()` non è meterato e non fa rete.
3. **Il venue si fissa PRIMA di qualunque backtest.** Gli insiemi di exchange supportati in backtest e in live **differiscono**: si può validare su un venue e non poterlo tradare.
4. **Costi espliciti dal primo backtest.** Funding = 0 in backtest è verificato nel sorgente: va compensato a posteriori o il backtest mente come il mock.
5. **Isolamento del venv.** Jesse pinna `pytest~=6.2.5` e trascina Postgres + Redis + Ray + FastAPI.

### Modo più probabile in cui fallisce
Non fallisce sul motore. Fallisce perché **si conserva il layer di generazione codice da blueprint
sopra il nuovo backend**, ricreando lo stesso teatro con candele vere sotto. Il secondo modo, già
misurabile: il primo backtest onesto produce **meno di 30 trade**, il gate blocca correttamente, e la
conclusione naturale ("l'engine è rotto") è sbagliata — è la strategia a non esistere.

---

## 6. Target architecture

```
   FASE RICERCA (offline, LLM ammesso)     │   FASE ESECUZIONE (online, LLM VIETATO)
─────────────────────────────────────────────────────────────────────────────────
  [1] Input schema-validati                │  [6] Runtime strategia (artefatto firmato)
        │                                  │        │  hash(commit)+hash(config)
  [2] Generatore → artefatto firmato ──────┼───────▶│  verificati all'avvio, fail-closed
        │                                  │        ▼
  [3] Backtester (jesse.research)          │  [7] Risk Governor INDIPENDENTE
        │  → trades reali + costi          │        │  (processo separato)
        ▼                                  │        ▼
  [4] Validatore statistico                │  [8] Order layer
        │  block bootstrap, p95, netto     │        │  client order ID deterministici
        ▼                                  │        ▼
  [5] Registro esperimenti append-only     │  [9] Riconciliatore → [10] Journal → [11] Console
```

| # | Componente | Chi lo fornisce | Perché non può essere più semplice |
|---|---|---|---|
| 1 | **Validazione input** — `pattern` su `indicators[].name`, `additionalProperties: {type: number}` su `params`, `exclusiveMinimum` su stop e sizing | Noi (`jsonschema`, già dipendenza) | È il trust boundary più esterno. Oggi lascia passare RCE e valori negativi |
| 2 | **Generatore** — `ast.parse()` sul file **prima** di scriverlo, header + hash, whitelist AST vera (`visit_Name` solleva su nomi non whitelisted) | Noi | Il codice generato è il perimetro: un `ast.parse` a valle costa 2 righe e chiude la classe di bug che lo schema non può prevedere |
| 3 | **Backtester** — `jesse.research.backtest()` in-process | Framework (MIT) | Sostituisce 403 righe. Nessun fallback: dati assenti = `NO_DATA`, mai `SUCCESS` |
| 4 | **Validatore** — gate su metriche **nette**, block bootstrap, verdetto sul p95 | Noi (~80 righe) | Non delegabile: il MC del vendor ha issue di correttezza aperte su quella statistica |
| 5 | **Registro esperimenti** — `experiments.jsonl` append-only | Noi (~10 righe) | Senza, ogni Sharpe riportato è il **massimo su N tentativi** presentato come misura singola |
| 6 | **Runtime strategia** — verifica all'avvio che `hash(codice)` e `hash(config)` corrispondano ai registrati; se no, non parte | Framework + noi (~15 righe) | È il confine "nessun LLM nel percorso dell'ordine": l'LLM **propone**, solo un merge umano abilita. Rinforzo: `assert not any(m in sys.modules for m in ('anthropic','openai'))` all'avvio — 5 righe, chiude la porta permanentemente |
| 7 | **Risk Governor** — processo **separato**, parla direttamente alla REST dell'exchange. (a) budget di perdita giornaliera, (b) posizione locale vs exchange, (c) kill switch | Noi (~150 righe) | **La distinzione non negoziabile**: bloccare *nuove* posizioni richiede un processo **vivo** che legge un flag (fail-closed se illeggibile); chiudere le posizioni deve funzionare a processo **morto**. Con lo stesso meccanismo, il giorno del crash resta un motore che non apre più e non chiude nemmeno. Uccidere il processo **non** è un kill switch |
| 8 | **Order layer** — `clientOrderId` deterministico persistito **prima** dell'HTTP. Su timeout: **mai reinviare**, interrogare; se non trovato dopo 3 lookup, reinviare **lo stesso id** | Framework o ccxt + noi (~80 righe) | L'unica risposta corretta a "non so" è "chiedi"; se non puoi chiedere, "fermati". Mai "riprova" |
| 9 | **Riconciliatore** — su spot `fetch_balance()` (il saldo **è** la posizione). Ogni divergenza si risolve in favore dell'exchange ed è un evento **allertato** | Noi (~60 righe spot) | Lo stato locale è una cache. Una riconciliazione che corregge senza allertare nasconde il bug che l'ha causata |
| 10 | **Journal** — SQLite WAL (stdlib), tabella `events(ts, kind, payload)`. Ogni intento, ogni risposta, ogni decisione **incluso lo SKIP con il motivo** | Noi (~5 righe) | Il campo "motivo" è ciò che risponde a "perché non ha aperto", oggi impossibile |
| 11 | **Console** — un endpoint `SELECT ... LIMIT 200` + pagina statica in polling a 5s. Zero CDN, zero SSE | Noi (~200 righe) | Il polling si riprende da solo dopo una disconnessione, SSE no. Deve funzionare quando tutto il resto è giù |

**Non costruire:** microservizi, message bus, Prometheus/Grafana, un secondo dashboard, PBO/CSCV,
`STRICT_MODE` configurabile, un exchange adapter generico.
Un operatore, una strategia, dodici numeri, un file.

---

## 7. Alternative scartate

| Alternativa | Perché scartata |
|---|---|
| Sostituire Jesse con freqtrade | Il verificatore ha smontato 2 dei 3 P0 su cui poggiava la raccomandazione. Il backtester Jesse è MIT e in-process: il costo di migrazione non è giustificato prima di avere un solo dato reale |
| `STRICT_MODE` come env flag (proposta GLM) | Sovra-ingegnerizzato: un env var che disattiva la sicurezza è un'altra cosa da sbagliare. Il fix corretto è che il mock non esista nel percorso di produzione |
| Correggere l'ottimizzatore | Non è un componente da correggere: sta risolvendo un'equazione che si è scritto da solo. Va sospeso finché le metriche non sono reali |
| Adottare `SovereignStrategy_v2.py` (GLM) | Il suo valore è ignoto finché non la si backtesta su dati veri. Copiarla prima di avere l'harness è ottimizzare alla cieca |
| PBO / CSCV (López de Prado ch.12) | La sensibilità parametrica su griglia è più economica e più informativa, e va fatta prima |
| Microservizi / event bus / Kubernetes | Nessuna necessità dimostrata. Un operatore, un processo, un database |

---

## 8. Contraddizioni fra ruoli

**Il fallback di sizing: quale trigger?** Cartografo, Security e Red Team affermano che il cold start
(ATR NaN) porta a `qty = capital/price`. Il verificatore Execution **ha eseguito il codice** e mostrato
che nessuno di quei percorsi ci arriva: `_safe_indicator` restituisce `price*0.01`, e il percorso
**normale** produce lo stesso numero per una strada diversa. Il Red Team ha invece dimostrato che
`pos_sizing=0`, `<0` e chiave mancante ci arrivano davvero.
→ Il fix proposto dai ruoli (`return 0.0`) **non chiude** l'esposizione. Serve il clamp di R-08.
→ Test risolutivo: unit test parametrizzato su `_position_qty`, asserendo `notional ≤ capital·cap`. 20 righe.

**R-09 è P0 o P1?** Cartografo e Security lo danno P0; Observability ha **falsificato la persistenza**
della modifica. Tenuto P0 per il bypass **entro la run**, che è deterministico e verificato.

**Finding confutati** (utili, non spazzatura): la premessa "date di backtest nel futuro" di R-34
(oggi 2026-08-03, la finestra è nel passato); il trigger cold-start di R-13; la severità P0/P1 di R-29
(la banda instabile è a pos=0.2, che l'ottimizzatore salta).
