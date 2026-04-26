# =============================================================================
# ROARBOT - Versión Refactorizada
# Autor: Tu nombre
# Descripción: Bot de trading con visión computacional, OCR y click automático
# =============================================================================

# --- IMPORTS ---
# Cada import trae una "caja de herramientas" externa al proyecto.
# Python no incluye todo por defecto — solo cargamos lo que necesitamos.

import cv2          # OpenCV: librería de visión computacional. Sirve para capturar
                    # imágenes, buscar patrones dentro de ellas y dibujar cosas.

import numpy as np  # NumPy: maneja arrays y matrices numéricas de forma muy eficiente.
                    # Las imágenes en memoria son básicamente matrices de números (píxeles),
                    # por eso OpenCV y NumPy trabajan juntos constantemente.

import mss          # MSS: captura la pantalla de forma muy rápida.
                    # Es más eficiente que otras alternativas como PIL/Pillow para capturas
                    # en tiempo real dentro de un loop.

import pydirectinput  # Simula input a nivel de DirectX (útil para juegos/apps que ignoran
                      # los clicks normales de Windows).

import time         # Módulo de tiempo: usamos time.sleep() para pausar la ejecución
                    # y time.time() para medir cuánto tardó algo.

import pytesseract  # Interfaz Python para Tesseract OCR.
                    # OCR = Optical Character Recognition: convierte imágenes de texto
                    # en texto real que podemos leer y procesar.

import tkinter as tk  # tkinter: librería de interfaces gráficas incluida con Python.
                      # La usamos para el HUD overlay que se muestra encima del juego.

import threading    # Permite ejecutar código en paralelo (en distintos "hilos").
                    # Sin esto, la interfaz gráfica y la lógica del bot se bloquearían
                    # mutuamente: uno esperaría al otro y nada funcionaría.

import ctypes       # Acceso directo a funciones del sistema operativo Windows.
                    # Lo usamos para mover el mouse y hacer clicks a nivel hardware,
                    # que es más confiable que las librerías de alto nivel.

import warnings     # Permite filtrar o silenciar mensajes de advertencia de Python.

import logging      # Sistema de logs profesional. Mucho mejor que usar print() porque:
                    # - Podés filtrar por nivel (DEBUG, INFO, WARNING, ERROR)
                    # - Podés redirigir los logs a un archivo fácilmente
                    # - Incluye timestamp automáticamente

import win32gui     # Acceso a la API de ventanas de Windows.
                    # Nos permite buscar ventanas por nombre, obtener su posición
                    # y dimensiones, y traerlas al frente automáticamente.
                    # Instalación: pip install pywin32

import win32process # Complemento de win32gui: nos permite obtener el PID y nombre
                    # del proceso asociado a una ventana. Así buscamos Exnova
                    # por nombre de .EXE y no por título de ventana (que puede cambiar).

import win32con     # Constantes de la API de Windows. Las usamos para traer
                    # la ventana de Exnova al frente (SW_RESTORE, SW_SHOW).

import psutil       # Librería para inspeccionar procesos del sistema.
                    # Nos permite buscar el PID de Exnova por nombre de .EXE.
                    # Instalación: pip install psutil

# =============================================================================
# CONFIGURACIÓN DEL SISTEMA DE LOGS
# =============================================================================

# Silenciamos los DeprecationWarnings que ensucian la consola sin aportar info útil
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configuramos el logger global del bot.
# basicConfig define el formato y el nivel mínimo de mensajes que se van a mostrar.
# %(asctime)s   → timestamp del mensaje (ej: 2025-04-23 10:30:00)
# %(levelname)s → nivel del mensaje (INFO, WARNING, ERROR, etc.)
# %(message)s   → el texto que nosotros escribimos
logging.basicConfig(
    level=logging.DEBUG,                              # Mostramos TODOS los niveles (DEBUG en adelante)
    format="%(asctime)s [%(levelname)s] %(message)s", # Formato del mensaje en consola
    datefmt="%H:%M:%S"                                # Solo mostramos hora:min:seg (más limpio)
)

# Silenciamos los loggers internos de librerías externas que spamean la consola.
# Tesseract/pytesseract genera decenas de líneas DEBUG por frame — inútil para nosotros.
# Con esto solo vemos los logs de NUESTRO código (logger "RoarBot").
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("pytesseract").setLevel(logging.WARNING)

# Creamos un logger específico para este módulo.
# Es buena práctica tener un logger por archivo/módulo.
logger = logging.getLogger("RoarBot")

# =============================================================================
# CONFIGURACIÓN GENERAL DEL BOT
# =============================================================================

# Umbral de confianza para el template matching.
# OpenCV devuelve un valor entre 0.0 y 1.0 al buscar una imagen dentro de otra.
# 0.8 significa "solo disparamos si la similitud es del 80% o más".
# Más alto = menos falsos positivos, pero puede perderse señales reales.
# Más bajo = más sensible, pero puede confundirse con imágenes parecidas.
UMBRAL_CONFIANZA = 0.8

# Coordenadas de los botones de compra y venta en la pantalla.
# Son tuplas (x, y) que indican dónde hacer click.
# IMPORTANTE: Si cambiás la resolución o movés la ventana, estos valores cambian.
COORDS_COMPRA = (1855, 400)
COORDS_VENTA  = (1855, 517)

# --- VENTANA DE TIEMPO PARA DISPARAR ---
# El bot opera SOLO cuando el reloj está entre estos valores (en segundos).
# Usamos un rango (33 a 30) en lugar de un valor exacto porque el OCR
# puede fallar 1 segundo ocasionalmente. Con el rango, si falla el 33
# pero lee el 32 o el 31, el bot igual opera. Más robusto.
SEGUNDO_TRIGGER_MIN = 30   # Mínimo: si el reloj muestra menos de 30s, ya es tarde
SEGUNDO_TRIGGER_MAX = 33   # Máximo: si el reloj muestra más de 33s, todavía es pronto

