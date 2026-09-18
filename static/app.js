const S = {
  mode: 'simulation',
  sensors: {},
  prediction: {},
  wind: { speed: 11.8, dir: 42 },
  hist: { t: [], h: [], p: [], r: [], prob: [] },
  charts: {},
  radarAnim: null,
  animFrame: null,
};

// ========== Smooth scroll & page transitions ==========
function smoothTransition(callback) {
  requestAnimationFrame(() => {
    requestAnimationFrame(callback);
  });
}

// --- Navigation ---
document.getElementById('navLinks').addEventListener('click', function(e) {
  const span = e.target.closest('span[data-sec]');
  if (!span) return;

  document.querySelectorAll('.links span').forEach(s => s.classList.remove('active'));
  span.classList.add('active');

  // Smooth page transition
  const currentPage = document.querySelector('.page.active');
  const nextPage = document.getElementById('page-' + span.dataset.sec);

  if (currentPage && nextPage && currentPage !== nextPage) {
    currentPage.style.opacity = '0';
    currentPage.style.transform = 'translateY(12px)';
    currentPage.style.filter = 'blur(4px)';

    setTimeout(() => {
      currentPage.classList.remove('active');
      currentPage.style.cssText = '';

      nextPage.classList.add('active');
      nextPage.style.opacity = '0';
      nextPage.style.transform = 'translateY(12px)';
      nextPage.style.filter = 'blur(4px)';

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          nextPage.style.opacity = '1';
          nextPage.style.transform = 'translateY(0)';
          nextPage.style.filter = 'blur(0)';
        });
      });

      if (span.dataset.sec === 'analytics') initAnalyticsCharts();
      if (span.dataset.sec === 'radar') initRadarCanvas();
    }, 300);
  } else if (nextPage) {
    nextPage.classList.add('active');
    if (span.dataset.sec === 'analytics') initAnalyticsCharts();
    if (span.dataset.sec === 'radar') initRadarCanvas();
  }
});

// --- Clock ---
function tick() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}
setInterval(tick, 1000);
tick();

