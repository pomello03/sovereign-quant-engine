# Guida Semplicissima al Sovereign Quant Engine

Questa guida spiega il funzionamento dell'infrastruttura utilizzando la metafora di un ristorante di lusso. Questo ti aiuterà a capire come le varie parti cooperano per proteggere il tuo denaro, senza bisogno di conoscere la programmazione o la finanza avanzata.

## 1. La Metafora del Ristorante
Per evitare errori, la gestione del sistema di trading è divisa in ruoli separati, proprio come in un ristorante:

*   **L'Agente Alpha (Il Menù / La Ricetta)**: Decide quali piatti preparare e quando servirli. Nel trading, sceglie quando comprare o vendere basandosi su regole (es. *"compra se il prezzo scende a un certo livello"*).
*   **L'Agente Rischio (Il Direttore di Sala)**: Gestisce la cassa. Decide quanto spendere per ogni tavolo (dimensione della posizione) e quando smettere di servire un piatto se i clienti si lamentano (Stop Loss).
*   **L'Agente Contesto (Il Meteo)**: Controlla le condizioni esterne (es. *"oggi c'è il sole, ci sarà molto afflusso"* oppure *"è un giorno feriale piovoso, ci sarà poca gente"*). Nel trading indica se il mercato è calmo o volatile.
*   **Lo Chef Supervisor (L'Ispettore Sanitario)**: È il controllore supremo. Legge le ricette proposte e si assicura che rispettino le regole di sicurezza del Direttore di Sala. Se una ricetta rischia di costare troppo (drawdown stimato > 2.0%), lo Chef **strappa il foglio** e blocca tutto (Bias di Rovina).
*   **L'Agente Developer (L'Aiuto Cuoco)**: Prepara materialmente il piatto (scrive il codice di trading) seguendo alla lettera le istruzioni del Supervisor, senza inventare nulla.

## 2. Il Ciclo Chiuso (Il Piatto Bruciato)
Se l'aiuto cuoco commette un errore di battitura e la strategia si blocca (il piatto si brucia), lo Chef gli mostra l'errore esatto (i log di backtest di Jesse). L'aiuto cuoco deve immediatamente correggere la ricetta e riprovare finché non è perfetta, senza inventare nuove logiche.

## 3. Stress Test Monte Carlo (Le 1.000 simulazioni del sabato sera)
Per verificare se la strategia è robusta, eseguiamo una simulazione statistica chiamata Monte Carlo. Immaginiamo di simulare 1.000 sabati sera diversi con eventi imprevisti (blackout, ritardi dei fornitori, clienti difficili). Questo ci permette di calcolare con precisione il **Risk of Ruin** (la probabilità percentuale che il ristorante esaurisca la cassa e debba chiudere).

---
### Note Correlate:
- [Indice della Documentazione](file:///C:/Users/francesco.bonino/Documents/SQE%20branch/docs/Sovereign_Quant_Engine.md)
- [Guida Master Completa](file:///C:/Users/francesco.bonino/Documents/SQE%20branch/docs/Guida%20Master%20Completa.md)
- [Pipeline Deploy IRL](file:///C:/Users/francesco.bonino/Documents/SQE%20branch/docs/Pipeline%20Deploy%20IRL%20Bybit%20Hetzner.md)
