# Protocollo di validazione e gate verso il live

Complementare a [`AUDIT_AND_TARGET_ARCHITECTURE.md`](AUDIT_AND_TARGET_ARCHITECTURE.md).
Nessun capitale reale può essere impegnato prima del Gate F.

---

## Parte 1 — Protocollo quantitativo minimo

Il criterio non è "dimostrare che funziona", è **il modo più economico di scoprire che non funziona**.

### Provenienza
Fonte unica, venue di esecuzione fissato **prima** del primo backtest. Minimo **36 mesi** di storia
(≈ 6570 barre 4h), finestra che termina almeno 7 giorni fa. Ogni report contiene
`data_fingerprint = {exchange, symbol, timeframe, first_ts, last_ts, n_candles, sha256}`.
**Report senza fingerprint = invalido, non entra nel registro.**

### Costi — sempre netto
- Fee taker reale del venue per lato, **letta a runtime**, mai hardcoded.
- Slippage ≥ **2 bps** su market 4h, 5 bps sopra il 90° percentile di ATR.
- Funding: `holding_hours/8 · 0.0001 · notional · segno`. Jesse restituisce 0 in backtest
  (`Position.py`: `if not jh.is_live(): return 0`, verificato nel sorgente) — va compensato a posteriori.
- Ogni metrica stampata in coppia **LORDO / NETTO**.
- **Scarto immediato se netto < 30 % del lordo**: la strategia vive dentro i costi.

### Separazione temporale
Su 36 mesi: **TRAIN 18 / VALIDATION 9 / TEST 9 sigillato**.
Il TEST si apre **una sola volta per famiglia di strategie**. Aperto due volte è bruciato: serve un
periodo nuovo o un asset nuovo. È una regola procedurale, ed è l'unica difesa contro il data snooping
che sopravvive all'automazione.

### Numerosità
Minimo **200 trade out-of-sample**. Derivato, non scelto: fissata a 0.15 la semi-larghezza accettabile
del 95%CI sullo Sharpe per-trade, `n ≈ (1.96/0.15)² ≈ 170 → 200`.
Sotto i 200 non si abbassa la soglia: si estende il periodo o si cambia timeframe.

Ogni Sharpe riportato porta il suo CI (Lo 2002, `SE = √((1+SR²/2)/n)`); ogni max drawdown porta p5/p95.
**Un numero puntuale senza intervallo non entra nel report** — è il formato stesso che produce
l'illusione di precisione. *(A n=30, SR=1.0 → 95%CI [0.562, 1.438]: ecco perché `MIN_REAL_TRADES=30`
non ha potenza statistica.)*

### Monte Carlo
- **Stationary block bootstrap** (Politis–Romano) sui rendimenti **per barra** della curva di equity,
  non per trade: il clustering vive nel tempo di mercato.
- Lunghezza media dei blocchi stimata dall'ACF (su BTC 4h attendersi **L = 20–50 barre**), riportata nel report.
- **10 000** percorsi. Orizzonte = trade attesi nel **periodo di deployment**, non `len(backtest)`.
  *(Misurato sul report attuale, variando solo l'orizzonte: RoR 0.15 % a n=40 → 6.90 % a n=250 → 55.40 % a n=2500.
  Il "risk of ruin 0.00 %" è interamente un artefatto di un orizzonte di 40 trade.)*
- Output obbligatori: mediana, **p95**, p99 del max drawdown.
- **Il gate usa il p95, mai la media.** *(Misurato: `average_max_drawdown` 13.10 % contro
  `peak_simulated_drawdown` 38.62 %. Si vive un percorso, non la media di mille.)*
- Riportare in parallelo il risultato IID: la differenza fra i due **è** la misura di quanto la
  strategia dipende dalla sequenza.

### Walk-forward
Ancorato, 6 fold: train 12 mesi / test 3, avanzamento 3.
Metriche **per fold**, mai aggregate in un numero.
Criteri: ≥ 5 fold su 6 con PnL netto > 0; nessun fold con maxDD > 2× il mediano;
**Sharpe(OOS medio) / Sharpe(IS medio) ≥ 0.5**.

Applicarlo ai parametri della **logica di ingresso**, non al position sizing — quello è
Sharpe-invariante per costruzione ed è esattamente la dimensione su cui l'ottimizzatore attuale
cerca inutilmente.

### Sensibilità parametrica
Più economica e più informativa del PBO, da fare **per prima**. Griglia a 5 punti su ±50 % per ogni parametro.
Sharpe netto positivo in ≥ 80 % dei punti; i due punti adiacenti su ogni asse valgono ≥ 60 % del picco.
**Un ottimo isolato si scarta anche se il TEST lo promuove.**

