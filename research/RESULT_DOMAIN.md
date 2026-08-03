# Misura del dominio, ed EXP-001

**Data:** 2026-08-03 · **Dati:** Bybit spot BTCUSDT, `sha256:42a8f62fd9f5236e…` (4h) e
`sha256:252993559a78e464…` (1m) · **Finestra:** 2024-01-01 → 2026-07-01
**Riproduci:** `.venv-jesse/Scripts/python.exe research/measure_domain.py` e `research/run_prereg_exp001.py`

Queste misure non riguardano una strategia. Riguardano il **campo di gioco**: quanto si muove
lo strumento, quanto costa operarci, e cosa produce entrare a caso. Sono i numeri contro cui
qualunque idea va confrontata, e non dipendono dall'avere un'idea.

---

## 1.1 · Quanto scende il Bitcoin da solo

```
storia completa 2021-07 → 2026-07      max drawdown  77.02%
finestra di test 2024-01 → 2026-07     max drawdown  53.44%   (e il periodo chiude a +38.5%)

BTC sta più del  2% sotto il proprio massimo il 91.6% del tempo
BTC sta più del 10% sotto il proprio massimo il 58.2% del tempo
```

Il secondo blocco è quello che conta. **Lo strumento stesso passa il 91.6 % del tempo più del
2 % sotto il proprio massimo.** Una strategia long-only che tiene BTC eredita quel drawdown
scalato per la propria esposizione. Per arrivare a un drawdown di conto del 2 % contro un
drawdown dello strumento del 53 % servirebbe un'esposizione del ~4 %: su 1000 € sono 40 €,
e con uno stop al 2 % l'ordine vale 0,80 € — sotto il minimo di 5 USDT di Bybit.

Il limite del 2 % e l'exchange non possono essere soddisfatti insieme. Non è severità: è
un'equazione senza soluzione.

---

## 1.2 · Le commissioni, accanto ai movimenti disponibili

Giro completo: **0.200 %** (0.1 % per lato).

| durata | movimento mediano | P(movimento > commissioni) | rapporto |
|---|---|---|---|
| 1 barra (4h) | 0.45 % | 74.7 % | **2.2×** |
| 3 barre (12h) | 0.84 % | 84.9 % | 4.2× |
| 6 barre (1 giorno) | 1.26 % | 90.4 % | 6.3× |
| 12 barre (2 giorni) | 1.95 % | 93.1 % | 9.8× |
| 30 barre (5 giorni) | 3.22 % | 95.7 % | 16.1× |
| 60 barre (10 giorni) | 4.64 % | 97.3 % | 23.2× |

**Le commissioni non sono la barriera fondamentale — a patto di tenere le posizioni almeno un
giorno.** A 4 ore il pedaggio si mangia il 44 % del movimento mediano; a cinque giorni il 6 %.
Questa è l'unica indicazione costruttiva dell'intera misura, ed è la ragione per cui EXP-001
si è concentrato su segnali di orizzonte più lungo.

Avvertenza: sono movimenti **assoluti**. Un ingresso a caso non ne cattura nulla in media. Dicono
quanto spazio c'è sopra il pedaggio, non che quello spazio sia raggiungibile.

---

## 1.3 · La baseline B2 — entrare a caso

Ingresso a una barra 4h qualunque, stop −2 %, target +4 %, risolti sulle candele reali a 1 minuto.

```
colpisce il target per primo     35.42%
rendimento netto medio per trade  -0.0751%

componendo 120 trade, 1000 ripetizioni:
                       p5    mediana      p95
  rendimento       -47.5%     -15.5%    +44.2%
  max drawdown      17.5%      33.5%     53.1%

  P(profittevole)                       31.6%
  P(max drawdown sotto il 2%)            0.0%     <- zero su mille
```

E il numero che spiega tutto il resto:

| | win rate |
|---|---|
| ingressi casuali | 35.42 % |
| **pareggio dopo commissioni** | **36.66 %** |
| ControlStrategy (incrocio SMA 50) | **36.67 %** |

Il segnale di trend ha informazione reale: **+1.25 punti percentuali** sul caso puro. Le
commissioni costano **+1.24 punti**. L'edge e il pedaggio hanno la stessa taglia, a due decimali.

Come test formale il controllo cade al **64.8° percentile** della distribuzione casuale. Per
passare serve il 95°. **Non passa.**

---

