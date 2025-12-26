import hid
import time

# TUS IDs (MCHOSE)
TARGET_VID = 0x41E4
TARGET_PID = 0x211A

print(f"--- ESCANER V2 (MODO ROBUSTO) PARA ID {hex(TARGET_VID)}:{hex(TARGET_PID)} ---")

# 1. Buscar dispositivos
device_info_list = hid.enumerate(TARGET_VID, TARGET_PID)
connected_devices = []

if not device_info_list:
    print("❌ No se encontró el dispositivo. Revisa el cable.")
else:
    print(f"✅ Se encontraron {len(device_info_list)} canales.")

    for info in device_info_list:
        interface_num = info['interface_number']
        path = info['path']

        # FILTRO DE SEGURIDAD:
        # Saltamos la Interfaz 0 porque Windows la bloquea y crashea el script.
        if interface_num == 0:
            print(f"  -> Saltando Interfaz #0 (Bloqueada por Windows)")
            continue

        try:
            h = hid.device()
            h.open_path(path)
            h.set_nonblocking(1) 
            
            # Guardamos info extra para identificarlo luego
            connected_devices.append({
                "device": h, 
                "id": f"Int#{interface_num}", 
                "path": path
            })
            print(f"  -> ✅ Conectado a Interfaz #{interface_num}")
        except Exception as e:
            print(f"  -> ❌ Error al abrir Interfaz #{interface_num}: {e}")

    print("\n--- INICIANDO MONITOR (Presiona Ctrl+C para salir) ---")
    print("Presiona teclas analógicas y busca qué línea cambia...")
    print("(Si ves muchos ceros, ignóralos. Busca cambios al presionar)")

    try:
        while True:
            for dev_obj in connected_devices:
                dev = dev_obj["device"]
                dev_id = dev_obj["id"]
                
                try:
                    # Leemos datos
                    data = dev.read(64)
                    
                    if data:
                        # TRUCO: Filtramos mensajes vacíos para limpiar la pantalla
                        # Solo mostramos si hay algún dato distinto de cero
                        if any(x != 0 for x in data):
                            hex_str = " ".join([f"{x:02X}" for x in data])
                            print(f"[{dev_id}] DATOS: {hex_str}")
                
                except OSError:
                    # Si una interfaz falla, la ignoramos y seguimos con las otras
                    pass

            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\nCerrando...")
        for dev_obj in connected_devices:
            dev_obj["device"].close()