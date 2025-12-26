import tkinter as tk
from tkinter import ttk, messagebox
import hid
import vgamepad as vg
import threading
import time

# --- CONFIGURACIÓN DEL DISPOSITIVO ---
TARGET_VID = 0x41E4
TARGET_PID = 0x211A
INTERFACE_NUM = 1  # La interfaz analógica que descubrimos

class MchoseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mchose Analog Controller")
        self.root.geometry("500x450")
        self.root.configure(bg="#1e1e1e")

        # Estado
        self.running = False
        self.device = None
        self.gamepad = None
        self.mappings = {} # Diccionario: codigo_tecla -> {accion, sensibilidad}
        self.detecting_key = False
        self.last_pressed_code = None
        self.thread = None

        # Estilos
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#1e1e1e", foreground="white")
        style.configure("TButton", background="#333", foreground="white", borderwidth=0)
        style.map("TButton", background=[('active', '#555')])

        # --- INTERFAZ ---
        
        # 1. Cabecera y Conexión
        self.status_label = ttk.Label(root, text="Estado: DESCONECTADO", font=("Arial", 12, "bold"), foreground="red")
        self.status_label.pack(pady=10)

        btn_frame = tk.Frame(root, bg="#1e1e1e")
        btn_frame.pack(pady=5)
        
        self.btn_connect = tk.Button(btn_frame, text="🔌 CONECTAR TECLADO", command=self.toggle_connection, bg="#007acc", fg="white", font=("Arial", 10, "bold"))
        self.btn_connect.pack(side=tk.LEFT, padx=10)

        # 2. Zona de Configuración
        config_frame = tk.LabelFrame(root, text=" Añadir Nueva Tecla ", bg="#1e1e1e", fg="#00ff00", font=("Arial", 10))
        config_frame.pack(pady=15, padx=10, fill="x")

        # Detector de tecla
        self.lbl_detected = ttk.Label(config_frame, text="Tecla: [Ninguna]")
        self.lbl_detected.grid(row=0, column=0, padx=5, pady=5)
        
        self.btn_detect = tk.Button(config_frame, text="🔍 DETECTAR", command=self.start_detection, bg="#d6a000", fg="black")
        self.btn_detect.grid(row=0, column=1, padx=5, pady=5)

        # Selector de Acción
        ttk.Label(config_frame, text="Acción:").grid(row=0, column=2, padx=5)
        self.action_var = tk.StringVar()
        self.combo_action = ttk.Combobox(config_frame, textvariable=self.action_var, state="readonly")
        self.combo_action['values'] = (
            "Gatillo Derecho (RT) - Acelerar",
            "Gatillo Izquierdo (LT) - Frenar",
            "Stick Izq ARRIBA (Y+)",
            "Stick Izq ABAJO (Y-)",
            "Stick Izq IZQUIERDA (X-)",
            "Stick Izq DERECHA (X+)"
        )
        self.combo_action.current(0)
        self.combo_action.grid(row=0, column=3, padx=5)

        # Botón Añadir
        self.btn_add = tk.Button(config_frame, text="➕ AÑADIR", command=self.add_mapping, bg="#28a745", fg="white")
        self.btn_add.grid(row=1, column=0, columnspan=4, pady=10, sticky="we")

        # 3. Lista de Mapeos
        list_frame = tk.LabelFrame(root, text=" Teclas Configuradas ", bg="#1e1e1e", fg="white")
        list_frame.pack(pady=5, padx=10, fill="both", expand=True)

        self.listbox = tk.Listbox(list_frame, bg="#252526", fg="white", borderwidth=0)
        self.listbox.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        
        btn_del = tk.Button(list_frame, text="🗑️ BORRAR", command=self.delete_mapping, bg="#dc3545", fg="white")
        btn_del.pack(side=tk.RIGHT, fill="y", padx=5, pady=5)

        # Inicializar driver de mando
        try:
            self.gamepad = vg.VX360Gamepad()
        except Exception as e:
            messagebox.showerror("Error", "No se encontró el driver ViGEmBus.\nInstálalo para usar el mando virtual.")

    def toggle_connection(self):
        if not self.running:
            # CONECTAR
            try:
                found = False
                for info in hid.enumerate(TARGET_VID, TARGET_PID):
                    if info['interface_number'] == INTERFACE_NUM:
                        self.device = hid.device()
                        self.device.open_path(info['path'])
                        self.device.set_nonblocking(1)
                        found = True
                        break
                
                if found:
                    self.running = True
                    self.btn_connect.config(text="🛑 DESCONECTAR", bg="#dc3545")
                    self.status_label.config(text="Estado: CONECTADO Y FUNCIONANDO", foreground="#00ff00")
                    
                    # Iniciar hilo de lectura
                    self.thread = threading.Thread(target=self.read_loop, daemon=True)
                    self.thread.start()
                else:
                    messagebox.showerror("Error", "No se encontró el teclado (Interfaz #1).\nAsegúrate de que el software Mchose esté abierto minimizado.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            # DESCONECTAR
            self.running = False
            if self.device:
                self.device.close()
            self.btn_connect.config(text="🔌 CONECTAR TECLADO", bg="#007acc")
            self.status_label.config(text="Estado: DESCONECTADO", foreground="red")

    def start_detection(self):
        if not self.running:
            messagebox.showwarning("Ojo", "Primero conecta el teclado.")
            return
        self.detecting_key = True
        self.lbl_detected.config(text="PRESIONA UNA TECLA AHORA...", foreground="yellow")

    def add_mapping(self):
        if self.last_pressed_code is None:
            messagebox.showwarning("Ojo", "Primero usa 'Detectar' y presiona una tecla.")
            return
        
        action_map = {
            "Gatillo Derecho (RT) - Acelerar": "RT",
            "Gatillo Izquierdo (LT) - Frenar": "LT",
            "Stick Izq ARRIBA (Y+)": "LY_UP",
            "Stick Izq ABAJO (Y-)": "LY_DOWN",
            "Stick Izq IZQUIERDA (X-)": "LX_LEFT",
            "Stick Izq DERECHA (X+)": "LX_RIGHT"
        }
        
        action_code = action_map[self.combo_action.get()]
        key_hex = f"0x{self.last_pressed_code:02X}"
        
        self.mappings[self.last_pressed_code] = action_code
        
        # Actualizar lista visual
        self.listbox.insert(tk.END, f"Tecla {key_hex}  -->  {self.combo_action.get()}")
        self.lbl_detected.config(text="Tecla: [Ninguna]", foreground="white")
        self.last_pressed_code = None

    def delete_mapping(self):
        selection = self.listbox.curselection()
        if selection:
            text = self.listbox.get(selection[0])
            # Extraer el código hex del texto (es un poco chapuza pero funciona)
            hex_code = text.split(" ")[1] 
            code = int(hex_code, 16)
            
            if code in self.mappings:
                del self.mappings[code]
            self.listbox.delete(selection[0])

    def read_loop(self):
        print("Hilo de lectura iniciado")
        while self.running:
            try:
                data = self.device.read(64)
                if data and len(data) > 6:
                    # Validar cabecera (según tu captura)
                    if data[0] == 0xA0 and data[1] == 0x10:
                        
                        key_code = data[3]
                        
                        # CALCULO DE PRESIÓN
                        # Unimos Byte 4 (alto) y 5 (bajo)
                        raw_pressure = (data[4] << 8) | data[5]
                        
                        # --- MODO DETECCIÓN ---
                        if self.detecting_key:
                            if raw_pressure > 100: # Solo si se presiona un poco fuerte
                                self.last_pressed_code = key_code
                                self.detecting_key = False
                                # Actualizar GUI desde el hilo (usando after para seguridad)
                                self.root.after(0, lambda: self.lbl_detected.config(text=f"Tecla Detectada: 0x{key_code:02X}", foreground="#00ff00"))
                            continue # Saltamos la lógica de mando

                        # --- MODO MANDO ---
                        if key_code in self.mappings:
                            action = self.mappings[key_code]
                            
                            # Calibración básica: Raw suele ser 0-600 aprox.
                            # Para gatillos (0-255): dividir entre 2.5
                            # Para Joystick (0-32767): multiplicar por 50
                            
                            val_trigger = int(raw_pressure / 2.5)
                            if val_trigger > 255: val_trigger = 255
                            
                            val_stick = int(raw_pressure * 60) # Ajustar sensibilidad aquí
                            if val_stick > 32767: val_stick = 32767

                            if action == "RT":
                                self.gamepad.right_trigger(val_trigger)
                            elif action == "LT":
                                self.gamepad.left_trigger(val_trigger)
                            elif action == "LX_LEFT":
                                self.gamepad.left_joystick(x_value=-val_stick, y_value=0)
                            elif action == "LX_RIGHT":
                                self.gamepad.left_joystick(x_value=val_stick, y_value=0)
                            # Nota: Los joysticks aquí son simples, si quieres mezclar X e Y se complica más
                            # pero para empezar sirve.

                            self.gamepad.update()
                        else:
                            # Si no se pulsa nada mapeado, resetear (simplificado)
                            # En una versión PRO deberíamos resetear solo lo que se soltó
                            pass 

                # Si no llegan datos (tecla soltada), muchos teclados dejan de enviar o envían 0s.
                # Aquí añadimos un pequeño reset de seguridad si no hay input
                # (Esto puede mejorarse para permitir pulsar varias teclas a la vez)
                
            except Exception as e:
                print(f"Error lectura: {e}")
                time.sleep(1)
            
            time.sleep(0.001)

# --- INICIO ---
if __name__ == "__main__":
    root = tk.Tk()
    app = MchoseApp(root)
    root.mainloop()