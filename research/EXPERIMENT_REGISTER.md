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
