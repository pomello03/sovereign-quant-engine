# P0-1 · Primo contatto con dati reali

**Data:** 2026-08-03 · **Venue:** Bybit spot · **Strumento:** BTCUSDT · **Timeframe:** 4h
**Dati:** 11.115 candele, 2021-07-05 → 2026-07-31, `sha256:42a8f62fd9f5236e…`
**Riproduci:** `python research/fetch_bybit_candles.py && python research/count_signals.py`

---

## Il risultato

La strategia specificata in `payload_drop/alpha_spec.json` **non apre nessuna posizione.**
Non poche. Zero. In cinque anni e 11.066 barre utilizzabili.

```
LONG   rsi(14) < 30  AND  close > sma(50)   ->  0 barre
SHORT  rsi(14) > 70  AND  close < sma(50)   ->  0 barre     [e su spot non è comunque eseguibile]
```

Non è un problema di soglia, ed è verificabile senza fidarsi di questa affermazione:

| misura | osservato | richiesto |
|---|---|---|
| RSI minimo mai osservato con `close > sma` | **36.59** | < 30 |
| `close/sma` massimo mai osservato con `RSI < 30` | **0.9811** | > 1.00 |
| corr(RSI, close/sma) su 11.066 barre | **+0.870** | — |

Le due condizioni non sono indipendenti: sono **due misure della stessa cosa**. RSI e distanza
dalla media mobile leggono entrambe il momentum recente della stessa serie di prezzi, con
correlazione 0.87. Richiedere che una sia bassa e l'altra alta è richiedere che il prezzo stia
scendendo e salendo contemporaneamente.

Se le due condizioni fossero indipendenti, ci si aspetterebbero ~284 barre
(5.07 % × 50.69 % × 11.066). Se ne osservano 0.

---

## Il controllo: come sappiamo che non è l'harness a essere rotto

Uno zero non si interpreta da solo. `ControlStrategy` ha la stessa identica
struttura di rischio (stesso stop, stesso target, stesso sizing) e una condizione
d'ingresso che sicuramente si attiva — un banale incrocio con la media mobile.
Entrambe girano sullo stesso simulatore, sulle stesse **1.402.560 candele a 1 minuto**
(`sha256:252993559a78e464…`, 2023-12-01 → 2026-07-31, completezza 100 %, 0 gap).

```
SpecStrategy      2024-01-01 -> 2026-07-01      0 trade    NO_TRADES
ControlStrategy   2024-01-01 -> 2026-07-01    120 trade    misurato
```

L'harness funziona. La differenza è la strategia.

### E il controllo ha detto qualcos'altro

| ControlStrategy, 120 trade su 2,5 anni | |
|---|---|
| PnL **lordo** | **+2081.64** |
| commissioni pagate | **−2559.88** |
| PnL **netto** | **−478.24** |
| commissioni / edge lordo | **1.23** |
| max drawdown | **−29.00 %** |
| nozionale massimo | **125.08 % dell'equity** |

Tre cose che nessun documento del progetto prevedeva:

1. **Le commissioni si mangiano il 123 % del vantaggio lordo.** Una strategia
   profittevole prima dei costi e perdente dopo. Il pipeline originale non
   modellava i costi in nessun punto: il `risk_of_ruin: 0.0` committato è
   calcolato su rendimenti al lordo di tutto.
2. **Il drawdown reale è −29 % contro un limite dichiarato del 2 %.** Quattordici
   volte e mezzo. Non è la prova che il 2 % sia irraggiungibile — è la prova che
   nessuno l'aveva mai misurato su questo dominio. Va rinegoziato o dimostrato,
   non ottenuto stringendo il sizing.
3. **Il nozionale tocca il 125 % dell'equity, su spot, senza leva.** Rischiare
   il 2 % dietro uno stop al 2 % significa aritmeticamente impiegare l'intero
   conto; l'equity che nel frattempo cresce fa il resto. Conferma sperimentale
   di R-08.

`ControlStrategy` non è una proposta. È un incrocio di medie da manuale, scelto
proprio perché nessuno sarà tentato di metterlo in produzione.

## Perché conta più di quanto sembri

Questa strategia è quella che il pipeline ha certificato **PASSED**, con
`risk_of_ruin: 0.0`, cinque iterazioni di ottimizzazione documentate, e una dashboard di grafici.

Un motore che non sa distinguere una strategia da 0 trade da una strategia buona non ha un bug:
non sta misurando. Il difetto è dimostrato una seconda volta e in modo indipendente rispetto
all'audit statico — non per lettura del codice, ma per confronto con il mercato.

**Questa strategia diventa un test di regressione permanente.** Il giorno in cui il pipeline
tornasse a dire `PASSED` su un alpha_spec che produce 0 trade, il pipeline è di nuovo rotto.

---

## Cosa NON facciamo

Portare la soglia RSI da 30 a 45 produce 71 ingressi e fa "funzionare" tutto:

```
  rsi < 30:     0 barre,    0 episodi
  rsi < 35:     0 barre,    0 episodi
  rsi < 40:     4 barre,    3 episodi
  rsi < 42:    19 barre,   17 episodi
  rsi < 45:   111 barre,   71 episodi     <- tentazione
  rsi < 50:   560 barre,  275 episodi
```

Non si fa. Cercare a posteriori la soglia che produce abbastanza trade **sugli stessi dati su cui
poi si valuta** è la definizione operativa di overfitting, ed è la stessa cosa che fa
`optimizer.py` quando dimezza il position size finché il verdetto non gira. Una soglia scelta così
non è un parametro: è un ricordo dei dati.

Se si vuole cambiare la strategia, si cambia **prima** di guardare, si dichiara nel registro
esperimenti, e si valuta su una finestra mai aperta. È la Parte 1 di
[`docs/VALIDATION_AND_LIVE_GATES.md`](../docs/VALIDATION_AND_LIVE_GATES.md).

---

## Conseguenze della scelta "Bybit spot"

1. **Il lato short dell'alpha_spec non è eseguibile.** Su spot si può solo comprare e vendere ciò
   che si possiede. `entry_short_conditions` va rimosso dallo schema o marcato come
   `derivatives-only`, non lasciato lì a suggerire una capacità che non esiste.
2. **`routes.py:5` è sbagliato** — dice `'Binance Perpetual'`. Va allineato.
3. **Nessuna liquidazione, nessun funding, nessuna leva.** Sparisce un'intera classe di failure
   mode, ed è il motivo per cui il layer di esecuzione costa ~5 giorni invece di ~5 settimane.
4. **Fee di riferimento: 0.1 % per lato** (Bybit spot, non-VIP), quindi **0.2 % andata e ritorno**.
   Con take profit al 4 % e stop al 2 %, le fee si mangiano il 5 % del guadagno e il 10 % della
   perdita — non trascurabile, e oggi non modellato da nessuna parte.

---

## Stato dei tre numeri di P0-1

| numero | valore | significato |
|---|---|---|
| `n_trades` | **0** | sotto la soglia di 30: non c'è nulla da validare |
| `max_drawdown` a sizing 1-2 % | **non misurabile** | nessuna posizione aperta |
| expectancy netta per trade | **non definita** | nessun trade |

Il primo numero rende gli altri due privi di oggetto. Questo era il rischio dichiarato in
`plans/ROADMAP_TO_CONTROLLED_LIVE.md` come *"l'esito più probabile"*, ed è l'esito osservato.

**È un risultato, non un fallimento.** Costa un pomeriggio saperlo adesso; costa un layer di
esecuzione completo saperlo dopo.