# --- ÁREA DEL RELOJ ---
# Rectángulo que recorta SOLO la zona del reloj en pantalla.
# Capturar solo esta región (no toda la pantalla) hace el OCR más rápido y preciso
# porque tiene menos "ruido visual" alrededor.
# top/left: coordenada de la esquina superior izquierda del recorte
# width/height: tamaño del recorte en píxeles
AREA_RELOJ = {
    "top":    115,
    "left":   1403,
    "width":  70,
    "height": 35
}

# --- ZONA VÁLIDA RELATIVA AL RELOJ ---
#
# ¿Por qué relativa y no fija?
# Cuando hacés zoom in/out en el gráfico, las velas y los triángulos
# se mueven horizontalmente. El reloj NO se mueve (es parte de la UI fija).
# Si usáramos coordenadas absolutas, con zoom in el triángulo quedaría
# fuera de la zona y el bot lo ignoraría aunque sea la última vela.
#
# La solución: definimos la zona como "a N píxeles a la izquierda del reloj".
# El reloj siempre está en el mismo x → la zona es siempre correcta.
#
# CENTRO_RELOJ_X: punto central horizontal del reloj. Es nuestra referencia fija.
# Se calcula desde AREA_RELOJ para que si ajustás el reloj, esto se actualice solo.
CENTRO_RELOJ_X = AREA_RELOJ["left"] + (AREA_RELOJ["width"] // 2)  # 1403 + 35 = 1438px

# TOLERANCIA_ZONA_PX: cuántos píxeles a la IZQUIERDA del centro del reloj
# aceptamos como "última vela válida".
#
# Con zoom intermedio las velas miden ~30-50px de ancho.
# El triángulo puede aparecer hasta ~100px antes del centro del reloj.
# Usamos 120px para tener margen cómodo.
#
# Ancho de la zona válida en píxeles a la izquierda del centro del reloj.
# Solo se detectan señales dentro de esta franja — todo lo demás se ignora.
#
# CALIBRACIÓN:
#   Bot ignora señales válidas      → aumentar este número
#   Bot detecta señales de velas viejas → reducirlo
TOLERANCIA_ZONA_PX = 350

# --- MULTI-SCALE MATCHING ---
# El zoom de Exnova hace que los triángulos cambien de tamaño en pantalla.
# Si el template mide 30x30px y el triángulo real mide 22x22px,
# matchTemplate no los considera iguales y la confianza cae a casi 0.
#
# Solución: buscamos el template a varios tamaños (escalas).
# Por cada escala redimensionamos el template y corremos matchTemplate.
# Nos quedamos con la escala que dio mayor confianza dentro de la zona.
#
# SCALE_MIN / SCALE_MAX: rango de escalas a probar.
#   0.7 = template al 70% de su tamaño original (triángulo pequeño en zoom out)
#   1.3 = template al 130% de su tamaño original (triángulo grande en zoom in)
#
# SCALE_STEPS: cuántas escalas intermedias probar.
#   10 pasos entre 0.7 y 1.3 = cada 6% de diferencia de tamaño.
#   Más pasos = más preciso pero más lento. 10 es el balance correcto.
SCALE_MIN   = 0.7
SCALE_MAX   = 1.3
# 6 pasos = escalas: 0.70, 0.82, 0.94, 1.06, 1.18, 1.30
# Menos pasos = matching más rápido. 6 cubre bien el rango de zoom de Exnova.
# Si necesitás más precisión subí a 8. Nunca más de 12 o el loop se atrasa.
SCALE_STEPS = 6

# Límites finales calculados automáticamente.
# X_MIN = 1438 - 120 = 1318  (hasta acá a la izquierda aceptamos el triángulo)
# X_MAX = 1438 + 35  = 1473  (hasta acá a la derecha, cubre el ancho del reloj)
ZONA_VELA_ACTUAL_X_MIN = CENTRO_RELOJ_X - TOLERANCIA_ZONA_PX
ZONA_VELA_ACTUAL_X_MAX = CENTRO_RELOJ_X + (AREA_RELOJ["width"] // 2)

# Ruta al ejecutable de Tesseract en Windows.
# Tesseract es el motor OCR que pytesseract usa internamente.
# pytesseract es solo un "wrapper" (envoltorio) de Python para llamarlo.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Tiempo de bloqueo después de una operación (en segundos).
# Evita que el bot dispare múltiples veces sobre la misma señal.
# 60s = una vela completa de margen antes de volver a escanear.
TIEMPO_BLOQUEO = 60

# --- NOMBRE DEL PROCESO DE EXNOVA ---
# Nombre exacto del .EXE tal como aparece en el Administrador de Tareas.
# El bot busca este proceso al iniciar para encontrar su ventana.
# Si no lo encontrás, abrí el Administrador de Tareas → pestaña Procesos
# → click derecho sobre Exnova → "Ir a detalles" → copiá el nombre exacto.
EXNOVA_PROCESO = "Exnova.exe"  # ← ajustá si el nombre es distinto

# =============================================================================
# CARGA Y VALIDACIÓN DE ASSETS (imágenes de señales)
# =============================================================================

def cargar_template(ruta: str) -> np.ndarray:
    """
    Carga una imagen EN COLOR (BGR) para usarla como template.

    ¿Por qué en color y no en grises?
    → Los triángulos verde y rojo en escala de grises se ven IGUAL:
      ambos son simplemente triángulos grises. OpenCV no puede distinguirlos.
    → En color, el verde tiene valores BGR completamente distintos al rojo.
      Esa diferencia es lo que permite al bot saber cuál es cuál.

    ¿No es más lento el matching en color?
    → Sí, un poco. Pero la precisión que ganamos vale completamente la pena.
      En la práctica la diferencia de velocidad es imperceptible en 1920x1080.
    """
    img = cv2.imread(ruta, cv2.IMREAD_COLOR)  # IMREAD_COLOR = carga en BGR (3 canales)
    
    if img is None:
        # FileNotFoundError es una excepción específica y descriptiva.
        # Mucho mejor que dejar que el programa crashee con un error críptico de OpenCV.
        raise FileNotFoundError(
            f"No se pudo cargar la imagen: '{ruta}'\n"
            f"Verificá que el archivo existe y está en la misma carpeta que main.py"
        )
    
    logger.info(f"Template cargado: {ruta} ({img.shape[1]}x{img.shape[0]} px)")
    return img

# Cargamos los templates al inicio. Si alguno falla, el programa para con un mensaje claro.
TEMPLATE_VERDE = cargar_template('verde.png')
TEMPLATE_ROJO  = cargar_template('rojo.png')

# =============================================================================
# ESTADO COMPARTIDO ENTRE HILOS (Thread-Safe)
# =============================================================================

# ¿Por qué necesitamos esto?
# El bot tiene DOS hilos corriendo al mismo tiempo:
#   Hilo 1: La interfaz gráfica (tkinter/HUD)
#   Hilo 2: La lógica de visión y clicks
#
# Si los dos hilos leen y escriben las mismas variables al mismo tiempo,
# puede pasar que uno sobreescriba al otro a mitad de una operación.
# Esto se llama "race condition" y produce bugs imposibles de reproducir.
#
# threading.Lock() es un "candado":
# Solo UN hilo puede estar dentro del bloque "with lock:" a la vez.
# El otro espera hasta que el primero termine. Así no se pisan.

_lock = threading.Lock()

# --- BUFFER DE DEBUG VISUAL ---
# El hilo de detección escribe el frame procesado acá.
# El hilo de display lo lee y lo muestra.
# Son hilos distintos: la detección nunca espera al display.
#
# ¿Por qué un dict con lock y no una variable global?
# Porque dos hilos accediendo a la misma variable sin sincronización
# pueden causar que uno lea un frame a medio escribir → crash o imagen corrupta.
_debug_buffer = {"frame": None}
_debug_lock   = threading.Lock()

def set_debug_frame(frame):
    """Escribe el último frame procesado. Thread-safe."""
    with _debug_lock:
        _debug_buffer["frame"] = frame

def get_debug_frame():
    """Lee el último frame disponible. Devuelve None si todavía no hay ninguno."""
    with _debug_lock:
        return _debug_buffer["frame"]

# Variables de estado envueltas en funciones para acceso seguro
_estado = {
    "operacion_bloqueada": False,  # ¿Acabamos de operar y esperamos el reset?
    "ultima_senal_tiempo": 0.0,    # Timestamp de la última operación (float de Unix time)

    # --- DETECCIÓN DE SEÑAL NUEVA ---
    # Guardamos si había señal en el frame anterior.
    # Si antes NO había y ahora SÍ hay → señal nueva → válida para operar.
    # Si antes YA había y ahora sigue → señal vieja → ignorar.
    # Este es el mecanismo clave para no operar sobre triángulos del pasado.
    "habia_verde_antes": False,
    "habia_rojo_antes":  False,
}

def get_estado(clave: str):
    """Lectura thread-safe del estado."""
    with _lock:                   # Pedimos el candado antes de leer
        return _estado[clave]     # Leemos el valor
                                  # Al salir del "with", el candado se libera solo

def set_estado(clave: str, valor):
    """Escritura thread-safe del estado."""
    with _lock:                   # Pedimos el candado antes de escribir
        _estado[clave] = valor    # Escribimos el valor
                                  # Al salir del "with", el candado se libera solo

# =============================================================================
# INTERFAZ HUD (Heads-Up Display)
# =============================================================================

class OverlayHUD:
    """
    Overlay transparente que se dibuja ENCIMA de Exnova, sin ventana separada.

    Dibuja directamente sobre la pantalla:
      - Rectángulo naranja = zona válida de la última vela
      - Círculo           = señal detectada (verde=compra, rojo=venta)
      - Texto HUD         = estado del bot y valores de debug

    ¿Por qué Canvas en lugar de Labels?
    → Los Labels solo muestran texto. El Canvas permite dibujar
      formas (rectángulos, círculos, líneas) en coordenadas absolutas.
    → Combinado con la ventana transparente, el Canvas se convierte
      en un overlay de dibujo directo sobre la pantalla.

    ¿Por qué no hay lag?
    → No movemos imágenes de la pantalla. Solo redibujamos formas simples
      (vectores) en cada frame. Es extremadamente rápido comparado con
      capturar, procesar y mostrar una imagen completa en otra ventana.
    """

    # Color transparente: cualquier píxel de este color desaparece.
    # Usamos un magenta muy específico para no chocar con colores de Exnova.
    TRANSPARENTE = "#ff00ff"

    def __init__(self):
        self.root = tk.Tk()

        # Ventana sin bordes, siempre arriba, cubre toda la pantalla
        self.root.overrideredirect(True)           # Sin barra de título ni bordes
        self.root.attributes("-topmost", True)      # Siempre encima de todo
        self.root.attributes("-transparentcolor", self.TRANSPARENTE)  # Transparencia
        self.root.geometry("1920x1080+0+0")         # Cubre pantalla completa 1920x1080
        self.root.config(bg=self.TRANSPARENTE)      # Fondo invisible

        # Canvas del tamaño de la pantalla completa.
        # El Canvas es el "lienzo" donde dibujamos todo.
        # highlightthickness=0 elimina el borde del Canvas que tkinter agrega por defecto.
        self.canvas = tk.Canvas(
            self.root,
            width=1920, height=1080,
            bg=self.TRANSPARENTE,
            highlightthickness=0
        )
        self.canvas.pack()

        # IDs de los elementos dibujados en el canvas.
        # Los guardamos para poder actualizarlos sin borrar y redibujar todo.
        # None = todavía no dibujado.
        self._id_zona     = None   # Rectángulo naranja de zona válida
        self._id_senal    = None   # Círculo de señal detectada
        self._id_status   = None   # Texto de estado del bot
        self._id_debug    = None   # Texto de valores debug

        # Dibujamos los elementos estáticos que no cambian (zona válida)
        self._dibujar_zona_valida()

    def _dibujar_zona_valida(self):
        """
        Dibuja el rectángulo naranja de zona válida.
        Es estático: se dibuja una vez al inicio y no cambia.
        Solo cambia si el usuario ajusta ZONA_VELA_ACTUAL_X_MIN/MAX.
        """
        self._id_zona = self.canvas.create_rectangle(
            ZONA_VELA_ACTUAL_X_MIN, 0,          # Esquina superior izquierda
            ZONA_VELA_ACTUAL_X_MAX, 1080,        # Esquina inferior derecha
            outline="#FF8C00",                   # Color del borde: naranja oscuro
            fill="",                             # Sin relleno (solo borde)
            width=2                              # Grosor del borde
        )
        self.canvas.create_text(
            ZONA_VELA_ACTUAL_X_MIN + 5, 20,
            text="ZONA VÁLIDA",
            anchor="nw",                         # Ancla en esquina superior izquierda
            fill="#FF8C00",
            font=("Consolas", 9, "bold")
        )

    def actualizar(self, status: str, debug: str,
                   senal_x: int = -1, senal_y: int = -1, senal_color: str = ""):
        """
        Actualiza el overlay desde cualquier hilo de forma thread-safe.

        Parámetros nuevos respecto a la versión anterior:
          senal_x, senal_y  → coordenadas donde dibujar el círculo de señal
                              -1 significa "no hay señal, borrar el círculo"
          senal_color       → "verde" o "rojo" según la señal detectada
        """
        # Empaquetamos todos los datos en una tupla para pasarlos al hilo principal.
        # Lambda captura la tupla completa para evitar problemas de closure en loops.
        datos = (status, debug, senal_x, senal_y, senal_color)
        self.root.after(0, lambda d=datos: self._actualizar_ui(*d))

    def _actualizar_ui(self, status: str, debug: str,
                       senal_x: int, senal_y: int, senal_color: str):
        """
        Actualización real del canvas. Solo se ejecuta en el hilo principal de tkinter.

        Estrategia de actualización:
        → Borramos el círculo y textos anteriores con canvas.delete(id)
        → Redibujamos con los nuevos valores
        → NO borramos la zona naranja (es estática, no cambia cada frame)

        Borrar y redibujar solo los elementos que cambian es más eficiente
        que hacer canvas.delete("all") y redibujar todo desde cero cada frame.
        """
        # --- Texto de estado ---
        if self._id_status:
            self.canvas.delete(self._id_status)   # Borramos el texto anterior
        color_status = "#00FF00" if "ESCANEANDO" in status else "#FF4444"
        self._id_status = self.canvas.create_text(
            10, 10, anchor="nw",
            text=status,
            fill=color_status,
            font=("Consolas", 13, "bold")
        )

        # --- Texto de debug ---
        if self._id_debug:
            self.canvas.delete(self._id_debug)
        self._id_debug = self.canvas.create_text(
            10, 32, anchor="nw",
            text=debug,
            fill="white",
            font=("Consolas", 10)
        )

        # --- Círculo de señal ---
        if self._id_senal:
            self.canvas.delete(self._id_senal)    # Borramos el círculo anterior
            self._id_senal = None

        if senal_x >= 0 and senal_y >= 0:
            # Solo dibujamos si hay señal activa (coordenadas válidas)
            color_circulo = "#00FF00" if senal_color == "verde" else "#FF0000"
            r = 22   # Radio del círculo en píxeles
            self._id_senal = self.canvas.create_oval(
                senal_x - r, senal_y - r,    # Esquina superior izquierda del bounding box
                senal_x + r, senal_y + r,    # Esquina inferior derecha
                outline=color_circulo,
                fill="",                      # Sin relleno
                width=3
            )


# Instanciamos el HUD. Esto crea la ventana pero no la muestra hasta el mainloop().
hud = OverlayHUD()

# =============================================================================
# CLICK A NIVEL HARDWARE
# =============================================================================

def click_pro(x: int, y: int):
    """
    Hace un click del mouse a nivel de hardware usando la API de Windows directamente.
    
    ¿Por qué no usar pyautogui.click()?
    → pyautogui usa la API de alto nivel de Windows, que algunos programas
      (especialmente plataformas de trading con anti-bot) pueden detectar e ignorar.
    → ctypes.windll.user32 llama directamente a las funciones del kernel de Windows,
      igual que si el usuario moviera el mouse físicamente.
    """
    # SetCursorPos mueve el cursor a las coordenadas absolutas de pantalla
    ctypes.windll.user32.SetCursorPos(x, y)
    
    time.sleep(0.1)  # Esperamos 100ms para que el sistema registre el movimiento
                     # antes de hacer el click. Sin esto puede fallar en PCs lentas.
    
    # mouse_event(flags, dx, dy, data, extra_info)
    # Flag 2 = MOUSEEVENTF_LEFTDOWN  → presionar botón izquierdo
    # Flag 4 = MOUSEEVENTF_LEFTUP    → soltar botón izquierdo
    # Los otros parámetros en 0 porque usamos coordenadas absolutas con SetCursorPos
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # Presionar
    time.sleep(0.05)                                   # Pequeña pausa realista entre press y release
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # Soltar
    
    logger.info(f"Click enviado → ({x}, {y})")

# =============================================================================
# LECTURA DEL RELOJ (OCR)
# =============================================================================

def obtener_segundos_restantes() -> int:
    """
    Captura la zona del reloj en pantalla y extrae el número de segundos via OCR.

    El reloj de Exnova muestra el tiempo en formato MM:SS → ej: "00:56", "00:31"
    Nosotros solo necesitamos los SEGUNDOS (los últimos 2 dígitos).

    Devuelve un int con los segundos, o -1 si no pudo leer nada.
    Devolvemos -1 en lugar de 0 para distinguir "falló el OCR" de "realmente hay 0 segundos".
    """
    try:
        with mss.MSS() as sct:
            screenshot = np.array(sct.grab(AREA_RELOJ))

            # mss captura en BGRA (4 canales) → convertimos a grises (1 canal)
            # Pasamos por BGR primero para evitar errores de conversión directa
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)

            # Agrandamos x3 en lugar de x2.
            # El reloj de Exnova tiene texto relativamente pequeño (height=35px).
            # Con x3 los dígitos quedan más grandes y Tesseract los lee mejor.
            # INTER_CUBIC = interpolación de alta calidad al agrandar.
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

            # Intentamos DOS métodos de binarización y nos quedamos con el que funcione.
            # ¿Por qué dos métodos?
            # → El reloj de Exnova puede tener texto blanco sobre fondo oscuro
            #   O texto amarillo/dorado sobre fondo negro según el estado.
            # → THRESH_BINARY_INV funciona bien para texto claro sobre fondo oscuro.
            # → THRESH_OTSU calcula automáticamente el umbral óptimo para la imagen actual.
            #   Es más robusto ante cambios de brillo/color del reloj.

            # Método 1: Otsu (automático, más robusto)
            _, thresh_otsu = cv2.threshold(
                gray, 0, 255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
                # THRESH_OTSU analiza el histograma de la imagen y elige
                # automáticamente el mejor valor de corte entre claro y oscuro.
                # El "0" como umbral es ignorado cuando se usa OTSU.
            )

            # Método 2: Inversión fija (texto claro sobre fondo oscuro)
            _, thresh_inv = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

            config_ocr = (
                '--psm 7 '                              # Imagen = una sola línea de texto
                '--oem 3 '                              # Motor OCR: LSTM (más preciso)
                '-c tessedit_char_whitelist=0123456789:'# Solo leer dígitos y dos puntos
            )

            # Probamos ambos thresholds y nos quedamos con el que dé un resultado válido
            for thresh in (thresh_otsu, thresh_inv):
                texto = pytesseract.image_to_string(thresh, config=config_ocr).strip()

                # Log de debug: muestra qué está leyendo el OCR en cada frame.
                # Muy útil para calibrar. Una vez que funcione bien, podés
                # cambiar logger.debug por pass para silenciarlo.
                logger.debug(f"OCR raw: '{texto}'")

                # Extraemos solo los dígitos del texto leído
                digitos = "".join(filter(str.isdigit, texto))

                # El reloj muestra "MM:SS" → después de filtrar dígitos tenemos "MMSS"
                # Ejemplo: "00:56" → "0056" → últimos 2 = "56" → 56 segundos
                # Ejemplo: "00:05" → "0005" → últimos 2 = "05" → 5 segundos
                # Necesitamos al menos 2 dígitos para extraer los segundos
                if len(digitos) >= 2:
                    segundos = int(digitos[-2:])
                    # Validamos que sea un valor de segundos razonable (0-59)
                    if 0 <= segundos <= 59:
                        return segundos

        # Si ningún método funcionó, retornamos -1 como señal de fallo
        logger.warning("OCR no pudo leer el reloj en ningún intento.")
        return -1

    except Exception as e:
        logger.warning(f"OCR excepción: {e}")
        return -1

# =============================================================================
# LOOP PRINCIPAL: VISIÓN + LÓGICA DE TRADING
# =============================================================================

def obtener_ventana_exnova() -> dict | None:
    """
    Busca la ventana del proceso Exnova.exe y devuelve su región de pantalla.

    Estrategia:
    1. Buscamos en todos los procesos activos el que se llama EXNOVA_PROCESO
    2. Con el PID encontrado, buscamos el HWND (handle de ventana) de Windows
    3. Con el HWND obtenemos las coordenadas exactas de la ventana
    4. Devolvemos esas coordenadas como diccionario compatible con mss

    ¿Por qué buscar por proceso y no por título de ventana?
    → El título puede cambiar según el par de divisas seleccionado
      (ej: "EUR/USD - Exnova", "AIG - Exnova"). El nombre del .EXE es fijo.

    Devuelve dict {"top": y, "left": x, "width": w, "height": h}
    o None si Exnova no está corriendo.
    """
    # Paso 1: buscar el PID del proceso Exnova
    pid_exnova = None
    for proc in psutil.process_iter(['pid', 'name']):
        # Comparamos en minúsculas para evitar problemas con mayúsculas
        if proc.info['name'].lower() == EXNOVA_PROCESO.lower():
            pid_exnova = proc.info['pid']
            break

    if pid_exnova is None:
        logger.warning(f"Proceso '{EXNOVA_PROCESO}' no encontrado. ¿Está Exnova abierto?")
        return None

    logger.info(f"Exnova encontrado → PID: {pid_exnova}")

    # Paso 2: buscar el HWND (handle) de la ventana asociada a ese PID
    # win32gui.EnumWindows recorre TODAS las ventanas abiertas y llama
    # a nuestra función callback por cada una.
    hwnd_encontrado = None

    def callback_ventana(hwnd, _):
        nonlocal hwnd_encontrado
        try:
            # Obtenemos el PID del proceso dueño de esta ventana
            _, pid_ventana = win32process.GetWindowThreadProcessId(hwnd)
            if pid_ventana == pid_exnova and win32gui.IsWindowVisible(hwnd):
                # Verificamos que tenga título (descarta ventanas fantasma internas)
                if win32gui.GetWindowText(hwnd):
                    hwnd_encontrado = hwnd
        except Exception:
            pass  # Algunas ventanas del sistema no permiten ser inspeccionadas
        return True  # Siempre seguimos enumerando — no retornamos False

    try:
        win32gui.EnumWindows(callback_ventana, None)
    except Exception:
        # pywin32 puede lanzar error si el callback lanza internamente.
        # Lo ignoramos — si hwnd_encontrado tiene valor, funcionó igual.
        pass

    if hwnd_encontrado is None:
        logger.warning("Exnova está corriendo pero no tiene ventana visible.")
        return None

    # Paso 3: obtener las coordenadas de la ventana
    # GetWindowRect devuelve (left, top, right, bottom) en píxeles de pantalla
    left, top, right, bottom = win32gui.GetWindowRect(hwnd_encontrado)
    width  = right - left
    height = bottom - top

    logger.info(f"Ventana Exnova → posición: ({left}, {top}) tamaño: {width}x{height}px")

    return {
        "hwnd":   hwnd_encontrado,
        "top":    top,
        "left":   left,
        "width":  width,
        "height": height
    }


def foco_exnova(hwnd: int):
    """
    Trae la ventana de Exnova al frente sin minimizarla ni moverla.
    La llamamos una vez al inicio para asegurarnos de que está visible.

    ¿Por qué no lo hacemos cada frame?
    → Traer una ventana al frente en cada captura robaría el foco del mouse
      y haría imposible usar otras ventanas mientras el bot corre.
      Una sola vez al inicio es suficiente.
    """
    # ShowWindow con SW_RESTORE: si está minimizada la restaura, si no la deja igual
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    # SetForegroundWindow: la trae al frente
    win32gui.SetForegroundWindow(hwnd)
    logger.info("Foco enviado a la ventana de Exnova.")


def hilo_debug_display():
    """
    Hilo dedicado exclusivamente a mostrar la ventana de debug.

    ¿Por qué un hilo separado?
    → El cv2.imshow() bloquea el hilo que lo llama mientras renderiza el frame.
    → Si está en el mismo hilo que la detección, cada render bloquea el bot
      entre 20-50ms, haciendo que pierda señales que aparecen en ese intervalo.
    → Separándolo, el hilo de detección corre sin interrupciones.
      El display toma el último frame disponible y lo muestra a su propio ritmo.

    Este hilo corre a 60fps para una visualización fluida del debug.
    vea qué está pasando. No afecta en nada la velocidad de detección.
    """
    logger.info("Hilo de debug display iniciado.")
    cv2.namedWindow("Debug Vision", cv2.WINDOW_NORMAL)

    while True:
        frame = get_debug_frame()  # Lee el último frame procesado

        if frame is not None:
            cv2.imshow("Debug Vision", frame)

        # waitKey es obligatorio para que OpenCV procese eventos de la ventana.
        # 16ms = ~60fps para el display. Completamente independiente del loop principal.
        # Si el usuario presiona 'q', cerramos la ventana de debug.
        key = cv2.waitKey(16)
        if key == ord('q'):
            cv2.destroyWindow("Debug Vision")
            logger.info("Ventana de debug cerrada por el usuario.")
            break


def buscar_y_operar():
    """
    Loop principal del bot. Corre en su propio hilo para no bloquear la UI.
    Captura pantalla, busca señales, lee el reloj y ejecuta operaciones.
    """
    logger.info("Hilo de visión iniciado.")
    
    # Creamos la ventana de debug una sola vez, fuera del loop.
    # Si la creáramos dentro del loop, crearíamos miles de ventanas.
    # La ventana de debug se crea en su propio hilo (hilo_debug_display).
    # Acá solo nos ocupamos de capturar y procesar.

    # 'with mss.MSS() as sct' abre el capturador de pantalla.
    # El 'with' garantiza que mss se cierre correctamente aunque haya un error.
    # Es mejor que llamar sct.close() manualmente (que podríamos olvidar).
    with mss.MSS() as sct:
        
        # Buscamos la ventana de Exnova al iniciar el bot
        info_ventana = obtener_ventana_exnova()
        if info_ventana is None:
            logger.error("No se pudo encontrar Exnova. Cerrando bot.")
            return

        # Traemos Exnova al frente una sola vez al inicio
        foco_exnova(info_ventana["hwnd"])
        time.sleep(0.5)  # Pequeña pausa para que el SO procese el cambio de foco

        # Región de captura: solo la ventana de Exnova
        # mss acepta el mismo formato de dict que ya teníamos para AREA_RELOJ
        region_exnova = {
            "top":    info_ventana["top"],
            "left":   info_ventana["left"],
            "width":  info_ventana["width"],
            "height": info_ventana["height"],
        }

        while True:  # Loop infinito: el bot corre hasta que lo cerremos

            # --- MEDICIÓN DE TIEMPO DEL LOOP ---
            loop_start = time.time()

            # --- CAPTURA SOLO DE LA VENTANA EXNOVA ---
            # En lugar de capturar toda la pantalla (1920x1080),
            # capturamos solo el área de la ventana de Exnova.
            # Si Exnova está en 1456x816, procesamos un 44% menos de píxeles
            # → matchTemplate es proporcionalmente más rápido.
            #
            # IMPORTANTE: si el usuario mueve la ventana de Exnova durante
            # la sesión, las coordenadas quedan desactualizadas.
            # Por eso re-consultamos la posición cada 5 segundos.
            if int(time.time()) % 5 == 0:
                nueva_info = obtener_ventana_exnova()
                if nueva_info:
                    region_exnova = {
                        "top":    nueva_info["top"],
                        "left":   nueva_info["left"],
                        "width":  nueva_info["width"],
                        "height": nueva_info["height"],
                    }

            img = np.array(sct.grab(region_exnova))  # Captura solo Exnova (BGRA)

            # Convertimos BGRA → BGR para el template matching en color.
            # mss captura con canal Alpha (transparencia) incluido = BGRA (4 canales).
            # OpenCV y nuestros templates trabajan en BGR (3 canales).
            # Si no hacemos esta conversión, el matchTemplate falla porque
            # la imagen tiene 4 canales y el template tiene 3.
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Versión en grises: SOLO para la ventana de debug visual.
            # Mostrar en grises en el debug es más claro para ver la zona naranja
            # y los círculos encima. No se usa para el matching.
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # Enviamos el frame RAW al buffer de debug INMEDIATAMENTE después
            # de capturar — antes de cualquier procesamiento.
            # Así el hilo de display siempre tiene el frame más reciente
            # sin esperar los ~150ms que tarda el multi-scale matching.
            # Los indicadores (zona, círculos) se dibujan después y se
            # envían como segundo frame, pero el display ya avanzó.
            set_debug_frame(cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR))

            # --- BÚSQUEDA DE SEÑALES (Template Matching) ---
            # Inicializamos con valores neutros.
            # Si operacion_bloqueada=True, saltamos el matching completo para ahorrar CPU.
            # No tiene sentido buscar señales si ya operamos y estamos esperando el reset.
            max_v, max_r = 0.0, 0.0
            loc_v, loc_r = (0, 0), (0, 0)
            
            # --- BÚSQUEDA DE SEÑALES EN ZONA VÁLIDA ---
            #
            # Lógica simple y directa:
            #   1. Corremos matchTemplate sobre toda la imagen
            #   2. Buscamos TODAS las coincidencias que superen el umbral
            #   3. De esas, nos quedamos SOLO con las que estén dentro de la zona válida
            #   4. Si hay alguna dentro → señal válida. Si no hay → ignoramos.
            #
            # ¿Por qué np.where en lugar de minMaxLoc?
            # minMaxLoc devuelve UNA SOLA coincidencia (la de mayor confianza).
            # Si esa coincidencia es una señal vieja fuera de la zona → falla.
            # np.where devuelve TODAS → podemos filtrar por zona y elegir la mejor.

            def buscar_multiscala(template: np.ndarray, imagen: np.ndarray) -> tuple:
                """
                Busca el template a múltiples escalas dentro de la zona válida.

                ¿Por qué múltiples escalas?
                → El zoom de Exnova cambia el tamaño de los triángulos en pantalla.
                → matchTemplate requiere que template e imagen tengan el mismo tamaño
                  de objeto. Si difieren aunque sea un 10%, la confianza cae a ~0.3.
                → Probando escalas entre SCALE_MIN y SCALE_MAX encontramos el tamaño
                  real del triángulo en pantalla, sin importar el zoom actual.

                Proceso por cada escala:
                  1. Redimensionamos el template a esa escala
                  2. Corremos matchTemplate sobre la imagen completa
                  3. Filtramos resultados dentro de la zona válida
                  4. Guardamos la mejor coincidencia de todas las escalas

                Devuelve (confianza, (x, y), escala_ganadora)
                o (0.0, (0,0), 1.0) si no encontró nada.
                """
                mejor_conf  = 0.0
                mejor_loc   = (0, 0)
                mejor_escala = 1.0

                # Generamos las escalas a probar de forma uniforme entre min y max
                # np.linspace(0.7, 1.3, 10) = [0.7, 0.77, 0.83, ..., 1.3]
                escalas = np.linspace(SCALE_MIN, SCALE_MAX, SCALE_STEPS)

                h_orig, w_orig = template.shape[:2]

                for escala in escalas:
                    # Calculamos el nuevo tamaño del template para esta escala
                    nuevo_w = int(w_orig * escala)
                    nuevo_h = int(h_orig * escala)

                    # El template redimensionado no puede ser más grande que la imagen
                    if nuevo_w >= imagen.shape[1] or nuevo_h >= imagen.shape[0]:
                        continue

                    # Redimensionamos el template
                    # INTER_AREA es el mejor algoritmo para reducir tamaño
                    # INTER_CUBIC es el mejor para agrandar
                    inter = cv2.INTER_AREA if escala < 1.0 else cv2.INTER_CUBIC
                    t_escalado = cv2.resize(template, (nuevo_w, nuevo_h), interpolation=inter)

                    # Corremos matchTemplate con este template escalado
                    resultado = cv2.matchTemplate(imagen, t_escalado, cv2.TM_CCOEFF_NORMED)

                    # Buscamos todos los puntos con confianza suficiente
                    filas, cols = np.where(resultado >= UMBRAL_CONFIANZA)

                    for y, x in zip(filas.tolist(), cols.tolist()):
                        # FILTRO PRINCIPAL: solo dentro de la zona válida
                        if not (ZONA_VELA_ACTUAL_X_MIN <= x <= ZONA_VELA_ACTUAL_X_MAX):
                            continue

                        conf = float(resultado[y, x])
                        if conf > mejor_conf:
                            mejor_conf   = conf
                            mejor_loc    = (x, y)
                            mejor_escala = escala

                if mejor_conf > 0:
                    logger.debug(
                        f"Detección → conf:{mejor_conf:.2f} "
                        f"pos:{mejor_loc} escala:{mejor_escala:.2f}x"
                    )

                return mejor_conf, mejor_loc

            # Valores por defecto
            max_v, loc_v = 0.0, (0, 0)
            max_r, loc_r = 0.0, (0, 0)

            if not get_estado("operacion_bloqueada"):
                max_v, loc_v = buscar_multiscala(TEMPLATE_VERDE, img_bgr)
                max_r, loc_r = buscar_multiscala(TEMPLATE_ROJO,  img_bgr)

            # Señal válida = confianza suficiente Y dentro de zona (ya filtrado adentro)
            hay_v = max_v >= UMBRAL_CONFIANZA
            hay_r = max_r >= UMBRAL_CONFIANZA
            
            # --- VISUALIZACIÓN DEBUG ---
            # Convertimos de gris a BGR para poder dibujar en colores.
            # OpenCV necesita 3 canales (BGR) para dibujar en color.
            debug_img = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)
            
            # Dibujamos la ZONA DE LA ÚLTIMA VELA como un rectángulo semitransparente.
            # Esto nos permite ver en tiempo real si el triángulo cae dentro o fuera.
            # cv2.rectangle dibuja el borde del rectángulo (no lo rellena).
            # Para ver la zona claramente usamos color naranja (0, 165, 255 en BGR).
            alto = img_gray.shape[0]  # shape[0] = alto de la imagen en píxeles
            cv2.rectangle(
                debug_img,
                (ZONA_VELA_ACTUAL_X_MIN, 0),      # Esquina superior izquierda de la zona
                (ZONA_VELA_ACTUAL_X_MAX, alto),    # Esquina inferior derecha (toca el piso)
                (0, 165, 255),                     # Naranja en BGR
                2                                  # Grosor del borde en píxeles
            )
            
            # Texto explicativo dentro de la zona
            cv2.putText(
                debug_img,
                "ZONA VALIDA",           # Texto a mostrar
                (ZONA_VELA_ACTUAL_X_MIN + 5, 30),  # Posición (x, y) del texto
                cv2.FONT_HERSHEY_SIMPLEX,          # Fuente
                0.5,                               # Escala del texto
                (0, 165, 255),                     # Color naranja
                1                                  # Grosor
            )
            
            # Rectángulo sobre la zona del reloj (cyan)
            r = AREA_RELOJ
            cv2.rectangle(
                debug_img,
                (r["left"], r["top"]),
                (r["left"] + r["width"], r["top"] + r["height"]),
                (0, 255, 255),  # Cyan en BGR
                2
            )
            
            # Círculos sobre las señales detectadas.
            # Verde si hay señal verde, rojo si hay señal roja.
            # El +15 centra el círculo sobre el triángulo (que mide ~30x30px).
            if max_v >= UMBRAL_CONFIANZA:
                # Verde = señal de compra (HIGHER)
                color = (0, 255, 0) if hay_v else (0, 100, 0)  # Verde brillante si válida, oscuro si fuera de zona
                cv2.circle(debug_img, (loc_v[0] + 15, loc_v[1] + 15), 20, color, 2)
            if max_r >= UMBRAL_CONFIANZA:
                # Rojo = señal de venta (LOWER)
                color = (0, 0, 255) if hay_r else (0, 0, 100)  # Rojo brillante si válida, oscuro si fuera de zona
                cv2.circle(debug_img, (loc_r[0] + 15, loc_r[1] + 15), 20, color, 2)
            
            # Enviamos el frame al buffer compartido.
            # El hilo de display lo leerá y mostrará de forma asíncrona.
            # Este set_debug_frame() tarda ~0.01ms — prácticamente nada.
            # Antes el imshow() bloqueaba ~30-50ms acá. Esa diferencia es
            # exactamente el tiempo que el bot perdía señales.
            set_debug_frame(debug_img)
            
            # --- LECTURA DEL RELOJ ---
            segundos = obtener_segundos_restantes()
            
            # --- ACTUALIZACIÓN DEL HUD ---
            bloqueado = get_estado("operacion_bloqueada")
            estado_str = "⏳ BLOQUEADO" if bloqueado else "🚀 ESCANEANDO"
            hud.actualizar(
                estado_str,
                f"V:{max_v:.2f} R:{max_r:.2f} | Reloj:{segundos}s"
            )
            
            # --- LÓGICA DE DISPARO ---
            # Condición completa para operar:
            # 1. Hay al menos una señal válida
            # 2. No estamos en período de bloqueo post-operación
            # 3. Los segundos del reloj están en la ventana de trigger (30-32)
            #    (rango en lugar de valor exacto = más robusto ante fallas de OCR)
            # segundos == -1 significa que el OCR falló → no operamos
            if (hay_v or hay_r) and not bloqueado and segundos != -1:
                
                if SEGUNDO_TRIGGER_MIN <= segundos <= SEGUNDO_TRIGGER_MAX:
                    
                    if hay_v:
                        logger.info(f"COMPRA ejecutada — segundo {segundos}")
                        click_pro(*COORDS_COMPRA)  # El * desempaqueta la tupla: (x,y) → x, y
                    else:
                        logger.info(f"VENTA ejecutada — segundo {segundos}")
                        click_pro(*COORDS_VENTA)
                    
                    # Bloqueamos para evitar doble disparo sobre la misma señal
                    set_estado("operacion_bloqueada", True)
                    set_estado("ultima_senal_tiempo", time.time())
                
                else:
                    # Señal detectada pero fuera de la ventana de tiempo
                    logger.debug(f"Señal detectada, esperando ventana {SEGUNDO_TRIGGER_MIN}-{SEGUNDO_TRIGGER_MAX}s (actual: {segundos}s)")
            
            # --- RESET DEL BLOQUEO ---
            # Si pasaron más de TIEMPO_BLOQUEO segundos desde la última operación,
            # desbloqueamos el bot para que pueda operar nuevamente.
            if bloqueado:
                tiempo_desde_op = time.time() - get_estado("ultima_senal_tiempo")
                if tiempo_desde_op > TIEMPO_BLOQUEO:
                    set_estado("operacion_bloqueada", False)
                    logger.info("Bot reseteado — listo para nueva señal.")
            
            # --- CONTROL DE CICLO ---
            # Calculamos cuánto tardó esta iteración completa.
            elapsed = time.time() - loop_start

            # TARGET_FRAME_TIME = 1.0s = 1 captura por segundo.
            #
            # ¿Por qué 1 segundo y no más rápido?
            # Las señales de Exnova aparecen sobre velas de 1 minuto.
            # Una señal que aparece no desaparece en menos de 1 segundo,
            # así que 1 captura/segundo es suficiente para detectarla
            # sin desperdiciar CPU en capturas innecesarias.
            #
            # Cuando integremos YOLO volvemos a evaluar este valor.
            # Por ahora 1s es el balance correcto para matchTemplate.
            #
            # Si necesitás más reactividad en el futuro, bajá este valor:
            #   0.5  → 2 capturas por segundo
            #   0.25 → 4 capturas por segundo
            # 0.1s = 10 capturas por segundo.
            # Necesitamos reactividad para no perdernos señales nuevas
            # que aparecen y se mueven rápido con la vela en formación.
            # Con 1s dormíamos demasiado y el triángulo nuevo ya había
            # salido de la zona válida cuando finalmente capturábamos.
            TARGET_FRAME_TIME = 0.1
            time.sleep(max(0.0, TARGET_FRAME_TIME - elapsed))

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    # '__main__' significa "este archivo se está ejecutando directamente",
    # no importado por otro módulo.
    # Es la convención estándar de Python para el punto de entrada del programa.
    
    logger.info("=" * 50)
    logger.info("RoarBot iniciando...")
    logger.info("Ejecutá como ADMINISTRADOR para que los clicks funcionen.")
    logger.info(f"Buscando proceso: {EXNOVA_PROCESO}")
    logger.info("=" * 50)
    logger.info("Dependencias necesarias: pip install pywin32 psutil")
    
    # Lanzamos el loop de visión en un hilo separado.
    # daemon=True significa que este hilo muere automáticamente
    # cuando el programa principal (la UI) se cierra.
    # Sin daemon=True, cerrar la ventana no mataría el hilo de fondo.
    # Hilo de detección: corre lo más rápido posible, sin display
    hilo_vision = threading.Thread(target=buscar_y_operar, daemon=True)
    hilo_vision.start()

    # Hilo de display: corre a 60fps para visualización fluida.
    # daemon=True → se cierra automáticamente cuando se cierra la ventana principal.
    hilo_display = threading.Thread(target=hilo_debug_display, daemon=True)
    hilo_display.start()
    
    # mainloop() arranca el loop de eventos de tkinter.
    # Esta línea BLOQUEA hasta que el usuario cierre la ventana.
    # Por eso el hilo de visión tiene que estar corriendo en paralelo.
    hud.root.mainloop()
    
    logger.info("Bot cerrado por el usuario.")