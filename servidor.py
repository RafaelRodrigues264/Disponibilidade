#!/usr/bin/env python3
"""
Servidor de Disponibilidade de Condutores — Versao Nuvem
Deploy: Railway, Render, Fly.io, etc.
Localmente: python servidor.py
"""

import os, json
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

UPLOAD_TOKEN = os.environ.get('UPLOAD_TOKEN', 'token-padrao')
PORT = int(os.environ.get('PORT', 5000))

# Armazenamento em memoria (reseta ao reiniciar — aceitavel para este uso)
store = {
    'records': [],
    'nomes': [],
    'updated_at': None,
    'lancamentos': {},
}


# ─── Rotas ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return Response(DASHBOARD_HTML, mimetype='text/html; charset=utf-8')


@app.route('/api/dados')
def api_dados():
    return jsonify({
        'records':    store['records'],
        'nomes':      store['nomes'],
        'lancamentos': store['lancamentos'],
        'updated_at': store['updated_at'] or datetime.now(timezone.utc).isoformat(),
    })


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Recebe os dados processados do ATUALIZAR.bat."""
    data = request.get_json(silent=True) or {}
    if data.get('token') != UPLOAD_TOKEN:
        return jsonify({'erro': 'Token invalido'}), 401
    store['records']    = data.get('records', [])
    store['nomes']      = data.get('nomes', [])
    store['updated_at'] = datetime.now(timezone.utc).isoformat()
    n = len(store['records'])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Dados atualizados: {n} condutores")
    return jsonify({'ok': True, 'condutores': n})


@app.route('/api/lancamento', methods=['POST'])
def post_lancamento():
    data = request.get_json(silent=True) or {}
    if not all(k in data for k in ('nome', 'tipo', 'dt')):
        return jsonify({'erro': 'Dados incompletos'}), 400
    store['lancamentos'][data['nome']] = {
        'tipo': data['tipo'],
        'dt':   data['dt'],
        'criado_em': datetime.now(timezone.utc).isoformat(),
    }
    return jsonify({'ok': True})


@app.route('/api/lancamento/<path:nome>', methods=['DELETE'])
def del_lancamento(nome):
    store['lancamentos'].pop(nome, None)
    return jsonify({'ok': True})


# ─── Dashboard HTML ───────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Disponibilidade de Condutores</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f1f5f9; color: #1e293b; min-height: 100vh; }

  .header { background: #1e293b; color: #fff; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
  .header h1 { font-size: 1.1rem; font-weight: 700; }
  .meta { font-size: .78rem; color: #94a3b8; display: flex; align-items: center; gap: 10px; }
  .meta strong { color: #e2e8f0; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: #22c55e; flex-shrink: 0; }
  .dot.err { background: #ef4444; }
  .dot.warn { background: #f59e0b; }

  .toolbar { background: #fff; border-bottom: 1px solid #e2e8f0; padding: 10px 24px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .search { flex: 1; min-width: 160px; max-width: 260px; padding: 7px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: .88rem; outline: none; }
  .search:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }
  .filters { display: flex; gap: 5px; flex-wrap: wrap; }
  .pill { padding: 5px 13px; border-radius: 999px; border: 1.5px solid #cbd5e1; background: #fff; font-size: .78rem; font-weight: 600; cursor: pointer; transition: all .15s; white-space: nowrap; }
  .pill:hover { background: #f8fafc; }
  .pill.active { border-color: transparent; color: #fff; }
  .pill[data-st="ALL"].active    { background: #1e293b; }
  .pill[data-st="EM_JORNADA"].active  { background: #2563eb; }
  .pill[data-st="INTERSTICIO"].active { background: #d97706; }
  .pill[data-st="DISPONIVEL"].active  { background: #16a34a; }
  .pill[data-st="EXCEDIDA"].active    { background: #dc2626; }
  .pill[data-st="AFASTADO"].active    { background: #6b7280; }
  .pill[data-fr="ALL"].active   { background: #4f46e5; }
  .pill[data-fr="CITRO"].active { background: #0891b2; }
  .pill[data-fr="FROTA"].active { background: #7c3aed; }
  .sep { width: 1px; height: 26px; background: #e2e8f0; flex-shrink: 0; }
  .btn-lanc { margin-left: auto; padding: 7px 16px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: .82rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
  .btn-lanc:hover { background: #4338ca; }

  .summary { display: flex; gap: 8px; padding: 10px 24px; flex-wrap: wrap; }
  .bc { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 7px; font-size: .78rem; font-weight: 700; }
  .bc-jornada    { background: #dbeafe; color: #1d4ed8; }
  .bc-intersticio{ background: #fef3c7; color: #b45309; }
  .bc-disponivel { background: #dcfce7; color: #15803d; }
  .bc-excedida   { background: #fee2e2; color: #b91c1c; }
  .bc-afastado   { background: #f1f5f9; color: #475569; }

  .empty-data { text-align: center; padding: 60px 24px; color: #94a3b8; }
  .empty-data p { margin-top: 8px; font-size: .88rem; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; padding: 14px 24px 32px; }
  .empty { grid-column: 1/-1; text-align: center; padding: 40px; color: #94a3b8; font-size: .9rem; }

  .card { background: #fff; border-radius: 10px; border: 1px solid #e2e8f0; padding: 14px 16px; border-left: 5px solid #e2e8f0; transition: transform .1s, box-shadow .1s; }
  .card:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(0,0,0,.08); }
  .card.st-EM_JORNADA  { border-left-color: #2563eb; }
  .card.st-INTERSTICIO { border-left-color: #d97706; }
  .card.st-DISPONIVEL  { border-left-color: #16a34a; }
  .card.st-EXCEDIDA    { border-left-color: #dc2626; }
  .card.st-AFASTADO    { border-left-color: #9ca3af; }
  .card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .card-nome { font-size: .85rem; font-weight: 700; line-height: 1.3; }
  .frota-tag { font-size: .68rem; font-weight: 700; padding: 2px 7px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; }
  .fr-CITRO { background: #e0f2fe; color: #0369a1; }
  .fr-FROTA { background: #ede9fe; color: #6d28d9; }
  .card-badges { display: flex; align-items: center; gap: 5px; margin-bottom: 7px; flex-wrap: wrap; }
  .status-badge { display: inline-flex; align-items: center; font-size: .72rem; font-weight: 700; padding: 2px 9px; border-radius: 999px; }
  .sb-EM_JORNADA  { background: #dbeafe; color: #1d4ed8; }
  .sb-INTERSTICIO { background: #fef3c7; color: #b45309; }
  .sb-DISPONIVEL  { background: #dcfce7; color: #15803d; }
  .sb-EXCEDIDA    { background: #fee2e2; color: #b91c1c; }
  .sb-AFASTADO    { background: #f1f5f9; color: #64748b; }
  .sb-SEM_DADOS   { background: #f8fafc; color: #94a3b8; }
  .manual-tag { background: #fef9c3; color: #854d0e; font-size: .68rem; font-weight: 700; padding: 2px 7px; border-radius: 999px; border: 1px solid #fde047; }
  .card-info { font-size: .8rem; color: #475569; line-height: 1.85; }
  .card-info strong { color: #1e293b; }
  .hl { font-size: .88rem; font-weight: 700; }
  .green { color: #16a34a; } .blue { color: #2563eb; } .amber { color: #d97706; } .red { color: #dc2626; }

  /* Painel lateral */
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 199; display: none; }
  .overlay.open { display: block; }
  .panel { position: fixed; right: 0; top: 0; height: 100vh; width: 340px; background: #fff; box-shadow: -6px 0 24px rgba(0,0,0,.15); z-index: 200; display: flex; flex-direction: column; transform: translateX(100%); transition: transform .25s ease; }
  .panel.open { transform: translateX(0); }
  .panel-hd { padding: 16px 18px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; background: #1e293b; color: #fff; }
  .panel-hd h2 { font-size: .95rem; font-weight: 700; }
  .btn-x { background: none; border: none; color: #94a3b8; font-size: 1.3rem; cursor: pointer; }
  .btn-x:hover { color: #fff; }
  .panel-body { flex: 1; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 14px; }
  label { display: block; font-size: .8rem; font-weight: 600; color: #475569; margin-bottom: 5px; }
  .panel-body input, .panel-body select { width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 7px; font-size: .88rem; outline: none; }
  .panel-body input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }
  .tipo-row { display: flex; gap: 8px; }
  .tipo-btn { flex: 1; padding: 9px 6px; border: 2px solid #e2e8f0; border-radius: 8px; background: #fff; font-size: .8rem; font-weight: 600; cursor: pointer; text-align: center; transition: all .15s; }
  .tipo-btn.sel-inicio { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }
  .tipo-btn.sel-fim    { border-color: #d97706; background: #fffbeb; color: #b45309; }
  .btn-ok { width: 100%; padding: 10px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: .9rem; font-weight: 700; cursor: pointer; }
  .btn-ok:hover { background: #4338ca; }
  .btn-ok:disabled { background: #cbd5e1; cursor: default; }
  .msg { font-size: .8rem; padding: 8px 10px; border-radius: 7px; text-align: center; }
  .msg.ok  { background: #dcfce7; color: #15803d; }
  .msg.err { background: #fee2e2; color: #b91c1c; }
  .lanc-list h3 { font-size: .78rem; font-weight: 700; color: #64748b; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .5px; padding-top: 14px; border-top: 1px solid #e2e8f0; }
  .lanc-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; padding: 8px 10px; background: #f8fafc; border-radius: 7px; margin-bottom: 6px; border: 1px solid #e2e8f0; }
  .lanc-info { font-size: .78rem; line-height: 1.5; }
  .lanc-nome { font-weight: 700; }
  .lanc-det { color: #64748b; }
  .btn-del { background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 1.1rem; padding: 2px; flex-shrink: 0; }
  .btn-del:hover { color: #ef4444; }

  @media (max-width: 600px) {
    .header, .toolbar, .summary, .grid { padding-left: 12px; padding-right: 12px; }
    .panel { width: 100%; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>Disponibilidade de Condutores</h1>
  <div class="meta">
    <span class="dot" id="dot"></span>
    Atualizado: <strong id="upd-time">—</strong>
    &nbsp;|&nbsp; Agora: <strong id="live-time"></strong>
  </div>
</div>

<div class="toolbar">
  <input class="search" type="text" placeholder="Buscar condutor..." id="search" oninput="render()">
  <div class="sep"></div>
  <div class="filters" id="st-f">
    <button class="pill active" data-st="ALL"         onclick="setF('st','ALL')">Todos</button>
    <button class="pill" data-st="EM_JORNADA"  onclick="setF('st','EM_JORNADA')">Em Jornada</button>
    <button class="pill" data-st="INTERSTICIO" onclick="setF('st','INTERSTICIO')">Interstício</button>
    <button class="pill" data-st="DISPONIVEL"  onclick="setF('st','DISPONIVEL')">Disponível</button>
    <button class="pill" data-st="EXCEDIDA"    onclick="setF('st','EXCEDIDA')">Excedida</button>
    <button class="pill" data-st="AFASTADO"    onclick="setF('st','AFASTADO')">Afastado</button>
  </div>
  <div class="sep"></div>
  <div class="filters" id="fr-f">
    <button class="pill active" data-fr="ALL"   onclick="setF('fr','ALL')">Todas frotas</button>
    <button class="pill" data-fr="CITRO" onclick="setF('fr','CITRO')">CITRO</button>
    <button class="pill" data-fr="FROTA" onclick="setF('fr','FROTA')">FROTA</button>
  </div>
  <button class="btn-lanc" onclick="abrirPainel()">✎ Lançamento Manual</button>
</div>

<div class="summary" id="summary"></div>
<div id="main-content">
  <div class="empty-data" id="sem-dados" style="display:none">
    <strong>Aguardando dados...</strong>
    <p>Execute o ATUALIZAR.bat para enviar as fichas ponto ao servidor.</p>
  </div>
  <div class="grid" id="grid"></div>
</div>

<!-- Painel lateral -->
<div class="overlay" id="overlay" onclick="fecharPainel()"></div>
<div class="panel" id="panel">
  <div class="panel-hd">
    <h2>✎ Lançamento Manual</h2>
    <button class="btn-x" onclick="fecharPainel()">✕</button>
  </div>
  <div class="panel-body">
    <div>
      <label>Condutor</label>
      <input type="text" id="p-nome" placeholder="Digite o nome..." list="dl-nomes" autocomplete="off">
      <datalist id="dl-nomes"></datalist>
    </div>
    <div>
      <label>Tipo de lançamento</label>
      <div class="tipo-row">
        <button class="tipo-btn" id="btn-ini" onclick="setTipo('inicio')">▶ Início de Jornada</button>
        <button class="tipo-btn" id="btn-fim" onclick="setTipo('fim')">■ Fim de Jornada</button>
      </div>
    </div>
    <div>
      <label>Data</label>
      <input type="date" id="p-data">
    </div>
    <div>
      <label>Horário</label>
      <input type="time" id="p-hora">
    </div>
    <div id="p-msg"></div>
    <button class="btn-ok" id="btn-ok" onclick="lancar()">Confirmar Lançamento</button>
    <div class="lanc-list" id="lanc-list"></div>
  </div>
</div>

<script>
let DATA = [], NOMES = [], LANCAMENTOS = {};
let stF = 'ALL', frF = 'ALL', tipoSel = null;

// ── Override client-side ──────────────────────────────────────────────────────

function aplicarOverride(rec, lancs) {
  const lanc = lancs[rec.nome];
  if (!lanc) return rec;
  const lancDt = new Date(lanc.dt);
  let excelDt = null;
  if (rec.ini_iso) excelDt = new Date(rec.ini_iso);
  if (rec.fim_iso) {
    const f = new Date(rec.fim_iso);
    if (!excelDt || f > excelDt) excelDt = f;
  }
  if (excelDt && lancDt <= excelDt) return rec; // Excel e mais recente
  const r = { ...rec, manual: true, no_jornada: false };
  if (lanc.tipo === 'inicio') {
    r.st = 'EM_JORNADA';
    r.ini_iso = lanc.dt;
    r.fim_iso = null; r.avail_iso = null;
    r.fim_est_iso = new Date(lancDt.getTime() + 43200000).toISOString();
  } else {
    const avail = new Date(lancDt.getTime() + 39600000);
    r.fim_iso = lanc.dt;
    r.avail_iso = avail.toISOString();
    r.st = new Date() >= avail ? 'DISPONIVEL' : 'INTERSTICIO';
  }
  return r;
}

// ── Live status ───────────────────────────────────────────────────────────────

function liveStatus(rec, now) {
  const st = rec.st;
  if (st === 'EM_JORNADA' || st === 'EXCEDIDA') {
    if (!rec.ini_iso) return { st: 'SEM_DADOS' };
    const ini = new Date(rec.ini_iso);
    const el = Math.max(0, Math.floor((now - ini) / 60000));
    const rem = 12 * 60 - el;
    return { st: rem > 0 ? 'EM_JORNADA' : 'EXCEDIDA', ini, el, rem: Math.max(0, rem),
             fimEst: new Date(ini.getTime() + 43200000), manual: rec.manual };
  }
  if (st === 'DISPONIVEL' || st === 'INTERSTICIO') {
    if (rec.no_jornada || !rec.avail_iso)
      return { st: 'DISPONIVEL', noJornada: true, manual: rec.manual };
    const avail = new Date(rec.avail_iso);
    const fim = rec.fim_iso ? new Date(rec.fim_iso) : null;
    if (now >= avail) return { st: 'DISPONIVEL', avail, fim, manual: rec.manual };
    return { st: 'INTERSTICIO', avail, fim, falta: Math.floor((avail - now) / 60000), manual: rec.manual };
  }
  return { st, manual: rec.manual };
}

// ── Formatação ────────────────────────────────────────────────────────────────

function fmtHM(m) {
  const h = Math.floor(Math.abs(m) / 60), min = Math.abs(m) % 60;
  return (m < 0 ? '-' : '') + (h > 0 ? `${h}h${String(min).padStart(2,'0')}` : `${min}min`);
}
function fmtTime(dt) { return dt.toLocaleTimeString('pt-BR', { hour:'2-digit', minute:'2-digit' }); }
function fmtDate(dt) { return dt.toLocaleDateString('pt-BR', { day:'2-digit', month:'2-digit' }); }
function fmtDT(dt) {
  if (!dt) return '—';
  const today = new Date(); today.setHours(0,0,0,0);
  const d = new Date(dt); d.setHours(0,0,0,0);
  const diff = Math.round((d - today) / 86400000);
  const lbl = diff === 0 ? 'hoje' : diff === -1 ? 'ontem' : diff === 1 ? 'amanhã' : fmtDate(dt);
  return `${fmtTime(dt)} (${lbl})`;
}

// ── Card ──────────────────────────────────────────────────────────────────────

const ST_LABEL = {
  EM_JORNADA:'▶ EM JORNADA', INTERSTICIO:'◷ INTERSTÍCIO', DISPONIVEL:'✓ DISPONÍVEL',
  EXCEDIDA:'⚠ EXCEDIDA', AFASTADO:'— AFASTADO', SEM_DADOS:'? SEM DADOS',
};

function cardHTML(rec, live) {
  const badge = `<span class="status-badge sb-${live.st}">${ST_LABEL[live.st]||live.st}</span>`;
  const manTag = live.manual ? `<span class="manual-tag">✎ Manual</span>` : '';
  const frTag  = `<span class="frota-tag fr-${rec.frota}">${rec.frota}</span>`;
  let lines = '';
  if (live.st === 'EM_JORNADA') {
    lines = `<div>Início: <strong>${fmtDT(live.ini)}</strong></div>
             <div>Trabalhado: <strong class="blue">${fmtHM(live.el)}</strong> &nbsp;|&nbsp; Restam: <strong class="blue hl">${fmtHM(live.rem)}</strong></div>
             <div>Fim limite: <strong>${fmtDT(live.fimEst)}</strong></div>`;
  } else if (live.st === 'EXCEDIDA') {
    lines = `<div>Início: <strong>${fmtDT(live.ini)}</strong></div>
             <div>Trabalhado: <strong class="red hl">${fmtHM(live.el)}</strong> &nbsp;|&nbsp; Excedeu: <strong class="red">${fmtHM(live.el-720)}</strong></div>`;
  } else if (live.st === 'INTERSTICIO') {
    lines = `<div>Fim da jornada: <strong>${fmtDT(live.fim)}</strong></div>
             <div>Disponível em: <strong class="amber hl">${fmtDT(live.avail)}</strong></div>
             <div>Falta: <strong class="amber">${fmtHM(live.falta)}</strong></div>`;
  } else if (live.st === 'DISPONIVEL') {
    lines = live.noJornada
      ? `<div class="green hl">Disponível</div><div>Sem jornada registrada no período</div>`
      : `<div>Fim da jornada: <strong>${fmtDT(live.fim)}</strong></div>
         <div>Disponível desde: <strong class="green hl">${fmtDT(live.avail)}</strong></div>`;
  } else if (live.st === 'AFASTADO') {
    lines = `<div>Situação: <strong>${rec.tipo||'—'}</strong></div>`;
  } else {
    lines = `<div>Sem registros no período</div>`;
  }
  return `<div class="card st-${live.st}">
    <div class="card-top"><div class="card-nome">${rec.nome}</div>${frTag}</div>
    <div class="card-badges">${badge}${manTag}</div>
    <div class="card-info">${lines}</div>
  </div>`;
}

// ── Render ────────────────────────────────────────────────────────────────────

function setF(type, val) {
  if (type === 'st') { stF = val; document.querySelectorAll('#st-f .pill').forEach(p => p.classList.toggle('active', p.dataset.st === val)); }
  else               { frF = val; document.querySelectorAll('#fr-f .pill').forEach(p => p.classList.toggle('active', p.dataset.fr === val)); }
  render();
}

function render() {
  const now = new Date();
  const q = document.getElementById('search').value.toLowerCase();
  const counts = { EM_JORNADA:0, INTERSTICIO:0, DISPONIVEL:0, EXCEDIDA:0, AFASTADO:0 };
  const cards = [];
  for (const rec of DATA) {
    const live = liveStatus(rec, now);
    if (counts[live.st] !== undefined) counts[live.st]++;
    if ((stF==='ALL'||live.st===stF) && (frF==='ALL'||rec.frota===frF) && (!q||rec.nome.toLowerCase().includes(q)))
      cards.push({ rec, live });
  }
  const ORD = { EXCEDIDA:0, EM_JORNADA:1, INTERSTICIO:2, DISPONIVEL:3, AFASTADO:4, SEM_DADOS:5 };
  cards.sort((a,b) => (ORD[a.live.st]??9)-(ORD[b.live.st]??9) || a.rec.nome.localeCompare(b.rec.nome,'pt-BR'));

  const semDados = document.getElementById('sem-dados');
  const grid = document.getElementById('grid');
  if (!DATA.length) { semDados.style.display='block'; grid.innerHTML=''; }
  else {
    semDados.style.display='none';
    grid.innerHTML = cards.length ? cards.map(c=>cardHTML(c.rec,c.live)).join('') : '<div class="empty">Nenhum condutor encontrado.</div>';
  }

  document.getElementById('summary').innerHTML = DATA.length ? `
    <span class="bc bc-jornada">▶ Em Jornada: ${counts.EM_JORNADA}</span>
    <span class="bc bc-intersticio">◷ Interstício: ${counts.INTERSTICIO}</span>
    <span class="bc bc-disponivel">✓ Disponível: ${counts.DISPONIVEL}</span>
    ${counts.EXCEDIDA?`<span class="bc bc-excedida">⚠ Excedida: ${counts.EXCEDIDA}</span>`:''}
    <span class="bc bc-afastado">— Afastado: ${counts.AFASTADO}</span>` : '';
}

// ── Dados ─────────────────────────────────────────────────────────────────────

async function buscarDados() {
  try {
    const r = await fetch('/api/dados');
    if (!r.ok) throw new Error();
    const json = await r.json();
    LANCAMENTOS = json.lancamentos || {};
    DATA  = (json.records || []).map(rec => aplicarOverride(rec, LANCAMENTOS));
    NOMES = json.nomes || [];
    const upd = json.updated_at ? new Date(json.updated_at) : null;
    document.getElementById('upd-time').textContent = upd
      ? upd.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'})
      : '—';
    document.getElementById('dot').className = 'dot';
    renderPainel();
    render();
  } catch {
    document.getElementById('dot').className = 'dot err';
  }
}

// ── Painel ────────────────────────────────────────────────────────────────────

function abrirPainel() {
  document.getElementById('overlay').classList.add('open');
  document.getElementById('panel').classList.add('open');
  const now = new Date();
  document.getElementById('p-data').value = now.toISOString().slice(0,10);
  document.getElementById('p-hora').value = now.toTimeString().slice(0,5);
  document.getElementById('p-nome').value = '';
  document.getElementById('p-msg').innerHTML = '';
  setTipo(null);
}
function fecharPainel() {
  document.getElementById('overlay').classList.remove('open');
  document.getElementById('panel').classList.remove('open');
}
function setTipo(t) {
  tipoSel = t;
  document.getElementById('btn-ini').className = 'tipo-btn' + (t==='inicio'?' sel-inicio':'');
  document.getElementById('btn-fim').className = 'tipo-btn' + (t==='fim'?' sel-fim':'');
}

async function lancar() {
  const nome = document.getElementById('p-nome').value.trim();
  const data = document.getElementById('p-data').value;
  const hora = document.getElementById('p-hora').value;
  const msg  = document.getElementById('p-msg');
  if (!nome)    { msg.innerHTML='<div class="msg err">Informe o nome do condutor.</div>'; return; }
  if (!tipoSel) { msg.innerHTML='<div class="msg err">Selecione Início ou Fim.</div>'; return; }
  if (!data||!hora) { msg.innerHTML='<div class="msg err">Informe data e horário.</div>'; return; }
  document.getElementById('btn-ok').disabled = true;
  try {
    const r = await fetch('/api/lancamento', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ nome, tipo: tipoSel, dt: `${data}T${hora}:00` })
    });
    if (!r.ok) throw new Error();
    msg.innerHTML = '<div class="msg ok">Lançado com sucesso!</div>';
    await buscarDados();
  } catch {
    msg.innerHTML = '<div class="msg err">Erro ao lançar. Tente novamente.</div>';
  } finally {
    document.getElementById('btn-ok').disabled = false;
  }
}

async function remover(nome) {
  if (!confirm(`Remover lançamento de ${nome}?`)) return;
  await fetch('/api/lancamento/'+encodeURIComponent(nome), {method:'DELETE'});
  await buscarDados();
}

function renderPainel() {
  document.getElementById('dl-nomes').innerHTML = NOMES.map(n=>`<option value="${n}">`).join('');
  const keys = Object.keys(LANCAMENTOS);
  const el = document.getElementById('lanc-list');
  if (!keys.length) { el.innerHTML=''; return; }
  el.innerHTML = `<h3>Lançamentos ativos (${keys.length})</h3>` + keys.map(nome => {
    const l = LANCAMENTOS[nome];
    const dt = new Date(l.dt);
    const tipo = l.tipo==='inicio'?'▶ Início':'■ Fim';
    const dtStr = fmtDate(dt)+' '+fmtTime(dt);
    return `<div class="lanc-item">
      <div class="lanc-info"><div class="lanc-nome">${nome}</div><div class="lanc-det">${tipo} — ${dtStr}</div></div>
      <button class="btn-del" onclick="remover(${JSON.stringify(nome)})">✕</button>
    </div>`;
  }).join('');
}

// ── Init ──────────────────────────────────────────────────────────────────────

function tick() {
  document.getElementById('live-time').textContent =
    new Date().toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});
  render();
}

buscarDados();
tick();
setInterval(buscarDados, 30000);
setInterval(tick, 60000);
</script>
</body>
</html>"""


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n  Servidor rodando em http://localhost:{PORT}")
    print(f"  Acesso externo (mesma rede): use o IP desta maquina")
    print(f"  Pressione Ctrl+C para encerrar.\n")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
