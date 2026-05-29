// Dashboard Sidriane — render + upload

const fmtBRL     = v => (v ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const fmtBRLfull = v => (v ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fmtNum     = v => (v ?? 0).toLocaleString('pt-BR');
const fmtDate    = s => new Date(s + 'T00:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });

Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#1b2740';
Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui";

const PALETTE = ['#0ea5e9','#14b8a6','#f59e0b','#ef4444','#8b5cf6','#22c55e','#ec4899','#f97316'];
const charts = {}; // instâncias para destroy ao re-render

// ============================ LOAD & RENDER ============================

async function loadAndRender() {
  // Streamlit embed: dados injetados via window.DASHBOARD_DATA
  if (window.DASHBOARD_DATA) {
    const data = window.DASHBOARD_DATA;
    if (data.empty) { renderEmpty(data.meta); return; }
    renderAll(data);
    return;
  }
  const res = await fetch('data.json', { cache: 'no-store' });
  if (!res.ok) {
    showError('Não foi possível carregar <code>data.json</code>. Faça upload de uma planilha ou rode o pipeline.');
    return;
  }
  const data = await res.json();
  if (data.empty) {
    renderEmpty(data.meta);
    return;
  }
  renderAll(data);
}

function renderEmpty(meta) {
  // destrói gráficos antigos (caso venham de upload anterior)
  Object.values(charts).forEach(c => { try { c.destroy(); } catch {} });

  document.getElementById('meta-periodo').innerHTML =
    `<span class="text-amber-400">Nenhum arquivo carregado.</span> Use a área "Importar planilhas" acima para começar.`;
  document.getElementById('meta-rodape').textContent = `Atualizado em ${new Date(meta.gerado_em).toLocaleString('pt-BR')}`;
  document.getElementById('meta-notas').innerHTML = (meta.notas || []).map(n => `• ${n}`).join('<br>');

  // KPIs zerados com placeholder
  const placeholders = ['Vendas geral','Unidades vendidas','Positivação','Ticket médio','Vendedores','Cobertura geo'];
  document.getElementById('kpis').innerHTML = placeholders.map(label => `
    <div class="kpi opacity-60">
      <span class="kpi-label">${label}</span>
      <span class="kpi-value text-slate-500">—</span>
      <span class="kpi-sub">aguardando upload</span>
    </div>`).join('');

  // Limpa containers
  ['chartDaily','chartVend','chartCanal','chartProd','chartUF'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { const ctx = el.getContext('2d'); ctx.clearRect(0, 0, el.width, el.height); }
  });
  const emptyMsg = '<tr><td colspan="6" class="text-slate-500 text-center py-6">Sem dados — faça upload de uma planilha.</td></tr>';
  document.querySelector('#tblPositivacao tbody').innerHTML = emptyMsg;
  document.querySelector('#tblEstoque tbody').innerHTML = emptyMsg;
  document.querySelector('#tblSegm tbody').innerHTML = emptyMsg;
  ['#tblVendedor tbody','#tblCanal tbody','#tblProdutos tbody','#tblUF tbody','#tblPosUF tbody','#tblPosCanal tbody','#tblPosMes tbody']
    .forEach(sel => { const el = document.querySelector(sel); if (el) el.innerHTML = emptyMsg; });
  const tblCli = document.querySelector('#tblClientes tbody');
  if (tblCli) tblCli.innerHTML = '<tr><td colspan="12" class="text-slate-500 text-center py-6">Sem dados — faça upload de uma planilha.</td></tr>';
  ['clientesCount','positivacaoResumo','estoqueStatus','estoqueResumo','serieResumo','highlightsGrid','projMetricas','prodCount']
    .forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = id === 'clientesCount' ? '0 CNPJs' : ''; });
}

let CURRENT_DATA = null;
let CURRENT_PERIOD = 'daily';

