
import cv2
import numpy as np
import mss
import pyautogui
import time

# CONFIGURACIÓN INICIAL
UMBRAL_CONFIANZA = 0.8  # 80% de similitud para evitar falsos positivos
COORDS_COMPRA = (1500, 400) # Reemplazá con tus coordenadas (X, Y)
COORDS_VENTA = (1500, 600)  # Reemplazá con tus coordenadas (X, Y)

# Cargamos las plantillas
temp_verde = cv2.imread('verde.png', 0)
temp_rojo = cv2.imread('rojo.png', 0)

def buscar_y_operar():
    with mss.mss() as sct:
        # Definí el área donde suelen aparecer las señales (Monitor 1)
        # Podés usar {"top": 0, "left": 0, "width": 1920, "height": 1080} para pantalla completa
        monitor = sct.monitors[1] 

        print("🤖 Bot en línea... Escaneando mercado.")

        while True:
            # 1. Capturar pantalla
            img = np.array(sct.grab(monitor))
            # Convertimos a escala de grises para que OpenCV trabaje más rápido
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 2. Buscar Triángulo Verde (Compra)
            res_v = cv2.matchTemplate(img_gray, temp_verde, cv2.TM_CCOEFF_NORMED)
            if np.any(res_v >= UMBRAL_CONFIANZA):
                print("🚀 SEÑAL VERDE DETECTADA - COMPRANDO...")
                pyautogui.click(COORDS_COMPRA)
                time.sleep(5) # Pausa para no cliquear mil veces la misma señal

            # 3. Buscar Triángulo Rojo (Venta)
            res_r = cv2.matchTemplate(img_gray, temp_rojo, cv2.TM_CCOEFF_NORMED)
            if np.any(res_r >= UMBRAL_CONFIANZA):
                print("📉 SEÑAL ROJA DETECTADA - VENDIENDO...")
                pyautogui.click(COORDS_VENTA)
                time.sleep(5)

            # Pequeño delay para no incinerar el procesador
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        buscar_y_operar()
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario.")