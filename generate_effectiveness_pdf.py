# generate_effectiveness_pdf.py
import os
import sys

# Ensure reportlab is installed
try:
    import reportlab
except ImportError:
    import subprocess
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
        self.setFillColor(colors.HexColor("#4B5563"))
        
        # Header rule and text
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(54, 750, 558, 750)
        self.drawString(54, 755, "Sovereign Quant Engine - Analisi di Efficacia e Robustezza")
        
        # Footer rule and page text
        self.line(54, 50, 558, 50)
        page_text = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(558, 38, page_text)
        self.drawString(54, 38, "Documento Riservato - Analisi Tecnica Interna")
        self.restoreState()

def generate_report(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Premium colors: Deep Slate Blue & Soft Teal
    primary = colors.HexColor("#1E3A8A")    # Blue 900
    secondary = colors.HexColor("#0D9488")  # Teal 600
    accent = colors.HexColor("#B45309")     # Amber 700
    dark_text = colors.HexColor("#111827")  # Slate 900
    muted_text = colors.HexColor("#4B5563") # Slate 600
    bg_light = colors.HexColor("#F0FDFA")   # Teal 50 (soft background)
    border_color = colors.HexColor("#E5E7EB")

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
        fontSize=11.5,
        leading=14.5,
        textColor=secondary,
        spaceBefore=12,
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
        fontSize=8.5,
        leading=11.5,
        textColor=dark_text,
        backColor=colors.HexColor("#F3F4F6"),
        borderColor=border_color,
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
        keepWithNext=True
    )

    callout_style = ParagraphStyle(
        'CalloutStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=13.5,
        textColor=dark_text,
        backColor=bg_light,
        borderColor=secondary,
        borderWidth=1,
        borderPadding=10,
        spaceBefore=6,
        spaceAfter=10
    )

    story = []

    # ================= PAGE 1: COVER =================
    story.append(Spacer(1, 150))
    story.append(Paragraph("ANALISI DI EFFICACIA E ROBUSTEZZA", title_style))
    story.append(Paragraph("Valutazione critica dell'infrastruttura Sovereign Quant Engine", subtitle_style))
    story.append(Spacer(1, 20))
    
    meta_data = [
        [Paragraph("<b>Progetto:</b> Sovereign Quant Engine (Jesse Multi-Agent Framework)", body_style)],
        [Paragraph("<b>Analista:</b> Antigravity AI Coding Assistant", body_style)],
        [Paragraph("<b>Ambito:</b> Controllo del Rischio, Automazione e Sicurezza Finanziaria", body_style)],
        [Paragraph("<b>Data di Valutazione:</b> Giugno 2026", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[380])
    t_meta.setStyle(TableStyle([
        ('LINEBEFORE', (0,0), (0,-1), 3, secondary),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    
    story.append(Spacer(1, 180))
    story.append(Paragraph("<i>Documento ad uso interno contenente l'audit strutturale e le metriche di affidabilità.</i>", body_style))
    story.append(PageBreak())

    # ================= PAGE 2: VALUTAZIONE METODOLOGIA =================
    story.append(Paragraph("1. Sintesi della Metodologia del Progetto", h1_style))
    story.append(Paragraph(
        "Il Sovereign Quant Engine propone una soluzione robusta ad uno dei problemi più critici del trading algoritmico "
        "gestito da intelligenze artificiali: <b>le allucinazioni del codice e la violazione dei limiti di rischio</b>. "
        "Molti sistemi falliscono perché il bot di trading scrive la strategia ed esegue l'ordine direttamente, senza passaggi "
        "intermedi di convalida del rischio.",
        body_style
    ))
    story.append(Paragraph(
        "L'efficacia del Sovereign Quant Engine si basa su una <b>pipeline a ciclo chiuso divisa in tre fasi distinte</b>:",
        body_style
    ))
    
    fasi_tabelle = [
        [Paragraph("<b>Fase dell'Engine</b>", body_style), Paragraph("<b>Meccanismo di Efficacia</b>", body_style), Paragraph("<b>Grado di Sicurezza</b>", body_style)],
        [Paragraph("<b>1. Supervisor & Contratti</b>", body_style), Paragraph("Valida i file JSON degli agenti Alpha, Risk e Context prima che venga scritta qualsiasi riga di codice. Applica il <i>Bias di Rovina</i> bloccando all'istante drawdown > 2.0%.", body_style), Paragraph("<font color='green'><b>Elevatissimo</b></font><br/>(Blocco statico)", body_style)],
        [Paragraph("<b>2. Developer & Closed-Loop</b>", body_style), Paragraph("Traduce la specifica in codice Python. Esegue il backtest e, in caso di errori di sintassi o import, corregge autonomamente il codice e ritenta l'esecuzione.", body_style), Paragraph("<font color='blue'><b>Alto</b></font><br/>(Autocorrettivo)", body_style)],
        [Paragraph("<b>3. Stress Test Monte Carlo</b>", body_style), Paragraph("Shuffla i rendimenti dei singoli scambi su 1.000 simulazioni basandosi su Win Rate e Profit Factor reali. Stima matematicamente la probabilità di rovina.", body_style), Paragraph("<font color='green'><b>Elevato</b></font><br/>(Statistico)", body_style)]
    ]
    t_fasi = Table(fasi_tabelle, colWidths=[130, 240, 130])
    t_fasi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E5E7EB")),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_fasi)
    
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Punto di Forza Chiave:</b> Il sistema non si limita a dire 'il backtest ha funzionato', ma risponde alla domanda: "
        "'Qual è la probabilità che, a causa della varianza casuale dei mercati, questa strategia superi il drawdown massimo?' "
        "Questo riduce drasticamente il rischio di overfitting.",
        callout_style
    ))
    story.append(PageBreak())

    # ================= PAGE 3: PUNTI DI FORZA E DEBOLEZZA =================
    story.append(Paragraph("2. Analisi dei Punti di Forza (Strengths)", h1_style))
    story.append(Paragraph(
        "L'architettura attuale presenta diversi elementi d'eccellenza dal punto di vista dell'ingegneria del software applicata alla finanza:",
        body_style
    ))
    story.append(Paragraph(
        "<b>&bull; Cross-Validation Rigida:</b> L'aggiunta del controllo di coerenza sul rapporto rischio/rendimento minimo impedisce "
        "l'esecuzione di strategie con impostazioni logiche palesemente errate (es. stop loss troppo larghi rispetto al target).<br/>"
        "<b>&bull; Monte Carlo Dinamico e Coerente:</b> L'utilizzo del Win Rate reale estratto dal backtest, combinato con la formula "
        "corretta per ricavare il guadagno medio mantenendo fermo il Profit Factor, fornisce simulazioni di equity realistiche.<br/>"
        "<b>&bull; Generazione di Codice Jesse Nativo:</b> Invece di limitarsi a inserire commenti, il Developer Bridge genera "
        "properties Python effettive per gli indicatori tecnici e traduce le regole in codice booleano. La strategia generata "
        "è immediatamente importabile ed eseguibile all'interno di Jesse.",
        body_style
    ))
    
    story.append(Paragraph("3. Aree di Vulnerabilità e Limitazioni (Weaknesses)", h1_style))
    story.append(Paragraph(
        "Nonostante l'elevata qualità dell'infrastruttura, sono state identificate alcune aree di miglioramento critiche per la produzione reale:",
        body_style
    ))
    
    debolezze = [
        [Paragraph("<b>Vulnerabilità Identificata</b>", body_style), Paragraph("<b>Impatto Operativo</b>", body_style), Paragraph("<b>Mitigazione Consigliata</b>", body_style)],
        [Paragraph("<b>Modello Monte Carlo Binario</b>", body_style), Paragraph("La simulazione assume che i trade siano solo vittorie (tutte uguali) o perdite (tutte uguali). Nella realtà, i profitti e le perdite seguono una distribuzione continua (Fat-Tailed).", body_style), Paragraph("Campionare direttamente dall'array storico dei singoli trade del backtest (Bootstrapping non parametrico).", body_style)],
        [Paragraph("<b>Robustezza del Parser Logico</b>", body_style), Paragraph("Il traduttore di espressioni in `developer_bridge.py` usa espressioni regolari semplici. Condizioni molto complesse o annidate potrebbero generare codice non valido.", body_style), Paragraph("Integrare un AST Parser (Abstract Syntax Tree) per convalidare e compilare le espressioni in modo formale.", body_style)],
        [Paragraph("<b>Assenza di Gestione Regime Dinamico</b>", body_style), Paragraph("Sebbene `context_regime.json` sia validato, i parametri della strategia (params.py) non cambiano dinamicamente in base allo stato del mercato (es. trend vs range).", body_style), Paragraph("Implementare selettori di parametri condizionali nel file params.py generato (regime-switching).", body_style)]
    ]
    t_deb = Table(debolezze, colWidths=[120, 190, 190])
    t_deb.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F9FAFB")),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_deb)
    story.append(PageBreak())

    # ================= PAGE 4: STRATEGIA DI SVILUPPO FUTURO =================
    story.append(Paragraph("4. Roadmap Consigliata per la Produzione Reale (IRL)", h1_style))
    story.append(Paragraph(
        "Per portare il Sovereign Quant Engine ad un livello di livello istituzionale (pronto per il live trading reale "
        "con capitale significativo), si consiglia di seguire i seguenti passi di sviluppo:",
        body_style
    ))
    
    story.append(Paragraph("Fase A: Ottimizzazione del Simulatore Monte Carlo", h2_style))
    story.append(Paragraph(
        "Implementare il campionamento statistico reale (Bootstrapping) sui trade eseguiti da Jesse. Invece di "
        "generare trade fittizi basati su Win Rate medio, lo stress test deve campionare casualmente (con ripetizione) "
        "dall'elenco effettivo dei trade storici. Questo catturerà automaticamente gli scostamenti insoliti e le sequenze di perdite consecutive reali.",
        body_style
    ))
    
    story.append(Paragraph("Fase B: AST Parser per le Condizioni Alpha", h2_style))
    story.append(Paragraph(
        "Sostituire il parser a base regex in `developer_bridge.py` con una classe di compilazione basata sulla libreria "
        "standard `ast` di Python. Questo permetterà all'utente di scrivere formule complesse nelle specifiche (es. "
        "`(rsi < 30 and close > sma) or macd_hist > 0`) garantendo che il codice generato sia sempre privo di errori di sintassi.",
        body_style
    ))
    
    story.append(Paragraph("Fase C: Integrazione Live con Notifiche Telegram e Discord", h2_style))
    story.append(Paragraph(
        "Sviluppare un microservizio in Docker che monitora lo stato del bot live su Hetzner. Se il bot genera un errore o "
        "il drawdown in tempo reale si avvicina al limite del 2%, il servizio deve poter arrestare automaticamente il container "
        "Docker e notificare istantaneamente l'operatore tramite un bot Telegram.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Verdetto di Efficacia Globale:</b> Il Sovereign Quant Engine è un'infrastruttura altamente efficace per "
        "il controllo del rischio. L'approccio rigoroso guidato da contratti JSON e convalidato da stress test statistici "
        "pone questo progetto ben al di sopra delle soluzioni di trading automatizzate retail, fornendo una reale barriera "
        "protettiva a difesa del capitale investito.",
        callout_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Effectiveness Report generated successfully as: {filename}")

if __name__ == "__main__":
    generate_report(os.path.join("docs", "Analisi_Efficacia_Sovereign_Quant_Engine.pdf"))