### Regimi
Partizionare il TEST in bull (rendimento trimestrale BTC > +20 %), bear (< −20 %), chop.
Minimo 30 trade per regime perché il segmento sia interpretabile; sotto, si riporta il conteggio e si
dichiara non conclusivo — non si nasconde. PnL netto > 0 in ≥ 2 regimi su 3.

### Multiple testing
`experiments.jsonl` append-only, mai cancellato, **incluse le varianti abbandonate a metà**: sono
estrazioni dalla distribuzione nulla come le altre.
Deflated Sharpe (Bailey & López de Prado 2014) con N = righe della stessa famiglia. Soglia **DSR > 0.95**.
Ordine obbligatorio: **registro prima, DSR dopo** — un DSR con N=1 è un bollino di rigore su un
numero non corretto.

Perché serve, in numeri: a n=30 osservazioni, N=30 tentativi producono `E[max SR] = 0.38` per-trade
da rumore puro, cioè **Sharpe annualizzato 3.2**. Con `max_iterations=10` × `max_retries=3` il sistema
attuale fa già 30 estrazioni per run e non ne registra nessuna.

### Baseline da battere — tutte NETTE, stesso periodo
| id | baseline |
|---|---|
| B1 | buy & hold |
| **B2** | **random entry a pari frequenza**: stesso numero di trade, stessa distribuzione di holding time, direzione 50/50, stesso SL/TP, **1000 ripetizioni** per costruire la distribuzione nulla |
| B3 | random long-only |
| B4 | esposizione costante long pari all'esposizione media |
| B5 | SMA(50) crossover nudo |

**Criterio: superare il p95 di B2 sullo Sharpe netto**, e battere B1/B3/B4/B5 su Sharpe netto **e** maxDD p95.
B2 è la più importante delle cinque ed è quella che il repo non ha.

### Criteri di abbandono — decisi ORA
L'unico momento in cui sono onesti è prima di avere i risultati.

- **A1** — 50 configurazioni registrate senza DSR > 0.95 sul TEST → si abbandona la famiglia. Non si prova la 51ª.
- **A2** — netto < 30 % del lordo.
- **A3** — Sharpe OOS < 50 % dell'IS.
- **A4** — se per ottenere 200 trade servisse accettare un drawdown superiore a quello tollerabile,
  il problema è il **mandato**: si cambia asset o timeframe, **non si stringe il sizing**.
  È esattamente ciò che l'ottimizzatore fa oggi, ed è come spegnere l'allarme antincendio.

---

## Parte 2 — Gate verso il live

Nessuna strategia passa direttamente dal backtest al capitale reale.
Ogni gate ha criteri di **uscita** e criteri di **regressione** al gate precedente.

### Gate A — Verità del dato
- **Ingresso:** repo attuale.
- **Uscita:** esiste un `result['trades']` prodotto da un backtest su candele reali, con `data_fingerprint`.
  `mcp_executor` sostituito dalla chiamata in-process; i quattro rami mock ritornano `NO_DATA`, mai `SUCCESS`.
  Campo `data_source` propagato fino alla UI; `validation_passed=True` rifiutato se ≠ `'jesse'`.
  `trade_returns` estratto dai trade reali (senza questo, R-02 rende il gate inutile).
- **Test:** un test che asserisce che un ambiente senza Jesse produce `NO_DATA` e **non** un verdetto.
  Un test che asserisce che metriche mancanti producono un fallimento, non un `True`.
- **Regressione:** se un solo percorso può ancora produrre `SUCCESS` senza dati, il gate non è superato.

### Gate B — Robustezza statistica
- **Ingresso:** A superato.
- **Uscita:** l'intera Parte 1 applicata su TRAIN+VALIDATION. Walk-forward, sensibilità, regimi,
  Monte Carlo a blocchi sul p95. Nessuna metrica lorda usata per una decisione.
- **Regressione → A:** se una metrica non è ricostruibile dai trade, o se un costo non è modellato.

### Gate C — Edge dimostrato
- **Ingresso:** B superato.
- **Uscita:** ≥ 200 trade OOS; **DSR > 0.95** con N dal registro; batte il **p95 di B2** e tutte le altre
  baseline su Sharpe netto **e** maxDD p95; walk-forward 6 fold con ≥ 5 positivi e OOS/IS ≥ 0.5;
  sensibilità ≥ 80 % della griglia positiva; ≥ 2 regimi su 3 positivi. **TEST aperto una volta.**