function renderAll(data) {
  CURRENT_DATA = data;
  renderMeta(data.meta);
  renderKpis(data.kpis);
  renderSerie(CURRENT_PERIOD);
  renderVendedor(data.by_vendedor);
  renderCanal(data.by_canal);
  renderProdutos(data.top_produtos);
  renderUF(data.by_uf);
  renderPositivacao(data.positivacao_por_vendedor, data.positivacao_extras);
  renderEstoque(data.estoque, data.estoque_resumo);
  renderSegm(data.segmentacao);
  renderClientes(data.clientes || []);
  renderHighlights(data.highlights || {});
}

function showError(html) {
  document.getElementById('meta-periodo').innerHTML =
    `<span class="text-rose-400">${html}</span>`;
}

function renderMeta(m) {
  document.getElementById('meta-periodo').textContent =
    `Período: ${fmtDate(m.data_min)} a ${fmtDate(m.data_max)}  ·  atualizado em ${new Date(m.gerado_em).toLocaleString('pt-BR')}`;
  document.getElementById('meta-rodape').textContent = `Atualizado em ${new Date(m.gerado_em).toLocaleString('pt-BR')}`;
  document.getElementById('meta-notas').innerHTML = m.notas.map(n => `• ${n}`).join('<br>');
}

function renderKpis(k) {
  const items = [
    { label: 'Vendas geral',      value: fmtBRL(k.vendas_total),  sub: `${fmtNum(k.transacoes)} transações · ${fmtNum(k.dias_com_venda)} dias` },
    { label: 'Unidades vendidas', value: fmtNum(k.unidades),      sub: `${fmtNum(k.produtos_ativos)} SKUs · ${k.unidades_por_transacao}/tx` },
    { label: 'Positivação',       value: fmtNum(k.positivacao),   sub: 'CNPJs únicos compradores' },
    { label: 'Ticket médio',      value: fmtBRL(k.ticket_medio),  sub: `por cliente · R$ ${fmtNum(k.ticket_transacao)}/tx` },
    { label: 'Preço médio unit.',  value: fmtBRL(k.preco_medio_unitario), sub: 'por unidade vendida' },
    { label: 'Vendas média/dia',  value: fmtBRL(k.vendas_dia_medio), sub: `${fmtNum(k.unidades_dia_medio)} un · ${fmtNum(k.transacoes_dia_medio)} tx` },
    { label: 'Vendedores',        value: fmtNum(k.vendedores),    sub: `${fmtNum(k.canais)} canais` },
    { label: 'Cobertura geo',     value: fmtNum(k.ufs) + ' UFs',  sub: 'estados atendidos' },
  ];
  document.getElementById('kpis').innerHTML = items.map(i => `
    <div class="kpi">
      <span class="kpi-label">${i.label}</span>
      <span class="kpi-value">${i.value}</span>
      <span class="kpi-sub">${i.sub}</span>
    </div>`).join('');
}

function renderHighlights(h) {
  const el = document.getElementById('highlightsGrid');
  if (!el) return;
  const items = [
    { l: 'Melhor dia',     v: h.melhor_dia?.data ? fmtDate(h.melhor_dia.data) : '—', s: fmtBRL(h.melhor_dia?.valor || 0) },
    { l: 'Melhor semana',  v: h.melhor_semana?.data ? fmtDate(h.melhor_semana.data) : '—', s: fmtBRL(h.melhor_semana?.valor || 0) },
    { l: 'Melhor mês',     v: h.melhor_mes?.data ? new Date(h.melhor_mes.data).toLocaleDateString('pt-BR',{year:'numeric',month:'short'}) : '—', s: fmtBRL(h.melhor_mes?.valor || 0) },
    { l: 'Top vendedor',   v: h.melhor_vendedor?.nome || '—', s: `${fmtBRL(h.melhor_vendedor?.valor || 0)} · ${h.share_top1_vendedor_pct || 0}%` },
    { l: 'Top produto',    v: (h.melhor_produto?.nome || '—').slice(0, 40), s: fmtBRL(h.melhor_produto?.valor || 0) },
    { l: 'Top canal',      v: h.melhor_canal?.nome || '—', s: `${fmtBRL(h.melhor_canal?.valor || 0)} · ${h.share_top1_canal_pct || 0}%` },
    { l: 'Top UF',         v: h.melhor_uf?.nome || '—', s: `${fmtBRL(h.melhor_uf?.valor || 0)} · ${h.share_top1_uf_pct || 0}%` },
    { l: 'Concentração',   v: `${h.concentracao_top10_produtos_pct || 0}%`, s: `top10 produtos · top10 clientes: ${h.concentracao_top10_clientes_pct || 0}%` },
  ];
  el.innerHTML = items.map(i => `
    <div class="kpi">
      <span class="kpi-label">${i.l}</span>
      <span class="kpi-value text-base" title="${i.v}">${i.v}</span>
      <span class="kpi-sub">${i.s}</span>
    </div>`).join('');
}

