"""
automacao_atslog.py
Automação do ATSLog GuiaRH: cálculo de jornada + exportação das fichas ponto + atualização do dashboard.

INSTALAÇÃO (executar UMA VEZ no terminal):
  pip install pyautogui pygetwindow pillow

COMO USAR:
  1. Abra o ATSLog GuiaRH e deixe na tela principal (Monitor de Jornada de Trabalho)
  2. Execute: python automacao_atslog.py  (ou dê duplo clique em AUTOMATIZAR.bat)
  3. Pressione ENTER quando pedido
  4. NÃO mexa no mouse nem no teclado enquanto o script roda
  5. Para CANCELAR emergencialmente: mova o mouse para o canto SUPERIOR ESQUERDO

CALIBRAÇÃO DE COORDENADAS:
  Execute calibrar.py para descobrir as coordenadas corretas para o seu monitor.
  Depois atualize o dicionário COORDS abaixo com os valores encontrados.
  (Os valores padrão são estimativas e podem não funcionar direto)
"""

import pyautogui
import time
import datetime
import subprocess
import os
import sys

try:
    import pygetwindow as gw
    TEM_PYGETWINDOW = True
except ImportError:
    TEM_PYGETWINDOW = False

# Segurança: mover mouse para o canto (0, 0) cancela o script imediatamente
pyautogui.FAILSAFE = True

# Pausa entre cada ação — aumente para 1.5 ou 2.0 se o computador for lento
pyautogui.PAUSE = 1.0

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================

PASTA = r"C:\Users\rafael.rodrigues\Downloads\ANALISE DE DISPONIBILIDADE"
ATUALIZAR_BAT = os.path.join(PASTA, "scripts", "ATUALIZAR.bat")

# Quantos dias para trás a data inicial vai (normalmente 7)
DIAS_PERIODO = 7

# Tempo máximo de espera para cada processo (em segundos)
# Aumente se o cálculo costuma demorar mais no seu computador
TIMEOUT_CALCULO_SEG   = 15 * 60   # 15 minutos por sindicato
TIMEOUT_RELATORIO_SEG =  8 * 60   # 8 minutos por relatório
INTERVALO_MINUTOS     = 30        # minutos de espera entre ciclos

# =============================================================================
# COORDENADAS DOS ELEMENTOS — atualize com os valores do calibrar.py
# =============================================================================
# Formato: 'nome': (X, Y)   onde X e Y são os valores mostrados pelo calibrar.py

COORDS = {

    # ── Tela Principal (Monitor de Jornada de Trabalho) ──────────────────────
    'btn_calcular_jornada':    (391, 106),

    # ── Tela "Calcular Jornada Condutores" ────────────────────────────────────
    'campo_data_inicial':      (217, 275),
    'campo_data_final':        (217, 297),
    'lupa_sindicato_calc':     (718, 338),
    'btn_executar_calc':       (29,  106),

    # ── Popup "Sindicatos" ────────────────────────────────────────────────────
    'sindicato_adi':           (229, 295),
    'sindicato_novo_bh':       (179, 368),
    'btn_confirmar':           (36,  116),

    # ── Popup "Mensagens" (após cálculo terminar) ─────────────────────────────
    'btn_ok_mensagens':        (992, 577),

    # ── Menu horizontal superior ──────────────────────────────────────────────
    'aba_principal':           (93,   62),   # volta para Monitor de Jornada
    'aba_relatorios':          (166,  62),
    'btn_ficha_simplif':       (1236, 107),

    # ── Tela "Ficha Ponto Simplificada Novo Rumo" ─────────────────────────────
    'dropdown_periodo':        (394, 251),
    'opcao_ultimos_7_dias':    (196, 314),
    'lupa_sindicato_ficha':    (715, 271),
    'btn_executar_ficha':      (29,  106),

    # ── Visualização do relatório gerado ─────────────────────────────────────
    'aba_inicio_visualizacao': (85,   63),
    'btn_exportar':            (383, 109),
    'opcao_excel':             (405, 217),

    # ── Diálogo "Salvar como" do Windows ─────────────────────────────────────
    'campo_nome_salvar':       (703, 465),
    'btn_salvar':              (1000, 562),
}

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def log(msg):
    agora = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"[{agora}] {msg}", flush=True)


