# generate_deploy_pdf.py
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
        self.drawString(54, 755, "Sovereign Quant Engine - Guida al Deploy Reale (IRL) Sicuro")
        
        # Footer rule and page text
        self.line(54, 50, 558, 50)
        page_text = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(558, 38, page_text)
        self.restoreState()

def create_deploy_manual(filename="Guida_Deploy_IRL_Sicuro.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette: Indigo, Rose (for warnings), Slate (for structure)
    primary = colors.HexColor("#312E81")    # Deep Indigo
    accent = colors.HexColor("#B91C1C")     # Crimson Red (warning / safety)
    dark_text = colors.HexColor("#1E293B")  # Slate 800
    muted_text = colors.HexColor("#475569") # Slate 600
    bg_light = colors.HexColor("#F8FAFC")   # Slate 50
    alert_bg = colors.HexColor("#FEF2F2")   # Rose 50 (danger background)

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
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
        fontSize=16,
        leading=20,
        textColor=primary,
        spaceBefore=16,
        spaceAfter=10,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=accent,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=dark_text,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
        backColor=colors.HexColor("#F1F5F9"),
        borderColor=colors.HexColor("#E2E8F0"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
        keepWithNext=True
    )

    callout_style = ParagraphStyle(
        'CalloutStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13.5,
        textColor=accent,
        backColor=alert_bg,
        borderColor=accent,
        borderWidth=1,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=10
    )

    story = []

    # ================= PAGE 1: COVER =================
    story.append(Spacer(1, 150))
    story.append(Paragraph("GUIDA AL DEPLOY REALE SICURO", title_style))
    story.append(Paragraph("Come lanciare il Sovereign Quant Engine a mercato reale senza rischiare il capitale", subtitle_style))
    story.append(Spacer(1, 20))
    
    meta_data = [
        [Paragraph("<b>Obiettivo:</b> Evitare perdite causate da bug o cattiva configurazione", body_style)],
        [Paragraph("<b>Approccio:</b> Deployment progressivo (Controllo del rischio in 3 step)", body_style)],
        [Paragraph("<b>Livello:</b> Semplice (zero concetti complessi di informatica)", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[380])
    t_meta.setStyle(TableStyle([
        ('LINEBEFORE', (0,0), (0,-1), 3, accent),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    
    story.append(Spacer(1, 170))
    story.append(Paragraph("<i>Regola d'oro: Non rischiare mai denaro che non puoi permetterti di perdere.</i>", body_style))
    story.append(PageBreak())

    # ================= PAGE 2: I PERICOLI E LE SOLUZIONI =================
    story.append(Paragraph("1. I Pericoli del Trading Reale (E come evitarli)", h1_style))
    story.append(Paragraph(
        "Lanciare un sistema di trading automatico collegato al proprio conto (wallet) reale comporta dei rischi "
        "enormi se non si prendono le giuste precauzioni. Un semplice computer di casa che si spegne, una connessione internet "
        "che salta, o un codice scritto male possono generare ordini errati a ripetizione e svuotare il portafoglio in pochi minuti.",
        body_style
    ))
    
    story.append(Paragraph("Come proteggiamo il conto reale:", h2_style))
    
    sicurezza_data = [
        [Paragraph("<b>Isolamento del Computer (VPS)</b>", body_style),
         Paragraph("Non fare mai trading reale dal tuo PC di casa. Se si aggiorna Windows o salta la corrente, il sistema perde il controllo delle posizioni. Si usa una VPS (un server remoto sempre acceso su internet) che costa circa 5-10 euro al mese.", body_style)],
        [Paragraph("<b>Chiavi API Bloccate (No Prelievi)</b>", body_style),
         Paragraph("Quando colleghi il motore all'exchange (es. Bybit o Binance), generi delle chiavi di connessione (API). Devi <b>ASSOLUTAMENTE DISABILITARE</b> il permesso di prelievo ('Withdrawal'). In questo modo, anche se un hacker o un bug violasse il sistema, nessuno potrà mai rubare o trasferire i tuoi soldi.", body_style)],
        [Paragraph("<b>Limiti di Rischio Rigidi (Sizing)</b>", body_style),
         Paragraph("La regola fondamentale è non mettere mai tutto il capitale su un singolo scambio. Il nostro Supervisor controlla che ogni operazione rischi al massimo l'1% o il 2% del portafoglio totale. Se la strategia impazzisce, i danni rimangono minimi.", body_style)]
    ]
    t_sic = Table(sicurezza_data, colWidths=[150, 350])
    t_sic.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_sic)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(
        "<b>ATTENZIONE:</b> Non spuntare MAI la casella 'Enable Withdrawals' o 'Abilita Prelievi' quando crei le chiavi "
        "API sul sito del tuo broker. Questa singola impostazione è la tua barriera di sicurezza definitiva contro i furti.",
        callout_style
    ))
    story.append(PageBreak())

    # ================= PAGE 3: I 3 PASSI DEL DEPLOY =================
    story.append(Paragraph("2. La Strategia del Deploy Progressivo (in 3 Step)", h1_style))
    story.append(Paragraph(
        "Per evitare di perdere soldi a causa di problemi di latenza o bug del software, non devi mai passare "
        "direttamente dalla simulazione al trading reale con molti soldi. Devi seguire un percorso di sicurezza in tre fasi:",
        body_style
    ))
    
    story.append(Paragraph("Step 1: Paper Trading in Tempo Reale (Soldi Finti)", h2_style))
    story.append(Paragraph(
        "In questa fase, il motore di trading si collega al mercato e riceve i prezzi reali in tempo reale, ma "
        "esegue operazioni simulate (soldi finti). Questo serve a verificare che la connessione sia stabile e "
        "che i calcoli avvengano nei tempi giusti. Fai girare questa fase per almeno 7-14 giorni.",
        body_style
    ))
    story.append(Paragraph(
        "jesse start-live-paper",
        code_style
    ))
    
    story.append(Paragraph("Step 2: Live Trading con Capitale Minimo (Micro-Sizing)", h2_style))
    story.append(Paragraph(
        "Questa è la fase più importante per fare le cose in modo furbo. Invece di investire il tuo capitale reale, "
        "carica sul conto il minimo assoluto consentito (es. 50 dollari in totale) e imposta la dimensione di ogni operazione "
        "al minimo possibile (es. 1 o 2 dollari per trade).<br/>"
        "In questo modo proverai l'esecuzione reale del broker (con le sue commissioni, tempi di risposta e slippage), ma "
        "se anche la strategia dovesse fallire completamente o riscontrare un bug bloccante, il danno economico massimo "
        "sarebbe limitato a pochissimi spiccioli.",
        body_style
    ))
    story.append(Paragraph(
        "jesse start-live",
        code_style
    ))
    
    story.append(Paragraph("Step 3: Scaling Graduale e Controllato", h2_style))
    story.append(Paragraph(
        "Solo dopo che la fase con capitale minimo ha dimostrato (dopo 2-3 settimane) di funzionare esattamente come "
        "previsto dai test e senza errori bloccanti, puoi iniziare a incrementare gradualmente la dimensione del conto "
        "(es. portandolo a 200$, poi a 500$). Non saltare mai questo passaggio per fretta.",
        body_style
    ))
    story.append(PageBreak())

    # ================= PAGE 4: NOTIFICHE E CONTROLLO =================
    story.append(Paragraph("3. Controllo in Tempo Reale (Notifiche e Alert)", h1_style))
    story.append(Paragraph(
        "Non puoi stare davanti allo schermo tutto il giorno a controllare cosa fa il computer. Devi fare in modo "
        "che il sistema ti avvisi sul telefono cellulare per ogni singola azione importante.",
        body_style
    ))
    
    story.append(Paragraph("Configura le notifiche Telegram o Discord:", h2_style))
    story.append(Paragraph(
        "Jesse integra un sistema di notifiche nativo. Puoi configurarlo inserendo il token del tuo canale Telegram "
        "nel file di configurazione. Ogni volta che la strategia:<br/>"
        "&bull; Apre una nuova posizione (compra)<br/>"
        "&bull; Chiude una posizione (vende)<br/>"
        "&bull; Raggiunge lo Stop Loss o il Take Profit<br/>"
        "&bull; Incontra un errore di connessione o di sistema<br/>"
        "Riceverai un messaggio istantaneo sul telefono. Questo ti permette di intervenire manualmente spegnendo "
        "il server in caso di comportamenti anomali.",
        body_style
    ))
    
    story.append(Paragraph("4. Riassunto delle Regole per Operare in Sicurezza", h1_style))
    
    regole = [
        [Paragraph("<b>1. Disabilita Prelievi</b>", body_style), Paragraph("Sulle chiavi API dell'exchange, togli il flag a qualsiasi opzione di prelievo. Il robot deve solo negoziare, mai prelevare.", body_style)],
        [Paragraph("<b>2. Usa una VPS</b>", body_style), Paragraph("Fai girare il bot su un server cloud affidabile (costo 5-10$/mese), non sul PC di casa.", body_style)],
        [Paragraph("<b>3. Partenza Micro</b>", body_style), Paragraph("Inizia il live trading con soli 50$ sul conto e operazioni da 1-2$ per verificare commissioni e slippage reali.", body_style)],
        [Paragraph("<b>4. Alert sul Telefono</b>", body_style), Paragraph("Collega Telegram per ricevere un messaggio a ogni acquisto/vendita o in caso di errore.", body_style)]
    ]
    t_reg = Table(regole, colWidths=[150, 350])
    t_reg.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
    ]))
    story.append(t_reg)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Deploy Manual generated successfully as: {filename}")

if __name__ == "__main__":
    create_deploy_manual()
