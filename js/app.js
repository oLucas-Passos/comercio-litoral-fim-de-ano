// Gráficos e textos do site. Os dados vêm de data/litoral.json, gerado por `python -m litoral`.
'use strict';

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const MESES_LONGOS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const CICLO = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]; // ordem dos meses nos perfis (abr a mar)
const pos = m => CICLO.indexOf(m);

const $ = id => document.getElementById(id);
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const num = (v, d = 1) => (v == null ? '' : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (v, d = 0, sinal = true) => {
  if (v == null) return '';
  const r = Math.round(v * 100 * 10 ** d) / 10 ** d || 0; // evita "-0%"
  return (sinal && r > 0 ? '+' : '') + num(r, d) + '%';
};
const reais = (v, d = 0) => (v == null ? '' : 'R$ ' + num(v, d));
const bilhoes = v => {
  if (v == null) return '';
  const a = Math.abs(v);
  if (a >= 1e9) return `R$ ${num(v / 1e9, 1)} bilhões`;
  if (a >= 1e6) return `R$ ${num(v / 1e6, 0)} milhões`;
  return reais(v);
};
const compacto = v => {
  const a = Math.abs(v);
  if (a >= 1e9) return `R$ ${num(v / 1e9, 1)} bi`;
  if (a >= 1e6) return `R$ ${num(v / 1e6, 1)} mi`;
  if (a >= 1e3) return `R$ ${num(v / 1e3, 0)} mil`;
  return reais(v);
};
const mesExtenso = m => { const [a, mm] = m.split('-'); return `${MESES_LONGOS[+mm - 1]} de ${a}`; };
const mesCurto = m => { const [a, mm] = m.split('-'); return `${MESES[+mm - 1]}/${a.slice(2)}`; };
const transparente = (hex, a) => hex + Math.round(a * 255).toString(16).padStart(2, '0');
const estreito = () => window.innerWidth < 560;
const escapar = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const arred = (v, d) => (v == null ? null : Math.round(v * 10 ** d) / 10 ** d);
const nCidades = n => `${num(n, 0)} ${n === 1 ? 'cidade' : 'cidades'}`;

let D;
const graficos = {};
const estado = { metricaRank: 'alta_tipica', ufRank: '', ordem: { chave: 'alta_tipica', dir: -1 }, busca: '' };
const cores = () => ({ mar: cssVar('--mar'), marClaro: cssVar('--mar-claro'), interior: cssVar('--interior'), coral: cssVar('--coral'), areia: cssVar('--areia'), t2: cssVar('--texto-2'), t3: cssVar('--texto-3'), linha: cssVar('--linha'), fundo: cssVar('--fundo') });

// ------------------------------------------------------------------ plugins

// Traço de intervalo (inf, sup) sobre cada ponto ou barra do conjunto.
const pluginIntervalo = {
  id: 'intervalo',
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    const horizontal = chart.options.indexAxis === 'y';
    const eixo = horizontal ? chart.scales.x : chart.scales.y;
    chart.data.datasets.forEach((ds, i) => {
      if (!ds.inf || chart.getDatasetMeta(i).hidden) return;
      ctx.save();
      ctx.strokeStyle = ds.corIntervalo || cssVar('--texto-2');
      ctx.lineWidth = 1.2;
      chart.getDatasetMeta(i).data.forEach((el, j) => {
        if (ds.inf[j] == null) return;
        const a = eixo.getPixelForValue(ds.inf[j]), b = eixo.getPixelForValue(ds.sup[j]);
        const c = horizontal ? el.y : el.x;
        ctx.beginPath();
        if (horizontal) {
          ctx.moveTo(a, c); ctx.lineTo(b, c);
          ctx.moveTo(a, c - 3); ctx.lineTo(a, c + 3); ctx.moveTo(b, c - 3); ctx.lineTo(b, c + 3);
        } else {
          ctx.moveTo(c, a); ctx.lineTo(c, b);
          ctx.moveTo(c - 3, a); ctx.lineTo(c + 3, a); ctx.moveTo(c - 3, b); ctx.lineTo(c + 3, b);
        }
        ctx.stroke();
      });
      ctx.restore();
    });
  },
};

// Linha de referência tracejada (100 nos índices, 0 nos efeitos).
const pluginReferencia = {
  id: 'referencia',
  beforeDatasetsDraw(chart, _a, op) {
    if (op?.valor == null) return;
    const { ctx, chartArea: area } = chart;
    const horizontal = chart.options.indexAxis === 'y';
    const eixo = horizontal ? chart.scales.x : chart.scales.y;
    const p = eixo.getPixelForValue(op.valor);
    ctx.save();
    ctx.strokeStyle = cssVar('--texto-3');
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    if (horizontal) { ctx.moveTo(p, area.top); ctx.lineTo(p, area.bottom); } else { ctx.moveTo(area.left, p); ctx.lineTo(area.right, p); }
    ctx.stroke();
    ctx.restore();
  },
};

// Faixas de temporada (dez a fev) e marcadores numerados de Carnaval acima da área do gráfico.
const pluginTemporadas = {
  id: 'temporadas',
  beforeDatasetsDraw(chart, _a, op) {
    if (!op) return;
    const { ctx, chartArea: area, scales: { x } } = chart;
    const passo = x.getPixelForValue(1) - x.getPixelForValue(0);
    ctx.save();
    ctx.fillStyle = transparente(cssVar('--areia'), 0.55);
    (op.faixas || []).forEach(([i0, i1]) => {
      const x0 = Math.max(area.left, x.getPixelForValue(i0) - passo / 2);
      const x1 = Math.min(area.right, x.getPixelForValue(i1) + passo / 2);
      ctx.fillRect(x0, area.top, x1 - x0, area.bottom - area.top);
    });
    (op.marcos || []).forEach((i, n) => {
      const px = x.getPixelForValue(i);
      ctx.strokeStyle = cssVar('--coral');
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(px, area.top); ctx.lineTo(px, area.bottom); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = cssVar('--coral');
      ctx.beginPath(); ctx.arc(px, area.top - 12, 8, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#fff';
      ctx.font = '700 10px system-ui, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(String(n + 1), px, area.top - 11.5);
    });
    ctx.restore();
  },
};

// Ponto no centro de cada intervalo (gráfico de robustez).
const pluginPontos = {
  id: 'pontos',
  afterDatasetsDraw(chart) {
    const { ctx, scales: { x } } = chart;
    chart.data.datasets.forEach((ds, i) => {
      if (!ds.pontos) return;
      chart.getDatasetMeta(i).data.forEach((el, j) => {
        ctx.save();
        ctx.fillStyle = ds.corPontos[j];
        ctx.strokeStyle = cssVar('--fundo');
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(x.getPixelForValue(ds.pontos[j]), el.y, 5.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.restore();
      });
    });
  },
};

// ---------------------------------------------------------------- utilidades

function opcoes({ eixoY = v => v, dica = v => v, legenda = true, extra = {} } = {}) {
  const c = cores();
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 250 },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: legenda, align: 'start', labels: { color: c.t2, usePointStyle: true, pointStyle: 'line', boxWidth: 18, padding: 14 } },
      tooltip: { backgroundColor: 'rgba(20,38,58,.92)', padding: 10, callbacks: { label: ctx => `${ctx.dataset.label}: ${dica(ctx.parsed.y ?? ctx.parsed.x, ctx)}` } },
    },
    scales: {
      x: { grid: { display: false }, border: { color: c.linha }, ticks: { color: c.t2, padding: 6, maxRotation: 0, autoSkipPadding: 14 } },
      y: { grid: { color: c.linha, drawTicks: false }, border: { display: false }, ticks: { color: c.t2, padding: 8, callback: eixoY } },
    },
    ...extra,
  };
}