def clicar(nome):
    x, y = COORDS[nome]
    pyautogui.click(x, y)


def ativar_janela_atslog():
    """Tenta trazer a janela do ATSLog para o foco."""
    if not TEM_PYGETWINDOW:
        return
    titulos = ['ATSLog GuiaRH', 'Calcular Jornada', 'Ficha Ponto']
    for titulo in titulos:
        wins = gw.getWindowsWithTitle(titulo)
        if wins:
            try:
                wins[0].activate()
                time.sleep(0.8)
                return
            except Exception:
                pass


def aguardar_popup_mensagens(timeout_seg):
    """
    Aguarda o popup 'Mensagens' aparecer (indica que o cálculo terminou).
    Se não conseguir detectar, usa espera com contador como fallback.
    Retorna quando detectar o popup OU quando o timeout for atingido.
    """
    inicio = time.time()
    detectado = False

    if TEM_PYGETWINDOW:
        log(f"  Aguardando conclusão (máx {timeout_seg // 60} min)...")
        while time.time() - inicio < timeout_seg:
            titulos = [w.title for w in gw.getAllWindows() if w.title]
            if any('Mensagens' in t or 'mensagens' in t.lower() for t in titulos):
                detectado = True
                break
            decorrido = int(time.time() - inicio)
            if decorrido > 0 and decorrido % 60 == 0:
                log(f"  Ainda processando... {decorrido // 60}min decorridos")
            time.sleep(5)
    else:
        # Fallback: espera com contador regressivo
        for restante in range(timeout_seg, 0, -30):
            time.sleep(30)
            log(f"  Aguardando... ~{restante // 60}min restantes")

    if detectado:
        log("  Popup de conclusão detectado!")
    else:
        log("  Tempo esgotado ou popup não detectável — continuando...")
    time.sleep(2)


def aguardar_relatorio(timeout_seg):
    """
    Aguarda o popup de progresso fechar e a Visualização aparecer.
    O popup é filho da mesma janela (não cria janela nova), então detectamos
    pela mudança de cor do pixel na posição do botão Exportar:
    - Durante popup: ribbon mostra botões do formulário (Executar etc.) → cor A
    - Quando termina: ribbon muda para Visualização (Exportar etc.) → cor B
    """
    log(f"  Aguardando geração do relatório (máx {timeout_seg // 60} min)...")
    time.sleep(5)  # aguardar popup aparecer e ribbon estabilizar

    x_ref, y_ref = COORDS['btn_exportar']
    cor_popup = pyautogui.pixel(x_ref, y_ref)
    log(f"  Monitorando ribbon — pixel em ({x_ref},{y_ref}): {cor_popup}")

    inicio = time.time()
    while time.time() - inicio < timeout_seg:
        time.sleep(8)
        cor_agora = pyautogui.pixel(x_ref, y_ref)
        if cor_agora != cor_popup:
            log(f"  Ribbon mudou ({cor_popup} → {cor_agora}) — relatório pronto!")
            time.sleep(1.5)
            return
        decorrido = int(time.time() - inicio)
        if decorrido > 0 and decorrido % 60 == 0:
            log(f"  Aguardando... {decorrido // 60}min decorridos")

    log("  Timeout — prosseguindo de qualquer forma...")
    time.sleep(3)


def definir_data(nome_campo, data_str):
    """Clica no campo de data e digita a data no formato dd/mm/aaaa."""
    clicar(nome_campo)
    time.sleep(0.4)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    pyautogui.write(data_str, interval=0.08)
    time.sleep(0.3)
    pyautogui.press('tab')
    time.sleep(0.3)


def selecionar_sindicato(coord_lupa, coord_linha):
    """Abre o popup de sindicatos, clica na linha e confirma."""
    x_lupa, y_lupa = coord_lupa
    pyautogui.click(x_lupa, y_lupa)  # 1º clique — pode ser consumido pelo foco
    time.sleep(1.2)
    pyautogui.click(x_lupa, y_lupa)  # 2º clique — garante que o popup abre
    time.sleep(5.0)  # aguardar popup abrir completamente

    x_sind, y_sind = coord_linha
    pyautogui.click(x_sind, y_sind)
    time.sleep(0.8)

    clicar('btn_confirmar')
    time.sleep(2.5)  # aguardar popup fechar e form atualizar


