#!/usr/bin/env python3
"""
Lê as fichas ponto e envia os dados para o servidor.
Chamado automaticamente pelo ATUALIZAR.bat.
"""

import xlrd, json, os, re, sys
from datetime import datetime, date, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, 'config.txt')
FILES = [
    (os.path.join(BASE, 'FICHA PONTO - CITRO.xls'), 'CITRO'),
    (os.path.join(BASE, 'FICHA PONTO - FROTA.xls'), 'FROTA'),
]


# ─── Configuracao ─────────────────────────────────────────────────────────────

def ler_config():
    if not os.path.exists(CONFIG_FILE):
        print("ERRO: config.txt nao encontrado.")
        print("Crie o arquivo config.txt com SERVIDOR_URL e TOKEN.")
        sys.exit(1)
    cfg = {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                k, v = linha.split('=', 1)
                cfg[k.strip()] = v.strip()
    url = cfg.get('SERVIDOR_URL', '').rstrip('/')
    token = cfg.get('TOKEN', '')
    if not url or url.startswith('https://SEU'):
        print("ERRO: SERVIDOR_URL nao configurada no config.txt")
        print("Cole a URL do seu servidor Railway no config.txt")
        sys.exit(1)
    if not token or token == 'mude-isso':
        print("AVISO: TOKEN nao configurado. Usando token padrao.")
    return url, token


# ─── Parsing do Excel ─────────────────────────────────────────────────────────

def parse_time(s):
    s = s.strip()
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_date(s):
    m = re.match(r'^\s*(\d{2})/(\d{2})/(\d{2})', s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def read_file(path, frota):
    try:
        wb = xlrd.open_workbook(path, logfile=open(os.devnull, 'w'))
    except Exception:
        try:
            wb = xlrd.open_workbook(path)
        except Exception as e:
            print(f"  Erro ao ler {os.path.basename(path)}: {e}")
            return []
    ws = wb.sheet_by_index(0)
    empls = {}
    cur = None
    for r in range(ws.nrows):
        def cv(c, row=r):
            return str(ws.cell_value(row, c)).strip() if c < ws.ncols else ''
        c0, c1, c3, c5 = cv(0), cv(1), cv(3), cv(5)
        if c0 == 'Funcionário:':
            cur = cv(1)
            if cur and cur not in empls:
                empls[cur] = {'nome': cur, 'frota': frota, 'dias': []}
            continue
        if not cur:
            continue
        d = parse_date(c0)
        if d is None or not c1:
            continue
        empls[cur]['dias'].append({
            'd': d, 'tipo': c1,
            'ini': parse_time(c3),
            'fim': parse_time(c5),
        })
    return list(empls.values())


# ─── Calculo de status ────────────────────────────────────────────────────────

WORK_TIPOS = {'trabalho', 'feriado'}


def make_dt(d, hm):
    return datetime(d.year, d.month, d.day, hm[0], hm[1])


def calc_status(emp, now):
    dias = sorted(emp['dias'], key=lambda x: x['d'], reverse=True)
    if not dias:
        return {'st': 'SEM_DADOS'}
    tipo_rec = dias[0]['tipo'].lower().strip()
    if tipo_rec not in WORK_TIPOS:
        return {'st': 'AFASTADO', 'tipo': dias[0]['tipo']}
    last = next((x for x in dias if x['ini'] is not None), None)
    if last is None:
        return {'st': 'DISPONIVEL', 'tipo': dias[0]['tipo'],
                'data_ref': dias[0]['d'].strftime('%d/%m'), 'no_jornada': True}
    ini_dt = make_dt(last['d'], last['ini'])
    ini_min = last['ini'][0] * 60 + last['ini'][1]
    if last['fim'] is None:
        elapsed = max(0, int((now - ini_dt).total_seconds() / 60))
        rem = 12 * 60 - elapsed
        fim_est = ini_dt + timedelta(hours=12)
        return {
            'st': 'EM_JORNADA' if rem > 0 else 'EXCEDIDA',
            'ini_iso': ini_dt.isoformat(),
            'fim_est_iso': fim_est.isoformat(),
            'tipo': last['tipo'], 'data_ref': last['d'].strftime('%d/%m'),
        }
    fim_min = last['fim'][0] * 60 + last['fim'][1]
    fim_date = last['d'] + (timedelta(days=1) if fim_min < ini_min else timedelta(0))
    fim_dt = make_dt(fim_date, last['fim'])
    avail_dt = fim_dt + timedelta(hours=11)
    base = {
        'ini_iso': ini_dt.isoformat(), 'fim_iso': fim_dt.isoformat(),
        'avail_iso': avail_dt.isoformat(),
        'tipo': last['tipo'], 'data_ref': last['d'].strftime('%d/%m'),
    }
    base['st'] = 'DISPONIVEL' if now >= avail_dt else 'INTERSTICIO'
    if base['st'] == 'INTERSTICIO':
        base['falta_min'] = int((avail_dt - now).total_seconds() / 60)
    return base


# ─── Envio para o servidor ────────────────────────────────────────────────────

def enviar(url, token, records, nomes):
    payload = json.dumps({
        'token': token,
        'records': records,
        'nomes': nomes,
    }, ensure_ascii=False, default=str).encode('utf-8')

    req = Request(
        f"{url}/api/upload",
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=15) as resp:
            resposta = json.loads(resp.read().decode('utf-8'))
            return resposta.get('ok', False), resposta.get('condutores', 0)
    except HTTPError as e:
        if e.code == 401:
            print("ERRO: Token invalido. Verifique TOKEN no config.txt e UPLOAD_TOKEN no Railway.")
        else:
            print(f"ERRO HTTP {e.code}: {e.reason}")
        return False, 0
    except URLError as e:
        print(f"ERRO de conexao: {e.reason}")
        print("Verifique se SERVIDOR_URL esta correto no config.txt")
        return False, 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    print(f"\n=== Atualizar Disponibilidade de Condutores ===")
    print(f"Hora: {now.strftime('%d/%m/%Y %H:%M')}\n")

    url, token = ler_config()
    print(f"Servidor: {url}")

    employees = []
    for path, frota in FILES:
        if os.path.exists(path):
            print(f"Lendo {os.path.basename(path)}...", end=' ', flush=True)
            emps = read_file(path, frota)
            print(f"{len(emps)} condutores.")
            employees.extend(emps)
        else:
            print(f"Nao encontrado: {os.path.basename(path)}")

    if not employees:
        print("\nNenhum dado encontrado. Verifique os arquivos Excel.")
        try: input("Pressione Enter para sair...")
        except EOFError: pass
        return

    records = []
    for emp in employees:
        st = calc_status(emp, now)
        records.append({'nome': emp['nome'], 'frota': emp['frota'], **st})

    nomes = sorted({e['nome'] for e in employees})

    print(f"\nEnviando {len(records)} condutores ao servidor...")
    ok, total = enviar(url, token, records, nomes)

    if ok:
        print(f"Dados enviados com sucesso! ({total} condutores no servidor)")
        print(f"\nAcesse: {url}")
    else:
        print("Falha ao enviar. Verifique os erros acima.")

    try: input("\nPressione Enter para fechar...")
    except EOFError: pass


if __name__ == '__main__':
    main()
