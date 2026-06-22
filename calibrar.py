"""
calibrar.py — Descobrir coordenadas dos botões para a automação

COMO USAR:
  1. Execute este script: python calibrar.py
  2. Posicione o mouse sobre cada botão/campo indicado na automação
  3. Anote as coordenadas X e Y exibidas
  4. Pressione Ctrl+C para sair
"""
import pyautogui
import time

print("=" * 45)
print("  CALIBRADOR DE COORDENADAS")
print("=" * 45)
print()
print("  Mova o mouse sobre cada botão ou campo")
print("  e anote os valores X e Y mostrados abaixo.")
print()
print("  Pressione Ctrl+C para encerrar.")
print()

try:
    while True:
        x, y = pyautogui.position()
        print(f"\r  Posição do mouse: X = {x:4d}   Y = {y:4d}     ", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\nCalibração encerrada. Atualize o dicionário COORDS em automacao_atslog.py")
