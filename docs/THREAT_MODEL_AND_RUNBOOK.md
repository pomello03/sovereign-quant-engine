# Threat model e runbook operativo

Stato attuale: **nessun asset finanziario è a rischio, perché nessun codice può inviare un ordine.**
Questo documento vale per il sistema quale sarà al Gate E–F. Le minacce marcate **ATTIVA** esistono già oggi.

---

## 1. Asset

| Asset | Dove vive | Perdita se compromesso |
|---|---|---|
| Chiavi API di trading | env del processo di esecuzione | Perdita totale del saldo del sub-account |
| Saldo del sub-account | Exchange | Capitale del canary |
| Artefatto strategia approvato | Repo, commit firmato | Un motore che esegue logica mai validata |
| Config di rischio attiva | File letto all'avvio | Guardrail disattivati senza che nessuno se ne accorga |
| Journal / audit log | SQLite locale | Impossibilità di ricostruire cosa è successo |
| Stato di posizione locale | SQLite locale | Divergenza dall'exchange → ordini duplicati o posizioni fantasma |
| Macchina di esecuzione | VPS | Tutto quanto sopra |

**Non è un asset:** il capitale principale dell'utente. Non deve mai stare sull'account operativo.

---

## 2. Trust boundary

```
[1] Input JSON di ricerca ──▶ Supervisor            ATTIVA — presidiata solo sui tipi
[2] Blueprint ──▶ Generatore di codice             ATTIVA — RCE dimostrato
[3] Codice generato ──▶ interprete Python          ATTIVA — nessuna revisione umana obbligatoria
[4] Rete pubblica ──▶ dashboard HTTP               ATTIVA — nessuna auth, CORS *
[5] Output exchange ──▶ decisione di rischio       futura — il confine più fragile
[6] Processo di esecuzione ──▶ exchange            futura — dove passano le credenziali
[7] LLM ──▶ qualunque cosa                         da progettare come confine, non come assenza
```

---

## 3. Minacce

### T-01 · Esecuzione di codice arbitrario via `alpha_spec.json` — **ATTIVA, P0**
`developer_bridge.py:262-263` interpola `indicators[].params` in una f-string che diventa una chiamata
Python. Lo schema non ha `pattern` né `additionalProperties`. PoC eseguito, marcatore creato
(vedi `PROJECT_STATE.md` V7). Il payload gira dentro il `lambda` che `_safe_indicator` avvolge in
`try/except`: la property restituisce il fallback e **nulla appare nei log**.

Inerte finché Jesse è assente. **Attivo al primo `pip install jesse`.**

**Controlli:**
- `pattern: "^[a-z_][a-z0-9_]*$"` su `indicators[].name`
- `additionalProperties: {"type": "number"}` su `indicators[].params` — i parametri sono numeri, non stringhe
- `visit_Name` che **solleva** su nomi non whitelisted (whitelist, non blacklist di due nodi)
- `ast.parse()` sul file generato **prima** di scriverlo su disco
- Il commit che porta Jesse nel venv principale **deve** contenere questi controlli

### T-02 · Il guardrail di rischio si disattiva da una query string — **ATTIVA, P0**
`main.py:49` accetta `drawdown_limit` senza bound; `:110-113` lo scrive in `risk_constraints.json`
**dopo** che il Ruin Bias è già passato. Verificato: `?drawdown_limit=99` fa passare una strategia con
DD simulato del 73.86 %. CORS `allow_origins=['*']` con `allow_credentials=True` (`:20-26`): Starlette
rispecchia l'Origin, quindi una pagina terza può anche **leggere** lo stream SSE.

**Controlli:** cancellare il parametro. Un limite di rischio non passa mai per HTTP.
CORS ristretto a `127.0.0.1`. La dashboard non è mai esposta oltre localhost o una VPN.

### T-03 · Credenziali esposte — futura
**Controlli obbligatori:**
- Chiave **trade-only**: permesso di prelievo **disabilitato lato exchange**, non lato codice
- Sub-account dedicato con saldo limitato al capitale del canary
- IP allowlist sulla chiave
- Segreti solo da env iniettata dall'esterno; mai in un file del repo, mai in un prompt, mai in un log
- `.gitignore` già copre `.env` e `*PAT*` — verificato
- Nessun segreto raggiungibile dal processo di ricerca: la ricerca non ha bisogno di chiavi
- Rotazione: procedura scritta, **eseguita una volta durante il Gate F** (non documentata soltanto)
- Fail-closed: se l'autenticazione è incerta, non si apre nulla

**Non costruire un custodian.** Un sub-account isolato con permessi minimi risolve il problema.

### T-04 · Un LLM modifica la strategia live — futura, ma è il vincolo fondante
**Controlli:**
- Il runtime verifica all'avvio che `hash(codice)` e `hash(config)` corrispondano a quelli registrati.
  Se non corrispondono, **non parte** (fail-closed).
- L'LLM **propone** codice; solo un merge umano verso il commit approvato lo abilita.
- Rinforzo, 5 righe all'avvio del processo live:
  `assert not any(m in sys.modules for m in ('anthropic','openai'))`
- Nessuna chiave API dell'exchange raggiungibile da un processo che ospita un LLM.
- Nessun tool MCP nel runtime di esecuzione.

### T-05 · Ordine duplicato dopo un timeout — futura, P0 operativo
Un timeout HTTP non dice se l'ordine è passato. Il retry cieco è il modo standard di perdere denaro.

