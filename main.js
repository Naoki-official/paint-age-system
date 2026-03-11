/**
 * 塗料年齢ダッシュボード v2 — メインスクリプト
 * 20系統対応 + 2段FIFOモデル表示
 */

// === グローバル状態 ===
let ageChart = null;
let levelChart = null;
let currentLineId = 1;
let currentHours = 6;
let allLines = [];

// === Chart.js グローバル設定 ===
Chart.defaults.color = '#9098ad';
Chart.defaults.borderColor = 'rgba(0,0,0,0.06)';
Chart.defaults.font.family = "'Inter', 'Noto Sans JP', sans-serif";
Chart.defaults.font.size = 11;

// === 初期化 ===
document.addEventListener('DOMContentLoaded', async () => {
    await loadLines();
    initTimeRangeSelector();
    initSearch();
    fetchAndRender(currentLineId, currentHours);
});

// === 系統リスト読み込み ===
async function loadLines() {
    try {
        const res = await fetch('/api/lines');
        allLines = await res.json();
        renderLineList(allLines);

        if (allLines.length > 0) {
            selectLine(allLines[0].line_id);
        }
    } catch (err) {
        console.error('系統リスト取得エラー:', err);
    }
}

// === 系統リスト描画 ===
function renderLineList(lines) {
    const list = document.getElementById('lineList');
    list.innerHTML = '';

    lines.forEach(line => {
        const item = document.createElement('div');
        item.className = `line-item${line.line_id === currentLineId ? ' active' : ''}`;
        item.dataset.lineId = line.line_id;

        const ageClass = getAgeClass(line.current_robot_age);

        item.innerHTML = `
            <span class="line-name" title="${line.name}">${line.name}</span>
            <span class="line-age ${ageClass}">${line.current_robot_age.toFixed(1)}H</span>
        `;

        item.addEventListener('click', () => {
            selectLine(line.line_id);
        });

        list.appendChild(item);
    });
}

function getAgeClass(age) {
    if (age < 8) return 'age-low';
    if (age < 16) return 'age-mid';
    return 'age-high';
}

// === 系統選択 ===
function selectLine(lineId) {
    currentLineId = lineId;

    // サイドバーのアクティブ状態更新
    document.querySelectorAll('.line-item').forEach(item => {
        item.classList.toggle('active', parseInt(item.dataset.lineId) === lineId);
    });

    // ヘッダー更新
    const line = allLines.find(l => l.line_id === lineId);
    document.getElementById('currentLineName').textContent =
        line ? line.name : `ライン ${lineId}`;

    fetchAndRender(lineId, currentHours);
}

// === 検索フィルター ===
function initSearch() {
    const input = document.getElementById('lineSearch');
    input.addEventListener('input', () => {
        const q = input.value.toLowerCase();
        const filtered = allLines.filter(l =>
            l.name.toLowerCase().includes(q) ||
            String(l.line_id).includes(q)
        );
        renderLineList(filtered);
    });
}

// === 時間範囲セレクター ===
function initTimeRangeSelector() {
    const selector = document.getElementById('timeRangeSelector');
    selector.querySelectorAll('.time-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            selector.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentHours = parseFloat(btn.dataset.hours);
            fetchAndRender(currentLineId, currentHours);
        });
    });
}