## EXP-001 · L'unico test pre-registrato

Regole fissate e committate **prima** dell'esecuzione (commit `3429720`,
[`EXPERIMENT_REGISTER.md`](EXPERIMENT_REGISTER.md)): sei segnali candidati, uscite identiche e non
ottimizzate, soglia al **99.17° percentile** (Bonferroni per sei test a α = 0.05), minimo 30
ingressi, rendimento positivo obbligatorio.

| segnale | n | netto | maxDD | win % | percentile | esito |
|---|---:|---:|---:|---:|---:|---|
| S1 breakout Donchian 20 | 148 | −17.8 % | 42.5 % | 35.1 % | 46.7 % | fallito |
| S2 rsi(14) < 30 | 118 | −30.4 % | 39.6 % | 32.2 % | 20.9 % | fallito |
| S3 Bollinger inferiore | 193 | −38.3 % | 48.4 % | 33.2 % | 22.0 % | fallito |
| S4 ema20 × ema50 | 50 | **+8.1 %** | 12.4 % | 40.0 % | 75.3 % | fallito |
| S5 momentum 30 barre | 337 | −50.8 % | 68.8 % | 33.8 % | 26.3 % | fallito |
| S6 pullback in trend | 63 | −14.0 % | 26.0 % | 33.3 % | 34.3 % | fallito |
| C0 sma(50) *(riferimento)* | 120 | −4.9 % | 27.1 % | 36.7 % | 57.8 % | — |

**Zero su sei.**

**S4 va nominato**, perché è esattamente il risultato che invita a barare: unico positivo, minor
drawdown, win rate 40 %. Ed è al **75.3° percentile**. Un ingresso casuale su quattro fa meglio.
Con 50 osservazioni è ciò che il caso produce senza sforzo. Promuoverlo, o riaprire il test con
una soglia più gentile, o aggiungere un settimo segnale finché uno passa, è la stessa identica
operazione che faceva `optimizer.py` dimezzando il position size finché il verdetto non girava —
la differenza sarebbe solo che stavolta la faremmo noi a mano.

**Il metodo è validato:** C0 dà qui −4.9 % su 120 trade; il simulatore Jesse completo, su
1,3 milioni di candele a 1 minuto, aveva dato −4.78 % su 120 trade. Il risultato non è un
artefatto della scorciatoia di calcolo.

---

## EXP-002 · Momentum cross-sectional — la seconda ipotesi

Domanda diversa da EXP-001: non *"quando comprare Bitcoin"* ma *"quali monete tenere"*,
ribilanciando ogni 28 giorni su 416 coppie spot USDT (`sha256:8b5330d5b11eb135…`),
46 ribilanciamenti dal 2023-01 al 2026-06. Regole committate prima dei dati (`5cff3fe`).

Il meccanismo dichiarato: ribilanciando mensilmente il pedaggio dello 0.2 % si applica a un
periodo in cui la dispersione fra la migliore e la peggiore moneta è di decine di punti — il
cuscinetto passa da ~2× a ~100×, ed è il fattore che aveva ucciso EXP-001. Più una ragione
plausibile per cui l'edge esista: le monete minori sono meno arbitraggiate e il flusso retail vi
si muove lentamente.

| | netto | maxDD |
|---|---:|---:|
| **momentum cross-sectional** | **−93.7 %** | 97.8 % |
| 5 monete a caso, mediana | −63.8 % | |
| 5 monete a caso, 95° percentile | +25.6 % | |
| universo equipesato | −47.2 % | |
| BTC comprato e tenuto | **+295.7 %** | |

**Sta allo 0.5° percentile del caso.** Peggio del 99.5 % delle scelte casuali. Dodici celle di
sensibilità, **tutte negative**, da −74.6 % a −98.6 %.

L'ipotesi è refutata con il segno rovesciato: comprare le altcoin appena salite è un modo
affidabile di comprare il massimo. La consistenza delle dodici celle esclude il rumore.

E un fatto che nessuno dei due esperimenti cercava: nella finestra **BTC ha fatto +295.7 % mentre
l'universo altcoin equipesato ha fatto −47.2 %.** Non è una strategia. È un'osservazione su un
periodo, e trasformarla in previsione sarebbe l'errore che il registro esiste per prevenire.