**Controlli:** `clientOrderId` deterministico persistito **prima** dell'HTTP; su timeout **mai reinviare,
interrogare**; se non trovato dopo 3 lookup, reinviare **lo stesso id** (l'exchange rifiuta il duplicato:
il lock è server-side, non lo scriviamo noi); se non si può interrogare, `HALT`.

L'unica risposta corretta a "non so" è "chiedi". Se non puoi chiedere, "fermati". Mai "riprova".

### T-06 · Divergenza fra stato locale ed exchange — futura
**Controlli:** lo stato locale è una **cache**, mai la verità. Riconciliazione periodica; su spot
`fetch_balance()` (il saldo **è** la posizione). Ogni divergenza si risolve in favore dell'exchange
**ed è un evento allertato**, mai una correzione silenziosa — una riconciliazione che corregge senza
allertare nasconde il bug che l'ha causata.

### T-07 · Il motore continua a operare su dati obsoleti — futura
**Controlli:** `now − last_close > 1.5 · timeframe → HALT`. Monotonia dei timestamp.
**Nessuna interpolazione sui gap.** Stato esplicito `STALE DATA`, mai un verde generico.

### T-08 · Supply chain del plugin live di Jesse — futura
`services/installer.py:70-107`: POST con `Bearer LICENSE_API_TOKEN`, nome file da `Content-Disposition`,
`_pip_install()`, `'beta': True` hardcoded, **zero verifica di hash o firma**. Il wheel è binario chiuso
e gira nel processo che detiene le API key.

**Controlli:** non adottare il live di Jesse prima del Gate F. Se adottato: hash del wheel pinnato e
verificato fuori banda, processo di esecuzione isolato dal processo di ricerca, e il test di
`T-08b` qui sotto eseguito.

### T-08b · Il license check blocca l'avvio con posizioni aperte — **NON VERIFICATO**
Non deducibile: il wheel è chiuso. Se il plugin facesse un check di licenza bloccante a runtime, un
token scaduto o un DNS bloccato impedirebbe l'avvio **con posizioni aperte**, convertendo un rischio di
licenza in un rischio di capitale.
**Test:** installare, bloccare `jesse.trade` in `hosts`, riavviare con posizione aperta in paper.

### T-09 · Perdere il controllo credendo di averlo — futura, P0 concettuale
**Uccidere il processo non è un kill switch.** È rinunciare al controllo lasciando il capitale esposto.

**Il controllo non negoziabile:** bloccare *nuove* posizioni e *chiudere* posizioni esistenti devono
usare meccanismi **diversi**.
- Bloccare nuove posizioni richiede un processo **vivo** che legge un flag → fail-closed se il flag è illeggibile.
- Chiudere le posizioni deve funzionare a processo **morto** → il risk governor è un processo separato
  che parla direttamente alla REST dell'exchange e non importa nulla del motore.

Se li implementi con lo stesso meccanismo, il giorno del crash resta un motore che non apre più e non
chiude nemmeno.

---

## 4. Runbook

### Arresto controllato
1. Pausa: nessuna nuova posizione, le esistenti restano gestite dagli stop.
2. Attendere la chiusura naturale o chiudere manualmente.
3. Arrestare il processo.
4. Verificare sulla dashboard **dell'exchange** che non ci siano ordini aperti.

### Emergenza — kill switch
1. Eseguire il kill switch del risk governor: **cancella tutti gli ordini, chiude tutte le posizioni, disarma**.
2. Il ri-armo è **manuale**, mai automatico.
3. Verificare sull'exchange, non sulla nostra console.
4. Se il risk governor non risponde: revocare la chiave API dal pannello dell'exchange
   (il motore non può più operare), poi chiudere a mano dalla UI dell'exchange.

**La procedura al punto 4 è quella che funziona sempre, e va provata prima di metterci soldi.**

### Compromissione sospetta di una credenziale
1. Revocare la chiave dal pannello dell'exchange. **Prima** di ogni altra cosa.
2. Verificare i prelievi: non devono esistere (la chiave è trade-only). Se esistono, la chiave non era trade-only.
3. Chiudere le posizioni a mano.
4. Ruotare, aggiornare l'env, riavviare in paper — mai direttamente in live.
5. Ricostruire dal journal cosa è stato fatto con la chiave e in quale finestra.

### Ripristino dopo un crash
1. **Non riavviare in automatico.**
2. Boot paranoico: risolvere gli intenti in stato `SENT` interrogando l'exchange, cancellare gli ordini
   orfani, **adottare** la posizione reale.
3. **Mai auto-flatten al boot**: chiudere automaticamente una posizione al riavvio è un modo di
   realizzare una perdita che il mercato non aveva ancora imposto.
4. Riconciliare prima di riprendere. Se la riconciliazione fallisce: stato `STATE NOT RECONCILED`,
   nessuna nuova posizione, allarme.

### Stati operativi — mutuamente esclusivi, mai un pallino verde
`RESEARCH ONLY` · `MOCK DATA` · `PAPER` · `SHADOW` · `LIVE — LIMITED CAPITAL` ·
`TRADING BLOCKED` · `STATE NOT RECONCILED` · `STALE DATA`

### I sei allarmi — e nessun altro
1. Kill switch scattato
2. Budget di perdita giornaliera esaurito
3. Riconciliazione fallita
4. Processo morto da più di 2 candele **con posizione aperta**
5. Credenziali rifiutate
6. N ordini rifiutati consecutivi

Un allarme ignorabile addestra a ignorarli tutti.