// === データ取得 & レンダリング ===
async function fetchAndRender(lineId, hours) {
    try {
        const res = await fetch(`/api/paint-age?line_id=${lineId}&hours=${hours}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.length === 0) {
            console.warn('データがありません');
            return;
        }

        updateStatCards(data);
        renderAgeChart(data);
        renderLevelChart(data);
        updateMeta(data);
    } catch (err) {
        console.error('データ取得エラー:', err);
    }
}

// === ステータスカード更新 ===
function updateStatCards(data) {
    const latest = data[data.length - 1];

    // ロボット到達年齢
    document.getElementById('valRobotAge').textContent = latest.robot_age.toFixed(1);

    // 配管内平均年齢
    document.getElementById('valPipeAge').textContent = latest.pipe_avg_age.toFixed(1);

    // タンクレベル
    const level = latest.level;
    document.getElementById('valTankLevel').textContent = level.toFixed(1);

    // タンクゲージ
    const tankGauge = document.getElementById('tankGaugeFill');
    tankGauge.style.width = `${Math.min(100, level)}%`;
    if (level < 30) {
        tankGauge.style.background = 'linear-gradient(90deg, #ef4565, #f5842a)';
    } else if (level < 50) {
        tankGauge.style.background = 'linear-gradient(90deg, #f5842a, #facc15)';
    } else {
        tankGauge.style.background = 'linear-gradient(90deg, #22c55e, #10b8d6)';
    }

    // 配管ゲージ
    const pipeGauge = document.getElementById('pipeGaugeFill');
    pipeGauge.style.width = `${Math.min(100, latest.pipe_fill_pct)}%`;

    // バッチ数
    document.getElementById('valTankBatches').textContent = latest.tank_batches;
    document.getElementById('valPipeBatches').textContent = latest.pipe_batches;
}

// === メタ情報 ===
function updateMeta(data) {
    const now = new Date();
    const first = new Date(data[0].timestamp);
    const last = new Date(data[data.length - 1].timestamp);
    document.getElementById('lastUpdated').textContent =
        `${formatDate(first)} ~ ${formatDate(last)}`;
}

function formatDate(dt) {
    const mm = String(dt.getMonth() + 1).padStart(2, '0');
    const dd = String(dt.getDate()).padStart(2, '0');
    const hh = String(dt.getHours()).padStart(2, '0');
    const mi = String(dt.getMinutes()).padStart(2, '0');
    return `${mm}/${dd} ${hh}:${mi}`;
}

// === 年齢チャート ===
function renderAgeChart(data) {
    const ctx = document.getElementById('ageChart').getContext('2d');
    const labels = data.map(d => new Date(d.timestamp));

    if (ageChart) ageChart.destroy();

    ageChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'ロボット到達年齢 [H]',
                    data: data.map(d => d.robot_age),
                    borderColor: '#ef4565',
                    backgroundColor: 'rgba(239, 69, 101, 0.06)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 8,
                },
                {
                    label: '配管内平均年齢 [H]',
                    data: data.map(d => d.pipe_avg_age),
                    borderColor: '#8b5cf6',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 8,
                },
                {
                    label: 'タンク内平均年齢 [H]',
                    data: data.map(d => d.tank_avg_age),
                    borderColor: '#4f7cff',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 8,
                },
                {
                    label: '移動平均 [H]',
                    data: data.map(d => d.robot_age_ma),
                    borderColor: '#10b8d6',
                    borderWidth: 1.5,
                    borderDash: [6, 3],
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 8,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#fff',
                    titleColor: '#1e2330',
                    bodyColor: '#5a6178',
                    borderColor: '#e4e7ed',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    callbacks: {
                        title: items => formatDate(new Date(items[0].parsed.x)),
                        label: item => `${item.dataset.label}: ${item.parsed.y.toFixed(2)} H`,
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        tooltipFormat: 'MM/dd HH:mm',
                        displayFormats: { minute: 'HH:mm', hour: 'MM/dd HH:mm', day: 'MM/dd' },
                    },
                    title: { display: true, text: '時間', color: '#9098ad' },
                    grid: { display: false },
                    ticks: { maxTicksLimit: 10 },
                },
                y: {
                    title: { display: true, text: '年齢 [H]', color: '#9098ad' },
                    min: 0,
                    grid: { color: 'rgba(0,0,0,0.04)' },
                },
            },
        },
    });
}

// === 液面レベルチャート ===
function renderLevelChart(data) {
    const ctx = document.getElementById('levelChart').getContext('2d');
    const labels = data.map(d => new Date(d.timestamp));

    if (levelChart) levelChart.destroy();

    const gradient = ctx.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, 'rgba(34, 197, 94, 0.18)');
    gradient.addColorStop(1, 'rgba(34, 197, 94, 0.0)');

    levelChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '液面レベル (%)',
                data: data.map(d => d.level),
                borderColor: '#22c55e',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.2,
                pointRadius: 0,
                pointHitRadius: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#fff',
                    titleColor: '#1e2330',
                    bodyColor: '#5a6178',
                    borderColor: '#e4e7ed',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    callbacks: {
                        title: items => formatDate(new Date(items[0].parsed.x)),
                        label: item => `液面: ${item.parsed.y.toFixed(1)}%`,
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        tooltipFormat: 'MM/dd HH:mm',
                        displayFormats: { minute: 'HH:mm', hour: 'MM/dd HH:mm', day: 'MM/dd' },
                    },
                    title: { display: true, text: '時間', color: '#9098ad' },
                    grid: { display: false },
                    ticks: { maxTicksLimit: 10 },
                },
                y: {
                    title: { display: true, text: '液面レベル (%)', color: '#9098ad' },
                    min: 0,
                    max: 110,
                    grid: { color: 'rgba(0,0,0,0.04)' },
                },
            },
        },
    });
}