function renderProjMetricas(m) {
  const el = document.getElementById('projMetricas');
  if (!el) return;
  if (!m || !Object.keys(m).length) { el.innerHTML = ''; return; }
  const items = [
    { l: 'R² (ajuste)',         v: (m.r2 ?? 0).toFixed(3) },
    { l: 'MAE',                 v: fmtBRL(m.mae || 0) },
    { l: 'MAPE',                v: `${m.mape_pct || 0}%` },
    { l: 'Total projetado',     v: fmtBRL(m.total_projetado || 0), s: `${m.horizonte_dias || 0} dias` },
    { l: 'Média diária proj.',   v: fmtBRL(m.media_diaria_projetada || 0) },
    { l: 'Banda min — max',     v: `${fmtBRL(m.min_projetado || 0)} — ${fmtBRL(m.max_projetado || 0)}` },
  ];
  el.innerHTML = items.map(i => `
    <div class="kpi">
      <span class="kpi-label">${i.l}</span>
      <span class="kpi-value text-base">${i.v}</span>
      ${i.s ? `<span class="kpi-sub">${i.s}</span>` : ''}
    </div>`).join('');
}

function makeChart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

function renderSerie(period) {
  if (!CURRENT_DATA) return;
  CURRENT_PERIOD = period;
  const map = {
    daily:   CURRENT_DATA.daily_sales || [],
    weekly:  CURRENT_DATA.weekly_sales || [],
    monthly: CURRENT_DATA.monthly_sales || [],
  };
  const series = map[period] || [];
  // resumo
  const total = series.reduce((a, r) => a + (r.valor || 0), 0);
  const qtd = series.reduce((a, r) => a + (r.qtd || 0), 0);
  const tx = series.reduce((a, r) => a + (r.transacoes || 0), 0);
  const periodos = series.length;
  const media = periodos ? total / periodos : 0;
  const labelPeriodo = { daily: 'Dias', weekly: 'Semanas', monthly: 'Meses' }[period];
  document.getElementById('serieResumo').innerHTML = [
    { l: labelPeriodo, v: fmtNum(periodos) },
    { l: 'Total no período', v: fmtBRL(total) },
    { l: `Média / ${labelPeriodo.toLowerCase().slice(0,-1)}`, v: fmtBRL(media) },
    { l: 'Unidades / Transações', v: `${fmtNum(qtd)} / ${fmtNum(tx)}` },
  ].map(x => `<div class="kpi"><span class="kpi-label">${x.l}</span><span class="kpi-value text-base">${x.v}</span></div>`).join('');

  // projeção apenas no diário
  const proj = period === 'daily' ? (CURRENT_DATA.projection || []) : [];
  renderDaily(series, proj, period);
  if (period === 'daily') renderProjMetricas(CURRENT_DATA.projection_metrics || {});
  else { const el = document.getElementById('projMetricas'); if (el) el.innerHTML = ''; }
}