// --- API ---
async function api(path) {
  try { const r = await fetch(path); return await r.json(); } catch(e) { return null; }
}
async function apiPost(path, body) {
  try {
    const r = await fetch(path, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    return await r.json();
  } catch(e) { return null; }
}

// --- Rain drops ---
(function initRain() {
  const el = document.getElementById('rain');
  if (!el) return;
  for (let i = 0; i < 40; i++) {
    const d = document.createElement('i');
    d.className = 'drop';
    d.style.left = Math.random() * 100 + '%';
    d.style.top = -Math.random() * 400 + 'px';
    d.style.height = (8 + Math.random() * 16) + 'px';
    d.style.animationDelay = Math.random() * 2 + 's';
    d.style.animationDuration = (1 + Math.random() * 1.5) + 's';
    el.appendChild(d);
  }
})();

// --- Wind simulation ---
function simWind() {
  S.wind.speed = Math.max(0, Math.min(30, S.wind.speed + (Math.random() - 0.5) * 1.2));
  S.wind.dir = (S.wind.dir + (Math.random() - 0.5) * 8 + 360) % 360;
  const dirs = ['N','NE','E','SE','S','SW','W','NW'];
  return { speed: S.wind.speed.toFixed(1), dir: dirs[Math.round(S.wind.dir / 45) % 8] + ' ' + Math.round(S.wind.dir) + '\u00B0' };
}

// --- Prediction ---
function predict(h, r, p, t) {
  let score = h * 0.65 + r * 0.28 + Math.max(0, 1018 - p) * 1.5 + Math.max(0, 32 - t) * 0.4;
  score = Math.max(4, Math.min(97, score));
  const cls = score >= 70 ? 'HIGH PROBABILITY' : score >= 45 ? 'MODERATE PROBABILITY' : 'LOW PROBABILITY';
  const detail = score >= 70 ? 'Rain expected' : score >= 45 ? 'Elevated precipitation chance' : 'Low precipitation probability';
  return { prob: score, cls, detail };
}

// --- Smooth value animation ---
function animateValue(el, target, decimals, suffix) {
  if (!el) return;
  const current = parseFloat(el.textContent) || 0;
  const diff = target - current;
  if (Math.abs(diff) < 0.01) {
    el.textContent = target.toFixed(decimals) + (suffix || '');
    return;
  }
  el.textContent = (current + diff * 0.15).toFixed(decimals) + (suffix || '');
}

// --- Main update ---
async function update() {
  const [sensors, prediction, status, history] = await Promise.all([
    api('/api/sensors'),
    api('/api/prediction'),
    api('/api/status'),
    api('/api/history?limit=30'),
  ]);

  if (sensors) updateSensors(sensors);
  if (prediction) updatePrediction(prediction);
  if (status) updateStatus(status);
  if (history && history.history) updateHistory(history.history);
}

function updateSensors(d) {
  S.sensors = d;
  const t = d.temperature, h = d.humidity, p = d.pressure, r = d.rain_sensor_calibrated;
  const isLive = d.mode === 'live';

  // Hero
  animateValue(document.getElementById('heroTemp'), t, 2, '\u00B0');

  // Sensor values with smooth transitions
  animateValue(document.getElementById('temp'), t, 2);
  animateValue(document.getElementById('hum'), h, 2);
  animateValue(document.getElementById('pressure'), p, 1);
  const rainEl = document.getElementById('rainVal');
  if (rainEl) rainEl.textContent = Math.round(r);

  // Sensor page
  animateValue(document.getElementById('temp2'), t, 2);
  animateValue(document.getElementById('hum2'), h, 2);
  animateValue(document.getElementById('pres2'), p, 1);
  animateValue(document.getElementById('rain2'), r, 1);

  // Tags
  const setTag = (id, live) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = live ? 'LIVE' : 'SIM';
    el.className = live ? 'tag' : 'tag sim';
  };
  setTag('tagTemp', isLive); setTag('tagHum', isLive);
  setTag('tagPres', isLive); setTag('tagRain', isLive);
  setTag('tagTemp2', isLive); setTag('tagHum2', isLive);
  setTag('tagPres2', isLive); setTag('tagRain2', isLive);

  // Wind
  const w = simWind();
  document.getElementById('wind').textContent = w.speed;
  document.getElementById('direction').textContent = w.dir;

  // Bars with smooth transitions
  const barTemp = document.getElementById('barTemp');
  const barHum = document.getElementById('barHum');
  const barPres = document.getElementById('barPres');
  const barRain = document.getElementById('barRain');
  if (barTemp) barTemp.style.width = ((t + 20) / 80 * 100) + '%';
  if (barHum) barHum.style.width = h + '%';
  if (barPres) barPres.style.width = ((p - 850) / 250 * 100) + '%';
  if (barRain) barRain.style.width = r + '%';

  // Rain state
  const rs = document.getElementById('rainState');
  if (rs) {
    if (r < 10) { rs.textContent = 'DRY'; rs.className = 'rainstate'; }
    else if (r < 30) { rs.textContent = 'LIGHT'; rs.className = 'rainstate light'; }
    else if (r < 60) { rs.textContent = 'MODERATE'; rs.className = 'rainstate moderate'; }
    else { rs.textContent = 'HEAVY'; rs.className = 'rainstate heavy'; }
  }

  // Feature table
  document.getElementById('ftT').textContent = t.toFixed(2) + ' \u00B0C';
  document.getElementById('ftH').textContent = h.toFixed(2) + ' %';
  document.getElementById('ftP').textContent = p.toFixed(2) + ' hPa';
  document.getElementById('ftR').textContent = r.toFixed(2) + ' %';

  // History
  S.hist.t.push(t); S.hist.h.push(h); S.hist.p.push(p); S.hist.r.push(r);
  if (S.hist.t.length > 30) { S.hist.t.shift(); S.hist.h.shift(); S.hist.p.shift(); S.hist.r.shift(); }
}