- **Test aggiuntivo:** rieseguire l'intero protocollo su un asset diverso e verificare che non passi per caso.
- **Regressione → B:** se una baseline non era netta, o se il TEST risulta aperto due volte, il gate è
  nullo e il periodo di TEST è bruciato.
- **Questo è il gate che deve FERMARE il progetto se l'alpha non esiste**, ed è l'unico modo di non perdere soldi.

### Gate D — Correttezza dell'esecuzione simulata
- **Ingresso:** C superato. *Prima di qualunque altra cosa:* R-07 (una sola distanza di stop),
  R-08 (clamp `qty ≤ capital·cap_notional/price`), R-13 (fallback → 0, mai capitale pieno),
  R-14/R-15 (take profit propagato, `exclusiveMinimum` sullo stop).
- **Uscita:** journal SQLite + `clientOrderId` deterministici; sequenza di boot paranoica
  (risolvi gli intenti `SENT`, cancella gli orfani, **adotta** la posizione reale — mai auto-flatten al boot);
  retry ambiguo risolto per lookup, mai per reinvio cieco; controlli sulle candele
  (freschezza `now − last_close > 1.5·timeframe → HALT`, monotonia, **niente interpolazione sui gap**);
  precisione e min notional via `load_markets()` con gate **hard**; logging strutturato + exit code.
