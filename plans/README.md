# Plans — Sovereign Quant Engine

Indice dei piani d'azione. Scritti contro il commit `a537770`.

| # | Piano | Priorità | Stato | Dipendenze |
|---|-------|----------|-------|------------|
| 001 | [Dal mock al primo backtest onesto](001-honest-backtest.md) | P0 — fai questo per primo | TODO | nessuna |

## Filosofia di questi piani

Prodotti combinando due lenti:
- **/improve** → cosa ha davvero leva (impatto ÷ sforzo).
- **/ponytail** → tagliare tutto ciò che è teatro; il percorso minimo che funziona.

Conclusione condivisa dalle due lenti: **il 90% del valore è un solo passo** — ottenere *un* backtest vero, misurato su dati reali, anche fuori da questa pipeline. Tutto il resto (gate statistici, live executor, portfolio, SaaS) è prematuro finché quel passo non è fatto.

## Cosa NON fare ora (deciso, non dimenticato)

Questi sono nell'analisi GLM ma vanno **rimandati** — non sono il collo di bottiglia:

- WFA / Deflated Sharpe / PBO (i 3 gate statistici): servono *dopo* aver fatto backtest veri ripetuti. Senza trade reali non hanno nulla su cui girare.
- `live_executor.py`, circuit breaker, Telegram alerting, reconciliation: roba da quando una strategia ha già superato i backtest. Mesi di distanza.
- Portfolio multi-strategy / multi-symbol, correlation matrix: idem.
- Copiare a mano la strategia v2 di GLM: spreco finché non c'è un harness di backtest funzionante (vedi piano 001, sezione "v2").
- Riscrivere il code generator AST per supportare strategie complesse: è il vero limite architetturale, ma è un progetto a sé — non toccarlo finché non sai (da backtest veri) che ne vale la pena.

## Considerati e rifiutati come priorità

- **STRICT_MODE / flag `is_mock` elaborato (deliverable B1 di GLM):** ridotto a una mitigazione da 2 righe nel piano 001. Un intero sistema di env-flag è teatro: il modo onesto di non farsi ingannare è non usare i numeri mock per decidere, non aggiungere infrastruttura.
- **Fix del bug sizing ATR×2 / stop 2% come task urgente:** è un fix concettuale da poche righe, ma irrilevante finché i numeri sono mock. Incluso nel piano 001 come step da fare *insieme* al primo backtest reale, non prima.
