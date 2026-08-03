# Registro esperimenti

Append-only. Ogni riga si scrive **prima** di eseguire, e non si riscrive dopo.
Il commit che introduce una registrazione deve precedere quello che ne riporta il risultato:
è la data di git a rendere la pre-registrazione verificabile invece che dichiarata.

Un registro che contiene solo gli esperimenti riusciti non è un registro, è una vetrina — e
qualunque correzione per test multipli calcolata su un registro incompleto è un bollino di
rigore su un numero sbagliato.

---

## EXP-001 · Un solo test pre-registrato di segnali standard

**Registrato:** 2026-08-03, prima di qualunque esecuzione.
**Motivo:** [`RESULT_DOMAIN.md`](RESULT_DOMAIN.md) mostra che l'edge disponibile da segnali
tecnici semplici è della stessa taglia del pedaggio commissionale (36.67 % contro 36.66 % di
pareggio). In quel terreno una ricerca aperta trova rumore per costruzione. Questo è un test
**singolo e chiuso**: si esegue una volta, non si itera, e l'esito decide se il progetto prosegue.

### Ipotesi

L'unica leva che la misura del dominio indica è la **durata della posizione**: il rapporto fra
movimento mediano e commissioni passa da 2.2× a 6 ore, a 6.3× a un giorno, a 16× a cinque giorni.
Se un edge esiste in questo dominio a questa scala di costi, sta su orizzonti più lunghi.

### Segnali — insieme fissato, sette voci, nessuna aggiunta ammessa

| # | segnale | famiglia |
|---|---|---|
| S1 | `close > max(high[-20:])` — breakout Donchian a 20 barre | rottura |
| S2 | `rsi(14) < 30` — solo mean reversion, senza filtro di trend | ritorno alla media |
| S3 | `close < sma(20) - 2·std(20)` — banda di Bollinger inferiore | ritorno alla media |
| S4 | `ema(20)` incrocia sopra `ema(50)` | trend |
| S5 | `close > close[-30]` — momentum a 30 barre | trend |
| S6 | `close > sma(200)` e `rsi(14) < 40` — pullback in trend rialzista | misto |
| C0 | `close` incrocia sopra `sma(50)` — **riferimento, non candidato** | trend |

C0 è il controllo già misurato (64.8° percentile). Serve a verificare che il metodo riproduca
un risultato noto, non a essere promosso.

### Uscite — identiche per tutti, non ottimizzate

Stop −2 %, target +4 %, commissioni 0.1 % per lato, risolte sulle candele a 1 minuto reali
(quando una singola candela tocca entrambi i livelli si assume lo stop). Nessuna posizione
sovrapposta: un segnale che arriva a posizione aperta viene ignorato.

Sono le uscite già usate dal controllo e dalla baseline. Non vengono toccate, perché variarle
insieme agli ingressi significherebbe non sapere quale delle due cose ha prodotto il risultato.

### Dati

Bybit spot BTCUSDT, `sha256:252993559a78e464…`, finestra 2024-01-01 → 2026-07-01.
Timeframe 4h. Riscaldamento indicatori sulle barre precedenti alla finestra.

### Criterio di superamento — fissato ora

Un segnale passa **solo se soddisfa tutte e tre** le condizioni:

1. **≥ 30 ingressi** nella finestra. Sotto questa soglia non c'è potenza statistica.
2. **Rendimento netto sopra il 99.17° percentile** della baseline B2 con lo stesso numero di
   trade. Il 99.17° e non il 95° è la correzione di Bonferroni per sei test simultanei a
   α = 0.05: provando sei cose, una supera il 95° per caso circa il 26 % delle volte.
3. **Rendimento netto positivo.** Battere una baseline che perde non basta.

### Cosa succede dopo — deciso ora, non dopo aver visto i numeri

- **Nessun segnale passa** → il progetto si ferma alla ricerca. Nessun capitale, nessun layer di
  esecuzione. Il motore onesto resta il deliverable.
- **Un segnale passa** → diventa l'unico candidato e va al protocollo completo di
  [`VALIDATION_AND_LIVE_GATES.md`](../docs/VALIDATION_AND_LIVE_GATES.md), su una finestra di test
  mai aperta. Passare qui **non** è una promozione: è il permesso di iniziare a validare.
- **Più segnali passano** → si prende il migliore e si applica comunque il protocollo completo,
  registrando che la selezione è avvenuta.

**In nessuno di questi casi si modificano soglie, si aggiungono segnali o si riesegue il test.**
Se il risultato non piace, il risultato resta.

### Esito — eseguito 2026-08-03, una volta sola