- **Test:**
  - **Chaos test SIGKILL**, 200 cicli su testnet. Invarianti dopo ogni ciclo: (a) la posizione non ha mai
    superato il massimo consentito, (b) non esistono due ordini con lo stesso `intent_seq`,
    (c) non esistono ordini aperti non presenti nel journal.
  - **Fault injection sul timeout** in tre varianti (ordine registrato / non registrato / lookup fallita):
    al termine esiste **al massimo un** ordine con quel `clientOrderId`; nel terzo caso lo stato è `HALT`.
  - **Replay test** su candele mutate (duplicato, gap, timestamp all'indietro, serie stantia):
    nei 4 casi **nessun ordine emesso**.
- **Regressione → C:** il sizing corretto (R-07/R-08) **cambierà** le metriche del backtest.
  Il gate C va rifatto con il codice corretto, e il TEST è già bruciato: serve una finestra nuova.

### Gate E — Paper / testnet
- **Ingresso:** D superato. Chiave API **trade-only** (withdraw disabilitato lato exchange),
  IP allowlist, valore iniettato da env esterna.
- **Uscita:** **60 giorni consecutivi** di paper/testnet con chaos test attivo; risk governor come
  processo separato in funzione; console che risponde a "quanto è esposto", "perché non ha aperto",
  "il processo è vivo", "lo stato è riconciliato"; **sei allarmi attivi e nessun altro**
  (kill switch scattato, budget giornaliero esaurito, riconciliazione fallita, processo morto > 2 candele
  **con posizione aperta**, credenziali rifiutate, N ordini rifiutati consecutivi) —
  un allarme ignorabile addestra a ignorarli tutti.
- **Test:** il kill switch va **eseguito** almeno una volta con posizione aperta.
  Un kill switch mai eseguito non è un kill switch. Riavvii deliberati sotto posizione: zero duplicati, zero orfani.
- **Regressione → D:** un singolo ordine duplicato, una posizione orfana, o una divergenza non allertata.
  **Il contatore dei 60 giorni riparte da zero.**
- **Regressione → B:** se lo Sharpe realizzato in paper cade **fuori dal 90%CI** del walk-forward,
  il modello di costi è sbagliato. Non si aumenta il capitale.

### Gate F — Canary reale
- **Ingresso:** E superato. Sub-account dedicato, capitale che si è disposti a perdere **interamente**,
  **spot long-only**, un simbolo, 4h, leva nulla, approvazione umana esplicita.
- **Uscita:** 30 giorni senza incidenti **operativi** — non senza perdite: le perdite sono previste,
  gli incidenti no.
- **Test:** riconciliazione confrontata a mano con la dashboard dell'exchange, settimanalmente.
  Procedura di rotazione chiavi eseguita una volta.
- **Regressione → E:** qualunque incidente operativo (ordine duplicato, posizione fantasma,
  kill switch che non ha chiuso, divergenza di riconciliazione). Si torna a testnet,
  **non si aggiusta in produzione**.

### Gate G — Aumento del capitale
- Solo su risultati **live netti**. Incremento progressivo, mai raddoppio.
- Un mese non costituisce evidenza: il minimo è **200 trade live** o 90 giorni, il maggiore dei due.
- Regressione automatica al gate precedente su qualunque anomalia.
- **Solo dopo F** si discute di derivati, leva, multi-simbolo — e solo lì la licenza Jesse live
  o un layer di esecuzione robusto diventano una spesa razionale, perché lì i failure mode
  (liquidazione, funding, reduce-only, stop resting) sono quelli su cui riscrivere da zero è irresponsabile.

---

## Parte 3 — Assunzioni e test di falsificazione

| assunzione | perché è critica | test più economico |
|---|---|---|
| `rsi<30 AND close>sma` su BTC 4h produce ≥ 30 trade | Se no, il gate `MIN_REAL_TRADES` blocca **correttamente** e ogni PASSED odierno era prodotto solo dal mock. Cambia la diagnosi da "engine rotto" a "strategia inesistente" | Primo backtest onesto: contare `total_trades` |
| Esiste un edge **lordo**, prima ancora dei costi | È la premessa di tutto il progetto. Nessuno l'ha mai misurata | Confronto con B2 (1000 ripetizioni). ~30 righe sui trade reali |
| I rendimenti hanno persistenza del segno (giustifica il block bootstrap) | Se sono IID, il MC attuale è difendibile | ACF lag 1..20 + runs test sui segni. **15 righe** |
| Il limite DD 2 % è raggiungibile senza scendere sotto il minimo operabile | Se no, l'apparato di guardrail è auto-contraddittorio e l'ottimizzatore convergerà sempre fuori dal dominio eseguibile | Leggere il maxDD misurato a sizing 1–2 % dal primo backtest reale |
| `_parse_jesse_output` funziona contro l'output reale di Jesse | **NON VERIFICATO da nessuno.** Degrada in numeri plausibili e sbagliati, non in `None` | Irrilevante se si adotta `jesse.research.backtest()`: il parser sparisce. È di per sé l'argomento decisivo |
| Il plugin live di Jesse non fa un license check bloccante a runtime | Se lo facesse, un token scaduto impedirebbe l'avvio **con posizioni aperte** = rischio di licenza convertito in rischio di capitale | Non deducibile (wheel chiuso). Installare, bloccare `jesse.trade` in `hosts`, riavviare con posizione aperta in paper |
| L'exchange rifiuta un `clientOrderId` già usato | Se un venue non lo rifiuta, l'intero schema di retry va ripensato per quel venue | Su testnet: inviare due volte lo stesso id. **~15 minuti** |
| Il canary sarà spot long-only | Rende quasi gratuiti 6 dei 9 meccanismi (su spot il saldo **è** la posizione). Se è perpetual, il layer passa da ~5 giorni-uomo a ~5 settimane | Una domanda all'owner |
| Il DD reale è non lineare nel position sizing | È ciò che rende l'euristica dell'ottimizzatore priva di garanzia su dati veri | Con trade reali: maxDD a 4 livelli di sizing. Se fosse lineare, l'ottimizzatore sarebbe recuperabile |

---

## Parte 4 — Evidenze che farebbero abbandonare la direzione

1. **`n_trades < 30` su 36 mesi**, e le varianti ragionevoli non lo cambiano. Il progetto è
   un'infrastruttura di validazione senza oggetto da validare.
2. **La strategia non supera il p95 di B2.** Non c'è edge di timing: ciò che sembra alpha è la
   distribuzione dei rendimenti di BTC filtrata a caso.
3. **PnL netto < 30 % del lordo.** La strategia vive dentro i costi. Non si ottimizza per ridurre i trade: si abbandona.
4. **50 configurazioni registrate senza DSR > 0.95.** Il generatore sta pescando rumore, e ogni
   tentativo aumenta il valore atteso del massimo senza aumentare quello dell'edge.
5. **Il maxDD reale a sizing operabile è ≥ 10× il limite del mandato**, e per rientrarci serve una size
   sotto il minimo dell'exchange. Mandato e dominio sono incompatibili.
6. **Sharpe OOS < 50 % dell'IS in modo persistente su famiglie diverse.** Non è un problema di questa
   strategia: è un problema del metodo di generazione.
7. **Paper a 60 giorni con Sharpe fuori dal 90%CI** del walk-forward, non spiegabile dai costi.
   Il modello di mercato è sbagliato in un modo che il backtest non può catturare. Nessun capitale reale.
8. **Il chaos test produce un ordine duplicato dopo due tentativi di fix.** Non abbiamo la competenza
   operativa per gestire capitale con questo profilo di guasto, e comprarla significa comprarla in
   forma non auditabile.
