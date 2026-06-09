# Pipeline Deploy IRL Bybit Hetzner

Questo manuale operativo definisce i requisiti fisici e i passaggi operativi per spostare le strategie dal tuo ambiente di sviluppo locale ad un server di produzione remoto, operando in sicurezza reale (In Real Life) su Bybit.

## 1. Confronto Ambienti: PC Locale vs VPS Cloud

| Caratteristica | Computer di Casa (Locale) | Server Cloud (VPS Hetzner) |
| :--- | :--- | :--- |
| **Connessione Internet** | Instabile (soggetta a disconnessioni o rallentamenti). | Garantita (uptime > 99.99% su rete in fibra ottica). |
| **Alimentazione Elettrica** | Rischio di blackout o spegnimenti involontari di Windows. | Ridondante (nessun arresto del server remoto). |
| **Latenza (Ping)** | Elevata (dai 30ms ai 100ms verso i server di Bybit). | Minima (< 2-5ms se ospitato nella stessa area geografica). |
| **Sistema Operativo** | Windows 10/11 (pesante per task in background). | Ubuntu 22.04 LTS (leggero, sicuro, headless). |

## 2. Fase A: Configurazione del Server (Hetzner Cloud)

1. Registrati su **Hetzner Cloud** e crea un nuovo progetto.
2. Crea un server ("Add Server") selezionando:
   - **Location:** Monaco (Munich) o Norimberga (Nuremberg).
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
apt install docker.exe docker-compose git -y
```

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

## 4. Fase C: Deployment del Codice sulla VPS

Copia la cartella del tuo progetto sul server Hetzner (clonando la tua repository privata tramite git). Posizionati nella directory sul server remoto ed avvia i container Docker:
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

## 5. Fase D: Esecuzione in Sicurezza (I 3 Step in Pratica)

- **Step 1: Testnet (1 Settimana)**
  Configura `BYBIT_IS_TESTNET=true` nel file `.env`. Fai girare il bot con fondi demo simulati da Bybit in tempo reale per verificare che la connessione di rete e l'invio degli ordini avvengano correttamente senza rischiare nulla.
- **Step 2: Micro-Sizing reale (2 Settimane)**
  Passa a `BYBIT_IS_TESTNET=false` e carica sul tuo conto Bybit solo **50 dollari**. Imposta la leva a 1x (nessuna leva finanziaria) e configura la dimensione delle posizioni al minimo assoluto consentito. Se riscontri un bug, la perdita sarà limitata a pochi centesimi.
- **Step 3: Scaling e Notifiche sul Telefono**
  Collega il bot a Telegram tramite il token bot generato con `@BotFather` per ricevere messaggi ad ogni operazione. Aumenta gradualmente il capitale sul conto solo se i dati di trading corrispondono perfettamente ai backtest del simulatore.