| segnale | n | netto | maxDD | win % | percentile | esito |
|---|---:|---:|---:|---:|---:|---|
| S1 breakout Donchian 20 | 148 | −17.8 % | 42.5 % | 35.1 % | 46.7 % | fallito |
| S2 rsi(14) < 30 | 118 | −30.4 % | 39.6 % | 32.2 % | 20.9 % | fallito |
| S3 banda di Bollinger inferiore | 193 | −38.3 % | 48.4 % | 33.2 % | 22.0 % | fallito |
| S4 ema20 × ema50 | 50 | **+8.1 %** | 12.4 % | 40.0 % | 75.3 % | fallito |
| S5 momentum 30 barre | 337 | −50.8 % | 68.8 % | 33.8 % | 26.3 % | fallito |
| S6 pullback in trend | 63 | −14.0 % | 26.0 % | 33.3 % | 34.3 % | fallito |
| C0 sma(50) *(riferimento)* | 120 | −4.9 % | 27.1 % | 36.7 % | 57.8 % | — |

**0 candidati su 6 hanno superato la soglia.**

S4 è l'unico con rendimento positivo e il drawdown più basso, e va nominato perché è
esattamente il risultato che invita a barare: 50 trade, +8.1 %, e il **75.3° percentile** contro
il 99.17° richiesto. Tre quarti degli ingressi casuali fanno peggio; un quarto fa meglio. Con
50 osservazioni è ciò che il caso produce senza sforzo. Promuoverlo — o riaprire il test con
soglie diverse, o aggiungere un settimo segnale — sarebbe la stessa operazione che
`optimizer.py` faceva dimezzando il position size finché il verdetto non girava.

**Validazione del metodo:** C0 qui dà −4.9 % su 120 trade; il simulatore Jesse completo su
1,3 milioni di candele a 1 minuto aveva dato −4.78 % su 120 trade. Le due strade concordano,
quindi il risultato non è un artefatto della scorciatoia di calcolo.

**Conseguenza, per la regola scritta sopra:** il progetto si ferma alla ricerca.
Nessun capitale, nessun layer di esecuzione. Vedi [`RESULT_DOMAIN.md`](RESULT_DOMAIN.md).

---

## EXP-002 · Momentum cross-sectional sull'universo spot

**Registrato:** 2026-08-04, prima dell'esecuzione. Lo script
[`run_prereg_exp002.py`](run_prereg_exp002.py) è committato insieme a questa voce e non viene
modificato dopo aver visto i risultati.

**Motivo.** EXP-001 ha chiesto *"quando comprare Bitcoin"* e ha risposto che l'edge di
temporizzazione dei segnali classici ha la stessa taglia della commissione (36.67 % contro
36.66 % di pareggio). Questa è una domanda diversa: *"quali monete tenere"*.

### Perché potrebbe funzionare — il meccanismo, non il grafico

Tre ragioni, e la prima è quella che ha ucciso EXP-001:

1. **Il pedaggio cambia di scala.** Ribilanciando ogni 28 giorni si paga lo 0.2 % su un periodo
   in cui la dispersione fra la moneta migliore e la peggiore dell'universo è tipicamente di
   decine di punti percentuali. Il cuscinetto passa da ~2× a ~100×.
2. **Esiste una ragione perché qualcuno stia dall'altra parte.** Le monete minori sono meno
   seguite e meno arbitraggiate, e il flusso di capitale retail vi si muove in modo lento e
   correlato. Non è una linea su un grafico: è un vincolo su altri partecipanti.
3. **È documentato.** Momentum e size cross-sectional sono fra i pochi risultati che sopravvivono
   nella letteratura accademica sulle criptovalute, non solo nei blog.

### Configurazione primaria — una sola, fissata ora

| parametro | valore |
|---|---|
| universo | tutte le coppie spot USDT di Bybit, candele giornaliere |
| finestra | 2023-01-01 → 2026-07-01 |
| lookback | **90 giorni** |
| posizioni tenute | **top 5**, equipesate |
| ribilanciamento | ogni **28 giorni** |
| filtro di liquidità | turnover giornaliero mediano ≥ **100.000 $** sul lookback |
| commissioni | 0.1 % per lato, applicate **solo alla frazione di portafoglio sostituita** |
| periodi minimi | 20 |

Nessuno stop, nessun target: si tiene fino al ribilanciamento successivo. Aggiungere uscite
sarebbe aggiungere parametri.

### Baseline — la barra è la selezione casuale

| # | baseline | ruolo |
|---|---|---|
| B1 | **5 monete a caso** dallo stesso insieme eleggibile a ogni ribilanciamento, 10.000 ripetizioni | **è questa la barra** |
| B2 | universo eleggibile equipesato | "comprare tutto" |
| B3 | BTC comprato e tenuto | l'alternativa ingenua |

Battere BTC non dimostrerebbe nulla: dimostrerebbe che le altcoin sono salite. L'unico confronto
che isola la **scelta** è contro chi sceglie a caso dallo stesso insieme.

### Criterio di superamento — tutte e tre

1. Rendimento netto **sopra il 95° percentile** di B1. Un'unica ipotesi primaria, quindi nessuna
   correzione di Bonferroni: α = 0.05.
2. Rendimento netto **positivo**.
3. **Superiore all'universo equipesato** (B2). Altrimenti conviene comprare tutto e basta.

### La griglia di sensibilità non può far passare nulla