function desenhar(chave, canvas, config) {
  if (graficos[chave]) {
    graficos[chave].data = config.data;
    graficos[chave].options = config.options;
    graficos[chave].update();
  } else {
    graficos[chave] = new Chart($(canvas), config);
  }
}

function passoRedondo(bruto) {
  const base = 10 ** Math.floor(Math.log10(bruto));
  const f = bruto / base;
  return (f <= 1.5 ? 1 : f <= 3 ? 2 : f <= 7 ? 5 : 10) * base;
}

// Limites e passo "redondos" para um eixo que precisa conter todos os valores.
function eixoRedondo(valores, { divisoes = 5, incluir = [] } = {}) {
  const v = [...valores, ...incluir].filter(x => x != null && isFinite(x));
  const lo = Math.min(...v), hi = Math.max(...v);
  const passo = passoRedondo((hi - lo || Math.abs(hi) || 1) / divisoes);
  return { min: Math.floor(lo / passo) * passo, max: Math.ceil(hi / passo) * passo, passo };
}

function aplicarEixo(escala, eixo) {
  escala.min = eixo.min;
  escala.max = eixo.max;
  escala.ticks = { ...escala.ticks, stepSize: eixo.passo };
}

function abas(id, itens, ativo, aoMudar) {
  const el = $(id);
  const render = () => {
    el.innerHTML = itens.map(([valor, rotulo]) => `<button type="button" data-v="${valor}" aria-pressed="${ativo() === valor}">${rotulo}</button>`).join('');
  };
  render();
  el.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    aoMudar(b.dataset.v);
    render();
  });
}

const tabelasCsv = {};

