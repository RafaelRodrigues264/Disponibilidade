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
TIMEOUT_CALCULO_SEG  = 15 * 60   # 15 minutos por sindicato
TIMEOUT_RELATORIO_SEG = 8 * 60   # 8 minutos por relatório

# =============================================================================
# COORDENADAS DOS ELEMENTOS — atualize com os valores do calibrar.py
# =============================================================================
# Formato: 'nome': (X, Y)   onde X e Y são os valores mostrados pelo calibrar.py

COORDS = {

    # ── Tela Principal (Monitor de Jornada de Trabalho) ──────────────────────
    # Botão "Calcular Jornada Condutores" na ribbon
    'btn_calcular_jornada':   (390, 120),

    # ── Tela "Calcular Jornada Condutores" ────────────────────────────────────
    # Campo Data Inicial (clique no campo com a data, não na seta)
    'campo_data_inicial':     (235, 274),
    # Campo Data Final
    'campo_data_final':       (235, 296),
    # Ícone de lupa ao lado do campo Sindicato
    'lupa_sindicato_calc':    (645, 341),
    # Botão "Executar" na ribbon (canto superior esquerdo)
    'btn_executar_calc':      (35, 120),

    # ── Popup "Sindicatos" ────────────────────────────────────────────────────
    # Linha "ADI5322 - NOVORUMO LIMEIRA - ATUAL" na lista
    'sindicato_adi':          (683, 314),
    # Linha "Sindicato Novo - Banco de Horas" na lista
    'sindicato_novo_bh':      (683, 367),
    # Botão "Confirmar" na ribbon do popup
    'btn_confirmar':          (36, 120),

    # ── Popup "Mensagens" (aparece após o cálculo terminar) ───────────────────
    # Botão "Ok" na parte inferior do popup
    'btn_ok_mensagens':       (997, 579),

    # ── Menu horizontal superior (abas Principal / Relatórios / Consultas...) ─
    # Aba "Relatórios"
    'aba_relatorios':         (170, 67),
    # Botão "Ficha Ponto Simplificada Novo Rumo" na ribbon de Relatórios
    'btn_ficha_simplif':      (1240, 120),

    # ── Tela "Ficha Ponto Simplificada Novo Rumo" ─────────────────────────────
    # Ícone de lupa ao lado do campo Sindicato NESSA tela
    'lupa_sindicato_ficha':   (645, 274),
    # Botão "Executar" na ribbon NESSA tela
    'btn_executar_ficha':     (35, 120),

    # ── Visualização do relatório gerado ─────────────────────────────────────
    # Aba "Início" na ribbon da visualização (volta ao formulário de seleção)
    'aba_inicio_visualizacao': (80, 67),
    # Botão "Exportar" na ribbon da visualização
    'btn_exportar':           (385, 120),
    # Opção "Excel" (primeira opção) no dropdown do Exportar
    'opcao_excel':            (400, 150),

    # ── Diálogo padrão "Salvar como" do Windows ──────────────────────────────
    # Campo de nome do arquivo (parte inferior do diálogo)
    'campo_nome_salvar':      (540, 580),
    # Botão "Salvar"
    'btn_salvar':             (760, 607),
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
    """Aguarda a geração do relatório (não tem popup OK, abre direto)."""
    log(f"  Aguardando geração do relatório (máx {timeout_seg // 60} min)...")
    # Espera fixa com contador — o relatório abre automaticamente quando pronto
    for restante in range(timeout_seg, 0, -30):
        time.sleep(30)
        if restante > 30:
            log(f"  Ainda processando... ~{restante // 60}min restantes")
    log("  Relatório deve estar pronto. Continuando...")
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
    pyautogui.click(x_lupa, y_lupa)
    time.sleep(2.0)  # aguardar popup abrir

    x_sind, y_sind = coord_linha
    pyautogui.click(x_sind, y_sind)
    time.sleep(0.5)

    clicar('btn_confirmar')
    time.sleep(1.5)


def calcular_jornada_sindicato(nome_sind, coord_linha, timeout):
    """Seleciona sindicato e executa o cálculo de jornada."""
    log(f"  Sindicato: {nome_sind}")

    selecionar_sindicato(COORDS['lupa_sindicato_calc'], coord_linha)

    log("  Executando cálculo...")
    clicar('btn_executar_calc')
    time.sleep(4)  # aguardar janela de Progresso aparecer

    aguardar_popup_mensagens(timeout)

    log("  Clicando OK...")
    clicar('btn_ok_mensagens')
    time.sleep(2)


def gerar_e_exportar_ficha(nome_sind, coord_linha, nome_arquivo, timeout):
    """Gera o relatório e exporta para Excel para um sindicato."""
    log(f"  Sindicato: {nome_sind}")

    selecionar_sindicato(COORDS['lupa_sindicato_ficha'], coord_linha)

    log("  Executando relatório...")
    clicar('btn_executar_ficha')
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
    time.sleep(2.5)
    log("  Arquivo salvo.")

    # Voltar ao formulário de seleção
    clicar('aba_inicio_visualizacao')
    time.sleep(2)


# =============================================================================
# FLUXO PRINCIPAL
# =============================================================================

def main():
    hoje = datetime.date.today()
    data_final   = hoje.strftime('%d/%m/%Y')
    data_inicial = (hoje - datetime.timedelta(days=DIAS_PERIODO)).strftime('%d/%m/%Y')

    tempo_total_min = (TIMEOUT_CALCULO_SEG * 2 + TIMEOUT_RELATORIO_SEG * 2) // 60

    print()
    print("=" * 58)
    print("   AUTOMAÇÃO ATSLOG — FICHAS PONTO + DASHBOARD")
    print("=" * 58)
    print(f"   Período: {data_inicial}  a  {data_final}")
    print(f"   Tempo estimado: ~{tempo_total_min} minutos")
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

    ativar_janela_atslog()
    time.sleep(1)

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 1 — Cálculo de jornada (2 sindicatos)
    # ──────────────────────────────────────────────────────────────────────────
    log("━" * 55)
    log("ETAPA 1/3 — Calculando jornada dos condutores")
    log("━" * 55)

    clicar('btn_calcular_jornada')
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

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 2 — Gerar e exportar fichas ponto (2 sindicatos)
    # ──────────────────────────────────────────────────────────────────────────
    log("━" * 55)
    log("ETAPA 2/3 — Gerando e exportando fichas ponto")
    log("━" * 55)

    clicar('aba_relatorios')
    time.sleep(1.0)
    clicar('btn_ficha_simplif')
    time.sleep(2.5)

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

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 3 — Atualizar dashboard
    # ──────────────────────────────────────────────────────────────────────────
    log("━" * 55)
    log("ETAPA 3/3 — Atualizando dashboard na nuvem")
    log("━" * 55)

    subprocess.run(ATUALIZAR_BAT, shell=True)

    print()
    print("=" * 58)
    print("   AUTOMAÇÃO CONCLUÍDA!")
    print("   Dashboard atualizado com sucesso.")
    print("=" * 58)
    print()


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