def calcular_jornada_sindicato(nome_sind, coord_linha, timeout):
    """Seleciona sindicato e executa o cálculo de jornada."""
    log(f"  Sindicato: {nome_sind}")

    selecionar_sindicato(COORDS['lupa_sindicato_calc'], coord_linha)

    log("  Executando cálculo...")
    clicar('btn_executar_calc')
    time.sleep(1.2)
    clicar('btn_executar_calc')  # 2º clique garante que o botão registra
    time.sleep(4)  # aguardar janela de Progresso aparecer

    aguardar_popup_mensagens(timeout)

    log("  Clicando OK...")
    clicar('btn_ok_mensagens')
    time.sleep(2)


def selecionar_periodo_7_dias():
    """Abre o dropdown de Período e seleciona 'Últimos 7 dias'. Chamar só uma vez."""
    log("  Definindo período: Últimos 7 dias")
    clicar('dropdown_periodo')
    time.sleep(1.0)
    clicar('opcao_ultimos_7_dias')
    time.sleep(0.8)


def gerar_e_exportar_ficha(nome_sind, coord_linha, nome_arquivo, timeout):
    """Gera o relatório e exporta para Excel para um sindicato."""
    log(f"  Sindicato: {nome_sind}")

    selecionar_sindicato(COORDS['lupa_sindicato_ficha'], coord_linha)

    log("  Executando relatório...")
    clicar('btn_executar_ficha')
    time.sleep(1.2)
    clicar('btn_executar_ficha')  # 2º clique garante que o botão registra
    time.sleep(4)

    aguardar_relatorio(timeout)

    # Nesse ponto o relatório deve estar na tela de Visualização
    log(f"  Exportando → {nome_arquivo}.xls")
    clicar('btn_exportar')
    time.sleep(1.0)
    clicar('opcao_excel')
    time.sleep(2.5)

    # Diálogo "Salvar como"
    clicar('campo_nome_salvar')
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    pyautogui.write(nome_arquivo, interval=0.05)
    time.sleep(0.3)
    clicar('btn_salvar')
    time.sleep(4.0)
    log("  Arquivo salvo.")

    # Voltar ao formulário de seleção (aba Início)
    # O 1º clique pode ser "consumido" para dar foco à janela;
    # o 2º garante que a aba efetivamente muda.
    ativar_janela_atslog()
    time.sleep(1.0)
    clicar('aba_inicio_visualizacao')
    time.sleep(1.2)
    clicar('aba_inicio_visualizacao')
    time.sleep(4.5)  # aguardar ribbon trocar de Visualização → Início


# =============================================================================
# FLUXO PRINCIPAL
# =============================================================================