function baixarCsv(nome) {
  const t = tabelasCsv[nome];
  if (!t) return;
  const celula = v => {
    if (v == null) return '';
    if (typeof v === 'number') return String(v).replace('.', ',');
    const txt = String(v);
    return /[;"\n]/.test(txt) ? `"${txt.replace(/"/g, '""')}"` : txt;
  };
  const csv = [t.cabecalho, ...t.linhas].map(l => l.map(celula).join(';')).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `litoral-${nome}-${D.cobertura.fim}.csv`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
}

const ultimaTemporada = () => D.kpis.temporada;
const efeitoMes = m => ({ pct: D.efeitos.pct[pos(m)], inf: D.efeitos.inf[pos(m)], sup: D.efeitos.sup[pos(m)], p: D.efeitos.p[pos(m)] });
const significativo = e => e.inf > 0 || e.sup < 0;

// ------------------------------------------------------------------- seções

function textos() {
  const c = D.cobertura;
  document.querySelectorAll('[data-inicio]').forEach(e => (e.textContent = mesExtenso(c.inicio)));
  document.querySelectorAll('[data-fim]').forEach(e => (e.textContent = mesExtenso(c.fim)));
  document.querySelectorAll('[data-n-litoral]').forEach(e => (e.textContent = num(c.municipios_litoral, 0)));
  document.querySelectorAll('[data-ano]').forEach(e => (e.textContent = D.gerado_em.slice(0, 4)));
  document.querySelectorAll('[data-gerado]').forEach(e => (e.textContent = D.gerado_em.split('-').reverse().join('/')));
}

function numeros() {
  const k = D.kpis;
  const itens = [
    [bilhoes(k.excesso).replace(' bilhões', ' bi').replace(' milhões', ' mi'), `a mais no caixa das empresas do litoral, fora as capitais, na temporada ${k.temporada}`],
    [pct(k.alta_temporada), `de alta média de dezembro a fevereiro em relação ao interior (intervalo de 95%: ${pct(k.alta_inf)} a ${pct(k.alta_sup)})`],
    [pct(k.alta_pico), `em ${MESES_LONGOS[MESES.indexOf(k.mes_pico)]}, o mês mais forte`],
    [pct(k.parcela, 0, false), 'de tudo que essas empresas receberam via Pix de dezembro a fevereiro é movimento extra da temporada'],
  ];
  $('numeros').innerHTML = itens.map(([v, r]) => `<div class="numero"><div class="valor">${v}</div><div class="rot">${r}</div></div>`).join('');
}

function perfil() {
  const c = cores();
  const lit = D.perfil.litoral, int = D.perfil.interior;
  const conj = (rot, p, cor) => ({
    label: rot, data: p.media.map(v => v * 100),
    inf: p.media.map((v, i) => (v - 1.96 * (p.ep[i] || 0)) * 100), sup: p.media.map((v, i) => (v + 1.96 * (p.ep[i] || 0)) * 100),
    borderColor: cor, backgroundColor: cor, corIntervalo: transparente(cor, 0.6), pointRadius: 3.5, pointHoverRadius: 5, borderWidth: 2.2, tension: 0.25,
  });
  const ds = [conj('Litoral', lit, c.mar), conj('Interior', int, c.interior)];
  const op = opcoes({ eixoY: v => num(v, 0), dica: v => num(v, 0) });
  aplicarEixo(op.scales.y, eixoRedondo(ds.flatMap(d => [...d.inf, ...d.sup]), { incluir: [100] }));
  op.scales.x.ticks.autoSkip = false;
  op.plugins.referencia = { valor: 100 };
  desenhar('perfil', 'chPerfil', { type: 'line', data: { labels: D.meses_ciclo, datasets: ds }, options: op, plugins: [pluginReferencia, pluginIntervalo] });

  const e = D.efeitos;
  const sig = e.pct.map((_, i) => e.inf[i] > 0 || e.sup[i] < 0);
  const op2 = opcoes({ legenda: false, eixoY: v => num(v, 0) + '%' });
  aplicarEixo(op2.scales.y, eixoRedondo([...e.inf, ...e.sup].map(v => v * 100), { incluir: [0] }));
  op2.scales.x.ticks.autoSkip = false;
  op2.plugins.referencia = { valor: 0 };
  op2.plugins.tooltip.callbacks.label = ctx => {
    const i = ctx.dataIndex;
    return `${pct(e.pct[i], 1)} (intervalo de ${pct(e.inf[i], 1)} a ${pct(e.sup[i], 1)})`;
  };
  desenhar('efeitos', 'chEfeitos', {
    type: 'bar',
    data: { labels: D.meses_ciclo, datasets: [{ label: 'Litoral sobre interior', data: e.pct.map(v => v * 100), inf: e.inf.map(v => v * 100), sup: e.sup.map(v => v * 100), backgroundColor: sig.map(s => (s ? c.mar : transparente(c.mar, 0.3))), borderRadius: 3, maxBarThickness: 34 }] },
    options: op2,
    plugins: [pluginReferencia, pluginIntervalo],
  });

  const pico = pos(1);
  const dez = efeitoMes(12), jan = efeitoMes(1), fev = efeitoMes(2), mar = efeitoMes(3), nov = efeitoMes(11);
  let txt = `Nas cidades de frente para o mar, o Pix recebido por empresas em janeiro fica em média ${pct(lit.media[pico] - 1)} acima de um mês comum. No interior, ${pct(int.media[pico] - 1)}. `
    + `Parte disso vale para o país todo, então a conta que importa é a do segundo gráfico: descontando o que é comum a todas as cidades em cada mês, o litoral fica ${pct(dez.pct)} acima do interior em dezembro, ${pct(jan.pct)} em janeiro e ${pct(fev.pct)} em fevereiro.`;
  if (significativo(nov) && nov.pct > 0) txt += ` O movimento já começa em novembro (${pct(nov.pct)}).`;
  if (significativo(mar) && mar.pct > 0) txt += ` Em março ainda sobra ${pct(mar.pct)}, em parte por causa dos anos em que o Carnaval caiu nesse mês.`;
  else txt += ' Em março tudo volta ao normal.';
  const base = [4, 5, 6, 7, 8, 9, 10].map(m => ({ m, ...efeitoMes(m) }));
  const fraco = base.reduce((a, b) => (b.pct < a.pct ? b : a));
  if (significativo(fraco) && fraco.pct < 0) txt += ` No sentido contrário, ${MESES_LONGOS[fraco.m - 1]} é o mês mais fraco do litoral (${pct(fraco.pct)}).`;
  $('txtQuando').textContent = txt;
}

function serie() {
  const c = cores();
  const s = D.serie;
  const faixas = [];
  s.meses.forEach((m, i) => {
    if (m.endsWith('-12')) faixas.push([i, Math.min(i + 2, s.meses.length - 1)]);
    else if (i === 0 && (m.endsWith('-01') || m.endsWith('-02'))) faixas.push([0, m.endsWith('-01') ? 1 : 0]);
  });
  const carnavais = s.carnaval.filter(m => s.meses.includes(m));
  const marcos = carnavais.map(m => s.meses.indexOf(m));
  const op = opcoes({ eixoY: v => num(v, 0), dica: v => num(v, 0) });
  op.plugins.temporadas = { faixas, marcos };
  op.plugins.referencia = { valor: 100 };
  op.plugins.legend.position = 'bottom';
  op.layout = { padding: { top: 26 } };
  op.scales.x.ticks.maxTicksLimit = estreito() ? 5 : 10;
  // Litoral dividido pelo interior: tira o que é comum (crescimento do Pix, dias do mês, Natal).
  const razao = s.litoral.map((v, i) => (v != null && s.interior[i] ? (v / s.interior[i]) * 100 : null));
  op.plugins.legend.display = false;
  op.plugins.tooltip.callbacks.label = ctx => `Litoral em relação ao interior: ${num(ctx.parsed.y, 0)}`;
  aplicarEixo(op.scales.y, eixoRedondo(razao, { incluir: [100], divisoes: 4 }));
  desenhar('serie', 'chSerie', {
    type: 'line',
    data: {
      labels: s.meses.map(mesCurto),
      datasets: [
        { label: 'Litoral em relação ao interior', data: razao, borderColor: c.mar, backgroundColor: c.mar, borderWidth: 2.2, pointRadius: 0, tension: 0.2, spanGaps: true },
      ],
    },
    options: op,
    plugins: [pluginReferencia, pluginTemporadas],
  });
  $('legendaSerie').innerHTML = '<li><i></i>Dezembro a fevereiro</li>'
    + carnavais.map((m, i) => `<li><b>${i + 1}</b>Carnaval de ${m.slice(0, 4)} (${MESES_LONGOS[+m.slice(5) - 1]})</li>`).join('');

  const t = D.por_temporada;
  const op2 = opcoes({ legenda: false, eixoY: v => num(v, 0) + '%' });
  aplicarEixo(op2.scales.y, eixoRedondo(t.flatMap(x => [x.pct_inf, x.pct_sup]).map(v => v * 100), { incluir: [0], divisoes: 4 }));
  op2.plugins.tooltip.callbacks.label = ctx => { const x = t[ctx.dataIndex]; return `${pct(x.pct, 1)} (intervalo de ${pct(x.pct_inf, 1)} a ${pct(x.pct_sup, 1)})`; };
  desenhar('temporadas', 'chTemporadas', {
    type: 'bar',
    data: { labels: t.map(x => x.temporada), datasets: [{ label: 'Alta', data: t.map(x => x.pct * 100), inf: t.map(x => x.pct_inf * 100), sup: t.map(x => x.pct_sup * 100), backgroundColor: c.mar, borderRadius: 3, maxBarThickness: 46 }] },
    options: op2,
    plugins: [pluginIntervalo],
  });

  const positivas = t.filter(x => x.pct_inf > 0).length;
  const maior = t.reduce((a, b) => (b.pct > a.pct ? b : a)), menor = t.reduce((a, b) => (b.pct < a.pct ? b : a));
  const voltaNormal = !(significativo(efeitoMes(4)) && efeitoMes(4).pct > 0.02);
  $('txtTodoAno').textContent = (positivas === t.length
    ? `Sim. Em todas as ${t.length} temporadas com dados completos o litoral sobe bem acima do interior entre dezembro e fevereiro${voltaNormal ? ' e volta ao nível normal depois' : ''}.`
    : `Na maior parte dos anos. Em ${positivas} das ${t.length} temporadas com dados completos a alta do litoral sobre o interior foi estatisticamente positiva.`)
    + ' O gráfico divide o índice do litoral pelo do interior, então o que aparece nele é só o que o litoral tem de diferente. As faixas em cor de areia marcam dezembro a fevereiro e os números indicam o mês do Carnaval, que muda de ano para ano e às vezes cai em março, fora da janela da temporada.';
  const primeiro = t[0], ultimo = t.at(-1);
  const sobrepoe = primeiro.pct_sup >= ultimo.pct_inf && ultimo.pct_sup >= primeiro.pct_inf;
  $('txtTemporadas').textContent = `Cada barra compara dezembro a fevereiro com abril a outubro do mesmo ano, no litoral contra o interior. A maior alta foi em ${maior.temporada} (${pct(maior.pct)}) e a menor em ${menor.temporada} (${pct(menor.pct)}). `
    + (sobrepoe
      ? `Os intervalos da primeira e da última temporada se sobrepõem, então não dá para dizer que o efeito mudou ao longo do tempo.`
      : `A diferença entre ${primeiro.temporada} e ${ultimo.temporada} é maior do que a incerteza das estimativas, então o efeito ${ultimo.pct > primeiro.pct ? 'cresceu' : 'diminuiu'} no período.`
        + (ultimo.pct > primeiro.pct && primeiro.temporada === '2021/22' ? ' Uma explicação provável é que, no primeiro verão, o Pix ainda era pouco usado por quem viaja, e a temporada coincidiu com a onda da variante ômicron.' : ''));
}

function quanto() {
  const c = cores();
  const ex = D.excesso;
  const op = opcoes({ legenda: false, eixoY: v => num(v, v < 10 ? 1 : 0), dica: v => `R$ ${num(v, 2)} bi` });
  op.plugins.tooltip.callbacks.label = ctx => { const x = ex[ctx.dataIndex]; return [`Valor a mais: ${bilhoes(x.excesso)}`, `Parcela do total: ${pct(x.parcela, 1, false)}`]; };
  aplicarEixo(op.scales.y, eixoRedondo(ex.map(x => x.excesso / 1e9), { incluir: [0], divisoes: 4 }));
  desenhar('excesso', 'chExcesso', {
    type: 'bar',
    data: { labels: ex.map(x => x.temporada), datasets: [{ label: 'Valor a mais', data: ex.map(x => x.excesso / 1e9), backgroundColor: ex.map((_, i) => (i === ex.length - 1 ? c.mar : transparente(c.mar, 0.55))), borderRadius: 3, maxBarThickness: 52 }] },
    options: op,
  });
  $('tblTemporadas').innerHTML = '<thead><tr><th>Temporada</th><th>Recebido no verão</th><th>Valor a mais</th><th>Parcela</th><th>Acima do interior</th></tr></thead><tbody>'
    + ex.map(x => `<tr><td>${x.temporada}</td><td>${compacto(x.movimento)}</td><td>${compacto(x.excesso)}</td><td>${pct(x.parcela, 1, false)}</td><td>${x.cidades_alta} de ${x.cidades}</td></tr>`).join('') + '</tbody>';
  tabelasCsv.temporadas = {
    cabecalho: ['temporada', 'recebido_dez_fev_reais', 'valor_a_mais_reais', 'parcela', 'cidades', 'cidades_acima_do_interior', 'alta_mediana'],
    linhas: ex.map(x => [x.temporada, x.movimento, x.excesso, x.parcela, x.cidades, x.cidades_alta, x.alta_mediana]),
  };
  const u = ex.at(-1);
  const p0 = ex[0];
  $('txtQuanto').textContent = `Na temporada ${u.temporada}, as empresas das ${num(u.cidades, 0)} cidades do litoral fora das capitais receberam ${bilhoes(u.movimento)} via Pix entre dezembro e fevereiro. Aplicando a alta típica de cada cidade, ${bilhoes(u.excesso)} desse total é movimento extra da temporada, ou ${pct(u.parcela, 1, false)}. `
    + `Na temporada ${p0.temporada} eram ${bilhoes(p0.excesso)}: o valor cresce junto com o uso do Pix, enquanto a parcela fica parecida. ${u.cidades_alta} das ${u.cidades} cidades ficaram acima do interior do próprio estado em ${u.temporada}.`;
}

const nomeCidade = c => `${c.nome} (${c.uf})`;
const METRICAS = {
  alta_tipica: { rotulo: 'Alta típica', cap: () => 'Alta de dezembro a fevereiro sobre o interior do estado, mediana das temporadas', valor: c => c.alta_tipica, fmt: v => pct(v), eixo: v => num(v * 100, 0) + '%' },
  alta: { rotulo: 'Última temporada', cap: () => `Alta de dezembro a fevereiro sobre o interior do estado, temporada ${ultimaTemporada()}`, valor: c => c.alta, fmt: v => pct(v), eixo: v => num(v * 100, 0) + '%' },
  excesso: { rotulo: 'Valor a mais', cap: () => `Movimento extra da temporada ${ultimaTemporada()}, fora as capitais`, semCapitais: true, valor: c => c.excesso, fmt: v => compacto(v), eixo: v => compacto(v) },
};

function ranking() {
  const c = cores();
  const m = METRICAS[estado.metricaRank];
  const lista = D.cidades.filter(x => x.ranking && (!estado.ufRank || x.uf === estado.ufRank) && m.valor(x) != null && !(m.semCapitais && x.capital))
    .sort((a, b) => m.valor(b) - m.valor(a)).slice(0, 20);
  $('capRank').textContent = `${m.cap()}. ${lista.length < 20 ? `${nCidades(lista.length)}.` : '20 maiores.'}`;
  const op = opcoes({ legenda: false, extra: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: true, axis: 'y' } } });
  op.scales.x = { ...op.scales.y, ticks: { ...op.scales.y.ticks, callback: m.eixo, maxTicksLimit: estreito() ? 4 : 7 } };
  op.scales.y = { grid: { display: false }, border: { color: c.linha }, ticks: { color: c.t2, autoSkip: false, font: { size: 12 } } };
  op.plugins.tooltip.callbacks.label = ctx => `${m.rotulo}: ${m.fmt(m.valor(lista[ctx.dataIndex]))}`;
  desenhar('rank', 'chRank', {
    type: 'bar',
    data: { labels: lista.map(x => (estreito() && x.nome.length > 16 ? x.nome.slice(0, 15) + '.' : x.nome) + (estado.ufRank ? '' : ` (${x.uf})`)), datasets: [{ data: lista.map(m.valor), backgroundColor: lista.map(x => (x.capital ? c.coral : c.mar)), borderRadius: 2, maxBarThickness: 18 }] },
    options: op,
  });
}

function textoCidades() {
  const validas = D.cidades.filter(x => x.ranking && x.alta_tipica != null);
  if (!validas.length) return;
  const top = validas[0];
  const mediana = arr => { const s = [...arr].sort((a, b) => a - b); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };
  const caps = validas.filter(x => x.capital).map(x => x.alta_tipica), outras = validas.filter(x => !x.capital).map(x => x.alta_tipica);
  const porExcesso = [...validas].filter(x => x.excesso != null && !x.capital).sort((a, b) => b.excesso - a.excesso)[0];
  let txt = `Numa temporada típica, ${nomeCidade(top)} é a cidade que mais se afasta do padrão do interior: recebe ${pct(top.alta_tipica)} a mais entre dezembro e fevereiro. `;
  if (caps.length && outras.length) {
    const mc = mediana(caps), mo = mediana(outras);
    txt += `As capitais (em coral no gráfico) têm alta mediana de ${pct(mc)}, contra ${pct(mo)} nas demais cidades${mc < mo - 0.03 ? ': numa cidade grande, o movimento dos visitantes pesa menos no total' : ''}. `;
  }
  if (porExcesso && porExcesso !== top) txt += `Em reais, fora as capitais, quem mais ganha é ${nomeCidade(porExcesso)}, com ${bilhoes(porExcesso.excesso)} a mais em ${ultimaTemporada()}.`;
  $('txtCidades').textContent = txt;
  $('notaCidades').textContent = `O ranking mostra só cidades com pelo menos ${D.parametros.min_empresas_ranking} empresas recebendo Pix num mês comum, porque em cidades muito pequenas uma única empresa muda o índice. A tabela tem todas. "Sem descontar o interior" é a alta bruta, sem comparar com nada. Algumas cidades ficam abaixo do interior no verão por motivos conhecidos: Barreirinhas e Santo Amaro do Maranhão, nos Lençóis Maranhenses, têm a temporada no meio do ano, quando as lagoas estão cheias; Cabedelo e São Francisco do Sul são cidades portuárias e Goiana tem um polo industrial, onde o Pix das empresas vem mais de negócios entre empresas.`;
}

function tabelaCidades() {
  const t = ultimaTemporada();
  const colunas = [
    { k: 'nome', t: 'Cidade', f: r => escapar(r.nome) + (r.capital ? ' <span class="fraco">capital</span>' : ''), txt: true },
    { k: 'uf', t: 'UF', f: r => r.uf, txt: true },
    { k: 'empresas', t: 'Empresas', f: r => num(r.empresas, 0), opc: true },
    { k: 'alta_tipica', t: 'Alta típica', f: r => `<span class="${r.alta_tipica > 0 ? 'positivo' : 'negativo'}">${pct(r.alta_tipica)}</span>` },
    { k: 'alta', t: `Alta ${t}`, f: r => pct(r.alta) },
    { k: 'bruto', t: 'Sem descontar o interior', f: r => pct(r.bruto), opc: true },
    { k: 'excesso', t: `Valor a mais ${t}`, f: r => (r.excesso == null ? '' : compacto(r.excesso)) },
  ];
  const termo = estado.busca.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const linhas = D.cidades.filter(r => !termo || r.nome.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().includes(termo) || r.uf.toLowerCase() === termo);
  const { chave, dir } = estado.ordem;
  linhas.sort((a, b) => {
    const va = a[chave], vb = b[chave];
    if (va == null) return 1;
    if (vb == null) return -1;
    return (typeof va === 'string' ? va.localeCompare(vb, 'pt-BR') : va - vb) * dir;
  });
  const cls = col => [col.txt ? 'txt' : '', col.opc ? 'opc' : ''].filter(Boolean).join(' ');
  const tbl = $('tblCidades');
  tbl.innerHTML = `<thead><tr>${colunas.map(col => `<th data-k="${col.k}" class="${cls(col)}"${col.k === chave ? ` aria-sort="${dir > 0 ? 'ascending' : 'descending'}"` : ''}>${col.t}</th>`).join('')}</tr></thead><tbody>`
    + (linhas.length ? linhas.map(r => `<tr>${colunas.map(col => `<td class="${cls(col)}">${col.f(r)}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${colunas.length}" class="fraco">Nenhuma cidade encontrada.</td></tr>`) + '</tbody>';
  tbl.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.k;
    estado.ordem = { chave: k, dir: estado.ordem.chave === k ? -estado.ordem.dir : (['nome', 'uf'].includes(k) ? 1 : -1) };
    tabelaCidades();
  }));
  const temporadas = D.ufs.temporadas;
  tabelasCsv.cidades = {
    cabecalho: ['codigo_ibge', 'cidade', 'uf', 'capital', 'empresas', 'alta_tipica', ...temporadas.map(x => `alta_${x.replace('/', '_')}`), `bruto_${t.replace('/', '_')}`, `valor_a_mais_${t.replace('/', '_')}`],
    linhas: D.cidades.map(r => [r.codigo, r.nome, r.uf, r.capital ? 'sim' : 'não', r.empresas, r.alta_tipica, ...temporadas.map(x => r.temporadas[x] ?? null), r.bruto, r.excesso]),
  };
}

function corCalor(v, max) {
  if (v == null) return null;
  const t = Math.max(-1, Math.min(1, v / max));
  const mistura = (a, b, f) => a.map((x, i) => Math.round(x + (b[i] - x) * f));
  const neutro = [244, 236, 220], mar = [11, 122, 133], meio = [159, 211, 214], coral = [233, 163, 130];
  const rgb = t >= 0 ? (t < 0.5 ? mistura(neutro, meio, t * 2) : mistura(meio, mar, (t - 0.5) * 2)) : mistura(neutro, coral, -t);
  const luz = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
  return { fundo: `rgb(${rgb.join(',')})`, texto: luz < 0.5 ? '#fff' : '#10202e' };
}

function estados() {
  const u = D.ufs;
  const linhas = u.linhas.map(l => ({ ...l, media: l.valores.filter(v => v != null).reduce((a, b, _, arr) => a + b / arr.length, 0) }))
    .sort((a, b) => b.media - a.media);
  const max = Math.max(...linhas.flatMap(l => l.valores.filter(v => v != null).map(Math.abs)), 0.01);
  $('heatUfs').innerHTML = `<thead><tr><th class="uf">UF</th>${u.temporadas.map(t => `<th>${t}</th>`).join('')}</tr></thead><tbody>`
    + linhas.map(l => `<tr><th class="uf">${l.uf}</th>${l.valores.map((v, i) => {
      const c = corCalor(v, max);
      return c ? `<td style="background:${c.fundo};color:${c.texto}" title="${l.uf}, ${u.temporadas[i]}: ${pct(v, 1)}">${pct(v)}</td>` : '<td class="vazio">sem dado</td>';
    }).join('')}</tr>`).join('') + '</tbody>';
  const temNegativo = linhas.some(l => l.valores.some(v => v != null && v < 0));
  $('escalaMin').textContent = temNegativo ? pct(-max) : '0%';
  $('escalaMax').textContent = pct(max);
  document.querySelector('.escala-cor i').style.background = temNegativo
    ? 'linear-gradient(90deg, rgb(233,163,130), rgb(244,236,220), rgb(159,211,214), rgb(11,122,133))'
    : 'linear-gradient(90deg, rgb(244,236,220), rgb(159,211,214), rgb(11,122,133))';
  if (linhas.length >= 2) {
    const a = linhas[0], z = linhas.at(-1);
    $('txtEstados').textContent = `Cada célula é a alta mediana das cidades do litoral do estado naquela temporada, sempre contra o interior do mesmo estado. ${a.uf} tem a maior média entre as temporadas (${pct(a.media)}) e ${z.uf} a menor (${pct(z.media)}). `
      + (() => {
        const media = ufs => { const v = linhas.filter(l => ufs.includes(l.uf)).map(l => l.media); return v.length ? v.reduce((x, y) => x + y, 0) / v.length : null; };
        const sul = media(['PR', 'SC', 'RS', 'SP']), ne = media(['MA', 'PI', 'CE', 'RN', 'PB', 'PE', 'AL', 'SE', 'BA']);
        return sul != null && ne != null && sul - ne > 0.05
          ? `Os estados do Sul e São Paulo ficam no topo (média de ${pct(sul)}) e os do Nordeste, mais embaixo (${pct(ne)}). Uma explicação provável é que no Nordeste o turismo de praia se espalha pelo ano inteiro, enquanto no Sul a praia se concentra no verão. `
          : '';
      })()
      + 'A variação de um ano para o outro é grande em estados com poucas cidades no litoral, como PI e AP, então vale olhar a linha inteira e não uma célula só.';
  }
}

function fora() {
  const c = cores();
  const r = D.perfil_pf.recebido_pj, p = D.perfil_pf.pago_pf;
  const op = opcoes({ eixoY: v => num(v, 0), dica: v => num(v, 0) });
  op.plugins.referencia = { valor: 100 };
  op.scales.x.ticks.autoSkip = false;
  aplicarEixo(op.scales.y, eixoRedondo([...r.media, ...p.media].map(v => v * 100), { incluir: [100] }));
  desenhar('fora', 'chFora', {
    type: 'line',
    data: {
      labels: D.meses_ciclo,
      datasets: [
        { label: 'Recebido por empresas', data: r.media.map(v => v * 100), borderColor: c.mar, backgroundColor: c.mar, borderWidth: 2.2, pointRadius: 3, tension: 0.25 },
        { label: 'Pago por moradores', data: p.media.map(v => v * 100), borderColor: c.coral, backgroundColor: c.coral, borderWidth: 2, pointRadius: 3, tension: 0.25, borderDash: [5, 4] },
      ],
    },
    options: op,
    plugins: [pluginReferencia],
  });
  const j = pos(1), rj = r.media[j] - 1, pj = p.media[j] - 1;
  const placebo = D.robustez.find(x => x.nome.startsWith('Pago por moradores'));
  const d = pos(12), rd = r.media[d] - 1, pd = p.media[d] - 1;
  let txt = `Em janeiro, o Pix recebido pelas empresas do litoral fica ${pct(rj)} acima de um mês comum. O Pix pago pelos moradores dessas mesmas cidades sobe ${pct(pj)}. `;
  if (rj - pj > 0.05) {
    txt += (Math.abs(rd - pd) < 0.03 ? `Em dezembro as duas linhas andam juntas (${pct(rd)} e ${pct(pd)}): é o Natal dos próprios moradores. Em janeiro elas se separam. ` : '')
      + 'A distância entre elas é o dinheiro de quem vem de fora: a conta do turista está registrada na cidade onde ele mora, então o pagamento dele aparece como recebido no litoral, mas não como pago por um morador.';
  } else {
    txt += 'As duas linhas andam juntas, então boa parte da alta pode vir dos próprios moradores e não só de visitantes.';
  }
  if (placebo) {
    txt += placebo.pct_inf < 0 && placebo.pct_sup > 0
      ? ` No modelo com efeitos fixos, o Pix pago por moradores do litoral não se afasta do interior no verão (intervalo de ${pct(placebo.pct_inf, 1)} a ${pct(placebo.pct_sup, 1)}).`
      : ` No modelo com efeitos fixos, o Pix pago por moradores do litoral fica ${pct(placebo.pct, 1)} acima do interior no verão, contra ${pct(D.kpis.alta_temporada, 1)} no recebido por empresas.`;
  }
  $('txtFora').textContent = txt;
}

function mercados() {
  const g = D.caged;
  if (!g) {
    $('blocoMercados').hidden = true;
    $('txtMercados').textContent = 'Os dados do CAGED ainda não foram incluídos nesta versão.';
    return;
  }
  const c = cores();
  const lit = g.perfil.litoral, int = g.perfil.interior;
  const conj = (rot, p, cor) => ({
    label: rot, data: p.media.map(v => v * 100),
    inf: p.media.map((v, i) => (v - 1.96 * (p.ep[i] || 0)) * 100), sup: p.media.map((v, i) => (v + 1.96 * (p.ep[i] || 0)) * 100),
    backgroundColor: cor, borderRadius: 2, maxBarThickness: 16,
  });
  const ds = [conj('Litoral', lit, c.mar), conj('Interior', int, c.interior)];
  const op = opcoes({ eixoY: v => num(v, 0), dica: v => num(v, 0) });
  op.plugins.legend.labels.pointStyle = 'rect';
  op.scales.x.ticks.autoSkip = false;
  op.plugins.referencia = { valor: 100 };
  aplicarEixo(op.scales.y, eixoRedondo(ds.flatMap(d => [...d.inf, ...d.sup]), { incluir: [100] }));
  op.scales.y.min = Math.min(op.scales.y.min, 60);
  desenhar('caged', 'chCaged', { type: 'bar', data: { labels: D.meses_ciclo, datasets: ds }, options: op, plugins: [pluginReferencia, pluginIntervalo] });

  const pts = g.pontos;
  const op2 = opcoes({ legenda: false, extra: { interaction: { mode: 'nearest', intersect: true } } });
  op2.scales.x = { ...op2.scales.y, title: { display: true, text: 'Alta do Pix no verão', color: c.t2 }, ticks: { ...op2.scales.y.ticks, callback: v => num(v, 0) + '%' } };
  op2.scales.y.ticks.callback = v => num(v, 0) + '%';
  op2.scales.y.title = { display: true, text: 'Alta das contratações', color: c.t2 };
  op2.plugins.tooltip.callbacks.label = ctx => { const x = pts[ctx.dataIndex]; return `${nomeCidade(x)}: Pix ${pct(x.pix)}, contratações ${pct(x.caged)}`; };
  desenhar('disp', 'chDispersao', {
    type: 'scatter',
    data: { datasets: [{ data: pts.map(x => ({ x: x.pix * 100, y: x.caged * 100 })), backgroundColor: transparente(c.mar, 0.55), borderColor: c.mar, pointRadius: 3.5, pointHoverRadius: 6 }] },
    options: op2,
  });

  const d = pos(12), ld = lit.media[d] - 1, id = int.media[d] - 1;
  const nov = pos(11), ln = lit.media[nov] - 1;
  const cor = g.correlacao;
  let txt = ld - id > 0.05
    ? `Sim. Em dezembro, as admissões em supermercados nas cidades do litoral ficam ${pct(ld)} acima de um mês comum, contra ${pct(id)} no interior. `
    : `Pouco. Em dezembro, as admissões em supermercados no litoral ficam ${pct(ld)} acima de um mês comum, perto do interior (${pct(id)}). `;
  if (ln > 0.05) txt += `As contratações começam antes do movimento: em novembro já estão ${pct(ln)} acima. `;
  if (cor.rho != null) {
    const forte = Math.abs(cor.rho) >= 0.5 ? 'forte' : Math.abs(cor.rho) >= 0.3 ? 'moderada' : 'fraca';
    txt += `Cidade a cidade, a relação entre a alta do Pix no verão e a alta das contratações de novembro a janeiro é ${forte} (correlação de Spearman de ${num(cor.rho, 2)}, ${num(cor.n, 0)} cidades com pelo menos ${D.parametros.min_admissoes_base} admissões por mês${cor.p_valor < 0.001 ? ', p < 0,001' : `, p = ${num(cor.p_valor, 3)}`}). `;
    if (cor.rho > 0.3) txt += 'Os dois dados vêm de fontes independentes e apontam para as mesmas cidades.';
  }
  $('txtMercados').textContent = txt;
}

// ---------------------------------------------------------------- simulador

const PERIODO_SIM = [11, 12, 1, 2, 3];

function simulador() {
  const lista = D.cidades.filter(x => x.perfil);
  const porNome = new Map(lista.map(x => [nomeCidade(x), x]));
  $('listaCidades').innerHTML = [...porNome.keys()].sort((a, b) => a.localeCompare(b, 'pt-BR')).map(n => `<option value="${escapar(n)}"></option>`).join('');
  const inicial = lista.find(x => x.ranking) || lista[0];
  $('simCidade').value = nomeCidade(inicial);
  const calcular = () => {
    const cidade = porNome.get($('simCidade').value);
    const valor = parseFloat($('simValor').value);
    if (!cidade) { $('notaSim').textContent = 'Escolha uma cidade da lista.'; return; }
    if (!(valor > 0)) { $('notaSim').textContent = 'Informe um faturamento maior que zero.'; return; }
    const interior = D.interior_uf[cidade.uf];
    $('tblSim').innerHTML = '<thead><tr><th>Mês</th><th>Seguindo a cidade</th><th>Só o efeito do verão</th><th>Interior do estado</th></tr></thead><tbody>'
      + PERIODO_SIM.map(m => {
        const pc = cidade.perfil[pos(m)], pi = interior ? interior[pos(m)] : null;
        return `<tr><td>${MESES_LONGOS[m - 1]}</td><td>${reais(valor * pc)}<span class="sub-info">${pct(pc - 1)}</span></td><td>${pi ? reais(valor * pc / pi) : ''}<span class="sub-info">${pi ? pct(pc / pi - 1) : ''}</span></td><td>${pi ? pct(pi - 1) : 'sem dado'}</td></tr>`;
      }).join('') + '</tbody>';
    const c = cores();
    const op = opcoes({ eixoY: v => num(v, 0), dica: v => num(v, 0) });
    op.plugins.referencia = { valor: 100 };
    op.scales.x.ticks.autoSkip = false;
    const ds = [{ label: cidade.nome, data: cidade.perfil.map(v => v * 100), borderColor: c.mar, backgroundColor: c.mar, borderWidth: 2.2, pointRadius: 2.5, tension: 0.25 }];
    if (interior) ds.push({ label: `Interior de ${cidade.uf}`, data: interior.map(v => v * 100), borderColor: c.interior, backgroundColor: c.interior, borderWidth: 1.8, pointRadius: 2, tension: 0.25 });
    aplicarEixo(op.scales.y, eixoRedondo(ds.flatMap(d => d.data), { incluir: [100], divisoes: 4 }));
    desenhar('sim', 'chSim', { type: 'line', data: { labels: D.meses_ciclo, datasets: ds }, options: op, plugins: [pluginReferencia] });
    $('capSim').textContent = `${nomeCidade(cidade)} e interior do estado (média de abril a outubro = 100)`;
    $('notaSim').textContent = `"Seguindo a cidade" aplica o padrão médio de ${cidade.nome} nos verões analisados. Inclui o crescimento do uso do Pix ao longo do ano e o Natal, então tende a exagerar um pouco. "Só o efeito do verão" divide pelo padrão do interior do estado e mostra o que a temporada acrescenta. É uma referência de ordem de grandeza: um negócio específico pode ter um padrão bem diferente da média da cidade.`;
  };
  $('simCidade').addEventListener('change', calcular);
  $('simCidade').addEventListener('input', () => { if (porNome.has($('simCidade').value)) calcular(); });
  $('simValor').addEventListener('input', calcular);
  calcular();
}

// ----------------------------------------------------------------- robustez

// Rótulos curtos para telas estreitas.
function nomeCurto(nome) {
  const curtos = [['Principal', 'Principal'], ['Comparando só', 'Interior do estado'], ['Sem as capitais', 'Sem capitais'], ['Só cidades', 'Cidades maiores'], ['Número de transações', 'Nº de transações'], ['Sem a temporada', nome.replace('Sem a temporada', 'Sem')], ['Pago por moradores', 'Pago por moradores']];
  const achado = curtos.find(([inicio]) => nome.startsWith(inicio));
  return achado ? achado[1] : nome;
}

function robustez() {
  const c = cores();
  const r = D.robustez;
  const ehPlacebo = x => x.nome.startsWith('Pago por moradores');
  const op = opcoes({ legenda: false, extra: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: false, axis: 'y' } } });
  const eixo = eixoRedondo(r.flatMap(x => [x.pct_inf, x.pct_sup]).map(v => v * 100), { incluir: [0] });
  op.scales.x = { ...op.scales.y, ticks: { ...op.scales.y.ticks, callback: v => num(v, 0) + '%', maxTicksLimit: estreito() ? 5 : 8 } };
  aplicarEixo(op.scales.x, eixo);
  op.scales.y = { grid: { display: false }, border: { color: c.linha }, ticks: { color: c.t2, autoSkip: false, font: { size: 12.5 } } };
  op.plugins.referencia = { valor: 0 };
  op.plugins.tooltip.callbacks.label = ctx => { const x = r[ctx.dataIndex]; return `${pct(x.pct, 1)} (intervalo de ${pct(x.pct_inf, 1)} a ${pct(x.pct_sup, 1)}), ${num(x.municipios, 0)} municípios`; };
  desenhar('rob', 'chRobustez', {
    type: 'bar',
    data: {
      labels: r.map(x => (estreito() ? nomeCurto(x.nome) : x.nome)),
      datasets: [{
        data: r.map(x => [x.pct_inf * 100, x.pct_sup * 100]),
        backgroundColor: r.map(x => transparente(ehPlacebo(x) ? c.coral : c.mar, 0.35)),
        barThickness: 4, borderRadius: 2,
        pontos: r.map(x => x.pct * 100), corPontos: r.map(x => (ehPlacebo(x) ? c.coral : c.mar)),
      }],
    },
    options: op,
    plugins: [pluginReferencia, pluginPontos],
  });
  const empresas = r.filter(x => !ehPlacebo(x));
  const placebo = r.find(ehPlacebo);
  const lo = Math.min(...empresas.map(x => x.pct)), hi = Math.max(...empresas.map(x => x.pct));
  let txt = `Repeti o modelo mudando uma escolha de cada vez. Em todas as versões com o Pix recebido por empresas, a alta média de dezembro a fevereiro ficou ${pct(lo, 1) === pct(hi, 1) ? `em ${pct(lo, 1)}` : `entre ${pct(lo, 1)} e ${pct(hi, 1)}`}. `
    + 'Comparar só com o interior do mesmo estado controla diferenças regionais de calendário e renda; tirar as capitais e as cidades pequenas mostra que o resultado não depende de poucos casos extremos; usar o número de transações em vez do valor descarta que seja efeito de preço.';
  if (placebo) {
    txt += placebo.pct_inf < 0 && placebo.pct_sup > 0
      ? ` A última linha é um teste de controle: o mesmo modelo aplicado ao Pix pago pelos moradores não mostra alta no verão (o intervalo vai de ${pct(placebo.pct_inf, 1)} a ${pct(placebo.pct_sup, 1)} e inclui zero).`
      : ` A última linha aplica o mesmo modelo ao Pix pago pelos moradores: ${pct(placebo.pct, 1)}, bem abaixo do recebido pelas empresas.`;
  }
  $('txtRobustez').textContent = txt;
}

