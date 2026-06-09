#!/usr/bin/env python3
"""
Gerador de Dashboard de Disponibilidade de Condutores
Le as fichas ponto (.xls) e gera dashboard.html
"""

import xlrd
import json
import os
import re
import webbrowser
from datetime import datetime, date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
FILES = [
    (os.path.join(BASE, 'FICHA PONTO - CITRO.xls'), 'CITRO'),
    (os.path.join(BASE, 'FICHA PONTO - FROTA.xls'), 'FROTA'),
]
OUT = os.path.join(BASE, 'dashboard.html')


# ─── Parsing ─────────────────────────────────────────────────────────────────

def parse_time(s):
    """'HH:MM' -> (h, m) ou None"""
    s = s.strip()
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_date(s):
    """'  01/06/26 seg' -> date ou None"""
    m = re.match(r'^\s*(\d{2})/(\d{2})/(\d{2})', s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def read_file(path, frota):
    """Le um arquivo .xls e retorna lista de dicts de funcionarios."""
    try:
        wb = xlrd.open_workbook(path, logfile=open(os.devnull, 'w'))
    except Exception as e:
        print(f"  Aviso: nao foi possivel ler {os.path.basename(path)}: {e}")
        return []

    ws = wb.sheet_by_index(0)
    empls = {}
    cur = None

    for r in range(ws.nrows):
        def cv(c):
            return str(ws.cell_value(r, c)).strip() if c < ws.ncols else ''

        c0, c1, c3, c5 = cv(0), cv(1), cv(3), cv(5)

        # Inicio de bloco de funcionario
        if c0 == 'Funcionário:':
            cur = cv(1)
            if cur and cur not in empls:
                empls[cur] = {'nome': cur, 'frota': frota, 'dias': []}
            continue

        if not cur:
            continue

        d = parse_date(c0)
        if d is None:
            continue

        # Segundo bloco tem Tipo vazio → ignorar
        if not c1:
            continue

        empls[cur]['dias'].append({
            'd': d,
            'tipo': c1,
            'ini': parse_time(c3),
            'fim': parse_time(c5),
        })

    return list(empls.values())


# ─── Calculo de status ────────────────────────────────────────────────────────

def make_dt(d, hm):
    return datetime(d.year, d.month, d.day, hm[0], hm[1])


def fmt_hm(mins):
    """Minutos -> 'Xh YYmin'"""
    if mins is None:
        return '--'
    neg = mins < 0
    mins = abs(mins)
    h, m = divmod(mins, 60)
    s = f"{h}h{m:02d}" if h else f"{m}min"
    return f"-{s}" if neg else s


# Tipos que indicam trabalho ativo (tudo mais = afastamento)
WORK_TIPOS = {'trabalho', 'feriado'}


def calc_status(emp, now):
    """Calcula o status de disponibilidade do funcionario."""
    dias = sorted(emp['dias'], key=lambda x: x['d'], reverse=True)

    if not dias:
        return {'st': 'SEM_DADOS'}

    # Verifica o tipo mais recente: se nao for trabalho/feriado → afastado
    tipo_recente = dias[0]['tipo'].lower().strip()
    if tipo_recente not in WORK_TIPOS:
        return {'st': 'AFASTADO', 'tipo': dias[0]['tipo']}

    # Dia mais recente com Inicio preenchido
    last = next((x for x in dias if x['ini'] is not None), None)

    if last is None:
        # Tipo recente e Trabalho mas sem horario → retorno de afastamento / disponivel
        return {
            'st': 'DISPONIVEL',
            'tipo': dias[0]['tipo'],
            'data_ref': dias[0]['d'].strftime('%d/%m'),
            'no_jornada': True,
        }

    ini_dt = make_dt(last['d'], last['ini'])
    ini_min = last['ini'][0] * 60 + last['ini'][1]

    # Jornada em aberto (sem Fim)
    if last['fim'] is None:
        elapsed = max(0, int((now - ini_dt).total_seconds() / 60))
        rem = 12 * 60 - elapsed
        fim_est = ini_dt + timedelta(hours=12)
        return {
            'st': 'EM_JORNADA' if rem > 0 else 'EXCEDIDA',
            'ini_iso': ini_dt.isoformat(),
            'fim_est_iso': fim_est.isoformat(),
            'tipo': last['tipo'],
            'data_ref': last['d'].strftime('%d/%m'),
        }

    # Jornada encerrada
    fim_min = last['fim'][0] * 60 + last['fim'][1]
    fim_date = last['d'] + (timedelta(days=1) if fim_min < ini_min else timedelta(0))
    fim_dt = make_dt(fim_date, last['fim'])
    avail_dt = fim_dt + timedelta(hours=11)

    base = {
        'ini_iso': ini_dt.isoformat(),
        'fim_iso': fim_dt.isoformat(),
        'avail_iso': avail_dt.isoformat(),
        'tipo': last['tipo'],
        'data_ref': last['d'].strftime('%d/%m'),
    }

    if now >= avail_dt:
        base['st'] = 'DISPONIVEL'
    else:
        base['st'] = 'INTERSTICIO'
        base['falta_min'] = int((avail_dt - now).total_seconds() / 60)

    return base


# ─── Geracao do HTML ──────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Disponibilidade de Condutores</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f1f5f9; color: #1e293b; min-height: 100vh; }

  .header { background: #1e293b; color: #fff; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
  .header h1 { font-size: 1.2rem; font-weight: 700; letter-spacing: .3px; }
  .header .meta { font-size: .8rem; color: #94a3b8; }
  .header .meta strong { color: #e2e8f0; }

  .toolbar { background: #fff; border-bottom: 1px solid #e2e8f0; padding: 12px 24px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .search { flex: 1; min-width: 180px; max-width: 280px; padding: 7px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: .9rem; outline: none; }
  .search:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }
  .filters { display: flex; gap: 6px; flex-wrap: wrap; }
  .pill { padding: 5px 14px; border-radius: 999px; border: 1.5px solid #cbd5e1; background: #fff; font-size: .8rem; font-weight: 600; cursor: pointer; transition: all .15s; white-space: nowrap; }
  .pill:hover { background: #f8fafc; }
  .pill.active { border-color: transparent; color: #fff; }
  .pill[data-st="ALL"].active   { background: #1e293b; }
  .pill[data-st="EM_JORNADA"].active { background: #2563eb; }
  .pill[data-st="INTERSTICIO"].active { background: #d97706; }
  .pill[data-st="DISPONIVEL"].active { background: #16a34a; }
  .pill[data-st="EXCEDIDA"].active   { background: #dc2626; }
  .pill[data-st="AFASTADO"].active   { background: #6b7280; }
  .pill[data-fr="ALL"].active  { background: #4f46e5; }
  .pill[data-fr="CITRO"].active { background: #0891b2; }
  .pill[data-fr="FROTA"].active { background: #7c3aed; }
  .sep { width: 1px; height: 28px; background: #e2e8f0; }

  .summary { display: flex; gap: 10px; padding: 12px 24px; flex-wrap: wrap; }
  .badge-count { display: flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 8px; font-size: .8rem; font-weight: 700; }
  .bc-jornada { background: #dbeafe; color: #1d4ed8; }
  .bc-intersticio { background: #fef3c7; color: #b45309; }
  .bc-disponivel { background: #dcfce7; color: #15803d; }
  .bc-excedida { background: #fee2e2; color: #b91c1c; }
  .bc-afastado { background: #f1f5f9; color: #475569; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; padding: 16px 24px 32px; }

  .card { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 16px 18px; border-left: 5px solid #e2e8f0; transition: transform .1s, box-shadow .1s; }
  .card:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(0,0,0,.08); }
  .card.st-EM_JORNADA  { border-left-color: #2563eb; }
  .card.st-INTERSTICIO { border-left-color: #d97706; }
  .card.st-DISPONIVEL  { border-left-color: #16a34a; }
  .card.st-EXCEDIDA    { border-left-color: #dc2626; }
  .card.st-AFASTADO    { border-left-color: #9ca3af; }
  .card.st-SEM_DADOS   { border-left-color: #e2e8f0; opacity: .7; }

  .card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
  .card-nome { font-size: .88rem; font-weight: 700; line-height: 1.3; }
  .frota-tag { font-size: .7rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; }
  .fr-CITRO { background: #e0f2fe; color: #0369a1; }
  .fr-FROTA { background: #ede9fe; color: #6d28d9; }

  .status-badge { display: inline-flex; align-items: center; gap: 5px; font-size: .75rem; font-weight: 700; padding: 3px 10px; border-radius: 999px; margin-bottom: 8px; }
  .sb-EM_JORNADA  { background: #dbeafe; color: #1d4ed8; }
  .sb-INTERSTICIO { background: #fef3c7; color: #b45309; }
  .sb-DISPONIVEL  { background: #dcfce7; color: #15803d; }
  .sb-EXCEDIDA    { background: #fee2e2; color: #b91c1c; }
  .sb-AFASTADO    { background: #f1f5f9; color: #64748b; }
  .sb-SEM_DADOS   { background: #f8fafc; color: #94a3b8; }

  .card-info { font-size: .82rem; color: #475569; line-height: 1.8; }
  .card-info strong { color: #1e293b; }
  .highlight { font-size: .9rem; font-weight: 700; }
  .green  { color: #16a34a; }
  .blue   { color: #2563eb; }
  .amber  { color: #d97706; }
  .red    { color: #dc2626; }

  .empty { grid-column: 1/-1; text-align: center; padding: 40px; color: #94a3b8; font-size: .9rem; }

  @media (max-width: 600px) {
    .header { padding: 12px 16px; }
    .toolbar, .summary, .grid { padding-left: 12px; padding-right: 12px; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>Disponibilidade de Condutores</h1>
  <div class="meta">
    Atualizado em <strong id="upd-time">__NOW__</strong> &nbsp;|&nbsp;
    Hora atual: <strong id="live-time"></strong>
  </div>
</div>

<div class="toolbar">
  <input class="search" type="text" placeholder="Buscar condutor..." id="search" oninput="render()">
  <div class="sep"></div>
  <div class="filters" id="st-filters">
    <button class="pill active" data-st="ALL" onclick="setFilter('st','ALL')">Todos</button>
    <button class="pill" data-st="EM_JORNADA"  onclick="setFilter('st','EM_JORNADA')">Em Jornada</button>
    <button class="pill" data-st="INTERSTICIO" onclick="setFilter('st','INTERSTICIO')">Interstício</button>
    <button class="pill" data-st="DISPONIVEL"  onclick="setFilter('st','DISPONIVEL')">Disponível</button>
    <button class="pill" data-st="EXCEDIDA"    onclick="setFilter('st','EXCEDIDA')">Excedida</button>
    <button class="pill" data-st="AFASTADO"    onclick="setFilter('st','AFASTADO')">Afastado</button>
  </div>
  <div class="sep"></div>
  <div class="filters" id="fr-filters">
    <button class="pill active" data-fr="ALL"   onclick="setFilter('fr','ALL')">Todas frotas</button>
    <button class="pill" data-fr="CITRO" onclick="setFilter('fr','CITRO')">CITRO</button>
    <button class="pill" data-fr="FROTA" onclick="setFilter('fr','FROTA')">FROTA</button>
  </div>
</div>

<div class="summary" id="summary"></div>
<div class="grid" id="grid"></div>

<script>
const DATA = __DATA__;
const NOW_ISO = '__NOW_ISO__';

let stFilter = 'ALL', frFilter = 'ALL';

function setFilter(type, val) {
  if (type === 'st') {
    stFilter = val;
    document.querySelectorAll('#st-filters .pill').forEach(p => p.classList.toggle('active', p.dataset.st === val));
  } else {
    frFilter = val;
    document.querySelectorAll('#fr-filters .pill').forEach(p => p.classList.toggle('active', p.dataset.fr === val));
  }
  render();
}

function liveStatus(rec, now) {
  const st = rec.st;
  if (st === 'EM_JORNADA' || st === 'EXCEDIDA') {
    const ini = new Date(rec.ini_iso);
    const elapsedMin = Math.max(0, Math.floor((now - ini) / 60000));
    const remMin = 12 * 60 - elapsedMin;
    const fimEst = new Date(ini.getTime() + 12 * 3600000);
    return { st: remMin > 0 ? 'EM_JORNADA' : 'EXCEDIDA', ini, elapsedMin, remMin: Math.max(0, remMin), fimEst };
  }
  if (st === 'DISPONIVEL' || st === 'INTERSTICIO') {
    if (rec.no_jornada) return { st: 'DISPONIVEL', noJornada: true };
    const avail = new Date(rec.avail_iso);
    if (now >= avail) return { st: 'DISPONIVEL', avail, fim: new Date(rec.fim_iso) };
    const faltaMin = Math.floor((avail - now) / 60000);
    return { st: 'INTERSTICIO', avail, fim: new Date(rec.fim_iso), faltaMin };
  }
  return { st };
}

function fmtHM(mins) {
  const h = Math.floor(Math.abs(mins) / 60);
  const m = Math.abs(mins) % 60;
  const neg = mins < 0 ? '-' : '';
  return h > 0 ? `${neg}${h}h${String(m).padStart(2,'0')}` : `${neg}${m}min`;
}

function fmtTime(dt) {
  return dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function fmtDate(dt) {
  return dt.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function fmtDT(dt) {
  const today = new Date(); today.setHours(0,0,0,0);
  const d = new Date(dt); d.setHours(0,0,0,0);
  const diff = (d - today) / 86400000;
  const prefix = diff === 0 ? 'hoje' : diff === -1 ? 'ontem' : diff === 1 ? 'amanhã' : fmtDate(dt);
  return `${fmtTime(dt)} (${prefix})`;
}

const ST_LABEL = {
  EM_JORNADA: '▶ EM JORNADA',
  INTERSTICIO: '◷ INTERSTÍCIO',
  DISPONIVEL: '✓ DISPONÍVEL',
  EXCEDIDA: '⚠ EXCEDIDA',
  AFASTADO: '— AFASTADO',
  SEM_DADOS: '? SEM DADOS',
};

function cardHTML(rec, live) {
  const badge = `<span class="status-badge sb-${live.st}">${ST_LABEL[live.st] || live.st}</span>`;
  const frota = `<span class="frota-tag fr-${rec.frota}">${rec.frota}</span>`;
  let lines = '';

  if (live.st === 'EM_JORNADA') {
    lines = `
      <div>Início: <strong>${fmtDT(live.ini)}</strong></div>
      <div>Trabalhado: <strong class="blue">${fmtHM(live.elapsedMin)}</strong> &nbsp;|&nbsp; Restam: <strong class="blue highlight">${fmtHM(live.remMin)}</strong></div>
      <div>Fim limite: <strong>${fmtDT(live.fimEst)}</strong></div>`;
  } else if (live.st === 'EXCEDIDA') {
    lines = `
      <div>Início: <strong>${fmtDT(live.ini)}</strong></div>
      <div>Trabalhado: <strong class="red highlight">${fmtHM(live.elapsedMin)}</strong> &nbsp;|&nbsp; Excedeu: <strong class="red">${fmtHM(live.elapsedMin - 720)}</strong></div>`;
  } else if (live.st === 'INTERSTICIO') {
    lines = `
      <div>Fim da jornada: <strong>${fmtDT(live.fim)}</strong></div>
      <div>Disponível em: <strong class="amber highlight">${fmtDT(live.avail)}</strong></div>
      <div>Falta: <strong class="amber">${fmtHM(live.faltaMin)}</strong></div>`;
  } else if (live.st === 'DISPONIVEL') {
    if (live.noJornada) {
      lines = `<div class="green highlight">Disponível</div><div>Sem jornada registrada no período</div>`;
    } else {
      lines = `
        <div>Fim da jornada: <strong>${fmtDT(live.fim)}</strong></div>
        <div>Disponível desde: <strong class="green highlight">${fmtDT(live.avail)}</strong></div>`;
    }
  } else if (live.st === 'AFASTADO') {
    lines = `<div>Situação: <strong>${rec.tipo || '—'}</strong></div>`;
  } else {
    lines = `<div>Sem registros no período</div>`;
  }

  return `<div class="card st-${live.st}">
    <div class="card-top">
      <div class="card-nome">${rec.nome}</div>
      ${frota}
    </div>
    ${badge}
    <div class="card-info">${lines}</div>
  </div>`;
}

function render() {
  const now = new Date();
  const q = document.getElementById('search').value.toLowerCase();

  const counts = { EM_JORNADA: 0, INTERSTICIO: 0, DISPONIVEL: 0, EXCEDIDA: 0, AFASTADO: 0 };
  const cards = [];

  for (const rec of DATA) {
    const live = liveStatus(rec, now);
    if (counts[live.st] !== undefined) counts[live.st]++;

    const matchSt = stFilter === 'ALL' || live.st === stFilter;
    const matchFr = frFilter === 'ALL' || rec.frota === frFilter;
    const matchQ  = !q || rec.nome.toLowerCase().includes(q);

    if (matchSt && matchFr && matchQ) {
      cards.push({ rec, live });
    }
  }

  // Sort: EXCEDIDA > EM_JORNADA > INTERSTICIO > DISPONIVEL > AFASTADO > SEM_DADOS
  const ORDER = { EXCEDIDA: 0, EM_JORNADA: 1, INTERSTICIO: 2, DISPONIVEL: 3, AFASTADO: 4, SEM_DADOS: 5 };
  cards.sort((a, b) => (ORDER[a.live.st] ?? 9) - (ORDER[b.live.st] ?? 9) || a.rec.nome.localeCompare(b.rec.nome, 'pt-BR'));

  document.getElementById('grid').innerHTML = cards.length
    ? cards.map(c => cardHTML(c.rec, c.live)).join('')
    : '<div class="empty">Nenhum condutor encontrado com os filtros selecionados.</div>';

  document.getElementById('summary').innerHTML = `
    <span class="badge-count bc-jornada">▶ Em Jornada: ${counts.EM_JORNADA}</span>
    <span class="badge-count bc-intersticio">◷ Interstício: ${counts.INTERSTICIO}</span>
    <span class="badge-count bc-disponivel">✓ Disponível: ${counts.DISPONIVEL}</span>
    ${counts.EXCEDIDA ? `<span class="badge-count bc-excedida">⚠ Excedida: ${counts.EXCEDIDA}</span>` : ''}
    <span class="badge-count bc-afastado">— Afastado: ${counts.AFASTADO}</span>`;
}

function updateClock() {
  document.getElementById('live-time').textContent =
    new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

render();
updateClock();
setInterval(() => { render(); updateClock(); }, 60000);
</script>
</body>
</html>"""


def gen_html(employees, now):
    records = []
    for emp in employees:
        st = calc_status(emp, now)
        records.append({'nome': emp['nome'], 'frota': emp['frota'], **st})

    data_json = json.dumps(records, ensure_ascii=False, default=str)
    now_str = now.strftime('%d/%m/%Y %H:%M')
    now_iso = now.isoformat()

    html = HTML_TEMPLATE
    html = html.replace('__DATA__', data_json)
    html = html.replace('__NOW__', now_str)
    html = html.replace('__NOW_ISO__', now_iso)
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    print(f"\n=== Dashboard de Disponibilidade de Condutores ===")
    print(f"Hora atual: {now.strftime('%d/%m/%Y %H:%M')}\n")

    employees = []
    for path, frota in FILES:
        if os.path.exists(path):
            print(f"Lendo {os.path.basename(path)}...", end=' ', flush=True)
            emps = read_file(path, frota)
            print(f"{len(emps)} condutores encontrados.")
            employees.extend(emps)
        else:
            print(f"Arquivo nao encontrado: {os.path.basename(path)}")

    if not employees:
        print("\nNenhum dado encontrado. Verifique os arquivos Excel.")
        input("Pressione Enter para sair...")
        return

    print(f"\nTotal: {len(employees)} condutores")
    print(f"Gerando {os.path.basename(OUT)}...")

    html = gen_html(employees, now)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Abrindo no navegador...")
    webbrowser.open(f'file:///{OUT.replace(os.sep, "/")}')
    print("Pronto!")


if __name__ == '__main__':
    main()