function renderDaily(daily, proj, period = 'daily') {
  const fmtLabel = period === 'monthly'
    ? (d) => new Date(d).toLocaleDateString('pt-BR', { year: 'numeric', month: 'short' })
    : period === 'weekly'
      ? (d) => 'Sem. ' + fmtDate(d)
      : fmtDate;

  const labels = [...daily.map(d => fmtLabel(d.data)), ...proj.map(d => fmtLabel(d.data))];
  const real = [...daily.map(d => d.valor), ...proj.map(() => null)];
  const projVals = [...daily.map(() => null), ...proj.map(d => d.valor_proj)];
  const upper = [...daily.map(() => null), ...proj.map(d => d.upper)];
  const lower = [...daily.map(() => null), ...proj.map(d => d.lower)];

  const datasets = [
    { label: 'Realizado', data: real, borderColor: PALETTE[0], backgroundColor: 'rgba(14,165,233,.15)', tension: .3, fill: true, pointRadius: 2 },
  ];
  if (proj.length) {
    datasets.push(
      { label: 'Projeção', data: projVals, borderColor: PALETTE[2], borderDash: [6,4], tension: .2, pointRadius: 0 },
      { label: 'Banda sup.', data: upper, borderColor: 'transparent', backgroundColor: 'rgba(245,158,11,.12)', fill: '+1', pointRadius: 0 },
      { label: 'Banda inf.', data: lower, borderColor: 'transparent', backgroundColor: 'rgba(245,158,11,.12)', fill: false, pointRadius: 0 },
    );
  }

  makeChart('chartDaily', {
    type: period === 'monthly' ? 'bar' : 'line',
    data: { labels, datasets },
    options: chartBase({ y: { ticks: { callback: v => 'R$ ' + (v/1000).toFixed(0) + 'k' } } })
  });
}

function renderVendedor(rows) {
  makeChart('chartVend', {
    type: 'bar',
    data: { labels: rows.map(r => r.vendedor),
            datasets: [{ label: 'Vendas (R$)', data: rows.map(r => r.valor), backgroundColor: PALETTE[1], borderRadius: 6 }] },
    options: chartBase({ indexAxis: 'y', x: { ticks: { callback: v => 'R$ ' + (v/1000).toFixed(0) + 'k' } } }, false)
  });
  const tb = document.querySelector('#tblVendedor tbody');
  if (tb) tb.innerHTML = rows.map(r => `
    <tr>
      <td>${r.vendedor}</td>
      <td class="num">${fmtBRLfull(r.valor)}</td>
      <td class="num">${r.share_pct}%</td>
      <td class="num">${fmtNum(r.qtd)}</td>
      <td class="num">${fmtNum(r.transacoes)}</td>
      <td class="num">${fmtNum(r.clientes)}</td>
      <td class="num">${fmtNum(r.dias_ativos)}</td>
      <td class="num">${fmtNum(r.produtos)}</td>
      <td class="num">${fmtNum(r.ufs)}</td>
      <td class="num">${fmtBRLfull(r.ticket_medio)}</td>
      <td class="num">${fmtBRLfull(r.preco_medio_unit)}</td>
      <td>${r.melhor_canal || '—'}</td>
      <td>${r.melhor_uf || '—'}</td>
    </tr>`).join('');
}

function renderCanal(rows) {
  makeChart('chartCanal', {
    type: 'doughnut',
    data: { labels: rows.map(r => r.canal),
            datasets: [{ data: rows.map(r => r.valor), backgroundColor: PALETTE, borderColor: '#0b1220', borderWidth: 3 }] },
    options: { maintainAspectRatio: false, responsive: true,
               plugins: { legend: { position: 'bottom' },
                          tooltip: { callbacks: { label: c => `${c.label}: ${fmtBRL(c.parsed)}` } } } }
  });
  const tb = document.querySelector('#tblCanal tbody');
  if (tb) tb.innerHTML = rows.map(r => `
    <tr>
      <td>${r.canal}</td>
      <td class="num">${fmtBRLfull(r.valor)}</td>
      <td class="num">${r.share_pct}%</td>
      <td class="num">${fmtNum(r.qtd)}</td>
      <td class="num">${fmtNum(r.transacoes)}</td>
      <td class="num">${fmtNum(r.clientes)}</td>
      <td class="num">${fmtNum(r.vendedores)}</td>
      <td class="num">${fmtNum(r.ufs)}</td>
      <td class="num">${fmtNum(r.produtos)}</td>
      <td class="num">${fmtBRLfull(r.ticket_medio)}</td>
      <td class="num">${fmtBRLfull(r.preco_medio_unit)}</td>
    </tr>`).join('');
}

