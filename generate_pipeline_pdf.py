# generate_pipeline_pdf.py
import sys
import subprocess
import os

try:
    import reportlab
except ImportError:
    print("Installing reportlab...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        if self._pageNumber == 1:
            return
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header rule and text
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 750, 558, 750)
        self.drawString(54, 755, "Sovereign Quant Engine - Pipeline Operativa di Deploy IRL")
        
        # Footer rule and page text
        self.line(54, 50, 558, 50)
        page_text = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(558, 38, page_text)
        self.restoreState()

def create_pipeline_manual(filename=None):
    if filename is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(base_dir, "docs", "Pipeline_Deploy_IRL_Bybit_Hetzner.pdf")
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Color Palette: Deep Blue (Trust), Emerald (Success/Money), Amber (Warning)
    primary = colors.HexColor("#1E3A8A")    # Deep Blue
    success = colors.HexColor("#047857")    # Emerald Green
    accent = colors.HexColor("#B45309")     # Amber/Orange
    dark_text = colors.HexColor("#1F2937")  # Slate 800
    muted_text = colors.HexColor("#4B5563") # Slate 600
    bg_light = colors.HexColor("#F0FDF4")   # Green 50 (soft background)

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=primary,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=muted_text,
        spaceAfter=25
    )
    
    h1_style = ParagraphStyle(
        'Header1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=primary,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=14,
        textColor=success,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=dark_text,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#111827"),
        backColor=colors.HexColor("#F3F4F6"),
        borderColor=colors.HexColor("#E5E7EB"),
        borderWidth=0.5,
        borderPadding=5,
        spaceBefore=3,
        spaceAfter=6,
        keepWithNext=True
    )

    callout_style = ParagraphStyle(
        'CalloutStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=accent,
        backColor=colors.HexColor("#FFFBEB"),
        borderColor=accent,
        borderWidth=1,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=8
    )

    story = []

    # ================= PAGE 1: COVER =================
    story.append(Spacer(1, 150))
    story.append(Paragraph("PIPELINE OPERATIVA DI DEPLOY", title_style))
    story.append(Paragraph("La combinazione Hetzner Cloud + Bybit per il trading quantitativo reale protetto", subtitle_style))
    story.append(Spacer(1, 20))
    
    meta_data = [
        [Paragraph("<b>VPS Consigliata:</b> Hetzner Cloud (Piano base, ~5&euro;/mese)", body_style)],
        [Paragraph("<b>Exchange Consigliato:</b> Bybit Perpetuals (Massima stabilità con Jesse)", body_style)],
        [Paragraph("<b>Rete di Sicurezza:</b> Nessun prelievo API e trading iniziale limitato a 50$", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[380])
    t_meta.setStyle(TableStyle([
        ('LINEBEFORE', (0,0), (0,-1), 3, success),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    
    story.append(Spacer(1, 180))
    story.append(Paragraph("<i>Guida pratica e specifica per la messa in produzione del bot di trading.</i>", body_style))
    story.append(PageBreak())

    # ================= PAGE 2: ARCHITETTURA STRUMENTI =================
    story.append(Paragraph("1. La Selezione dei Componenti (Perché Bybit e Hetzner?)", h1_style))
    story.append(Paragraph(
        "Per fare trading in modo professionale non servono infrastrutture costose, ma strumenti mirati che riducono "
        "la latenza (ritardi) ed eliminano le interruzioni di rete.",
        body_style
    ))
    
    confronto_data = [
        [Paragraph("<b>Componente</b>", body_style), Paragraph("<b>Scelta Strategica</b>", body_style), Paragraph("<b>Perché questa scelta?</b>", body_style)],
        [Paragraph("<b>Exchange</b>", body_style), Paragraph("<b>Bybit (Perpetual Futures)</b>", body_style), Paragraph("È l'exchange retail più liquido al mondo. Le sue API per inviare ordini sono stabili e Jesse le supporta nativamente con bassissime commissioni.", body_style)],
        [Paragraph("<b>Server (VPS)</b>", body_style), Paragraph("<b>Hetzner Cloud (Munich/Nuremberg)</b>", body_style), Paragraph("I server sono fisicamente vicini ai nodi di rete degli exchange europei. Con 4.50&euro;/mese ottieni una VPS (piano CX21) stabile 24/7.", body_style)],
        [Paragraph("<b>Sistema Operativo</b>", body_style), Paragraph("<b>Ubuntu 22.04 LTS</b>", body_style), Paragraph("Il sistema Linux standard, leggero e sicuro per far girare Docker senza interfaccia grafica che spreca memoria.", body_style)]
    ]
    t_conf = Table(confronto_data, colWidths=[100, 150, 250])
    t_conf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E5E7EB")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_conf)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Fase A: Configurazione del Server (Hetzner Cloud)", h1_style))
    story.append(Paragraph(
        "1. Registrati su <b>Hetzner Cloud</b> e crea un nuovo progetto.<br/>"
        "2. Crea un server ('Add Server') selezionando:<br/>"
        "   &bull; <b>Location:</b> Monaco (Munich) o Norimberga (Nuremberg).<br/>"
        "   &bull; <b>OS:</b> Ubuntu 22.04 LTS.<br/>"
        "   &bull; <b>Type:</b> Shared vCPU (Piano CX21 o CPX11 a circa 4-5&euro;/mese).<br/>"
        "3. Riceverai via email l'indirizzo IP del server e la password per connetterti.",
        body_style
    ))
    
    story.append(Paragraph("Connessione e Configurazione Iniziale:", h2_style))
    story.append(Paragraph(
        "Apri la PowerShell del tuo computer Windows e connettiti al server remoto tramite SSH (sostituisci l'IP con quello fornito da Hetzner):",
        body_style
    ))
    story.append(Paragraph(
        "ssh root@IL_TUO_IP_HETZNER",
        code_style
    ))
    story.append(Paragraph(
        "Una volta dentro il server, esegui questi comandi per aggiornare il sistema e installare Docker (il motore che fa girare il nostro quant engine in modo isolato):",
        body_style
    ))
    story.append(Paragraph(
        "apt update && apt upgrade -y<br/>"
        "apt install docker.exe docker-compose git -y",
        code_style
    ))
    story.append(PageBreak())

    # ================= PAGE 3: CONFIGURAZIONE BYBIT E DEPLOY =================
    story.append(Paragraph("3. Fase B: Configurazione di Sicurezza su Bybit", h1_style))
    story.append(Paragraph(
        "1. Accedi a Bybit e vai su <b>API</b> nel tuo menù utente (sotto-opzione 'API Management').<br/>"
        "2. Clicca su <b>Create New Key</b> (System-generated API Key) e seleziona <b>API Transaction</b>.<br/>"
        "3. Imposta i permessi con la massima attenzione seguendo la tabella sottostante:",
        body_style
    ))
    
    api_settings = [
        [Paragraph("<b>Impostazione API</b>", body_style), Paragraph("<b>Stato da Configurare</b>", body_style), Paragraph("<b>Spiegazione logica di sicurezza</b>", body_style)],
        [Paragraph("<b>Permesso di Scrittura</b>", body_style), Paragraph("<font color='green'><b>Read-Write</b></font>", body_style), Paragraph("Necessario per inserire e cancellare gli ordini di trading.", body_style)],
        [Paragraph("<b>Permesso di Prelievo</b>", body_style), Paragraph("<font color='red'><b>DISABILITATO (No Withdrawal)</b></font>", body_style), Paragraph("Impedisce a chiunque (compreso il bot in caso di bug) di prelevare fondi dal conto.", body_style)],
        [Paragraph("<b>IP Restriction</b>", body_style), Paragraph("<font color='orange'><b>Restrict Access to Trusted IPs Only</b></font>", body_style), Paragraph("Inserisci qui l'IP fisso del tuo server Hetzner. In questo modo Bybit rifiuterà qualsiasi ordine che non provenga dal tuo server cloud.", body_style)],
        [Paragraph("<b>Tipi di Mercato</b>", body_style), Paragraph("<b>Contract / USDT Margined Trading</b>", body_style), Paragraph("Abilita il trading sui contratti Futures perpetui in USDT (quelli usati da Jesse).", body_style)]
    ]
    t_api = Table(api_settings, colWidths=[120, 160, 220])
    t_api.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E5E7EB")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_api)
    story.append(Spacer(1, 10))

    story.append(Paragraph("4. Fase C: Deployment del Codice sulla VPS", h1_style))
    story.append(Paragraph(
        "Copia la cartella del tuo progetto sul server Hetzner (puoi usare Git clonando la tua repository privata o trasferendo i file tramite FileZilla SFTP). "
        "Una volta posizionato nella cartella del progetto sul server remoto, avvia i container Docker:",
        body_style
    ))
    story.append(Paragraph(
        "cd /root/sovereign-quant-engine<br/>"
        "docker-compose up -d",
        code_style
    ))
    
    story.append(Paragraph("Configura il file .env per Bybit:", h2_style))
    story.append(Paragraph(
        "All'interno della cartella `jesse_workspace`, modifica il file di configurazione per collegare Jesse all'exchange inserendo le chiavi API appena create:",
        body_style
    ))
    story.append(Paragraph(
        "# jesse_workspace/.env<br/>"
        "BYBIT_API_KEY=La_Tua_API_Key_Bybit<br/>"
        "BYBIT_API_SECRET=Il_Tuo_Secret_Bybit<br/>"
        "BYBIT_IS_TESTNET=false # Imposta su true se usi il conto demo",
        code_style
    ))
    story.append(PageBreak())

    # ================= PAGE 4: PIPELINE DI SICUREZZA =================
    story.append(Paragraph("5. Fase D: Esecuzione in Sicurezza (I 3 Step in Pratica)", h1_style))
    story.append(Paragraph(
        "Per evitare brutte sorprese finanziarie, non caricare mai somme ingenti all'inizio. Segui questa scaletta:",
        body_style
    ))
    
    fasi_operazione = [
        [Paragraph("<b>Step 1: Testnet (1 Settimana)</b>", body_style),
         Paragraph("Configura `BYBIT_IS_TESTNET=true` nel file `.env`. Fai girare il bot con fondi demo simulati da Bybit in tempo reale. Questo ti permette di verificare che la connessione di rete e l'invio degli ordini avvengano correttamente senza rischiare nulla.", body_style)],
        [Paragraph("<b>Step 2: Micro-Sizing con 50 USDT (2 Settimane)</b>", body_style),
         Paragraph("Passa a `BYBIT_IS_TESTNET=false` e carica sul tuo conto Bybit solo <b>50 dollari</b>.<br/>"
                   "Imposta la leva a 1x (nessuna leva finanziaria) e configura la dimensione delle posizioni al minimo assoluto consentito (es. 0.001 BTC per operazione).<br/>"
                   "In questo modo testerai commissioni reali, tempi di risposta e slippage sul mercato vero. Se riscontri un bug, la perdita sarà limitata a pochi centesimi.", body_style)],
        [Paragraph("<b>Step 3: Scaling e Notifiche sul Telefono</b>", body_style),
         Paragraph("Collega il bot a Telegram tramite il token bot generato con `@BotFather` per ricevere messaggi ad ogni operazione. Se dopo 2 settimane i dati di trading corrispondono perfettamente ai backtest del simulatore, aumenta il capitale sul conto a 200$, poi 500$, monitorando costantemente.", body_style)]
    ]
    t_oper = Table(fasi_operazione, colWidths=[150, 350])
    t_oper.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
    ]))
    story.append(t_oper)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(
        "<b>REGOLA CARDINALE:</b> Se noti una discrepanza tra i trade reali eseguiti su Bybit e i trade simulati "
        "dalla dashboard di validazione locale (es. commissioni troppo alte, scostamenti di prezzo elevati), "
        "<b>spegni subito il bot</b> ed analizza i log di errore. Non incrementare mai il capitale se la strategia "
        "mostra comportamenti anomali.",
        callout_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Pipeline Manual generated successfully as: {filename}")

if __name__ == "__main__":
    create_pipeline_manual()
