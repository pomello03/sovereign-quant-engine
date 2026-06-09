// Dashboard state variables
let eventSource = null;
let optChart = null;

// DOM elements
const startBtn = document.getElementById('start-btn');
const maxIterationsInput = document.getElementById('max-iterations');
const drawdownLimitInput = document.getElementById('drawdown-limit');

const systemStatusBadge = document.getElementById('system-status-badge');
const systemStatusIndicator = systemStatusBadge.querySelector('.status-indicator');
const systemStatusText = document.getElementById('system-status-text');

const terminalBody = document.getElementById('terminal-body');
const clearBtn = document.getElementById('clear-btn');

const metricSharpe = document.getElementById('metric-sharpe');
const metricSharpeStatus = document.getElementById('metric-sharpe-status');
const metricPf = document.getElementById('metric-pf');
const metricPfStatus = document.getElementById('metric-pf-status');
const metricDd = document.getElementById('metric-dd');
const metricDdStatus = document.getElementById('metric-dd-status');
const metricRuin = document.getElementById('metric-ruin');
const metricRuinStatus = document.getElementById('metric-ruin-status');

const chartPlaceholder = document.getElementById('chart-placeholder-text');

const stepSupervisor = document.getElementById('step-supervisor');
const stepBridge = document.getElementById('step-bridge');
const stepValidator = document.getElementById('step-validator');
const stepOptimizer = document.getElementById('step-optimizer');

const verdictModal = document.getElementById('verdict-modal');
const verdictIconContainer = document.getElementById('verdict-icon-container');
const verdictIcon = document.getElementById('verdict-icon');
const verdictTitle = document.getElementById('verdict-title');
const verdictSubtitle = document.getElementById('verdict-subtitle');
const closeModalBtn = document.getElementById('close-modal-btn');

const vSizing = document.getElementById('v-sizing');
const vSl = document.getElementById('v-sl');
const vAvgDd = document.getElementById('v-avg-dd');
const vPeakDd = document.getElementById('v-peak-dd');
const vRuin = document.getElementById('v-ruin');

// Help Modal elements
const helpModal = document.getElementById('help-modal');
const helpTitle = document.getElementById('help-title');
const helpSubtitle = document.getElementById('help-subtitle');
const helpDescription = document.getElementById('help-description');
const helpBullets = document.getElementById('help-bullets');
const helpIcon = document.getElementById('help-icon');
const closeHelpBtn = document.getElementById('close-help-btn');

