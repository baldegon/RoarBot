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
# CALIBRACIÓN (ajustá si el bot falla):
#   Bot ignora señales válidas   → aumentar (ej: 160)
#   Bot opera sobre velas viejas → reducir  (ej: 80)
TOLERANCIA_ZONA_PX = 120

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

# Variables de estado envueltas en funciones para acceso seguro
_estado = {
    "operacion_bloqueada": False,  # ¿Acabamos de operar y esperamos el reset?
    "ultima_senal_tiempo": 0.0,    # Timestamp de la última operación (float de Unix time)
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
    Ventana transparente que se dibuja encima de todo como un HUD.
    
    ¿Por qué una clase?
    → Porque agrupa datos (labels, ventana) + comportamiento (actualizar)
      en un solo lugar. Más ordenado que variables sueltas.
    """
    
    def __init__(self):
        self.root = tk.Tk()
        
        # bg='magenta' + transparentcolor='magenta' → el magenta se vuelve transparente.
        # Es el truco clásico para ventanas overlay: pintamos el fondo de un color
        # que después hacemos invisible. Lo que queda visible son solo los labels.
        self.root.config(bg='magenta')
        self.root.attributes(
            "-transparentcolor", "magenta",  # Este color se vuelve transparente
            "-topmost", True                 # La ventana siempre queda arriba de todo
        )
        self.root.overrideredirect(True)  # Quitamos la barra de título y bordes de Windows
        self.root.geometry("400x120+100+100")  # Tamaño (400x120) y posición (+100+100)
        
        # Label principal: muestra el estado del bot
        self.label_status = tk.Label(
            self.root,
            text="🤖 BOT: STANDBY",
            font=("Consolas", 14, "bold"),
            fg="#00FF00",   # Verde brillante (fácil de leer sobre cualquier fondo)
            bg="magenta"    # Mismo color que el fondo → se ve transparente
        )
        self.label_status.pack(anchor="w")  # anchor="w" = alineado a la izquierda (West)
        
        # Label secundario: muestra valores de debug en tiempo real
        self.label_debug = tk.Label(
            self.root,
            text="Iniciando...",
            font=("Consolas", 10),
            fg="white",
            bg="magenta"
        )
        self.label_debug.pack(anchor="w")
    
    def actualizar(self, status: str, debug: str):
        """
        Método público para actualizar el HUD desde cualquier hilo.
        
        ¿Por qué usar self.root.after(0, ...)?
        → tkinter NO es thread-safe. Si llamamos .config() directamente desde
          otro hilo, puede crashear de forma silenciosa o impredecible.
        → root.after(0, función) le dice a tkinter: "ejecutá esta función
          en el hilo principal tan pronto como puedas".
        → El "0" significa "sin delay adicional, lo antes posible".
        → Así la UI siempre se actualiza desde su propio hilo. Seguro.
        """
        self.root.after(0, lambda: self._actualizar_ui(status, debug))
    
    def _actualizar_ui(self, status: str, debug: str):
        """
        Actualización real de los labels. Solo llamar desde el hilo principal.
        El guión bajo al inicio (_) es convención Python para "método interno/privado".
        """
        self.label_status.config(text=status)
        self.label_debug.config(text=debug)


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
    
    Devuelve un int con los segundos, o 0 si no pudo leer nada.
    El '-> int' es un type hint: documentamos qué tipo devuelve la función.
    """
    try:
        with mss.MSS() as sct:
            # Capturamos SOLO el área del reloj, no toda la pantalla.
            # Esto es mucho más rápido y el OCR comete menos errores
            # porque tiene menos "ruido visual" alrededor.
            screenshot = np.array(sct.grab(AREA_RELOJ))
            
            # Convertimos a escala de grises.
            # El OCR funciona mejor en grises que en color:
            # elimina información que no necesita (color) y es más rápido.
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # Agrandamos la imagen x2 con interpolación cúbica.
            # Tesseract trabaja mejor con texto grande. Si el reloj es pequeño
            # en pantalla, los caracteres tienen pocos píxeles y el OCR falla.
            # INTER_CUBIC es más lento que INTER_LINEAR pero da mejor calidad al agrandar.
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
            # Binarización (threshold): convertimos la imagen a blanco y negro puro.
            # THRESH_BINARY_INV invierte los colores: texto oscuro → blanco, fondo → negro.
            # Tesseract lee mejor texto blanco sobre negro en imágenes binarizadas.
            # 180 es el umbral: píxeles más claros que 180 → negro; más oscuros → blanco.
            _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
            
            # Configuración de Tesseract:
            # --psm 7 = "tratar la imagen como una sola línea de texto"
            #           (perfecto para un reloj que muestra "0:31" o "31")
            # tessedit_char_whitelist = solo reconocer estos caracteres
            #           (ignorar letras, signos raros que confunden el OCR)
            config_ocr = '--psm 7 -c tessedit_char_whitelist=0123456789:'
            texto = pytesseract.image_to_string(thresh, config=config_ocr).strip()
            
            # Filtramos todo lo que no sea dígito.
            # .strip() ya quitó espacios, pero pueden quedar caracteres raros.
            texto_filtrado = "".join(filter(str.isdigit, texto))
            
            # Tomamos los últimos 2 dígitos como los segundos.
            # Si el reloj muestra "1:31", texto_filtrado = "131" → tomamos "31".
            # Si muestra "31", texto_filtrado = "31" → tomamos "31".
            if len(texto_filtrado) >= 2:
                return int(texto_filtrado[-2:])  # [-2:] = últimos 2 caracteres
            elif len(texto_filtrado) == 1:
                return int(texto_filtrado)
                
    except Exception as e:
        # Ahora el error es visible. Antes se tragaba silenciosamente.
        logger.warning(f"OCR falló: {e}")
    
    return 0  # Valor neutro si no pudimos leer el reloj

# =============================================================================
# LOOP PRINCIPAL: VISIÓN + LÓGICA DE TRADING
# =============================================================================

def buscar_y_operar():
    """
    Loop principal del bot. Corre en su propio hilo para no bloquear la UI.
    Captura pantalla, busca señales, lee el reloj y ejecuta operaciones.
    """
    logger.info("Hilo de visión iniciado.")
    
    # Creamos la ventana de debug una sola vez, fuera del loop.
    # Si la creáramos dentro del loop, crearíamos miles de ventanas.
    cv2.namedWindow("Debug Vision", cv2.WINDOW_NORMAL)
    
    # 'with mss.MSS() as sct' abre el capturador de pantalla.
    # El 'with' garantiza que mss se cierre correctamente aunque haya un error.
    # Es mejor que llamar sct.close() manualmente (que podríamos olvidar).
    with mss.MSS() as sct:
        
        monitor = sct.monitors[1]  # monitors[0] = todos los monitores juntos
                                   # monitors[1] = primer monitor (el principal)
                                   # monitors[2] = segundo monitor (si existe)
        
        while True:  # Loop infinito: el bot corre hasta que lo cerremos
            
            # --- MEDICIÓN DE TIEMPO DEL LOOP ---
            # Guardamos el tiempo al inicio de cada iteración.
            # Al final calculamos cuánto tardó y ajustamos el sleep.
            # Así el bot siempre intenta correr a ~20fps sin importar
            # cuánto tarde el template matching en cada frame.
            loop_start = time.time()
            
            # --- CAPTURA DE PANTALLA ---
            img = np.array(sct.grab(monitor))  # Captura full screen como array NumPy (BGRA)

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
            
            # --- BÚSQUEDA DE SEÑALES (Template Matching) ---
            # Inicializamos con valores neutros.
            # Si operacion_bloqueada=True, saltamos el matching completo para ahorrar CPU.
            # No tiene sentido buscar señales si ya operamos y estamos esperando el reset.
            max_v, max_r = 0.0, 0.0
            loc_v, loc_r = (0, 0), (0, 0)
            
            if not get_estado("operacion_bloqueada"):
                # matchTemplate recorre img_gray píxel por píxel buscando el template.
                # TM_CCOEFF_NORMED normaliza el resultado entre -1.0 y 1.0.
                # 1.0 = coincidencia perfecta | 0.0 = sin parecido | -1.0 = inverso
                # Usamos img_bgr (color) para que OpenCV pueda distinguir
                # el triángulo VERDE del ROJO. En grises son indistinguibles.
                res_v = cv2.matchTemplate(img_bgr, TEMPLATE_VERDE, cv2.TM_CCOEFF_NORMED)
                res_r = cv2.matchTemplate(img_bgr, TEMPLATE_ROJO,  cv2.TM_CCOEFF_NORMED)
                
                # minMaxLoc devuelve (min_val, max_val, min_loc, max_loc)
                # Solo nos importan:
                #   max_v / max_r → nivel de confianza de la mejor coincidencia
                #   loc_v / loc_r → posición (x, y) de esa mejor coincidencia
                _, max_v, _, loc_v = cv2.minMaxLoc(res_v)
                _, max_r, _, loc_r = cv2.minMaxLoc(res_r)
            
            # --- FILTRO DE ZONA: ÚLTIMA VELA ---
            # Esta es la regla más importante del bot:
            # "Solo operar si la señal está en la última vela"
            #
            # Implementación: verificamos que la coordenada X del triángulo
            # esté dentro de ZONA_VELA_ACTUAL_X_MIN y ZONA_VELA_ACTUAL_X_MAX.
            # Esa franja cubre exactamente la zona de la última vela en tu pantalla.
            #
            # loc_v[0] y loc_r[0] son la coordenada X (horizontal) donde OpenCV
            # encontró el template. [0] = X, [1] = Y (vertical).
            #
            # Condición completa para que una señal sea VÁLIDA:
            #   1. Confianza >= umbral (la imagen se parece al template)
            #   2. X >= ZONA_VELA_ACTUAL_X_MIN (no está en velas viejas)
            #   3. X <= ZONA_VELA_ACTUAL_X_MAX (no está fuera del gráfico)
            def en_zona_ultima_vela(loc: tuple) -> bool:
                # Función auxiliar local: recibe una posición (x,y) y
                # devuelve True si X está dentro de la zona válida.
                # Definirla acá (dentro del loop) es válido para funciones pequeñas
                # que solo se usan en este contexto.
                x = loc[0]
                return ZONA_VELA_ACTUAL_X_MIN <= x <= ZONA_VELA_ACTUAL_X_MAX
            
            hay_v = (max_v >= UMBRAL_CONFIANZA) and en_zona_ultima_vela(loc_v)
            hay_r = (max_r >= UMBRAL_CONFIANZA) and en_zona_ultima_vela(loc_r)
            
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
            
            cv2.imshow("Debug Vision", debug_img)
            cv2.waitKey(1)  # waitKey(1) = procesar eventos de la ventana OpenCV por 1ms.
                            # Sin esta línea la ventana se congela. Es OBLIGATORIO en el loop.
            
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
            if (hay_v or hay_r) and not bloqueado:
                
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
            
            # --- CONTROL DE FPS ---
            # Calculamos cuánto tardó esta iteración completa.
            elapsed = time.time() - loop_start
            
            # TARGET_FRAME_TIME = 0.05s = 50ms = ~20fps
            # Si el loop tardó menos de 50ms, dormimos la diferencia.
            # Si tardó más de 50ms (PC lenta), max(0,...) evita sleep negativo.
            TARGET_FRAME_TIME = 0.05
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
    logger.info("=" * 50)
    
    # Lanzamos el loop de visión en un hilo separado.
    # daemon=True significa que este hilo muere automáticamente
    # cuando el programa principal (la UI) se cierra.
    # Sin daemon=True, cerrar la ventana no mataría el hilo de fondo.
    hilo_vision = threading.Thread(target=buscar_y_operar, daemon=True)
    hilo_vision.start()
    
    # mainloop() arranca el loop de eventos de tkinter.
    # Esta línea BLOQUEA hasta que el usuario cierre la ventana.
    # Por eso el hilo de visión tiene que estar corriendo en paralelo.
    hud.root.mainloop()
    
    logger.info("Bot cerrado por el usuario.")