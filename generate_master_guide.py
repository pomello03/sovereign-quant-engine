# generate_master_guide.py
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
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
            return  # Cover page
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 745, 558, 745)
        self.drawString(54, 752, "Sovereign Quant Engine - Guida Master Completa")
        
        # Footer line
        self.line(54, 50, 558, 50)
        self.drawString(54, 38, "RISERVATO - Sovereign Quant Engine System")
        page_text = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(558, 38, page_text)
        self.restoreState()

def create_master_manual(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Color scheme
    primary = colors.HexColor("#0F172A")    # Deep Slate
    accent = colors.HexColor("#2563EB")     # Royal Blue
    success = colors.HexColor("#16A34A")    # Emerald Green
    warning_color = colors.HexColor("#D97706") # Amber
    bg_light = colors.HexColor("#F8FAFC")   # Page body fallback / card bg
    border_color = colors.HexColor("#E2E8F0")

    # Typography styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
        textColor=primary,
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#475569"),
        spaceAfter=40
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
        fontSize=13,
        leading=16,
        textColor=accent,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        backColor=bg_light,
        borderColor=border_color,
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )

    story = []

    # --- COVER PAGE ---
    story.append(Spacer(1, 100))
    story.append(Paragraph("SOVEREIGN QUANT ENGINE", title_style))
    story.append(Paragraph("Manuale Operativo Master & Guida Completa all'Infrastruttura", subtitle_style))
    
    # Metadata Block
    meta_text = """
    <b>Autore:</b> Sovereign Engine Team & Antigravity AI<br/>
    <b>Stato:</b> Approvato per Produzione<br/>
    <b>Ultimo Aggiornamento:</b> Giugno 2026<br/>
    <b>Ambiente:</b> Jesse Trading Framework v0.40+ / Python 3.10+
    """
    story.append(Paragraph(meta_text, body_style))
    story.append(PageBreak())

    # --- SECTION 1: ARCHITETTURA ---
    story.append(Paragraph("1. Panoramica del Sistema e Architettura", h1_style))
    story.append(Paragraph(
        "Il <b>Sovereign Quant Engine</b> è un'infrastruttura integrata a ciclo chiuso (Closed-Loop) per "
        "il design sicuro, la generazione di codice, il backtesting automatizzato e lo stress testing quantitativo "
        "di strategie algoritmiche destinate al mercato delle criptovalute.",
        body_style
    ))
    
    # Table of Nodes
    data_nodes = [
        [Paragraph("<b>Componente (Nodo)</b>", body_style), Paragraph("<b>Funzione Principale</b>", body_style), Paragraph("<b>Sicurezza & Validazione</b>", body_style)],
        [Paragraph("Supervisor", body_style), Paragraph("Valida i file in ingresso (payload) ed emette il blueprint strutturato.", body_style), Paragraph("Verifica schemi JSON formali.", body_style)],
        [Paragraph("Developer Bridge", body_style), Paragraph("Traduce le specifiche logiche in classi Python conformi a Jesse.", body_style), Paragraph("AST parser whitelist. Rifiuta esecuzione di comandi o letture arbitrarie.", body_style)],
        [Paragraph("Quant Validator", body_style), Paragraph("Esegue test Monte Carlo (bootstrap e log-normale) e controlla i limiti di rischio.", body_style), Paragraph("Blocca strategie che superano la probabilità critica di rovina.", body_style)]
    ]
    t = Table(data_nodes, colWidths=[1.5*inch, 2.5*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), border_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # --- SECTION 2: DISPOSITIVI DI SICUREZZA ---
    story.append(Paragraph("2. Dispositivi di Sicurezza Implementati", h1_style))
    
    story.append(Paragraph("2.1 AST Condition Parser", h2_style))
    story.append(Paragraph(
        "Per prevenire attacchi di iniezione di codice (Code Injection) attraverso parametri non fidati, "
        "le stringhe delle condizioni tecniche (es. 'RSI < 30') non vengono mai valutate direttamente tramite eval() o exec(). "
        "Il motore utilizza un <b>Abstract Syntax Tree (AST) Parser</b> che analizza formalmente l'espressione prima "
        "della traduzione in codice Python. Qualsiasi operazione non esplicitamente autorizzata (chiamate a funzioni, "
        "importazioni di librerie, o letture di attributi di sistema) solleva immediatamente un'eccezione di sicurezza.",
        body_style
    ))

    story.append(Paragraph("2.2 Stress Testing Monte Carlo Avanzato", h2_style))
    story.append(Paragraph(
        "Il modulo di validazione quantitativa implementa un doppio motore Monte Carlo per calcolare la probabilità di rovina (Risk of Ruin):",
        body_style
    ))
    story.append(Paragraph(
        "<b>A. Bootstrap Non-Parametrico (Empirico):</b> Se il report del backtest contiene i rendimenti trade-by-trade reali, "
        "l'algoritmo esegue un ricampionamento con reinserimento preservando fedelmente la distribuzione di probabilità originaria "
        "e catturando asimmetrie ed eventi reali.",
        body_style
    ))
    story.append(Paragraph(
        "<b>B. Modello Parametrico Mixture Log-Normale (Fallback):</b> Qualora i dati dei singoli trade non fossero disponibili, "
        "il sistema simula i rendimenti generando campioni casuali da una distribuzione asimmetrica log-normale tarata sui parametri macro "
        "(Sharpe Ratio, Win Rate, Profit Factor, numero totale di operazioni), garantendo una stima accurata della coda di rischio.",
        body_style
    ))
    story.append(Spacer(1, 15))

    # --- SECTION 3: ISTRUZIONI DI CONFIGURAZIONE ---
    story.append(Paragraph("3. Configurazione dell'Infrastruttura", h1_style))
    
    story.append(Paragraph("3.1 Blueprint del Payload (strategy_blueprint.json)", h2_style))
    story.append(Paragraph(
        "Il file blueprint contiene la struttura logica della strategia da testare. Esempio di schema autorizzato:",
        body_style
    ))
    
    blueprint_example = """{
  "strategy_name": "SovereignStrategy",
  "indicators": [
    {"name": "RSI", "params": {"period": 14}}
  ],
  "rules": {
    "entry_long": "RSI < 30",
    "exit_long": "RSI > 70"
  },
  "context": {
    "market_regime": "trending_bullish"
  }
}"""
    story.append(Paragraph(blueprint_example.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))
    
    story.append(Paragraph("3.2 Vincoli di Rischio (risk_constraints.json)", h2_style))
    story.append(Paragraph(
        "Questo file definisce le metriche massime tollerate dal validatore quantitativo:",
        body_style
    ))
    
    constraints_example = """{
  "max_allowed_drawdown": 15.0,
  "max_risk_of_ruin": 0.05,
  "min_sharpe_ratio": 1.2
}"""
    story.append(Paragraph(constraints_example.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))
    story.append(PageBreak())

    # --- SECTION 4: GUIDA OPERATIVA ---
    story.append(Paragraph("4. Istruzioni Operative Step-by-Step", h1_style))
    
    story.append(Paragraph("4.1 Setup Iniziale", h2_style))
    story.append(Paragraph(
        "Clonare il repository e configurare l'ambiente virtuale Python:",
        body_style
    ))
    story.append(Paragraph(
        "git clone https://github.com/pomello03/sovereign-quant-engine.git<br/>"
        "cd sovereign-quant-engine<br/>"
        "pip install -r requirements.txt",
        code_style
    ))

    story.append(Paragraph("4.2 Esecuzione dei Test Unitari", h2_style))
    story.append(Paragraph(
        "Prima di ogni deployment, validare tutti i meccanismi di sicurezza dell'AST e del validatore quantitativo:",
        body_style
    ))
    story.append(Paragraph(
        "pytest -v",
        code_style
    ))

    story.append(Paragraph("4.3 Lancio della Simulazione di Pipeline", h2_style))
    story.append(Paragraph(
        "Eseguire la simulazione end-to-end (dalla generazione automatica del codice al report quantitativo Monte Carlo):",
        body_style
    ))
    story.append(Paragraph(
        "python run_simulation.py",
        code_style
    ))
    story.append(Paragraph(
        "Questo script genera automaticamente i file della strategia dentro <b>jesse_workspace/strategies/SovereignStrategy/</b> "
        "ed esporta i risultati quantitativi in <b>payload_drop/validation_report.json</b>.",
        body_style
    ))

    story.append(Paragraph("4.4 Visualizzazione del Dashboard Grafico", h2_style))
    story.append(Paragraph(
        "Aprire il file <b>payload_drop/validation_dashboard.html</b> in qualsiasi browser web per visualizzare l'interfaccia interattiva "
        "con le curve di stress test Monte Carlo e il responso finale del validatore.",
        body_style
    ))
    
    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(base_dir, "docs", "Guida_Master_Completa.pdf")
    create_master_manual(target_path)
    print(f">> Master manual created successfully at: {target_path}")