function renderProdutos(rows) {
  const top15 = rows.slice(0, 15);
  makeChart('chartProd', {
    type: 'bar',
    data: { labels: top15.map(r => (r.produto_canon || '').slice(0,55)),
            datasets: [{ label: 'Valor (R$)', data: top15.map(r => r.valor), backgroundColor: PALETTE[3], borderRadius: 6 }] },
    options: chartBase({ indexAxis: 'y', x: { ticks: { callback: v => 'R$ ' + (v/1000).toFixed(0) + 'k' } } }, false)
  });
  const pc = document.getElementById('prodCount');
  if (pc) pc.textContent = `${rows.length} produtos`;
  const tb = document.querySelector('#tblProdutos tbody');
  if (tb) tb.innerHTML = rows.map((r, i) => `
    <tr>
      <td class="num text-slate-500">${i + 1}</td>
      <td class="max-w-[360px] truncate" title="${(r.produto_canon || '').replace(/"/g,'&quot;')}">${r.produto_canon || '—'}</td>
      <td class="num">${fmtBRLfull(r.valor)}</td>
      <td class="num">${r.share_pct}%</td>
      <td class="num">${fmtNum(r.qtd)}</td>
      <td class="num">${fmtBRLfull(r.preco_medio_unit)}</td>
      <td class="num">${fmtNum(r.transacoes)}</td>
      <td class="num">${fmtNum(r.clientes)}</td>
      <td class="num">${fmtNum(r.vendedores)}</td>
      <td class="num">${fmtNum(r.canais)}</td>
      <td class="num">${fmtNum(r.ufs)}</td>
    </tr>`).join('');
}

function renderUF(rows) {
  makeChart('chartUF', {
    type: 'bar',
    data: { labels: rows.map(r => r.uf),
            datasets: [{ label: 'Valor (R$)', data: rows.map(r => r.valor), backgroundColor: PALETTE[4], borderRadius: 6 }] },
    options: chartBase({ y: { ticks: { callback: v => 'R$ ' + (v/1000).toFixed(0) + 'k' } } })
  });
  const tb = document.querySelector('#tblUF tbody');
  if (tb) tb.innerHTML = rows.map(r => `
    <tr>
      <td>${r.uf}</td>
      <td class="num">${fmtBRLfull(r.valor)}</td>
      <td class="num">${r.share_pct}%</td>
      <td class="num">${fmtNum(r.qtd)}</td>
      <td class="num">${fmtNum(r.clientes)}</td>
      <td class="num">${fmtNum(r.vendedores)}</td>
      <td class="num">${fmtNum(r.produtos)}</td>
      <td class="num">${fmtBRLfull(r.ticket_medio)}</td>
    </tr>`).join('');
}

function renderPositivacao(rows, extras) {
  document.querySelector('#tblPositivacao tbody').innerHTML = rows.map(r => `
    <tr>
      <td>${r.vendedor}</td>
      <td class="num">${fmtNum(r.clientes_ativos)}</td>
      <td class="num">${r.share_carteira_pct}%</td>
      <td class="num">${fmtNum(r.dias_com_venda)}</td>
      <td class="num">${fmtNum(r.transacoes)}</td>
      <td class="num">${fmtNum(r.qtd)}</td>
      <td class="num">${fmtNum(r.ufs)}</td>
      <td class="num">${fmtNum(r.produtos)}</td>
      <td class="num">${fmtBRLfull(r.valor_por_cliente)}</td>
      <td class="num">${fmtNum(r.unidades_por_cliente)}</td>
      <td class="num">${fmtNum(r.transacoes_por_cliente)}</td>
    </tr>`).join('');

  if (!extras) return;
  const r = extras.resumo || {};
  document.getElementById('positivacaoResumo').innerHTML = [
    { l: 'Total CNPJs', v: fmtNum(r.total_cnpjs || 0) },
    { l: 'Novos (≤7 dias)', v: fmtNum(r.novos_7d || 0) },
    { l: 'Recorrentes', v: fmtNum(r.recorrentes || 0) },
    { l: 'Compra única', v: fmtNum(r.compra_unica || 0) },
    { l: 'Inativos (>30d)', v: fmtNum(r.inativos_30d || 0) },
  ].map(x => `<div class="kpi"><span class="kpi-label">${x.l}</span><span class="kpi-value text-base">${x.v}</span></div>`).join('');

  const rowsTpl = (arr, key) => (arr || []).map(x => `
    <tr><td>${x[key] || '—'}</td><td class="num">${fmtNum(x.cnpjs)}</td><td class="num">${fmtBRLfull(x.valor)}</td></tr>`).join('');
  document.querySelector('#tblPosUF tbody').innerHTML = rowsTpl(extras.por_uf, 'uf');
  document.querySelector('#tblPosCanal tbody').innerHTML = rowsTpl(extras.por_canal, 'canal');
  const mesRows = (extras.por_mes || []).map(x => `
    <tr><td>${new Date(x.mes).toLocaleDateString('pt-BR',{year:'numeric',month:'short'})}</td>
        <td class="num">${fmtNum(x.cnpjs)}</td><td class="num">${fmtBRLfull(x.valor)}</td></tr>`).join('');
  document.querySelector('#tblPosMes tbody').innerHTML = mesRows;
}

