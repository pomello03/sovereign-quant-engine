# Pipeline Deploy IRL Bybit Hetzner

Questo manuale operativo definisce i requisiti fisici e i passaggi operativi per spostare le strategie dal tuo ambiente di sviluppo locale ad un server di produzione remoto, operando in sicurezza reale (In Real Life) su Bybit.

---

## 1. Confronto Ambienti: PC Locale vs VPS Cloud

| Caratteristica | Computer di Casa (Locale) | Server Cloud (VPS Hetzner) |
| :--- | :--- | :--- |
| **Connessione Internet** | Instabile (soggetta a disconnessioni o rallentamenti). | Garantita (uptime > 99.99% su rete in fibra ottica). |
| **Alimentazione Elettrica** | Rischio di blackout o spegnimenti involontari di Windows. | Ridondante (nessun arresto del server remoto). |
| **Latenza (Ping)** | Elevata (dai 30ms ai 100ms verso i server di Bybit). | Minima (< 2-5ms se ospitato nella stessa area geografica). |
| **Sistema Operativo** | Windows 10/11 (pesante per task in background). | Ubuntu 22.04 LTS (leggero, sicuro, headless). |

---

## 2. Fase A: Configurazione del Server (Hetzner Cloud)

1. Registrati su **Hetzner Cloud** e crea un nuovo progetto.
2. Crea un server ("Add Server") selezionando:
   - **Location:** Monaco (Munich) o Norimberga (Nuremberg) (per minima latenza verso i server Bybit in Europa).
   - **OS:** Ubuntu 22.04 LTS.
   - **Type:** Shared vCPU (Piano CX21 o CPX11 a circa 4-5€/mese).
3. Riceverai via email l'indirizzo IP del server e la password per connetterti.

### Connessione e Configurazione Iniziale:
Apri la PowerShell del tuo computer Windows e connettiti al server remoto tramite SSH:
```bash
ssh root@IL_TUO_IP_HETZNER
```

Aggiorna il sistema operativo e installa Docker e Git:
```bash
apt update && apt upgrade -y
apt install docker.io docker-compose git -y
```

---

## 3. Fase B: Configurazione di Sicurezza su Bybit

1. Accedi a Bybit e vai su **API** nel tuo menù utente ("API Management").
2. Clicca su **Create New Key** (System-generated API Key) e seleziona **API Transaction**.
3. Imposta i permessi con la massima attenzione seguendo la tabella sottostante:

| Impostazione API | Stato da Configurare | Spiegazione logica di sicurezza |
| :--- | :--- | :--- |
| **Permesso di Scrittura** | **Read-Write** | Necessario per inserire e cancellare gli ordini di trading. |
| **Permesso di Prelievo** | **DISABILITATO (No Withdrawal)** | Impedisce a chiunque (compreso il bot in caso di bug) di prelevare fondi dal conto. |
| **IP Restriction** | **Restrict Access to Trusted IPs Only** | Inserisci l'IP fisso del tuo server Hetzner. Bybit rifiuterà qualsiasi ordine non proveniente da qui. |
| **Tipi di Mercato** | **Contract / USDT Margined Trading** | Abilita il trading sui contratti Futures perpetui in USDT usati da Jesse. |

> [!CAUTION]
> Non spuntare MAI la casella "Enable Withdrawals" o "Abilita Prelievi". Questa impostazione è la tua barriera di sicurezza definitiva contro i furti.

---

## 4. Fase C: Deployment del Codice sulla VPS

Copiare la cartella del progetto sul server Hetzner (clonando la repository privata tramite git). Posizionarsi nella directory sul server remoto ed avviare i container Docker:
```bash
cd /root/sovereign-quant-engine
docker-compose up -d
```

### Configura il file `.env` per Bybit:
All'interno della cartella `jesse_workspace/`, crea o modifica il file `.env` per inserire le chiavi API:
```env
BYBIT_API_KEY=La_Tua_API_Key_Bybit
BYBIT_API_SECRET=Il_Tuo_Secret_Bybit
BYBIT_IS_TESTNET=false
```

---

## 5. Fase D: Esecuzione in Sicurezza (Deployment Progressivo)

Per evitare perdite improvvise a causa di logiche errate, segui rigorosamente questa scaletta temporale:

*   **Step 1: Testnet (Fondi Simulati - 1 Settimana)**
    Configura `BYBIT_IS_TESTNET=true` nel file `.env`. Fai girare il bot in tempo reale per verificare che la VPS riceva i dati di mercato, esegua la logica del regime switching e invii gli ordini demo senza alcun rischio.
*   **Step 2: Micro-Sizing reale (2 Settimane)**
    Imposta `BYBIT_IS_TESTNET=false` e carica sul conto reale di Bybit solo **50 dollari**. Configura la dimensione della posizione al minimo consentito (es. 1 o 2 dollari) e mantieni la leva finanziaria a 1x. In caso di bug latente, la perdita sarà irrilevante.
*   **Step 3: Notifiche e Scaling**
    Crea un bot Telegram tramite `@BotFather` ed inietta il token in Jesse. Riceverai notifiche in tempo reale ad ogni esecuzione e ad ogni errore direttamente sul telefono. Aumenta gradualmente il capitale solo dopo 2 settimane di performance stabili coerenti con i backtest.