// ------------------------------------------------------------------- método

function metodo() {
  const e = D.efeitos;
  const pv = v => (v < 0.001 ? '< 0,001' : num(v, 3));
  $('tblCoef').innerHTML = '<thead><tr><th>Mês</th><th>Coeficiente (log)</th><th>Erro padrão</th><th>p-valor</th><th>Em %</th></tr></thead><tbody>'
    + D.meses_ciclo.map((m, i) => `<tr><td>${MESES_LONGOS[MESES.indexOf(m)]}</td><td>${num(e.coef[i], 4)}</td><td>${num(e.ep[i], 4)}</td><td>${pv(e.p[i])}</td><td>${pct(e.pct[i], 1)}</td></tr>`).join('')
    + `<tr><td><b>Média dez a fev</b></td><td>${num(e.temporada.coef, 4)}</td><td>${num(e.temporada.ep, 4)}</td><td>${pv(e.temporada.p_valor)}</td><td>${pct(e.temporada.pct, 1)}</td></tr></tbody>`;
  $('notaCoef').textContent = `Cada coeficiente é a diferença entre o litoral e o interior naquele mês menos a média dessa diferença de abril a outubro. ${num(e.n_obs, 0)} observações (município x mês), ${num(e.n_municipios, 0)} municípios.`;
  const c = D.cobertura;
  $('excluidos').textContent = `${num(c.excluidos, 0)} municípios, ${c.excluidos_litoral ? `dos quais ${num(c.excluidos_litoral, 0)} no litoral` : 'nenhum no litoral'}`;
  $('txtCobertura').textContent = `O painel tem ${num(c.municipios, 0)} municípios (${num(c.municipios_litoral, 0)} no litoral) e ${c.meses} meses, de ${mesExtenso(c.inicio)} a ${mesExtenso(c.fim)}.`
    + (c.ipca_repetido.length ? ` O IPCA de ${c.ipca_repetido.map(mesCurto).join(', ')} ainda não tinha saído; repeti o último índice disponível.` : '')
    + (D.caged ? ` O CAGED vai até ${mesExtenso(D.caged.fim)}.` : '');
  $('avisos').innerHTML = D.avisos.map(a => `<li>${escapar(a)}</li>`).join('');
}