function renderEstoque(rows, resumo) {
  document.getElementById('estoqueResumo').innerHTML = [
    { l: 'SKUs', v: fmtNum(resumo.skus) },
    { l: 'Unidades em estoque', v: fmtNum(resumo.unidades_totais) },
    { l: 'Valor em estoque', v: fmtBRL(resumo.valor_total) },
    { l: 'Cobertura média', v: `${resumo.cobertura_media_dias || 0} d` },
    { l: 'SKUs CRÍT / BAIXO', v: `${resumo.criticos} / ${resumo.baixos}` },
  ].map(x => `<div class="kpi"><span class="kpi-label">${x.l}</span><span class="kpi-value">${x.v}</span></div>`).join('');

  const statusEl = document.getElementById('estoqueStatus');
  if (statusEl) {
    statusEl.innerHTML = [
      { l: 'CRÍTICO', n: resumo.criticos || 0, v: resumo.valor_critico || 0, cls: 'text-rose-400' },
      { l: 'BAIXO',   n: resumo.baixos || 0,   v: resumo.valor_baixo || 0,   cls: 'text-amber-400' },
      { l: 'OK',      n: resumo.ok || 0,       v: resumo.valor_ok || 0,      cls: 'text-emerald-400' },
      { l: 'ALTO',    n: resumo.alto || 0,     v: resumo.valor_alto || 0,    cls: 'text-sky-400' },
    ].map(x => `<div class="kpi"><span class="kpi-label ${x.cls}">${x.l}</span><span class="kpi-value text-base">${fmtNum(x.n)} SKUs</span><span class="kpi-sub">${fmtBRL(x.v)}</span></div>`).join('');
  }

  document.querySelector('#tblEstoque tbody').innerHTML = rows.map(r => `
    <tr>
      <td class="max-w-[420px] truncate" title="${r.produto_canon}">${r.produto_canon}</td>
      <td class="num">${fmtNum(r.unidades_estoque)}</td>
      <td class="num">${fmtBRLfull(r.valor_estoque)}</td>
      <td class="num">${(r.vendas_diaria_media ?? 0).toFixed(2)}</td>
      <td class="num">${r.cobertura_dias}</td>
      <td><span class="pill pill-${r.status}">${r.status}</span></td>
    </tr>`).join('');
}

function renderSegm(rows) {
  const tb = document.querySelector('#tblSegm tbody');
  if (!rows.length) { tb.innerHTML = '<tr><td colspan="6" class="text-slate-500">Sem dados suficientes para segmentar.</td></tr>'; return; }
  tb.innerHTML = rows.map(r => `
    <tr>
      <td><strong>${r.label}</strong> <span class="text-slate-500 text-xs">#${r.cluster}</span></td>
      <td class="num">${fmtNum(r.n_clientes)}</td>
      <td class="num">${r.recency_media}</td>
      <td class="num">${r.freq_media}</td>
      <td class="num">${fmtBRLfull(r.valor_medio)}</td>
      <td class="num">${fmtBRLfull(r.valor_total)}</td>
    </tr>`).join('');
}