def executar_ciclo():
    """Executa um ciclo completo: cálculo → fichas → dashboard."""
    hoje = datetime.date.today()
    data_final   = hoje.strftime('%d/%m/%Y')
    data_inicial = (hoje - datetime.timedelta(days=DIAS_PERIODO)).strftime('%d/%m/%Y')

    log(f"Período: {data_inicial} → {data_final}")

    ativar_janela_atslog()
    time.sleep(1.5)

    # ── ETAPA 1 — Cálculo de jornada ─────────────────────────────────────────
    log("━" * 55)
    log("ETAPA 1/3 — Calculando jornada dos condutores")
    log("━" * 55)

    clicar('btn_calcular_jornada')
    time.sleep(1.2)
    clicar('btn_calcular_jornada')  # 2º clique garante abertura da tela
    time.sleep(2.5)

    log("Definindo datas...")
    definir_data('campo_data_inicial', data_inicial)
    definir_data('campo_data_final',   data_final)
    time.sleep(0.5)

    log("Calculando: ADI5322 - NOVORUMO LIMEIRA - ATUAL")
    calcular_jornada_sindicato(
        'ADI5322 - NOVORUMO LIMEIRA - ATUAL',
        COORDS['sindicato_adi'],
        TIMEOUT_CALCULO_SEG
    )

    log("Calculando: Sindicato Novo - Banco de Horas")
    calcular_jornada_sindicato(
        'Sindicato Novo - Banco de Horas',
        COORDS['sindicato_novo_bh'],
        TIMEOUT_CALCULO_SEG
    )

    log("Voltando ao menu principal (ESC)...")
    pyautogui.press('escape')
    time.sleep(2.5)

    # ── ETAPA 2 — Gerar e exportar fichas ponto ───────────────────────────────
    log("━" * 55)
    log("ETAPA 2/3 — Gerando e exportando fichas ponto")
    log("━" * 55)

    clicar('aba_relatorios')
    time.sleep(1.0)
    clicar('btn_ficha_simplif')
    time.sleep(4.5)  # aguardar janela abrir completamente

    selecionar_periodo_7_dias()

    log("Ficha 1/2 — ADI5322 (FROTA)")
    gerar_e_exportar_ficha(
        'ADI5322 - NOVORUMO LIMEIRA - ATUAL',
        COORDS['sindicato_adi'],
        'FICHA PONTO - FROTA',
        TIMEOUT_RELATORIO_SEG
    )

    log("Ficha 2/2 — Sindicato Novo (CITRO)")
    gerar_e_exportar_ficha(
        'Sindicato Novo - Banco de Horas',
        COORDS['sindicato_novo_bh'],
        'FICHA PONTO - CITRO',
        TIMEOUT_RELATORIO_SEG
    )

    # ── ETAPA 3 — Atualizar dashboard ─────────────────────────────────────────
    log("━" * 55)
    log("ETAPA 3/3 — Atualizando dashboard na nuvem")
    log("━" * 55)

    subprocess.run(f'"{ATUALIZAR_BAT}"', shell=True, stdin=subprocess.DEVNULL)

    # Voltar para tela principal (Monitor de Jornada) para o próximo ciclo
    pyautogui.press('escape')
    time.sleep(2.0)
    clicar('aba_principal')
    time.sleep(2.0)

    log("━" * 55)
    log("Ciclo concluído — dashboard atualizado!")
    log("━" * 55)


def main():
    tempo_ciclo_min = (TIMEOUT_CALCULO_SEG * 2 + TIMEOUT_RELATORIO_SEG * 2) // 60

    print()
    print("=" * 58)
    print("   AUTOMAÇÃO ATSLOG — FICHAS PONTO + DASHBOARD")
    print("=" * 58)
    print(f"   Tempo por ciclo: ~{tempo_ciclo_min} min")
    print(f"   Intervalo entre ciclos: {INTERVALO_MINUTOS} min")
    print()
    print("   PRÉ-REQUISITOS:")
    print("   • ATSLog GuiaRH aberto na tela principal")
    print("     (Monitor de Jornada de Trabalho)")
    print("   • Não feche nem minimize o ATSLog durante a automação")
    print()
    print("   PARA CANCELAR: mova o mouse para o CANTO SUPERIOR")
    print("   ESQUERDO da tela (posição 0, 0)")
    print()
    input("   Pressione ENTER para iniciar... ")
    print()

    log("Iniciando em 5 segundos — não mexa no mouse...")
    time.sleep(5)

    ciclo = 0
    while True:
        ciclo += 1
        log(f"╔══ CICLO {ciclo} {'═' * 44}")
        try:
            executar_ciclo()
        except pyautogui.FailSafeException:
            raise  # propaga para cancelar tudo
        except Exception as e:
            log(f"ERRO no ciclo {ciclo}: {e}")
            log("Aguardando próximo ciclo mesmo assim...")

        log(f"╚══ Próximo ciclo em {INTERVALO_MINUTOS} min...")
        for min_restante in range(INTERVALO_MINUTOS, 0, -1):
            time.sleep(60)
            if min_restante > 1:
                log(f"   Próximo ciclo em {min_restante - 1} min...")


if __name__ == '__main__':
    try:
        main()
    except pyautogui.FailSafeException:
        print()
        print("AUTOMAÇÃO CANCELADA — mouse foi para o canto superior esquerdo")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("AUTOMAÇÃO INTERROMPIDA pelo usuário (Ctrl+C)")
        sys.exit(1)
