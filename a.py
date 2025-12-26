import hid
import vgamepad as vg
import time

# --- CONFIGURACIÓN ---
# IDs de tu Mchose (Confirmados por tu captura)
TARGET_VID = 0x41E4
TARGET_PID = 0x211A

# Mapeo de teclas (Código HEX -> Qué hace en el mando)
# 0x1A es 'W'  |  0x16 es 'S'  |  0x04 es 'A'  |  0x07 es 'D'
KEY_W = 0x1A
KEY_S = 0x16

print("--- INICIANDO MCHOSE ANALOG CONTROLLER ---")

# 1. Crear el Mando Virtual de Xbox 360
try:
    gamepad = vg.VX360Gamepad()
    print("✅ Mando Virtual creado. Windows debería hacer sonido de 'Nuevo Dispositivo'.")
except Exception as e:
    print(f"❌ Error creando mando virtual: {e}")
    print("SOLUCIÓN: Instala el driver ViGEmBus (busca en Google 'ViGEmBus release').")
    exit()

# 2. Conectar al Teclado (Específicamente a la Interfaz #1 que descubrimos)
device = None
found = False

# Buscamos la Interfaz 1 específicamente
for info in hid.enumerate(TARGET_VID, TARGET_PID):
    if info['interface_number'] == 1: # ¡La Interfaz 1 es la clave!
        try:
            device = hid.device()
            device.open_path(info['path'])
            device.set_nonblocking(1)
            found = True
            print(f"✅ Conectado con éxito a la Interfaz #1.")
            break
        except:
            pass

if not found:
    print("❌ No se pudo conectar a la Interfaz #1.")
    print("Asegúrate de que el software de Mchose esté abierto en segundo plano")
    print("o que hayas ejecutado el escaner antes para 'despertar' el teclado.")
    exit()

print("\n🏎️  LISTO PARA CONDUCIR 🏎️")
print("Presiona 'W' para Acelerar (Gatillo Derecho)")
print("Presiona 'S' para Frenar (Gatillo Izquierdo)")
print("Presiona Ctrl+C para salir.")

# --- BUCLE PRINCIPAL ---
try:
    while True:
        data = device.read(64)
        
        if data and len(data) > 6:
            # Filtro: El paquete debe empezar por A0 10 (según tu captura)
            if data[0] == 0xA0 and data[1] == 0x10:
                
                # Extraemos qué tecla es y cuánta presión tiene
                key_code = data[3]
                
                # Unimos Byte 4 y 5 para sacar el valor analógico (16 bits)
                # Tu teclado envía "Big Endian" (El byte mayor primero)
                presion_raw = (data[4] << 8) | data[5]
                
                # CALIBRACIÓN:
                # Tu teclado parece llegar hasta ~650 de máximo.
                # El mando de Xbox espera 0 a 255.
                # Fórmula: presion / 2.5 (ajusta este 2.5 si no llega al tope)
                presion_xbox = int(presion_raw / 2.5)
                
                # Limitamos para que no pase de 255
                if presion_xbox > 255: presion_xbox = 255

                # --- LÓGICA DE JUEGO ---
                if key_code == KEY_W:
                    # Acelerar (Right Trigger)
                    gamepad.right_trigger(presion_xbox)
                    gamepad.left_trigger(0) # Soltamos freno por si acaso
                    print(f"Acelerar: {presion_xbox}/255", end='\r')
                    
                elif key_code == KEY_S:
                    # Frenar (Left Trigger)
                    gamepad.left_trigger(presion_xbox)
                    gamepad.right_trigger(0)
                    print(f"Frenar:   {presion_xbox}/255", end='\r')
                
                else:
                    # Si sueltas o tocas otra tecla, soltamos los gatillos
                    # (Esto se puede mejorar para permitir pulsar los dos a la vez)
                    # Pero por seguridad, reseteamos si no detectamos W o S
                    gamepad.right_trigger(0)
                    gamepad.left_trigger(0)
                    
                gamepad.update()

        time.sleep(0.001) # Ultra rápido (1ms)

except KeyboardInterrupt:
    print("\nApagando motor...")
    device.close()