function renderClientes(rows) {
  const tb = document.querySelector('#tblClientes tbody');
  const countEl = document.getElementById('clientesCount');
  if (!tb) return;
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="12" class="text-slate-500 text-center py-6">Sem dados.</td></tr>';
    if (countEl) countEl.textContent = '0 CNPJs';
    return;
  }
  const q = (document.getElementById('clienteFiltro')?.value || '').trim().toLowerCase();
  const ordem = document.getElementById('clienteOrdem')?.value || 'valor_total';

  let filtered = rows;
  if (q) {
    filtered = rows.filter(r =>
      (r.cnpj || '').toLowerCase().includes(q) ||
      (r.cliente || '').toLowerCase().includes(q) ||
      (r.uf || '').toLowerCase().includes(q) ||
      (r.canal || '').toLowerCase().includes(q) ||
      (r.vendedor || '').toLowerCase().includes(q) ||
      (r.top_produto || '').toLowerCase().includes(q)
    );
  }
  const asc = (ordem === 'recency_dias');
  filtered = [...filtered].sort((a, b) => asc ? (a[ordem] - b[ordem]) : (b[ordem] - a[ordem]));

  if (countEl) countEl.textContent = `${fmtNum(filtered.length)} CNPJs` + (q ? ` (de ${fmtNum(rows.length)})` : '');

  const view = filtered.slice(0, 500); // limite de render
  tb.innerHTML = view.map(r => `
    <tr>
      <td class="font-mono text-xs">${r.cnpj || '—'}</td>
      <td class="max-w-[260px] truncate" title="${(r.cliente || '').replace(/"/g,'&quot;')}">${r.cliente || '—'}</td>
      <td>${r.uf || '—'}</td>
      <td>${r.canal || '—'}</td>
      <td class="max-w-[200px] truncate" title="${(r.vendedor || '').replace(/"/g,'&quot;')}">${r.vendedor || '—'}</td>
      <td class="num">${fmtBRLfull(r.valor_total)}</td>
      <td class="num">${fmtNum(r.unidades)}</td>
      <td class="num">${fmtNum(r.transacoes)}</td>
      <td class="num">${fmtNum(r.dias_ativos)}</td>
      <td class="num">${fmtNum(r.n_produtos)}</td>
      <td class="max-w-[280px] truncate" title="${(r.top_produto || '').replace(/"/g,'&quot;')}">${r.top_produto || '—'} <span class="text-slate-500 text-xs">(${fmtBRL(r.top_produto_valor || 0)})</span></td>
      <td class="num">${fmtDate(r.ultima_compra)} <span class="text-slate-500 text-xs">(${r.recency_dias}d)</span></td>
    </tr>`).join('');
}

function chartBase(opts = {}, showLegend = true) {
  const { x, y, indexAxis, ...rest } = opts;
  return {
    maintainAspectRatio: false, responsive: true,
    ...(indexAxis ? { indexAxis } : {}),
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { display: showLegend, position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } },
      tooltip: { backgroundColor: '#111a2c', borderColor: '#1b2740', borderWidth: 1, padding: 10,
                 callbacks: { label: c => `${c.dataset.label || ''}: ${fmtBRLfull(c.parsed.y ?? c.parsed.x ?? c.parsed)}` } }
    },
    scales: {
      x: { grid: { display: false }, ...(x || {}) },
      y: { grid: { color: 'rgba(27,39,64,.6)' }, ...(y || {}) },
    },
    ...rest,
  };
}

// ============================ UPLOAD ============================

const dz = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const statusEl = document.getElementById('uploadStatus');
const resultEl = document.getElementById('uploadResult');

dz.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => uploadFiles(e.target.files));

['dragenter','dragover'].forEach(ev => dz.addEventListener(ev, e => {
  e.preventDefault(); dz.classList.add('drop-active');
}));
['dragleave','drop'].forEach(ev => dz.addEventListener(ev, e => {
  e.preventDefault(); dz.classList.remove('drop-active');
}));
dz.addEventListener('drop', e => uploadFiles(e.dataTransfer.files));

document.getElementById('btnReset').addEventListener('click', resetAll);