// ------------------------------------------------------------------- início

function observarTamanho() {
  let espera, largura = window.innerWidth;
  const ajustar = () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      const mudouFaixa = (largura < 560) !== estreito();
      largura = window.innerWidth;
      if (mudouFaixa) { ranking(); serie(); robustez(); }
      Object.values(graficos).forEach(g => g.resize());
    }, 120);
  };
  window.addEventListener('resize', ajustar);
  if ('ResizeObserver' in window) {
    const obs = new ResizeObserver(ajustar);
    document.querySelectorAll('.grafico').forEach(el => obs.observe(el));
  }
}

function menu() {
  const botao = $('menuBotao'), lista = $('menuLista');
  const abrir = aberto => { lista.hidden = !aberto; botao.setAttribute('aria-expanded', String(aberto)); };
  botao.addEventListener('click', e => { e.stopPropagation(); abrir(lista.hidden); });
  lista.addEventListener('click', e => { if (e.target.closest('a')) abrir(false); });
  document.addEventListener('click', e => { if (!lista.hidden && !e.target.closest('.menu')) abrir(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !lista.hidden) { abrir(false); botao.focus(); } });
}

async function iniciar() {
  menu();
  const resp = await fetch('data/litoral.json');
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  D = await resp.json();
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;

  document.querySelectorAll(D.caged ? '[data-sem-caged]' : '[data-caged]').forEach(el => (el.hidden = true));
  let n = 0;
  document.querySelectorAll('main > section').forEach(sec => { if (!sec.hidden) sec.classList.toggle('alt', n++ % 2 === 1); });
  textos();
  numeros();
  perfil();
  serie();
  quanto();

  const ufs = [...new Set(D.cidades.filter(x => x.ranking).map(x => x.uf))].sort();
  $('selUfRank').innerHTML = '<option value="">Todos</option>' + ufs.map(u => `<option>${u}</option>`).join('');
  $('selUfRank').addEventListener('change', e => { estado.ufRank = e.target.value; ranking(); });
  abas('abaRank', Object.entries(METRICAS).map(([k, m]) => [k, m.rotulo]), () => estado.metricaRank, v => { estado.metricaRank = v; ranking(); });
  ranking();
  textoCidades();
  tabelaCidades();
  $('buscaCidade').addEventListener('input', e => { estado.busca = e.target.value.trim(); tabelaCidades(); });

  estados();
  fora();
  mercados();
  simulador();
  robustez();
  metodo();
  document.querySelectorAll('[data-csv]').forEach(b => b.addEventListener('click', () => baixarCsv(b.dataset.csv)));
  observarTamanho();
}

iniciar().catch(err => {
  console.error(err);
  document.querySelector('main').insertAdjacentHTML('afterbegin', '<p class="wrap texto">Não foi possível carregar os dados. Se estiver rodando localmente, use um servidor (por exemplo, <code>python -m http.server</code>).</p>');
});