**Non si inverte.** L'idea di comprare i perdenti nasce *guardando questo risultato*: testarla su
questa stessa finestra descriverebbe il passato, non prevederebbe nulla. Richiederebbe una nuova
pre-registrazione su dati mai aperti, e resterebbe evidenza più debole di un'ipotesi formulata
prima di guardare.

---

# Decisioni

## Decisione A — il limite di drawdown del 2 % è abbandonato

**Motivo:** non è raggiungibile su questo strumento. Lo strumento è oltre il 2 % sotto il
proprio massimo il 91.6 % del tempo; zero percorsi casuali su mille sono rimasti sotto; e
l'esposizione necessaria per rispettarlo produce ordini sotto il minimo dell'exchange.

Il numero 2.0 stava facendo due lavori diversi confusi in uno. Ora sono separati:

| prima | dopo | cosa controlla davvero |
|---|---|---|
| `max_drawdown_limit_pct: 2.0` | `max_drawdown_limit_pct: 20.0` | quanto può perdere il conto nel suo periodo peggiore |
| — | `max_risk_per_trade_pct: 1.0` | quanto costa una singola perdita — **è questo che il 2 % stava governando** |
| `max_position_sizing_pct: 2.0` | `max_position_sizing_pct: 1.0` | con stop al 2 %, impiega il 50 % del conto invece del 100 % |
| tetto di schema 2.0 | tetto di schema **30.0** | resta un tetto, così il numero non torna a essere libero |

20 % non è un obiettivo: è un budget dichiarato, e resta molto dentro il 53 % del comprare-e-tenere.
`MAX_DRAWDOWN_CEILING_PCT` in [`supervisor.py`](../core_engine/supervisor.py) porta la misura
nel commento, così il prossimo che lo trova non deve fidarsi.

**Nota importante:** questo non rende il sistema più pronto. Alza un limite che era falso.
Un vincolo mai misurato non è prudenza, è un numero — ma un vincolo rilassato non è un progresso.

## Decisione B — ci si ferma alla ricerca

**Non c'è una strategia.** Due ipotesi indipendenti, entrambe con un meccanismo dichiarato,
entrambe pre-registrate prima dell'esecuzione, entrambe refutate su dati reali:

- **EXP-001**, temporizzazione su BTC: sei segnali classici, il migliore al 75° percentile del
  caso. L'edge di un segnale di trend e il pedaggio commissionale hanno la stessa taglia.
- **EXP-002**, selezione cross-sectional: allo 0.5° percentile del caso, dodici celle di
  sensibilità tutte negative. Il meccanismo ipotizzato esiste con il segno opposto.

Questo **non** dimostra che nessun edge esista. Dimostra che i due candidati ragionevoli
accessibili da questa postazione — dati di prezzo pubblici, commissioni retail, un exchange —
non ci sono, e che il modo in cui non ci sono è misurato e non congetturato.

**Nessun capitale. Nessun layer di esecuzione.** Costruire il Gate D per una strategia senza edge
dimostrato sono cinque giorni-uomo spesi per aumentare la superficie di rischio di zero vantaggio.

**Perché non una ricerca aperta (B2).** La misura dice che l'edge dei segnali tecnici semplici su
BTC ha la stessa taglia del pedaggio commissionale — 1.25 punti contro 1.24. Su un terreno così,
provando abbastanza combinazioni se ne trova sempre una che sembra funzionare **sui dati passati**,
e la macchina statistica per distinguerla dal rumore costa più di quanto valga il risultato atteso.
Il valore atteso è negativo, ed è misurato, non temuto.

**Cosa resta, e non è poco.** Un motore che non mente: misura su dati reali con provenienza
tracciata, distingue "non ha funzionato" da "non ho misurato", non può essere convinto da un
mock, e ha un registro esperimenti in cui gli esiti negativi sono scritti. Ha già prodotto tre
risultati che il progetto precedente non poteva ottenere — la strategia certificata non opera,
le commissioni si mangiano l'edge, il limite di rischio era impossibile.

**Cosa lo riaprirebbe.** Non un'altra passata di segnali. Una **ipotesi di mercato con un
meccanismo** — una ragione per cui qualcuno dovrebbe essere disposto a perdere denaro dall'altra
parte del trade — dichiarata prima di guardare i dati e registrata in `EXPERIMENT_REGISTER.md`.
Quello è il tipo di input che questa infrastruttura ora sa valutare onestamente, e che nessuna
quantità di codice può generare al posto tuo.