// Helper to log to the terminal
function log(message, type = 'system') {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span style="color: #6b7280; font-weight: 500;">[${time}]</span> ${message}`;
    terminalBody.appendChild(line);
    terminalBody.scrollTop = terminalBody.scrollHeight;
}

// Reset stepper UI
function resetStepper() {
    [stepSupervisor, stepBridge, stepValidator, stepOptimizer].forEach(el => {
        el.className = 'step';
    });
}

// Set status badge state
function setSystemStatus(state, text) {
    systemStatusIndicator.className = `status-indicator ${state}`;
    systemStatusText.innerText = text;
}

// Initialize the dual Y-axis Chart
function initChart() {
    if (optChart) {
        optChart.destroy();
    }
    
    chartPlaceholder.style.display = 'none';
    
    const ctx = document.getElementById('opt-chart').getContext('2d');
    optChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Risk of Ruin (%)',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.05)',
                    borderWidth: 3,
                    tension: 0.35,
                    fill: true,
                    yAxisID: 'yRuin'
                },
                {
                    label: 'Position Size (%)',
                    data: [],
                    borderColor: '#06b6d4',
                    borderDash: [5, 5],
                    borderWidth: 2.5,
                    tension: 0.1,
                    yAxisID: 'ySizing'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false // We use custom legends in HTML
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleFont: { family: 'Outfit', size: 13, weight: '700' },
                    bodyFont: { family: 'Outfit', size: 12 },
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)'
                    },
                    ticks: {
                        color: '#9ca3af',
                        font: { family: 'Outfit', weight: '500' }
                    },
                    title: {
                        display: true,
                        text: 'Optimization Iterations',
                        color: '#9ca3af',
                        font: { family: 'Outfit', size: 11, weight: '600' }
                    }
                },
                yRuin: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    min: 0,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#f59e0b',
                        font: { family: 'Outfit', weight: '600' },
                        callback: function(value) { return value + '%'; }
                    },
                    title: {
                        display: true,
                        text: 'Risk of Ruin',
                        color: '#f59e0b',
                        font: { family: 'Outfit', size: 11, weight: '600' }
                    }
                },
                ySizing: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    min: 0,
                    max: 4,
                    grid: {
                        drawOnChartArea: false // Avoid duplicate grid lines
                    },
                    ticks: {
                        color: '#06b6d4',
                        font: { family: 'Outfit', weight: '600' },
                        callback: function(value) { return value + '%'; }
                    },
                    title: {
                        display: true,
                        text: 'Position Sizing Limit',
                        color: '#06b6d4',
                        font: { family: 'Outfit', size: 11, weight: '600' }
                    }
                }
            }
        }
    });
}

// Reset metric widgets
function resetMetrics() {
    metricSharpe.innerText = '-';
    metricSharpeStatus.innerText = 'Waiting...';
    metricPf.innerText = '-';
    metricPfStatus.innerText = 'Waiting...';
    metricDd.innerText = '-';
    metricDdStatus.innerText = 'Waiting...';
    metricRuin.innerText = '-';
    metricRuinStatus.innerText = 'Waiting...';
}

// Start simulation run
function startSimulation() {
    // Disable inputs
    startBtn.disabled = true;
    maxIterationsInput.disabled = true;
    drawdownLimitInput.disabled = true;
    
    // Clear terminal & reset layout
    terminalBody.innerHTML = '';
    resetStepper();
    resetMetrics();
    initChart();
    
    setSystemStatus('active', 'SIMULATION RUNNING');
    log('Initiating real-time quantitative simulation...', 'running');
    
    const maxIter = maxIterationsInput.value;
    const ddLimit = drawdownLimitInput.value;
    
    const url = `/api/run?max_iterations=${maxIter}&drawdown_limit=${ddLimit}`;
    
    eventSource = new EventSource(url);
    
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        switch (data.event) {
            case 'step_start':
                handleStepStart(data);
                break;
                
            case 'step_success':
                handleStepSuccess(data);
                break;
                
            case 'step_error':
                handleStepError(data);
                break;
                
            case 'validator_verdict':
                handleValidatorVerdict(data);
                break;
                
            case 'optimizer_iteration_start':
                log(`[Optimizer] Starting Iteration ${data.iteration}: testing PosSize=${data.pos_size.toFixed(3)}%, StopLoss=${(data.sl*100).toFixed(2)}%`, 'warning');
                break;
                
            case 'optimizer_iteration_result':
                handleOptimizerResult(data);
                break;
                
            case 'simulation_success':
                handleSimulationFinished(data, true);
                break;
                
            case 'simulation_failed_opt':
                handleSimulationFinished(data, false);
                break;
        }
    };
    
    eventSource.onerror = function() {
        log('SSE stream disconnected or encountered an error.', 'error');
        stopSimulation();
    };
}

// Handler functions for SSE events
function handleStepStart(data) {
    log(`[STAGE] Starting ${data.step.toUpperCase()}: ${data.message}`, 'running');
    
    if (data.step === 'supervisor') {
        stepSupervisor.className = 'step active';
    } else if (data.step === 'developer_bridge') {
        stepSupervisor.className = 'step completed';
        stepBridge.className = 'step active';
    } else if (data.step === 'validator') {
        stepBridge.className = 'step completed';
        stepValidator.className = 'step active';
    } else if (data.step === 'optimizer') {
        stepValidator.className = 'step completed';
        stepOptimizer.className = 'step active';
    }
}

function handleStepSuccess(data) {
    log(`[STAGE] Success: ${data.message}`, 'success');
    
    if (data.step === 'supervisor') {
        stepSupervisor.className = 'step completed';
    } else if (data.step === 'developer_bridge') {
        stepBridge.className = 'step completed';
        // Display initial backtest metrics
        const m = data.data;
        metricSharpe.innerText = m.sharpe_ratio.toFixed(2);
        metricSharpeStatus.innerText = 'Initial Backtest';
        metricPf.innerText = m.profit_factor.toFixed(2);
        metricPfStatus.innerText = `Trades: ${m.total_trades}`;
        metricDd.innerText = m.max_drawdown.toFixed(2) + '%';
        metricDdStatus.innerText = `Target: < ${drawdownLimitInput.value}%`;
    }
}

function handleStepError(data) {
    log(`[ERROR] Stage failed: ${data.message}`, 'error');
    if (data.stdout) {
        log(`--- Process Output ---\n${data.stdout}`, 'system');
    }
    if (data.stderr) {
        log(`--- Error Output ---\n${data.stderr}`, 'error');
    }
    
    // Set failed step UI
    const activeStep = document.querySelector('.step.active');
    if (activeStep) activeStep.className = 'step error';
    
    setSystemStatus('error', 'SIMULATION FAILED');
    stopSimulation();
}

function handleValidatorVerdict(data) {
    const report = data.report;
    const mc = report.monte_carlo_results;
    
    // Update live metrics widgets
    metricSharpe.innerText = report.metrics.sharpe_ratio.toFixed(2);
    metricPf.innerText = report.metrics.profit_factor.toFixed(2);
    metricDd.innerText = report.metrics.max_drawdown.toFixed(2) + '%';
    
    const ruinProb = mc.risk_of_ruin * 100;
    metricRuin.innerText = ruinProb.toFixed(1) + '%';
    metricRuinStatus.innerText = `Drawdown limit: ${mc.drawdown_limit_used}%`;
    
    if (ruinProb > 5.0) {
        metricRuin.className = 'metric-value text-rose';
        log(`[Validator] Risk of Ruin (${ruinProb.toFixed(2)}%) exceeds limit (5%). Rejected.`, 'error');
    } else {
        metricRuin.className = 'metric-value text-emerald';
        log(`[Validator] Risk of Ruin (${ruinProb.toFixed(2)}%) satisfies limit.`, 'success');
    }
    
    log(`[Validator] Verdict: ${data.passed ? 'PASSED' : 'REJECTED (REQUIRES OPTIMIZATION)'}`, data.passed ? 'success' : 'warning');
}

function handleOptimizerResult(data) {
    const ruinProb = data.risk_of_ruin * 100;
    log(`[Optimizer] Iteration ${data.iteration} Results: Drawdown = ${data.max_dd.toFixed(2)}%, Risk of Ruin = ${ruinProb.toFixed(2)}%, Passed? ${data.passed ? 'YES' : 'NO'}`, data.passed ? 'success' : 'system');
    
    // Dynamic chart update
    if (optChart) {
        optChart.data.labels.push(`Iter ${data.iteration}`);
        optChart.data.datasets[0].data.push(ruinProb); // Left axis
        optChart.data.datasets[1].data.push(data.pos_size); // Right axis
        optChart.update();
    }
    
    // Update live widgets
    metricDd.innerText = data.max_dd.toFixed(2) + '%';
    metricRuin.innerText = ruinProb.toFixed(1) + '%';
    metricRuinStatus.innerText = `Iter ${data.iteration} Sizing: ${data.pos_size.toFixed(3)}%`;
}

function handleSimulationFinished(data, isApproved) {
    log(data.message, isApproved ? 'success' : 'error');
    
    // Update step UI
    stepOptimizer.className = isApproved ? 'step completed' : 'step error';
    
    setSystemStatus(isApproved ? 'success' : 'error', isApproved ? 'VERDICT: APPROVED' : 'VERDICT: REJECTED');
    stopSimulation();
    
    // Populate verdict modal
    const report = data.report;
    const mc = report.monte_carlo_results;
    
    verdictTitle.innerText = isApproved ? 'STRATEGY APPROVED' : 'STRATEGY REJECTED';
    verdictSubtitle.innerText = isApproved 
        ? 'Sovereign Strategy successfully meets all risk limits' 
        : 'Sovereign Strategy failed to meet risk limits within max iterations';
    
    verdictIconContainer.className = `verdict-icon-container ${isApproved ? 'success' : 'error'}`;
    verdictIcon.className = `fa-solid ${isApproved ? 'fa-shield-check' : 'fa-triangle-exclamation'}`;
    
    vSizing.innerText = report.constraints.max_position_sizing_pct?.toFixed(3) + '%';
    vSl.innerText = (report.constraints.stop_loss_value * 100)?.toFixed(2) + '%';
    vAvgDd.innerText = mc.average_max_drawdown.toFixed(2) + '%';
    vPeakDd.innerText = mc.peak_simulated_drawdown.toFixed(2) + '%';
    vRuin.innerText = (mc.risk_of_ruin * 100).toFixed(2) + '%';
    
    // Show modal
    verdictModal.style.display = 'flex';
}

function stopSimulation() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    // Re-enable inputs
    startBtn.disabled = false;
    maxIterationsInput.disabled = false;
    drawdownLimitInput.disabled = false;
}

// Help Contents dictionary (Italian)
const helpContent = {
    'sharpe': {
        title: 'Sharpe Ratio',
        subtitle: 'Efficienza del rendimento corretto per il rischio',
        desc: 'Misura quanto rendimento extra genera la strategia per ogni unità di volatilità (rischio) assunta. Risponde alla domanda: "I guadagni compensano la volatilità subita?"',
        bullets: [
            '<strong>Formula:</strong> (Rendimento Strategia - Tasso Risk-Free) / Deviazione Standard Rendimenti',
            '<strong>Minimo SQE:</strong> Deve essere &ge; 1.50 per superare il controllo di validità.',
            '<strong>Valutazione:</strong> Da 1.5 a 2.0 è buono; sopra 2.0 è eccellente; sopra 3.0 è eccezionale.',
            '<strong>Importanza:</strong> Aiuta a scartare strategie che guadagnano molto ma con sbalzi finanziari enormi ed insostenibili.'
        ],
        icon: 'fa-gauge-high'
    },
    'pf': {
        title: 'Profit Factor',
        subtitle: 'Rapporto tra profitti lordi e perdite lorde',
        desc: 'Indica la redditività grezza della strategia. Dice quanti dollari vengono generati per ogni singolo dollaro perso nel backtest.',
        bullets: [
            '<strong>Formula:</strong> Guadagni Totali Lordi / Perdite Totali Lorde',
            '<strong>Minimo SQE:</strong> Deve essere &ge; 1.20.',
            '<strong>Valutazione:</strong> Sotto 1.0 (in perdita); 1.0 - 1.2 (break-even instabile); 1.2 - 1.8 (buona stabilità); &gt; 2.0 (altamente redditizio).',
            '<strong>Importanza:</strong> Più è alto, più la strategia è statisticamente robusta contro le perdite.'
        ],
        icon: 'fa-money-bill-trend-up'
    },
    'dd': {
        title: 'Max Drawdown',
        subtitle: 'Peggiore calo storico del capitale',
        desc: 'Rappresenta la massima discesa percentuale accumulata dal picco di equity più alto prima di stabilire un nuovo massimo.',
        bullets: [
            '<strong>Calcolo:</strong> Misura il picco massimo di discesa del capitale storico durante il backtest.',
            '<strong>Limite SQE:</strong> Deve essere inferiore alla soglia impostata (es. 1.5%).',
            '<strong>Importanza:</strong> Rappresenta lo scenario storico peggiore. Se è troppo elevato, indica che la strategia espone il conto a rischi di liquidazione o margin call eccessivi.'
        ],
        icon: 'fa-arrow-trend-down'
    },
    'ruin': {
        title: 'Risk of Ruin (Monte Carlo)',
        subtitle: 'Probabilità statistica di fallimento del capitale',
        desc: 'Calcola la percentuale di simulazioni in cui la strategia supera la soglia di drawdown critico impostata (ruina statistica), basandosi su 1000 iterazioni stocastiche.',
        bullets: [
            '<strong>Soglia Limite:</strong> Deve essere &le; 5.0% (5% di probabilità). Se superiore, la strategia viene scartata.',
            '<strong>Funzionamento:</strong> Riordina casualmente i rendimenti reali dei trade (Bootstrap) o simula variazioni log-normali calibrate sui parametri della strategia per creare 1000 percorsi storici alternativi.',
            '<strong>Importanza:</strong> Protegge dalla "sfortuna temporale". Un buon backtest può essere fortunato; il Monte Carlo stressa la strategia per verificarne la stabilità statistica nel lungo periodo.'
        ],
        icon: 'fa-triangle-exclamation'
    },
    'supervisor': {
        title: 'Supervisor Validator',
        subtitle: 'Fase 1: Controllo formale dello schema e del rischio base',
        desc: 'Valida la configurazione iniziale della strategia (blueprint) garantendo che rispetti rigorosamente i vincoli strutturali e che non contenga parametri di rischio assurdi o assenti.',
        bullets: [
            '<strong>Verifiche:</strong> Presenza degli indicatori richiesti, timeframe validi, e configurazioni obbligatorie.',
            '<strong>Prevenzione Ruina:</strong> Blocca all\'origine blueprint senza stop loss, o con drawdown consentito superiore al 2.0%.',
            '<strong>Output:</strong> Produce il file `strategy_blueprint.json` pronto per la generazione del codice.'
        ],
        icon: 'fa-shield-halved'
    },
    'developer_bridge': {
        title: 'Developer Bridge',
        subtitle: 'Fase 2: Generazione codice AST e compilazione sicura',
        desc: 'Prende le condizioni descritte nel blueprint e le traduce in codice Python compilabile per Jesse, eseguendo contemporaneamente un severo audit statico.',
        bullets: [
            '<strong>AST Translation:</strong> Mappa in modo sicuro indicatori e variabili di prezzo (close, volume, ecc.) come riferimenti validi a `self.X` nella strategia.',
            '<strong>Static Audit:</strong> Esegue Ruff (formattatore/linter), Vulture (dead code) e Xenon (complessità ciclomatica). Ogni pezzo di codice deve soddisfare i parametri qualitativi più severi.',
            '<strong>Correzione Automatica:</strong> Se viene rilevato un errore di compilazione o di audit, rigenera autonomamente il codice applicando modifiche correttive.'
        ],
        icon: 'fa-code'
    },
    'validator': {
        title: 'Quantitative Validator',
        subtitle: 'Fase 3: Stress-Testing quantitativo e Monte Carlo',
        desc: 'Esegue i calcoli di convalida sulle metriche estratte dai backtest storici e avvia lo stress test Monte Carlo su 1000 simulazioni stocastiche.',
        bullets: [
            '<strong>Metric Validation:</strong> Confronta Sharpe, Drawdown e Profit Factor del backtest con i limiti impostati.',
            '<strong>Monte Carlo Stress Gate:</strong> Respinge la strategia se la probabilità di rovina supera il 5% o se il drawdown medio simulato supera il limite configurato.',
            '<strong>Output:</strong> Genera il report `validation_report.json` e la dashboard interattiva.'
        ],
        icon: 'fa-chart-line'
    },
    'optimizer': {
        title: 'Risk Optimizer (Closed-Loop)',
        subtitle: 'Fase 3.5: Ottimizzazione ricorsiva dei parametri di rischio',
        desc: 'Interviene automaticamente se una strategia ha buoni risultati storici ma fallisce lo stress test Monte Carlo (es. Risk of Ruin elevato).',
        bullets: [
            '<strong>Heuristic Tuning:</strong> Riduce la dimensione massima della posizione (`max_position_sizing_pct`) per abbassare il drawdown reale.',
            '<strong>Stop Loss Adjustment:</strong> Se la dimensione della posizione è già al minimo, riduce la distanza del livello di stop loss.',
            '<strong>Closed Loop:</strong> Riesegue la generazione, la compilazione, il backtest e lo stress test ad ogni iterazione fino ad ottenere una configurazione sicura.'
        ],
        icon: 'fa-gears'
    }
};

// Help display logic
function showHelp(key) {
    const info = helpContent[key];
    if (!info) return;
    
    helpTitle.innerText = info.title;
    helpSubtitle.innerText = info.subtitle;
    helpDescription.innerText = info.desc;
    
    // Clear and build bullets
    helpBullets.innerHTML = '';
    info.bullets.forEach(b => {
        const li = document.createElement('div');
        li.style.display = 'flex';
        li.style.alignItems = 'flex-start';
        li.style.gap = '8px';
        li.style.fontSize = '13.5px';
        li.style.color = 'var(--color-text-muted)';
        
        const dot = document.createElement('span');
        dot.innerHTML = '<i class="fa-solid fa-circle-dot" style="font-size: 8px; color: var(--color-cyan); margin-top: 6px;"></i>';
        
        const text = document.createElement('span');
        text.innerHTML = b;
        
        li.appendChild(dot);
        li.appendChild(text);
        helpBullets.appendChild(li);
    });
    
    // Set icon
    helpIcon.className = `fa-solid ${info.icon}`;
    
    // Show modal
    helpModal.style.display = 'flex';
}

// Event Listeners
startBtn.addEventListener('click', startSimulation);

clearBtn.addEventListener('click', () => {
    terminalBody.innerHTML = '';
});

closeModalBtn.addEventListener('click', () => {
    verdictModal.style.display = 'none';
});

closeHelpBtn.addEventListener('click', () => {
    helpModal.style.display = 'none';
});

// Bind Metric Cards Clicks for Tooltips
document.getElementById('card-sharpe').addEventListener('click', () => showHelp('sharpe'));
document.getElementById('card-pf').addEventListener('click', () => showHelp('pf'));
document.getElementById('card-dd').addEventListener('click', () => showHelp('dd'));
document.getElementById('card-ruin').addEventListener('click', () => showHelp('ruin'));

// Bind Pipeline Steps Clicks for Tooltips
stepSupervisor.addEventListener('click', () => showHelp('supervisor'));
stepBridge.addEventListener('click', () => showHelp('developer_bridge'));
stepValidator.addEventListener('click', () => showHelp('validator'));
stepOptimizer.addEventListener('click', () => showHelp('optimizer'));

// Close modals when clicking outside their card box
window.addEventListener('click', (event) => {
    if (event.target === verdictModal) {
        verdictModal.style.display = 'none';
    }
    if (event.target === helpModal) {
        helpModal.style.display = 'none';
    }
});
