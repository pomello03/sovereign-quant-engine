# generate_pdf.py
import sys
import subprocess
import os

# Auto-install reportlab if missing
try:
    import reportlab
except ImportError:
    print("ReportLab is required to generate the PDF. Installing reportlab via pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
    print("ReportLab installed successfully.")

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
            return  # Suppress page number on cover page
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header rule and text
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 750, 558, 750)
        self.drawString(54, 755, "Sovereign Quant Engine - Guida per Principianti")
        
        # Footer rule and page text
        self.line(54, 50, 558, 50)
        page_text = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(558, 38, page_text)
        self.drawString(54, 38, "Documento Riservato - Sovereign Engine")
        self.restoreState()

def create_manual(filename=None):
    if filename is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(base_dir, "docs", "Sovereign_Quant_Engine_Manual.pdf")
    # Target size: letter. Margins: 0.75 in (54 pt)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    primary = colors.HexColor("#8B5CF6")    # Violet
    secondary = colors.HexColor("#06B6D4")  # Cyan
    dark_text = colors.HexColor("#0F172A")  # Slate 900
    muted_text = colors.HexColor("#475569") # Slate 600
    bg_light = colors.HexColor("#F8FAFC")   # Slate 50
    border_color = colors.HexColor("#E2E8F0") # Slate 200

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=32,
        leading=38,
        textColor=primary,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=18,
        textColor=muted_text,
        spaceAfter=30
    )
    
    h1_style = ParagraphStyle(
        'Header1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary,
        spaceBefore=20,
        spaceAfter=12,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=secondary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=dark_text,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
        backColor=bg_light,
        borderColor=border_color,
        borderWidth=1,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=10,
        keepWithNext=True
    )

    callout_style = ParagraphStyle(
        'CalloutStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=13.5,
        textColor=muted_text,
        backColor=colors.HexColor("#EEF2F6"),
        borderColor=colors.HexColor("#3B82F6"),
        borderWidth=1,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=10
    )

    story = []

    # ================= PAGE 1: COVER =================
    story.append(Spacer(1, 150))
    story.append(Paragraph("SOVEREIGN QUANT ENGINE", title_style))
    story.append(Paragraph("Manuale Operativo e Guida per Principianti", subtitle_style))
    story.append(Spacer(1, 30))
    
    # Metadata Block
    meta_data = [
        [Paragraph("<b>Autore:</b> Antigravity AI Coding Assistant", body_style)],
        [Paragraph("<b>Versione:</b> 1.0.0 (Stabile)", body_style)],
        [Paragraph("<b>Destinatario:</b> Sovereign Quant Engine Operator", body_style)],
        [Paragraph("<b>Data Rilascio:</b> Giugno 2026", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[300])
    t_meta.setStyle(TableStyle([
        ('LINEBEFORE', (0,0), (0,-1), 3, primary),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    
    story.append(Spacer(1, 150))
    story.append(Paragraph("<i>Architettura Multi-Agente a Ciclo Chiuso basata su Jesse Framework via MCP</i>", body_style))
    story.append(PageBreak())

    # ================= PAGE 2: INTRODUZIONE =================
    story.append(Paragraph("1. Cos'è il Sovereign Quant Engine?", h1_style))
    story.append(Paragraph(
        "Il <b>Sovereign Quant Engine</b> è un'infrastruttura di trading quantitativo avanzata progettata per "
        "automatizzare e blindare il processo di creazione di strategie di trading finanziario. A differenza dei sistemi "
        "tradizionali in cui un singolo sviluppatore scrive codice e logica di money management contemporaneamente, "
        "questo motore separa nettamente la fase logica da quella di programmazione per eliminare le allucinazioni delle IA "
        "e prevenire l'azzeramento del capitale (Rovina).",
        body_style
    ))
    
    story.append(Paragraph("L'architettura si divide in due fasi distinte:", h2_style))
    
    fasi_data = [
        [Paragraph("<b>Fase 1: Specifica Logica (Nodi Worker)</b>", body_style),
         Paragraph("Gli agenti di Alpha, Rischio e Contesto producono esclusivamente file di specifica strutturati in formato JSON. Questi agenti non hanno accesso al codice sorgente e non possono inventare o modificare logiche a partita in corso.", body_style)],
        [Paragraph("<b>Fase 2: Compilazione & Validazione (Supervisor/Core)</b>", body_style),
         Paragraph("Il <b>Supervisor</b> valida i JSON della Fase 1, applica il <b>Bias di Rovina</b> (rifiuta all'istante drawdown stimati &gt; 2.0%) e invoca l'agente Developer per implementare la strategia conforme a Jesse. Il codice viene testato via backtest e validato con stress test Monte Carlo.", body_style)]
    ]
    t_fasi = Table(fasi_data, colWidths=[150, 350])
    t_fasi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_fasi)
    story.append(Spacer(1, 15))

    story.append(Paragraph("2. Struttura dei Contratti Dati (I file JSON)", h1_style))
    story.append(Paragraph(
        "I nodi operativi comunicano scambiandosi file JSON rigorosamente controllati da schemi predefiniti nella cartella <b>schemas/</b>:",
        body_style
    ))
    
    json_list = [
        [Paragraph("<b>alpha_spec.json</b>", body_style), Paragraph("Contiene il nome della strategia, la lista degli indicatori tecnici (es. RSI, SMA) ed i rispettivi parametri, e le condizioni logiche per l'apertura delle posizioni Long e Short.", body_style)],
        [Paragraph("<b>risk_constraints.json</b>", body_style), Paragraph("Contiene i parametri di gestione del rischio: massimo drawdown tollerato, tipo e valore dello Stop Loss, Take Profit e sizing massimo della posizione.", body_style)],
        [Paragraph("<b>context_regime.json</b>", body_style), Paragraph("Contiene i dati di contesto sul mercato: se è in trend (bullish/bearish), in fase di accumulazione/range, la forza del trend e lo stato di volatilità.", body_style)],
        [Paragraph("<b>strategy_blueprint.json</b>", body_style), Paragraph("Generato dal Supervisor. Unisce le tre specifiche precedenti in un unico file con verdetto 'APPROVED' per dare il via libera all'agente Developer.", body_style)]
    ]
    t_json = Table(json_list, colWidths=[130, 370])
    t_json.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-2), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_json)
    story.append(PageBreak())

    # ================= PAGE 3: GUIDA DI SETUP =================
    story.append(Paragraph("3. Setup e Accensione dell'Infrastruttura", h1_style))
    story.append(Paragraph(
        "Per poter eseguire la simulazione della pipeline e il paper trading, devi assicurarti che tutti i componenti siano 'accesi' "
        "e pronti a comunicare tra loro. Il database PostgreSQL funge da memoria centrale in cui Jesse salva i dati storici delle candele.",
        body_style
    ))
    
    story.append(Paragraph("Passo 1: Avviare i container Docker", h2_style))
    story.append(Paragraph(
        "Apri il terminale PowerShell di Windows ed esegui i seguenti comandi per avviare il database PostgreSQL in background:",
        body_style
    ))
    story.append(Paragraph(
        "cd C:\\Users\\franc\\Documents\\sovereign-quant-engine<br/>"
        "docker-compose up -d",
        code_style
    ))
    
    story.append(Paragraph("Passo 2: Verificare lo stato dei servizi", h2_style))
    story.append(Paragraph(
        "Per accertarti che il database sia correttamente ONLINE e in ascolto sulla porta standard (5432), esegui:",
        body_style
    ))
    story.append(Paragraph(
        "docker ps",
        code_style
    ))
    story.append(Paragraph(
        "<i>Dovresti vedere una riga con l'immagine postgres:15-alpine e lo stato 'Up ...'. In caso di errore, assicurati che Docker Desktop sia aperto e in esecuzione sul tuo computer.</i>",
        callout_style
    ))
    
    story.append(Paragraph("4. Eseguire la Pipeline di Validazione", h1_style))
    story.append(Paragraph(
        "Abbiamo predisposto uno script completo, <b>run_simulation.py</b>, per consentirti di testare l'intera pipeline logica e "
        "di autocorrezione con un solo comando. Lo script si occuperà di simulare la generazione del codice di trading in base al "
        "blueprint approvato e di eseguire stress test Monte Carlo.",
        body_style
    ))
    
    story.append(Paragraph("Esegui lo script di simulazione:", h2_style))
    story.append(Paragraph(
        "python run_simulation.py",
        code_style
    ))
    
    story.append(Paragraph(
        "<b>Cosa succede sotto il cofano:</b><br/>"
        "1. Il Supervisor legge i file in <i>payload_drop/</i> e verifica che rispettino i contratti.<br/>"
        "2. Viene verificata l'invariante del Rischio: se il drawdown impostato supera il 2.0%, lo script si interrompe immediatamente per proteggerti.<br/>"
        "3. Se approvato, il Developer Bridge scrive il codice Python in <i>jesse_workspace/strategies/SovereignStrategy/</i>.<br/>"
        "4. Il Validator esegue il backtest e genera uno stress test Monte Carlo con 1.000 iterazioni, scrivendo il report di validazione.",
        callout_style
    ))
    story.append(PageBreak())

    # ================= PAGE 4: RISCONTRI GRAFICI =================
    story.append(Paragraph("5. Visualizzare i Riscontri Grafici", h1_style))
    story.append(Paragraph(
        "Un quant trader non può operare senza metriche grafiche e curve di rendimento. Il Sovereign Quant Engine "
        "offre due opzioni principali per analizzare visivamente le performance prima di andare a mercato.",
        body_style
    ))
    
    story.append(Paragraph("Opzione A: Dashboard di Validazione Interattiva (Inclusa)", h2_style))
    story.append(Paragraph(
        "Ogni volta che avvii <i>run_simulation.py</i>, il motore compila una splendida pagina web interattiva locale nella cartella di scambio. "
        "Questa pagina non richiede installazioni aggiuntive ed è apribile su qualsiasi browser.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Percorso del file:</b><br/>"
        "Fai doppio clic sul file: <font face='Courier'>C:\\Users\\franc\\Documents\\sovereign-quant-engine\\payload_drop\\validation_dashboard.html</font>",
        callout_style
    ))
    story.append(Paragraph(
        "La dashboard ti mostrerà:<br/>"
        "&bull; <b>L'Equity Curve Media:</b> La traiettoria di rendimento attesa della strategia.<br/>"
        "&bull; <b>10 Percorsi Casuali Monte Carlo:</b> Simulazioni statistiche per valutare scenari peggiori e dispersione dei trade.<br/>"
        "&bull; <b>Risk of Ruin:</b> La probabilità percentuale che la strategia azzeri il capitale superando il drawdown massimo.",
        body_style
    ))

    story.append(Paragraph("Opzione B: Connessione Grafica con Jesse Trade Dashboard", h2_style))
    story.append(Paragraph(
        "Per visualizzare l'interfaccia ufficiale di Jesse (con grafici a candele e posizioni reali a mercato) senza installare moduli locali pesanti, "
        "puoi connetterti al client web ufficiale di Jesse:",
        body_style
    ))
    story.append(Paragraph(
        "cd jesse_workspace<br/>"
        "jesse make-ip",
        code_style
    ))
    story.append(Paragraph(
        "Il comando genererà un <b>Indirizzo IP locale</b> (es. 127.0.0.1:8000) e una <b>Password/Token</b>. "
        "Ti basterà aprire il browser su <b>https://jesse.trade/dashboard</b>, inserire l'IP locale e il token per iniziare a visualizzare "
        "l'equity curve in tempo reale.",
        body_style
    ))

    story.append(Paragraph("6. Glossario Essenziale delle Metriche", h1_style))
    story.append(Paragraph(
        "Per valutare se la tua strategia è solida, devi concentrarti su queste 4 metriche fondamentali:",
        body_style
    ))
    
    glossario = [
        [Paragraph("<b>Sharpe Ratio</b>", body_style), Paragraph("Misura il rendimento extra ottenuto per unità di rischio. Più è alto, più il rendimento è stabile. Obiettivo: &ge; 1.5 per strategie reali.", body_style)],
        [Paragraph("<b>Max Drawdown (DD)</b>", body_style), Paragraph("Rappresenta la massima perdita registrata dal picco di equity più alto al punto più basso. Nella nostra bibbia, è limitato severamente al 2.0% per prevenire la rovina.", body_style)],
        [Paragraph("<b>Profit Factor</b>", body_style), Paragraph("Rapporto tra il profitto lordo e la perdita lorda delle operazioni. Un valore di 1.5 significa che per ogni dollaro perso, la strategia ne ha guadagnati 1.5. Obiettivo: &gt; 1.3.", body_style)],
        [Paragraph("<b>Risk of Ruin (Rovina)</b>", body_style), Paragraph("La probabilità statistica, calcolata tramite il nostro stress test Monte Carlo, che la strategia superi il drawdown massimo consentito nel corso della sua vita.", body_style)]
    ]
    t_glos = Table(glossario, colWidths=[130, 370])
    t_glos.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-2), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_glos)

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Manual generated successfully as: {filename}")

if __name__ == "__main__":
    create_manual()