// Period switcher (Daily / Weekly / Monthly)
document.getElementById('periodSwitch')?.addEventListener('click', e => {
  const btn = e.target.closest('button[data-period]');
  if (!btn) return;
  document.querySelectorAll('#periodSwitch button').forEach(b => {
    b.classList.remove('bg-brand-500/20', 'text-brand-300');
    b.classList.add('text-slate-300', 'hover:bg-ink-800');
  });
  btn.classList.add('bg-brand-500/20', 'text-brand-300');
  btn.classList.remove('text-slate-300', 'hover:bg-ink-800');
  renderSerie(btn.dataset.period);
});

// Clientes (CNPJs) filtro + ordenação
document.getElementById('clienteFiltro')?.addEventListener('input', () => renderClientes(CURRENT_DATA?.clientes || []));
document.getElementById('clienteOrdem')?.addEventListener('change', () => renderClientes(CURRENT_DATA?.clientes || []));

async function uploadFiles(fileList) {
  const files = [...fileList].filter(f => /\.xlsx?$/i.test(f.name));
  if (!files.length) { setStatus('Selecione arquivos .xlsx', 'error'); return; }

  const fd = new FormData();
  files.forEach(f => fd.append('files', f));

  setStatus(`Processando ${files.length} arquivo(s)... ML inferindo schema e recalculando KPIs`, 'loading');
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || !data.ok) { setStatus('Erro: ' + (data.erro || 'desconhecido'), 'error'); return; }
    setStatus(`OK · ${data.salvos.length} arquivo(s) processado(s). Uploads ativos: ${data.uploads_ativos.length}`, 'ok');
    renderUploadResult(data);
    await loadAndRender();
  } catch (e) {
    setStatus('Falha de rede: ' + e.message, 'error');
  } finally {
    fileInput.value = '';
  }
}

async function resetAll() {
  setStatus('Resetando para o estado original...', 'loading');
  try {
    const res = await fetch('/api/reset', { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) { setStatus('Erro: ' + (data.erro || 'desconhecido'), 'error'); return; }
    setStatus('Reset concluído', 'ok');
    resultEl.classList.add('hidden');
    await loadAndRender();
  } catch (e) { setStatus('Falha: ' + e.message, 'error'); }
}

function setStatus(msg, kind) {
  const colors = { loading: 'text-brand-400', ok: 'text-emerald-400', error: 'text-rose-400' };
  statusEl.className = `text-xs ${colors[kind] || 'text-slate-400'}`;
  statusEl.textContent = msg;
}

function renderUploadResult(data) {
  resultEl.classList.remove('hidden');
  const fieldOrder = ['cliente','cnpj','uf','data','ean','produto','valor','qtd','canal'];
  const blocks = Object.entries(data.mappings).map(([file, info]) => {
    if (info.erro) {
      return `<div class="mapping-card"><div class="mapping-head">${file}</div>
              <div class="text-rose-400 text-sm">Erro: ${info.erro}</div></div>`;
    }
    const rows = fieldOrder.map(f => {
      const col = info.mapping[f];
      const conf = info.confidences[f];
      if (!col) return `<tr><td>${f}</td><td class="text-slate-500">(não detectado)</td><td class="num text-slate-500">—</td></tr>`;
      const c = (conf * 100).toFixed(0);
      const klass = conf > 0.7 ? 'text-emerald-400' : conf > 0.4 ? 'text-amber-400' : 'text-rose-400';
      return `<tr><td>${f}</td><td><code>${col}</code></td><td class="num ${klass}">${c}%</td></tr>`;
    }).join('');
    return `
      <div class="mapping-card">
        <div class="mapping-head">${file} <span class="text-slate-500 text-xs">· ${info.linhas} linhas</span></div>
        <table class="data-table">
          <thead><tr><th>Campo</th><th>Coluna detectada</th><th class="num">Confiança</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }).join('');
  resultEl.innerHTML = `
    <div class="text-xs text-slate-400 mb-2">Mapping inferido pelo ML:</div>
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">${blocks}</div>`;
}

// ============================ BOOT ============================
loadAndRender();