function updatePrediction(d) {
  S.prediction = d;
  const prob = d.probability * 100;
  const isTrained = d.model_status === 'trained';
  const isDemo = d.model_status === 'demo';

  // Gauge with smooth animation
  const deg = prob * 3.6;
  const gauge = document.getElementById('gauge');
  if (gauge) {
    gauge.style.background =
      'conic-gradient(var(--cyan) 0deg, var(--vio) ' + deg + 'deg, rgba(255,255,255,0.05) ' + deg + 'deg)';
  }
  animateValue(document.getElementById('prob'), prob, 0, '%');

  const conf = Math.round(78 + prob * 0.18);
  document.getElementById('confidence').textContent = conf + '%';

  const pred = predict(d.features.humidity, d.features.rain_sensor, d.features.pressure, d.features.temperature);
  document.getElementById('forecast').textContent = pred.cls + ' \u00B7 ' + pred.detail;

  const label = isTrained ? 'MODEL: RANDOM FOREST / STATUS: TRAINED' : isDemo ? 'MODEL: RANDOM FOREST / STATUS: SIMULATION' : 'MODEL: NOT TRAINED';
  document.getElementById('modelLabel').textContent = label;

  // Prediction page
  const gauge2 = document.getElementById('gauge2');
  if (gauge2) {
    gauge2.style.background =
      'conic-gradient(var(--cyan) 0deg, var(--vio) ' + deg + 'deg, rgba(255,255,255,0.05) ' + deg + 'deg)';
    animateValue(document.getElementById('prob2'), prob, 0, '%');
    document.getElementById('probClass2').textContent = d.class;
    document.getElementById('forecast2').textContent = pred.cls + ' \u00B7 ' + pred.detail;
    document.getElementById('modelLabel2').textContent = isTrained ? 'TRAINED RANDOM FOREST' : 'SIMULATION MODE';
  }

  S.hist.prob.push(prob);
  if (S.hist.prob.length > 30) S.hist.prob.shift();
}

function updateStatus(d) {
  S.mode = d.mode;
  const isLive = d.mode === 'live' && d.esp32_connected;

  document.getElementById('heroStatus').textContent = d.mode === 'live' ? (isLive ? 'MONITORING ACTIVE \u2014 LIVE' : 'ESP32 NOT CONNECTED') : 'MONITORING ACTIVE';

  // Mode buttons
  ['btnSim','btnSim2'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.toggle('active', d.mode === 'simulation'); });
  ['btnLive','btnLive2'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.toggle('active', d.mode === 'live'); });

  // Hardware
  const setHw = (id, text, cls, dotCls) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = '<span class="sdot ' + dotCls + '"></span>' + text;
    el.className = 'state ' + cls;
  };
  if (d.mode === 'live') {
    const c = d.esp32_connected;
    setHw('hwEsp32', c ? 'CONNECTED' : 'DISCONNECTED', c ? '' : '', c ? '' : 'off');
    setHw('hwEsp32b', c ? 'CONNECTED' : 'DISCONNECTED', c ? '' : '', c ? '' : 'off');
    setHw('hwDht', c ? 'LIVE' : 'SIMULATED', c ? '' : 'amber', c ? '' : 'off');
    setHw('hwDhtb', c ? 'LIVE' : 'SIMULATED', c ? '' : 'amber', c ? '' : 'off');
    setHw('hwBmp', c ? 'LIVE' : 'SIMULATED', c ? '' : 'amber', c ? '' : 'amber');
    setHw('hwBmpb', c ? 'LIVE' : 'SIMULATED', c ? '' : 'amber', c ? '' : 'amber');
    setHw('hwRain', c ? 'LIVE' : 'SIMULATED', c ? '' : 'amber', c ? '' : 'amber');
    setHw('hwRainb', c ? 'LIVE' : 'SIMULATED', c ? '' : 'amber', c ? '' : 'amber');
  } else {
    setHw('hwEsp32', 'STANDOFF', '', 'off');
    setHw('hwEsp32b', 'STANDOFF', '', 'off');
    setHw('hwDht', 'SIMULATED', 'amber', 'amber');
    setHw('hwDhtb', 'SIMULATED', 'amber', 'amber');
    setHw('hwBmp', 'SIMULATED', 'amber', 'amber');
    setHw('hwBmpb', 'SIMULATED', 'amber', 'amber');
    setHw('hwRain', 'SIMULATED', 'amber', 'amber');
    setHw('hwRainb', 'SIMULATED', 'amber', 'amber');
  }
  const aiLabel = d.model_status === 'trained' ? 'ACTIVE / TRAINED' : 'ACTIVE / SIM';
  const aiCls = d.model_status === 'trained' ? '' : 'amber';
  setHw('hwAi', aiLabel, aiCls, aiCls ? 'amber' : '');
  setHw('hwAib', aiLabel, aiCls, aiCls ? 'amber' : '');

  // Serial
  document.getElementById('serialPort').textContent = d.serial_port || '--';
  document.getElementById('serialBaud').textContent = d.baud_rate || '--';
  document.getElementById('serialPkts').textContent = d.packet_count || 0;
  document.getElementById('serialInvalid').textContent = d.invalid_packet_count || 0;
  document.getElementById('serialLast').textContent = d.last_packet_time ? new Date(d.last_packet_time).toLocaleTimeString() : '--';
  document.getElementById('serialQuality').textContent = d.data_quality || '--';

  // Network
  const netLabel = isLive ? 'CONNECTED' : 'SIMULATED';
  const netColor = isLive ? 'var(--green)' : 'var(--mut)';
  ['netEsp','netEsp2'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.textContent = netLabel; el.style.color = netColor; }
  });
}

