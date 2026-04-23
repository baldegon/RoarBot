import pyautogui

print("Posicioná el mouse y esperá...")
try:
    while True:
        x, y = pyautogui.position()
        print(f"X: {x}, Y: {y}", end="\r")
except KeyboardInterrupt:
    print("\nListo.")
