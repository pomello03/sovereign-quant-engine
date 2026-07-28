/* ==========================================================================
 * Sovereign Quant Engine — dashboard_app.js
 * Pure JS/Chart.js logic for the glassmorphic validation dashboard.
 * Reads the global SQE_REPORT_DATA object injected by quant_validator.py
 * into validation_dashboard.html (REPORT_JSON_PLACEHOLDER marker).
 * ========================================================================== */
(function () {
    'use strict';

    const report = (typeof SQE_REPORT_DATA !== 'undefined') ? SQE_REPORT_DATA : null;
    if (!report) {
        document.body.innerHTML =
            '<p style="color:#f87171;font-family:monospace;padding:2rem">' +
            'SQE_REPORT_DATA missing — regenerate the dashboard via QuantValidator.generate_report().</p>';
        return;
    }

    const history = report.optimization_history || [];
    const mc = report.monte_carlo_results || {};
    let equityChart = null;
    let drawdownChart = null;

    /* ---------------------------------------------------------------- *
     * Helpers
     * ---------------------------------------------------------------- */
    const $ = (id) => document.getElementById(id);

    function fmt(value, digits, suffix) {
        if (value === null || value === undefined || Number.isNaN(value)) return 'N/A';
        return Number(value).toFixed(digits === undefined ? 2 : digits) + (suffix || '');
    }

    // Box-Muller standard normal
    function randn() {
        let u = 0, v = 0;
        while (u === 0) u = Math.random();
        while (v === 0) v = Math.random();
        return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    }

    /* Client-side port of the backend parametric log-normal mixture model
     * (QuantValidator.run_monte_carlo) — used to re-render charts for
     * historical optimizer iterations without stored trajectories. */
    function simulateParametric(metrics, nPaths) {
        const totalTrades = Math.max(metrics.total_trades || 100, 10);
        let pf = metrics.profit_factor || 1.5;
        if (pf <= 0) pf = 1.5;
        let winRate = metrics.win_rate;
        if (winRate === null || winRate === undefined || !(winRate > 0 && winRate < 1)) winRate = 0.5;

        const absMaxDd = Math.abs(metrics.max_drawdown || 10.0);
        const scale = Math.max(0.0001, absMaxDd / 10.0);
        const sigmaWin = 0.005 * scale;
        const muWin = Math.log(pf * 0.01 * scale) - 0.5 * sigmaWin * sigmaWin;
        const sigmaLoss = 0.003 * scale;
        const muLoss = Math.log(0.01 * scale) - 0.5 * sigmaLoss * sigmaLoss;

        const equityTrajs = [];
        const ddTrajs = [];
        for (let p = 0; p < nPaths; p++) {
            let equity = 100.0, peak = 100.0;
            const eqPath = [100.0], ddPath = [0.0];
            for (let t = 0; t < totalTrades; t++) {
                const r = (Math.random() < winRate)
                    ? Math.exp(muWin + sigmaWin * randn())
                    : -Math.exp(muLoss + sigmaLoss * randn());
                equity = Math.max(0.0, equity * (1 + r));
                let dd = 0.0;
                if (equity > peak) peak = equity;
                else dd = (peak - equity) / peak * 100.0;
                eqPath.push(Number(equity.toFixed(2)));
                ddPath.push(Number(dd.toFixed(3)));
            }
            equityTrajs.push(eqPath);
            ddTrajs.push(ddPath);
        }
        return { equityTrajs: equityTrajs, ddTrajs: ddTrajs };
    }

    // Pointwise median across trajectories (highlighted curve fallback)
    function medianPath(trajs) {
        if (!trajs || trajs.length === 0) return null;
        const len = Math.max.apply(null, trajs.map((t) => t.length));
        const median = [];
        for (let i = 0; i < len; i++) {
            const col = trajs.filter((t) => i < t.length).map((t) => t[i]).sort((a, b) => a - b);
            median.push(col[Math.floor(col.length / 2)]);
        }
        return median;
    }

    /* ---------------------------------------------------------------- *
     * Verdict badge & sidebar parameters
     * ---------------------------------------------------------------- */
    function renderVerdict(passed) {
        const badge = $('verdict-badge');
        // A mock run means no market was ever touched: say so above the verdict,
        // otherwise APPROVED reads as a real result.
        const mockWarning = report.is_mock
            ? '<div class="rounded-xl border border-amber-500/50 bg-amber-500/10 px-4 py-3 mb-3">' +
              '<div class="flex items-center gap-2 mb-1">' +
              '<i data-lucide="alert-triangle" class="h-5 w-5 text-amber-400"></i>' +
              '<span class="font-bold text-amber-300 tracking-wide">DATI FINTI</span></div>' +
              '<p class="text-[11px] leading-snug text-amber-200/80">Jesse non ha eseguito nessun backtest. ' +
              'Tutti i numeri di questa pagina sono calcolati dai parametri di rischio, non misurati sul mercato. ' +
              'Non usarli per decidere.</p></div>'
            : '';
        badge.innerHTML = mockWarning + (passed
            ? '<div class="glow-emerald rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 flex items-center gap-2">' +
              '<i data-lucide="shield-check" class="h-5 w-5 text-emerald-400"></i>' +
              '<span class="font-bold text-emerald-300 tracking-wide">APPROVED</span></div>'
            : '<div class="glow-rose rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 flex items-center gap-2">' +
              '<i data-lucide="shield-x" class="h-5 w-5 text-rose-400"></i>' +
              '<span class="font-bold text-rose-300 tracking-wide">REJECTED</span></div>');
    }

    function paramRow(label, value) {
        return '<div class="flex items-center justify-between rounded-lg bg-zinc-900/60 border border-zinc-800/50 px-3 py-2">' +
               '<span class="text-zinc-400 text-xs">' + label + '</span>' +
               '<span class="font-mono text-xs text-zinc-200">' + value + '</span></div>';
    }

    function renderParams() {
        const bp = report.strategy_blueprint || {};
        const alpha = bp.alpha || {};
        const risk = bp.risk || report.constraints || {};
        let html = '';

        (alpha.indicators || []).forEach(function (ind) {
            const params = ind.params
                ? Object.entries(ind.params).map(([k, v]) => k + '=' + v).join(', ')
                : '';
            html += paramRow('<span class="text-violet-300">' + ind.name + '</span>', params || 'attivo');
        });
        if (risk.max_position_sizing_pct !== undefined) html += paramRow('Position size', fmt(risk.max_position_sizing_pct, 3, '%'));
        if (risk.stop_loss_value !== undefined) html += paramRow('Stop loss', fmt(risk.stop_loss_value * 100, 2, '%'));
        if (risk.take_profit_value !== undefined) html += paramRow('Take profit', fmt(risk.take_profit_value * 100, 2, '%'));
        if (risk.max_drawdown_limit_pct !== undefined) html += paramRow('Max DD limit', fmt(risk.max_drawdown_limit_pct, 2, '%'));
        const ctx = bp.context || {};
        if (ctx.market_regime) html += paramRow('Regime', ctx.market_regime);
        if (ctx.timeframe) html += paramRow('Timeframe', ctx.timeframe);

        $('strategy-params').innerHTML = html || '<p class="text-xs text-zinc-600">Blueprint non disponibile.</p>';
    }

    /* ---------------------------------------------------------------- *
     * Optimizer stepper (interactive vertical timeline)
     * ---------------------------------------------------------------- */
    function renderStepper() {
        const container = $('optimizer-stepper');
        if (history.length === 0) {
            container.innerHTML = '<p class="text-xs text-zinc-600">Nessuna ottimizzazione eseguita: validazione diretta.</p>';
            return;
        }
        container.innerHTML = history.map(function (entry, idx) {
            const passed = entry.validation_passed;
            const icon = passed ? 'check-circle-2' : 'x-circle';
            const color = passed ? 'text-emerald-400' : 'text-rose-400';
            const verdict = passed ? 'Passato' : 'Fallito';
            return '<div class="stepper-node rounded-xl border border-transparent px-3 py-2.5 flex items-start gap-3" data-step="' + idx + '">' +
                   '<div class="flex flex-col items-center pt-0.5">' +
                   '<i data-lucide="' + icon + '" class="h-4 w-4 ' + color + '"></i>' +
                   (idx < history.length - 1 ? '<span class="w-px h-6 bg-zinc-800 mt-1"></span>' : '') +
                   '</div><div class="min-w-0">' +
                   '<p class="text-xs font-semibold text-zinc-200">Step ' + entry.iteration +
                   ' <span class="font-mono text-zinc-400">' + fmt(entry.params.max_position_sizing_pct, 3, '%') + ' size</span></p>' +
                   '<p class="text-[11px] text-zinc-500">SL ' + fmt(entry.params.stop_loss_value * 100, 2, '%') +
                   ' · RoR ' + fmt(entry.risk_of_ruin * 100, 1, '%') +
                   ' · <span class="' + color + '">' + verdict + '</span></p>' +
                   '</div></div>';
        }).join('');

        container.querySelectorAll('.stepper-node').forEach(function (node) {
            node.addEventListener('click', function () {
                selectIteration(parseInt(node.getAttribute('data-step'), 10));
            });
        });
    }

    function highlightStepperNode(idx) {
        document.querySelectorAll('.stepper-node').forEach(function (node) {
            node.classList.toggle('active', parseInt(node.getAttribute('data-step'), 10) === idx);
        });
    }

    /* ---------------------------------------------------------------- *
     * Metrics bento grid + MC stats panel
     * ---------------------------------------------------------------- */
    function renderMetrics(metrics, ruin, avgDd) {
        $('metric-sharpe').textContent = fmt(metrics.sharpe_ratio);
        $('metric-sharpe-sub').textContent = 'Target ≥ ' + fmt(report.constraints.sharpe_ratio_minimum !== undefined ? report.constraints.sharpe_ratio_minimum : 1.0, 2);
        $('metric-maxdd').textContent = fmt(metrics.max_drawdown, 2, '%');
        $('metric-maxdd-sub').textContent = 'Limite: ' + fmt(report.constraints.max_drawdown_limit_pct, 2, '%') + ' · MC avg: ' + fmt(avgDd, 2, '%');
        $('metric-pf').textContent = fmt(metrics.profit_factor);
        $('metric-pf-sub').textContent = (metrics.total_trades || 0) + ' trade · win rate ' + fmt((metrics.win_rate || 0) * 100, 1, '%');
        $('metric-ruin').textContent = fmt(ruin * 100, 2, '%');
        $('metric-ruin-sub').textContent = 'P(drawdown > ' + fmt(mc.drawdown_limit_used, 2, '%') + ')';
    }

    function statRow(label, value) {
        return '<div class="flex justify-between py-2.5"><span class="text-zinc-500">' + label + '</span>' +
               '<span class="font-mono text-zinc-200">' + value + '</span></div>';
    }

    function renderMcStats() {
        $('mc-stats').innerHTML =
            statRow('Simulazioni', mc.num_simulations || 'N/A') +
            statRow('Modalità', mc.simulation_mode === 'bootstrap' ? 'Bootstrap' : 'Log-Normal') +
            statRow('Avg Max Drawdown', fmt(mc.average_max_drawdown, 2, '%')) +
            statRow('Peak Drawdown', fmt(mc.peak_simulated_drawdown, 2, '%')) +
            statRow('Win rate usato', fmt((mc.win_rate_used || 0) * 100, 1, '%')) +
            statRow('Limite drawdown', fmt(mc.drawdown_limit_used, 2, '%'));
    }

    /* ---------------------------------------------------------------- *
     * Charts
     * ---------------------------------------------------------------- */
    const GRID = { color: 'rgba(255, 255, 255, 0.04)' };
    const TICKS = { color: '#52525b', font: { family: 'JetBrains Mono', size: 10 } };

    function baseOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            elements: { point: { radius: 0 } },
            scales: { x: { grid: GRID, ticks: TICKS }, y: { grid: GRID, ticks: TICKS } }
        };
    }

    function trajDatasets(trajs, color) {
        return trajs.map(function (path) {
            return { data: path, borderColor: color, borderWidth: 1, fill: false, tension: 0.1 };
        });
    }

    function buildCharts(equityTrajs, ddTrajs, realEquity, realDd) {
        if (equityChart) equityChart.destroy();
        if (drawdownChart) drawdownChart.destroy();

        const maxLen = Math.max.apply(null,
            equityTrajs.map((t) => t.length).concat(realEquity ? [realEquity.length] : [1]));
        const labels = Array.from({ length: maxLen }, (_, i) => i);

        // --- Equity: thin semi-transparent simulated paths + thick real curve
        const eqDatasets = trajDatasets(equityTrajs, 'rgba(99, 102, 241, 0.12)');
        const emphasized = realEquity || medianPath(equityTrajs);
        if (emphasized) {
            eqDatasets.push({
                data: emphasized,
                borderColor: '#c7d2fe',
                borderWidth: 3,
                fill: false,
                tension: 0.1
            });
        }
        equityChart = new Chart($('equityChart').getContext('2d'), {
            type: 'line',
            data: { labels: labels, datasets: eqDatasets },
            options: baseOptions()
        });
        $('equity-chart-sub').textContent = equityTrajs.length + ' traiettorie simulate · curva ' +
            (realEquity ? 'backtest reale' : 'mediana') + ' in evidenza';

        // --- Drawdown: underwater chart (negated values)
        const ddDatasets = trajDatasets(
            ddTrajs.map((p) => p.map((v) => -v)), 'rgba(244, 63, 94, 0.12)');
        const ddEmphasized = realDd ? realDd.map((v) => -v) : medianPath(ddTrajs.map((p) => p.map((v) => -v)));
        if (ddEmphasized) {
            ddDatasets.push({
                data: ddEmphasized,
                borderColor: '#fda4af',
                borderWidth: 2.5,
                fill: false,
                tension: 0.1
            });
        }
        drawdownChart = new Chart($('drawdownChart').getContext('2d'), {
            type: 'line',
            data: { labels: labels, datasets: ddDatasets },
            options: baseOptions()
        });
    }

    /* ---------------------------------------------------------------- *
     * Iteration selection (stepper interactivity)
     * ---------------------------------------------------------------- */
    function selectIteration(idx) {
        highlightStepperNode(idx);
        const banner = $('iteration-banner');
        const isFinal = (idx === null || idx === history.length - 1);

        if (isFinal) {
            banner.classList.add('hidden');
            renderMetrics(report.metrics, mc.risk_of_ruin || 0, mc.average_max_drawdown);
            const eqTrajs = (mc.equity_trajectories && mc.equity_trajectories.length > 0)
                ? mc.equity_trajectories
                : simulateParametric(report.metrics, 50).equityTrajs;
            const ddTrajs = (mc.drawdown_trajectories && mc.drawdown_trajectories.length > 0)
                ? mc.drawdown_trajectories
                : simulateParametric(report.metrics, 50).ddTrajs;
            buildCharts(eqTrajs, ddTrajs, report.backtest_equity_curve, report.backtest_drawdown_curve);
        } else {
            const entry = history[idx];
            banner.textContent = 'Vista iterazione ' + entry.iteration + ' (rigenerata client-side)';
            banner.classList.remove('hidden');
            renderMetrics(entry.metrics, entry.risk_of_ruin || 0, entry.average_max_drawdown);
            const sim = simulateParametric(entry.metrics, 50);
            buildCharts(sim.equityTrajs, sim.ddTrajs, null, null);
        }
        if (window.lucide) lucide.createIcons();
    }

    /* ---------------------------------------------------------------- *
     * Strategy code drawer (basic Python syntax highlighting)
     * ---------------------------------------------------------------- */
    function highlightPython(source) {
        const escaped = source
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return escaped
            .replace(/(#[^\n]*)/g, '<span class="code-token-com">$1</span>')
            .replace(/(&quot;[^&]*?&quot;|'[^'\n]*'|"[^"\n]*")/g, '<span class="code-token-str">$1</span>')
            .replace(/\b(def|class|return|import|from|if|else|elif|for|while|in|not|and|or|None|True|False|self|pass|try|except|raise|with|as|lambda)\b/g,
                '<span class="code-token-kw">$1</span>')
            .replace(/\b(\d+\.?\d*)\b/g, '<span class="code-token-num">$1</span>');
    }

    function initCodeDrawer() {
        const drawer = $('code-drawer');
        const toggle = $('code-drawer-toggle');
        const chevron = $('code-drawer-chevron');
        if (report.strategy_code) {
            $('strategy-code').innerHTML = highlightPython(report.strategy_code);
        }
        let open = false;
        toggle.addEventListener('click', function () {
            open = !open;
            drawer.style.maxHeight = open ? drawer.scrollHeight + 'px' : '0';
            chevron.style.transform = open ? 'rotate(180deg)' : 'rotate(0deg)';
        });
    }

    /* ---------------------------------------------------------------- *
     * Boot
     * ---------------------------------------------------------------- */
    $('validated-at').textContent = report.validated_at || '—';
    renderVerdict(report.validation_passed);
    renderParams();
    renderStepper();
    renderMcStats();
    initCodeDrawer();
    selectIteration(history.length > 0 ? history.length - 1 : null);
    if (window.lucide) lucide.createIcons();
})();