function updateHistory(rows) {
  const body = document.getElementById('histBody');
  document.getElementById('histCount').textContent = rows.length;
  body.innerHTML = rows.slice().reverse().map(r => '<tr><td>' +
    new Date(r.timestamp).toLocaleTimeString() + '</td><td>' + r.mode + '</td><td>' +
    r.temperature.toFixed(1) + '</td><td>' + r.humidity.toFixed(1) + '</td><td>' +
    r.pressure.toFixed(1) + '</td><td>' + r.rain_calibrated.toFixed(1) + '</td><td>' +
    r.prediction_class + '</td><td>' + (r.prediction_probability * 100).toFixed(1) + '%</td></tr>'
  ).join('');
}

function downloadCSV() { window.location.href = '/api/history/download'; }

// ========== Charts ==========
let analyticsInited = false;
function initAnalyticsCharts() {
  if (analyticsInited) return;
  analyticsInited = true;
}

function drawChart(canvas, data, color) {
  if (!canvas || !data) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight || 220;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  for (let i = 0; i < 5; i++) {
    const y = 20 + i * (h - 40) / 4;
    ctx.beginPath(); ctx.moveTo(25, y); ctx.lineTo(w - 15, y); ctx.stroke();
  }

  if (data.length < 2) return;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  // Gradient fill
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, color + '30');
  gradient.addColorStop(1, color + '00');

  ctx.beginPath();
  data.forEach((v, i) => {
    const x = 25 + i * (w - 40) / (data.length - 1);
    const y = h - 20 - (v - min) / range * (h - 40);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.stroke();

  // Fill
  ctx.lineTo(25 + (data.length - 1) * (w - 40) / (data.length - 1), h - 20);
  ctx.lineTo(25, h - 20);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();
}

// --- Main chart ---
function drawMainChart() {
  const canvas = document.getElementById('chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight || 285;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  for (let i = 0; i < 5; i++) {
    const y = 20 + i * (h - 40) / 4;
    ctx.beginPath(); ctx.moveTo(25, y); ctx.lineTo(w - 15, y); ctx.stroke();
  }

  [[S.hist.t, 28, 35, '#70e7ff'], [S.hist.h, 45, 95, '#a78bfa']].forEach(([data, min, max, color]) => {
    if (data.length < 2) return;

    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, color + '25');
    gradient.addColorStop(1, color + '00');

    ctx.beginPath();
    data.forEach((v, i) => {
      const x = 25 + i * (w - 40) / 29;
      const y = h - 20 - (v - min) / (max - min) * (h - 40);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    // Fill area under curve
    ctx.lineTo(25 + (data.length - 1) * (w - 40) / 29, h - 20);
    ctx.lineTo(25, h - 20);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
  });
}

// --- Radar ---
function initRadarCanvas() {
  if (S.radarAnim) cancelAnimationFrame(S.radarAnim);
}

// ========== Poll with requestAnimationFrame for smooth updates ==========
let lastUpdate = 0;
function smoothLoop(timestamp) {
  if (timestamp - lastUpdate >= 1500) {
    update();
    drawMainChart();
    lastUpdate = timestamp;
  }
  S.animFrame = requestAnimationFrame(smoothLoop);
}

// Start the loop
requestAnimationFrame(smoothLoop);
update();
