# generate_easy_pdf.py
import sys
import subprocess
import os

# Auto-install reportlab if missing
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
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header rule and text
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 750, 558, 750)
        self.drawString(54, 755, "Sovereign Engine spiegato a un Cameriere o Giardiniere")
        
        # Footer rule and page text
        self.line(54, 50, 558, 50)
        page_text = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(558, 38, page_text)
        self.restoreState()

def create_easy_manual(filename=None):
    if filename is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(base_dir, "docs", "Guida_Semplicissima_Sovereign_Quant_Engine.pdf")
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Premium colors: Warm Amber and Indigo
    primary = colors.HexColor("#4F46E5")    # Indigo
    secondary = colors.HexColor("#D97706")  # Amber
    dark_text = colors.HexColor("#1E293B")  # Slate 800
    muted_text = colors.HexColor("#475569") # Slate 600
    bg_light = colors.HexColor("#FFFBEB")   # Amber 50 (very soft cream)
    border_color = colors.HexColor("#F3F4F6")

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
        textColor=primary,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=17,
        textColor=muted_text,
        spaceAfter=30
    )
    
    h1_style = ParagraphStyle(
        'Header1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary,
        spaceBefore=18,
        spaceAfter=10,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=secondary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=dark_text,
        spaceAfter=10
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
        backColor=colors.HexColor("#F1F5F9"),
        borderColor=colors.HexColor("#CBD5E1"),
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
        leading=14,
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
    story.append(Spacer(1, 140))
    story.append(Paragraph("LA GUIDA SEMPLICISSIMA", title_style))
    story.append(Paragraph("Capire il Sovereign Quant Engine usando la metafora della Cucina e del Giardino", subtitle_style))
    story.append(Spacer(1, 25))
    
    meta_data = [
        [Paragraph("<b>Pensato per:</b> Chi ha zero conoscenze di informatica o finanza", body_style)],
        [Paragraph("<b>Metodo:</b> Analogie pratiche (Camerieri, Cuochi, Semi e Terreni)", body_style)],
        [Paragraph("<b>Data di Pubblicazione:</b> Giugno 2026", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[350])
    t_meta.setStyle(TableStyle([
        ('LINEBEFORE', (0,0), (0,-1), 3, secondary),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    
    story.append(Spacer(1, 160))
    story.append(Paragraph("<i>Non serve essere programmatori per capire come difendere il proprio capitale.</i>", body_style))
    story.append(PageBreak())

    # ================= PAGE 2: LE METAFORE =================
    story.append(Paragraph("1. La Metafora del Ristorante (Come funziona l'Engine)", h1_style))
    story.append(Paragraph(
        "Immagina di voler gestire un ristorante di lusso, ma invece di assumere una persona che fa tutto da sola "
        "(e che rischierebbe di fare confusione tra i tavoli e i fornelli), decidi di dividere i compiti in modo rigoroso. "
        "Questo ristorante è il nostro <b>Sovereign Quant Engine</b>.",
        body_style
    ))
    
    story.append(Paragraph("I Ruoli in Cucina:", h2_style))
    
    cucina_data = [
        [Paragraph("<b>L'Agente Alpha (Il Menù / La Ricetta)</b>", body_style),
         Paragraph("Lui decide quali piatti preparare e quando servirli. Nel trading, decide se comprare o vendere basandosi su regole fisse (es. 'Se l'ingrediente costa poco, compralo').", body_style)],
        [Paragraph("<b>L'Agente Rischio (Il Direttore di Sala)</b>", body_style),
         Paragraph("Lui controlla la cassa. Dice: 'Oggi non possiamo spendere più di 50 euro per tavolo' (dimensione della posizione) e 'Se un tavolo rimanda indietro il cibo, smettiamo subito di servire quel piatto per non perdere soldi' (Stop Loss).", body_style)],
        [Paragraph("<b>L'Agente Contesto (Il Meteo)</b>", body_style),
         Paragraph("Lui controlla l'esterno. Dice: 'Oggi piove, arriveranno pochi clienti' oppure 'È sabato sera, ci sarà il pienone' (Regime di mercato, trend e volatilità).", body_style)],
        [Paragraph("<b>Lo Chef Supervisor (L'Ispettore Sanitario)</b>", body_style),
         Paragraph("Lui è il giudice supremo. Controlla che le ricette del Menù rispettino le regole del Direttore di Sala. Se il Menù rischia di spendere troppo budget o propone cibi non sicuri (un drawdown stimato oltre il 2%), lo Chef <b>strappa il foglio</b> e blocca tutto (Bias di Rovina).", body_style)]
    ]
    t_cucina = Table(cucina_data, colWidths=[160, 340])
    t_cucina.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
    ]))
    story.append(t_cucina)
    
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Il Ciclo Chiuso (Il Piatto Bruciato):</b> Se l'aiuto cuoco (l'agente Developer) commette un errore di ortografia nel codice "
        "e la strategia non funziona (piatto bruciato), lo Chef gli mostra esattamente l'errore commesso. L'aiuto cuoco "
        "deve rifare il piatto seguendo le correzioni finché non è servito alla perfezione.",
        callout_style
    ))
    story.append(PageBreak())

    # ================= PAGE 3: ACCENDERE E FAR GIRARE =================
    story.append(Paragraph("2. Come 'Accendere' la Cucina (I Frigoriferi e la Corrente)", h1_style))
    story.append(Paragraph(
        "Prima di poter cucinare, devi accendere la luce e i frigoriferi del ristorante. Se la corrente è spenta, "
        "tutto il cibo nei frigoriferi andrà a male. Nel nostro computer, questa fonte di energia e conservazione "
        "è il database (PostgreSQL) gestito da Docker.",
        body_style
    ))
    
    story.append(Paragraph("Passo 1: Accendi l'elettricità (Docker)", h2_style))
    story.append(Paragraph(
        "È come premere l'interruttore generale della cucina. Apri il terminale PowerShell di Windows e scrivi:",
        body_style
    ))
    story.append(Paragraph(
        "cd C:\\Users\\franc\\Documents\\sovereign-quant-engine<br/>"
        "docker-compose up -d",
        code_style
    ))
    
    story.append(Paragraph("Passo 2: Controlla che i frigoriferi siano freddi", h2_style))
    story.append(Paragraph(
        "Esegui questo comando per verificare che il database (il nostro frigorifero) sia acceso e funzionante:",
        body_style
    ))
    story.append(Paragraph(
        "docker ps",
        code_style
    ))
    story.append(Paragraph(
        "Se vedi apparire una tabella con scritto 'sovereign-postgres' sotto la colonna NAMES, la cucina ha corrente "
        "ed è pronta ad ospitare le ricette di trading.",
        body_style
    ))

    story.append(Paragraph("Passo 3: Manda in cucina gli ordini", h2_style))
    story.append(Paragraph(
        "Ora puoi avviare la simulazione automatica. Questo comando prende il menù (Alpha), le regole di spesa (Risk) e il meteo (Context), "
        "controlla che tutto sia sicuro, genera il piatto di trading e testa la ricetta nel passato per vedere se fa guadagnare il ristorante:",
        body_style
    ))
    story.append(Paragraph(
        "python run_simulation.py",
        code_style
    ))
    story.append(PageBreak())

    # ================= PAGE 4: RISCONTRI GRAFICI =================
    story.append(Paragraph("3. I Riscontri Grafici (Il Libro dei Conti ed i Grafici)", h1_style))
    story.append(Paragraph(
        "Per capire se il tuo ristorante sta guadagnando o se rischi di fallire, hai bisogno di un riscontro visivo chiaro. "
        "Non serve leggere righe di codice: abbiamo creato strumenti visivi adatti a tutti.",
        body_style
    ))
    
    story.append(Paragraph("La Dashboard di Validazione (Il tuo Pannello di Controllo)", h2_style))
    story.append(Paragraph(
        "Alla fine di ogni simulazione, il motore crea un file speciale chiamato <b>validation_dashboard.html</b>. "
        "È come un grande schermo touch appeso in cucina che mostra l'andamento delle spese.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Come aprirlo:</b> Fai semplicemente doppio clic sul file sul tuo computer:<br/>"
        "<font face='Courier'>C:\\Users\\franc\\Documents\\sovereign-quant-engine\\payload_drop\\validation_dashboard.html</font>",
        callout_style
    ))
    
    story.append(Paragraph("Cosa guardare su questo schermo:", h2_style))
    
    indicatori_data = [
        [Paragraph("<b>Sharpe Ratio (La Costanza della Cucina)</b>", body_style),
         Paragraph("Indica se i tuoi profitti sono costanti o se sono dovuti a pura fortuna. Se il valore è sopra 1.5, significa che il tuo ristorante serve piatti di qualità costante tutti i giorni.", body_style)],
        [Paragraph("<b>Max Drawdown (La Peggiore Giornata)</b>", body_style),
         Paragraph("Rappresenta la perdita più grande che il ristorante ha registrato in un singolo mese (es. se hai dovuto buttare del cibo andato a male). Per sicurezza, non lasciamo mai che superi il 2.0% delle nostre risorse.", body_style)],
        [Paragraph("<b>Risk of Ruin (Il Rischio di Fallimento)</b>", body_style),
         Paragraph("Tramite una simulazione chiamata <b>Monte Carlo</b> (che simula 1.000 sabati sera diversi con eventi casuali come blackout, ritardi dei fornitori o clienti difficili), calcoliamo qual è la probabilità percentuale che il ristorante finisca i soldi e debba chiudere.", body_style)]
    ]
    t_ind = Table(indicatori_data, colWidths=[180, 320])
    t_ind.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-2), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_ind)
    
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Ricorda:</b> Se vedi la scritta rossa 'REJECTED (RISK LIMIT VIOLATION)' sulla dashboard, significa che "
        "l'Ispettore Sanitario (il Supervisor) ha fermato la strategia perché rischiava di farti perdere troppi soldi. "
        "Il motore ti protegge impedendo l'esecuzione di strategie pericolose.",
        callout_style
    ))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Easy Manual generated successfully as: {filename}")

if __name__ == "__main__":
    create_easy_manual()
