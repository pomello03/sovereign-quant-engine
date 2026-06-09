# Guida al Deploy IRL (In Real Life) Sicuro

Questa guida descrive i passaggi fisici e i requisiti necessari per lanciare la tua strategia sul mercato reale in modo sicuro, riducendo a zero le possibilità di perdite dovute a malfunzionamenti del computer.

## 1. I Tre Pilastri della Sicurezza

*   **1. Server Cloud (VPS - Virtual Private Server)**: Non far mai girare il bot di trading dal tuo computer di casa. Se manca la corrente, si riavvia Windows o cade internet, il bot perde il controllo delle posizioni aperte. Si usa una VPS (es. **Hetzner Cloud** - piano base CX21 a circa 4-5€/mese con Ubuntu 22.04 LTS), che garantisce uptime del 99.99%.
*   **2. API Key Senza Prelievi (Fondamentale)**: Quando colleghi il bot al tuo broker (es. **Bybit**), crei una chiave API di connessione. Nelle impostazioni su Bybit, devi **disabilitare rigorosamente il permesso di prelievo (Withdrawal)**. In questo modo il bot potrà solo scambiare e operare, ma in nessun caso i tuoi fondi potranno essere prelevati o rubati.
*   **3. Restrizione IP**: Associa la chiave API del broker esclusivamente all'indirizzo IP fisso del tuo server Hetzner. Bybit rifiuterà qualsiasi ordine che non arrivi direttamente dal tuo server protetto.

## 2. La Scaletta Operativa in 3 Fasi (Deployment Progressivo)

*   **Fase 1: Testnet (Soldi Finti dal vivo - 1 Settimana)**
    Collega Jesse alla Testnet di Bybit. Il bot opererà in tempo reale sui mercati veri ma usando monete demo. Questo serve a verificare la stabilità dei server.
*   **Fase 2: Micro-Sizing reale (2 Settimane)**
    Carica sul conto Bybit reale solo **50 dollari**. Imposta la dimensione delle operazioni al minimo possibile (es. 1 o 2 dollari per trade) e la leva a 1x (senza leva). Se si verifica un bug imprevisto, la perdita massima sarà limitata a pochissimi centesimi, ma potrai misurare le commissioni e i tempi reali del broker.
*   **Fase 3: Scaling e Notifiche**
    Crea un bot Telegram tramite `@BotFather` e inserisci il token in Jesse. Riceverai un messaggio sul telefono ogni volta che il bot acquista, vende o incontra un errore. Aumenta gradualmente il capitale solo se i dati corrispondono ai test.

---
### Note Correlate:
- [[Sovereign Quant Engine]] (Indice)
- [[Guida Semplicissima]]
- [[Architecture Bible]]