Vengono riportate anche 12 combinazioni di lookback e K. Sono **descrittive**. Una cella che
supera la barra **non costituisce un superamento**. Se la primaria fallisce e qualche cella
riesce, quella è evidenza di **sensibilità ai parametri**, che è l'aspetto che ha il rumore —
non un risultato da promuovere.

### Bias di sopravvivenza — dichiarato, non risolto

L'endpoint di Bybit elenca **solo le coppie ancora quotate oggi**. Le monete delistate, collassate
o silenziosamente morte sono assenti, e la loro assenza gonfia qualunque risultato calcolato su
ciò che resta. Non è correggibile da questa fonte dati.

**Ciò che salva il confronto:** la baseline B1 pesca dallo *stesso* universo di sopravvissute,
quindi eredita esattamente lo stesso bias. Il rendimento assoluto è gonfiato; il **percentile
rispetto al caso** resta interpretabile. È la ragione per cui la barra è B1 e non un numero
assoluto.

### Cosa succede dopo — deciso ora

- **Fallisce** → la conclusione onesta diventa: battere il mercato con dati di prezzo pubblici e
  commissioni retail non è raggiungibile da questa postazione. Il progetto si ferma, e si ferma
  con evidenza invece che per stanchezza.
- **Passa** → è l'**unico** candidato, e va al protocollo completo di
  [`VALIDATION_AND_LIVE_GATES.md`](../docs/VALIDATION_AND_LIVE_GATES.md) su una finestra mai
  aperta. Prima di qualunque capitale va inoltre risolto il bias di sopravvivenza con una fonte
  dati che includa i delisting — perché un risultato che dipende dal non aver visto i morti non è
  un risultato.

**In nessuno dei due casi si modificano soglie, si aggiungono configurazioni o si riesegue.**

### Esito — eseguito 2026-08-04, una volta sola

416 coppie scaricate, `sha256:8b5330d5b11eb135…`, 46 ribilanciamenti dal 2023-01-01 al 2026-06-14.
Universo eleggibile per periodo: min 46, mediana 180, max 299.

| | netto | maxDD |
|---|---:|---:|
| **momentum cross-sectional (primaria)** | **−93.7 %** | 97.8 % |
| 5 monete a caso, mediana | −63.8 % | |
| 5 monete a caso, 95° percentile | +25.6 % | |
| universo equipesato | −47.2 % | |
| BTC comprato e tenuto | **+295.7 %** | |

**La strategia sta allo 0.5° percentile della selezione casuale.** Non manca la barra: è peggio
del 99.5 % delle scelte fatte a caso. Tutti e tre i criteri falliti. **VERDETTO: FALLITO.**

Griglia di sensibilità, dodici celle: **tutte negative**, da −74.6 % a −98.6 %.

### Cosa dice davvero questo risultato

L'ipotesi era che il flusso retail si muovesse lentamente attraverso le monete minori, facendo
persistere il momentum. **È refutata, e con il segno opposto.** Comprare le altcoin che sono
appena salite è un modo affidabile di comprare il massimo. La consistenza delle dodici celle
esclude che sia rumore: è un effetto reale nella direzione contraria.

C'è poi un fatto che nessuno dei due esperimenti cercava, e che salta agli occhi: nella finestra,
**BTC ha fatto +295.7 % mentre l'universo altcoin equipesato ha fatto −47.2 %.** Non è una
strategia — è un'osservazione su un periodo specifico, e trattarla come una previsione sarebbe
esattamente l'errore che questo registro esiste per prevenire.

### La tentazione, nominata e rifiutata

Il pensiero immediato è: *invertilo, compra i perdenti*. Non si fa, per due ragioni distinte:

1. **La regola scritta sopra lo vieta.** "In nessuno dei due casi si modificano soglie, si
   aggiungono configurazioni o si riesegue." La pre-registrazione vale solo se resiste al momento
   in cui i risultati non piacciono. Questo è quel momento.
2. **Sarebbe un'ipotesi generata dai dati.** Un'idea nata guardando questo risultato e testata su
   questa stessa finestra non porta informazione: si sta descrivendo il passato, non prevedendo.
   Testarla richiederebbe una **nuova** pre-registrazione su una finestra mai aperta — e resterebbe
   comunque evidenza più debole di un'ipotesi formulata prima di guardare.

### Conseguenza, per la regola scritta prima dell'esecuzione

> *Fallisce → la conclusione onesta diventa: battere il mercato con dati di prezzo pubblici e
> commissioni retail non è raggiungibile da questa postazione. Il progetto si ferma, e si ferma
> con evidenza invece che per stanchezza.*

**Il progetto si ferma qui.** Due ipotesi indipendenti, entrambe con un meccanismo dichiarato,
entrambe pre-registrate, entrambe refutate su dati reali.

Questo **non** dimostra che nessun edge esista. Dimostra che questi due, che erano i candidati
ragionevoli accessibili da questa postazione, non ci sono. Vedi
[`RESULT_DOMAIN.md`](RESULT_DOMAIN.md).
