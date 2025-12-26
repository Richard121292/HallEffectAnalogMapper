import hid
import time

TARGET_VID = 0x41E4
TARGET_PID = 0x211A
INTERFACE_NUM = 1

print("Buscando teclado Mchose...")

path = None
for d in hid.enumerate(TARGET_VID, TARGET_PID):
    print(f"  Interface {d['interface_number']}: {d['path']}")
    if d['interface_number'] == INTERFACE_NUM:
        path = d['path']

if not path:
    print("No encontrado!")
    exit()

print(f"\nConectando a interface {INTERFACE_NUM}...")
device = hid.device()
device.open_path(path)
device.set_nonblocking(1)

print("Leyendo datos raw. Presiona teclas para ver los valores.\n")
print("Formato: [key_hex] raw_value")
print("-" * 50)

# Track last values to only show changes
last_values = {}
significant_threshold = 50  # Solo mostrar si raw > este valor

try:
    while True:
        data = device.read(64)
        if data and len(data) > 6 and data[0] == 0xA0:
            key = data[3]
            raw = (data[4] << 8) | data[5]
            
            # Solo mostrar si el valor es significativo o cambió mucho
            prev = last_values.get(key, 0)
            if raw > significant_threshold or (prev > significant_threshold and raw <= significant_threshold):
                print(f"[0x{key:02X}] raw={raw:4d}  {'*' * min(50, raw // 20)}")
            
            last_values[key] = raw
        
        time.sleep(0.001)  # Pequeña pausa para no saturar CPU
        
except KeyboardInterrupt:
    print("\nCerrando...")
    device.close()
