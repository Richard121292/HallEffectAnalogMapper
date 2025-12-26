import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import hid
import vgamepad as vg
import threading
import time
import json
import os
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════════════
#                          MCHOSE STUDIO PRO v2.0
#        Controlador Hall Effect → Gamepad Virtual (Sin software Mchose)
# ══════════════════════════════════════════════════════════════════════════════

# --- CONFIGURACIÓN HARDWARE ---
TARGET_VID = 0x41E4
TARGET_PID = 0x211A
CONFIG_FILE = "mchose_config.json"

# --- MAPA DE TECLAS HID ESTÁNDAR ---
HID_MAP = {
    0x29: "ESC", 0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4", 0x3E: "F5", 
    0x3F: "F6", 0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10", 0x44: "F11", 0x45: "F12",
    0x35: "`", 0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5", 0x23: "6", 
    0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0", 0x2D: "-", 0x2E: "=", 0x2A: "BACK",
    0x2B: "TAB", 0x14: "Q", 0x1A: "W", 0x08: "E", 0x15: "R", 0x17: "T", 0x1C: "Y", 
    0x18: "U", 0x0C: "I", 0x12: "O", 0x13: "P", 0x2F: "[", 0x30: "]", 0x31: "\\",
    0x39: "CAPS", 0x04: "A", 0x16: "S", 0x07: "D", 0x09: "F", 0x0A: "G", 0x0B: "H", 
    0x0D: "J", 0x0E: "K", 0x0F: "L", 0x33: ";", 0x34: "'", 0x28: "ENTER",
    0xE1: "LSHFT", 0x1D: "Z", 0x1B: "X", 0x06: "C", 0x19: "V", 0x05: "B", 0x11: "N", 
    0x10: "M", 0x36: ",", 0x37: ".", 0x38: "/", 0xE5: "RSHFT",
    0xE0: "LCTRL", 0xE2: "WIN", 0xE3: "LALT", 0x2C: "SPACE", 0xE6: "RALT", 
    0xE7: "FN", 0x65: "MENU", 0xE4: "RCTRL",
    # Teclas adicionales
    0x46: "PRTSC", 0x47: "SCRLK", 0x48: "PAUSE",
    0x49: "INS", 0x4A: "HOME", 0x4B: "PGUP",
    0x4C: "DEL", 0x4D: "END", 0x4E: "PGDN",
    0x4F: "→", 0x50: "←", 0x51: "↓", 0x52: "↑",
}
NAME_TO_HID = {v: k for k, v in HID_MAP.items()}

# --- ACCIONES DE GAMEPAD ---
CONTROLLER_ACTIONS = [
    "Ninguna",
    "🎮 RT - Acelerar",
    "🎮 LT - Frenar", 
    "🕹️ Stick Izq: ARRIBA",
    "🕹️ Stick Izq: ABAJO",
    "🕹️ Stick Izq: IZQUIERDA",
    "🕹️ Stick Izq: DERECHA",
    "🕹️ Stick Der: ARRIBA",
    "🕹️ Stick Der: ABAJO",
    "🕹️ Stick Der: IZQUIERDA",
    "🕹️ Stick Der: DERECHA",
    "🔘 Botón A",
    "🔘 Botón B",
    "🔘 Botón X",
    "🔘 Botón Y",
    "🔘 LB (Bumper Izq)",
    "🔘 RB (Bumper Der)",
    "🔘 Start",
    "🔘 Back",
]

# Colores del tema
COLORS = {
    "bg_dark": "#0d1117",
    "bg_card": "#161b22",
    "bg_input": "#21262d",
    "accent": "#58a6ff",
    "accent_hover": "#79b8ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "text": "#c9d1d9",
    "text_dim": "#8b949e",
    "border": "#30363d",
    "key_default": "#21262d",
    "key_mapped": "#1f6feb",
    "key_active": "#238636",
    "key_selected": "#9e6a03",
}


class MchoseStudioPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configuración de ventana
        self.title("⌨️ MCHOSE STUDIO PRO")
        self.geometry("1400x800")
        self.minsize(1200, 700)
        
        # Tema
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Estado de la aplicación
        self.running = False
        self.devices = []  # Lista de dispositivos HID conectados
        self.gamepad = None
        self.mappings = {}
        self.settings = {
            "deadzone": 30,
            "sensitivity": 1.0,
            "max_pressure": 600,  # Valor máximo típico del Hall Effect
            "analog_mode": True,  # True = analógico, False = binario (on/off)
            "curve": "linear",    # linear, aggressive, smooth
        }
        self.active_keys = {}
        self.key_pressures = defaultdict(int)  # Presiones por tecla
        self.buttons_ui = {}
        self.selected_key_code = None
        self.data_mode = "unknown"  # "analog_0xA0", "hid_standard", "unknown"
        self.prev_active_keys = set()  # Para actualizar solo teclas que cambian
        
        # Variables para throttling de UI (evitar lag)
        self.last_ui_update = 0
        self.ui_update_interval = 0.033  # ~30 FPS para UI
        self.pending_ui_update = False
        self.last_gamepad_values = (0, 0, 0, 0, 0, 0)  # rt, lt, lx, ly, rx, ry
        
        # Cargar configuración
        self.load_config()
        
        # Construir UI
        self.build_ui()
        
        # Inicializar gamepad virtual
        self.init_gamepad()
        
        # Auto-conectar al inicio
        self.after(500, self.auto_connect)

    def build_ui(self):
        """Construye toda la interfaz de usuario"""
        # Grid principal
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # ══════════════════ PANEL IZQUIERDO ══════════════════
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        self.left_panel.grid_rowconfigure(1, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)
        
        # Header con estado y controles
        self.build_header()
        
        # Visualización del teclado
        self.build_keyboard()
        
        # Barra de información inferior
        self.build_info_bar()
        
        # ══════════════════ PANEL DERECHO ══════════════════
        self.right_panel = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        
        # Scroll para el panel derecho
        self.build_config_panel()

    def build_header(self):
        """Barra superior con estado y controles"""
        header = ctk.CTkFrame(self.left_panel, fg_color=COLORS["bg_card"], corner_radius=12, height=70)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)
        
        # Logo/Título
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        ctk.CTkLabel(
            title_frame, 
            text="⌨️ MCHOSE STUDIO PRO",
            font=("Segoe UI", 22, "bold"),
            text_color=COLORS["accent"]
        ).pack(side="left")
        
        ctk.CTkLabel(
            title_frame,
            text="  v2.0",
            font=("Segoe UI", 12),
            text_color=COLORS["text_dim"]
        ).pack(side="left", pady=(8, 0))
        
        # Centro - Estado
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=1, pady=15)
        
        self.status_dot = ctk.CTkLabel(
            status_frame,
            text="●",
            font=("Segoe UI", 20),
            text_color=COLORS["error"]
        )
        self.status_dot.pack(side="left", padx=(0, 8))
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Desconectado",
            font=("Segoe UI", 14),
            text_color=COLORS["text_dim"]
        )
        self.status_label.pack(side="left")
        
        self.mode_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=("Segoe UI", 11),
            text_color=COLORS["text_dim"]
        )
        self.mode_label.pack(side="left", padx=(15, 0))
        
        # Derecha - Botón conectar
        self.btn_connect = ctk.CTkButton(
            header,
            text="🔌 CONECTAR",
            font=("Segoe UI", 13, "bold"),
            fg_color=COLORS["success"],
            hover_color="#2ea043",
            width=140,
            height=40,
            corner_radius=8,
            command=self.toggle_connection
        )
        self.btn_connect.grid(row=0, column=2, padx=20, pady=15, sticky="e")

    def build_keyboard(self):
        """Visualización interactiva del teclado"""
        kb_frame = ctk.CTkFrame(self.left_panel, fg_color=COLORS["bg_card"], corner_radius=12)
        kb_frame.grid(row=1, column=0, sticky="nsew")
        
        # Título del teclado
        kb_header = ctk.CTkFrame(kb_frame, fg_color="transparent")
        kb_header.pack(fill="x", padx=20, pady=(15, 5))
        
        ctk.CTkLabel(
            kb_header,
            text="🎹 TECLADO HALL EFFECT",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left")
        
        # Leyenda
        legend_frame = ctk.CTkFrame(kb_header, fg_color="transparent")
        legend_frame.pack(side="right")
        
        legends = [
            ("●", COLORS["key_default"], "Sin mapear"),
            ("●", COLORS["key_mapped"], "Mapeada"),
            ("●", COLORS["key_active"], "Activa"),
            ("●", COLORS["key_selected"], "Seleccionada"),
        ]
        for dot, color, text in legends:
            ctk.CTkLabel(legend_frame, text=dot, text_color=color, font=("Segoe UI", 12)).pack(side="left", padx=(10, 2))
            ctk.CTkLabel(legend_frame, text=text, text_color=COLORS["text_dim"], font=("Segoe UI", 10)).pack(side="left")
        
        # Contenedor del teclado
        container = ctk.CTkFrame(kb_frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Centrar el teclado
        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        
        # Filas del teclado
        rows = [
            ["ESC", None, "F1", "F2", "F3", "F4", None, "F5", "F6", "F7", "F8", None, "F9", "F10", "F11", "F12"],
            ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "BACK"],
            ["TAB", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
            ["CAPS", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "ENTER"],
            ["LSHFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "RSHFT"],
            ["LCTRL", "WIN", "LALT", "SPACE", "RALT", "FN", "MENU", "RCTRL"],
        ]
        
        for row_data in rows:
            row_frame = ctk.CTkFrame(inner, fg_color="transparent")
            row_frame.pack(pady=2)
            
            for key in row_data:
                if key is None:
                    # Espaciador
                    ctk.CTkFrame(row_frame, fg_color="transparent", width=20, height=45).pack(side="left", padx=1)
                    continue
                
                code = NAME_TO_HID.get(key, 0)
                
                # Tamaño de tecla
                width = 48
                if key == "SPACE":
                    width = 280
                elif key in ["BACK", "TAB", "CAPS", "ENTER", "LSHFT", "RSHFT"]:
                    width = 80
                elif key in ["LCTRL", "RCTRL", "LALT", "RALT", "WIN", "FN", "MENU"]:
                    width = 58
                
                btn = ctk.CTkButton(
                    row_frame,
                    text=key,
                    width=width,
                    height=45,
                    corner_radius=6,
                    fg_color=COLORS["key_default"],
                    hover_color=COLORS["bg_input"],
                    font=("Segoe UI", 11),
                    text_color=COLORS["text"],
                    border_width=1,
                    border_color=COLORS["border"],
                    command=lambda c=code, n=key: self.select_key(c, n)
                )
                btn.pack(side="left", padx=2)
                
                if code:
                    self.buttons_ui[code] = btn
        
        self.refresh_keyboard_visuals()

    def build_info_bar(self):
        """Barra de información inferior"""
        info_bar = ctk.CTkFrame(self.left_panel, fg_color=COLORS["bg_card"], corner_radius=12, height=50)
        info_bar.grid(row=2, column=0, sticky="ew", pady=(15, 0))
        info_bar.grid_propagate(False)
        
        # Info de teclas mapeadas
        self.lbl_mapped_count = ctk.CTkLabel(
            info_bar,
            text="📋 0 teclas mapeadas",
            font=("Segoe UI", 11),
            text_color=COLORS["text_dim"]
        )
        self.lbl_mapped_count.pack(side="left", padx=20, pady=15)
        
        # Datos recibidos
        self.lbl_data_info = ctk.CTkLabel(
            info_bar,
            text="📡 Sin datos",
            font=("Segoe UI", 11),
            text_color=COLORS["text_dim"]
        )
        self.lbl_data_info.pack(side="right", padx=20, pady=15)

    def build_config_panel(self):
        """Panel de configuración lateral"""
        # Scroll
        scroll = ctk.CTkScrollableFrame(
            self.right_panel, 
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_input"],
            scrollbar_button_hover_color=COLORS["border"]
        )
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # ══════════ SECCIÓN: TECLA SELECCIONADA ══════════
        self.build_section_header(scroll, "⚙️ CONFIGURACIÓN DE TECLA")
        
        key_card = ctk.CTkFrame(scroll, fg_color=COLORS["bg_input"], corner_radius=8)
        key_card.pack(fill="x", padx=10, pady=(0, 15))
        
        self.lbl_selected_key = ctk.CTkLabel(
            key_card,
            text="Selecciona una tecla del teclado",
            font=("Segoe UI", 13),
            text_color=COLORS["warning"]
        )
        self.lbl_selected_key.pack(pady=15)
        
        ctk.CTkLabel(
            key_card,
            text="Acción del Gamepad:",
            font=("Segoe UI", 11),
            text_color=COLORS["text_dim"]
        ).pack(anchor="w", padx=15)
        
        self.action_var = ctk.StringVar(value="Ninguna")
        self.combo_action = ctk.CTkComboBox(
            key_card,
            values=CONTROLLER_ACTIONS,
            variable=self.action_var,
            command=self.on_action_change,
            state="disabled",
            font=("Segoe UI", 12),
            dropdown_font=("Segoe UI", 11),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_input"],
            width=250
        )
        self.combo_action.pack(fill="x", padx=15, pady=(5, 15))
        
        # ══════════ SECCIÓN: AJUSTES ANALÓGICOS ══════════
        self.build_section_header(scroll, "📊 AJUSTES ANALÓGICOS")
        
        analog_card = ctk.CTkFrame(scroll, fg_color=COLORS["bg_input"], corner_radius=8)
        analog_card.pack(fill="x", padx=10, pady=(0, 15))
        
        # Modo analógico/binario
        mode_frame = ctk.CTkFrame(analog_card, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            mode_frame,
            text="Modo de entrada:",
            font=("Segoe UI", 11),
            text_color=COLORS["text"]
        ).pack(side="left")
        
        self.analog_switch = ctk.CTkSwitch(
            mode_frame,
            text="Analógico",
            font=("Segoe UI", 11),
            progress_color=COLORS["accent"],
            command=self.toggle_analog_mode
        )
        self.analog_switch.pack(side="right")
        if self.settings["analog_mode"]:
            self.analog_switch.select()
        
        # Sliders
        self.deadzone_slider = self.create_slider(
            analog_card, 
            "Zona Muerta", 
            0, 150, 
            self.settings["deadzone"],
            "deadzone",
            "Ignora presiones menores a este valor"
        )
        
        self.sensitivity_slider = self.create_slider(
            analog_card,
            "Sensibilidad",
            0.5, 3.0,
            self.settings["sensitivity"],
            "sensitivity",
            "Multiplica la respuesta del input"
        )
        
        self.max_pressure_slider = self.create_slider(
            analog_card,
            "Presión Máxima",
            200, 1000,
            self.settings["max_pressure"],
            "max_pressure",
            "Valor máximo del sensor Hall Effect"
        )
        
        # Curva de respuesta
        curve_frame = ctk.CTkFrame(analog_card, fg_color="transparent")
        curve_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkLabel(
            curve_frame,
            text="Curva de Respuesta:",
            font=("Segoe UI", 11),
            text_color=COLORS["text"]
        ).pack(anchor="w")
        
        self.curve_var = ctk.StringVar(value=self.settings["curve"])
        curves_frame = ctk.CTkFrame(curve_frame, fg_color="transparent")
        curves_frame.pack(fill="x", pady=5)
        
        for curve in ["linear", "aggressive", "smooth"]:
            ctk.CTkRadioButton(
                curves_frame,
                text=curve.capitalize(),
                variable=self.curve_var,
                value=curve,
                font=("Segoe UI", 11),
                fg_color=COLORS["accent"],
                command=lambda: self.update_setting("curve", self.curve_var.get())
            ).pack(side="left", padx=(0, 15))
        
        # ══════════ SECCIÓN: MONITOR EN VIVO ══════════
        self.build_section_header(scroll, "📺 MONITOR EN VIVO")
        
        monitor_card = ctk.CTkFrame(scroll, fg_color=COLORS["bg_input"], corner_radius=8)
        monitor_card.pack(fill="x", padx=10, pady=(0, 15))
        
        self.bars = {}
        self.bars['rt'] = self.create_monitor_bar(monitor_card, "🎮 RT (Gas)", COLORS["success"])
        self.bars['lt'] = self.create_monitor_bar(monitor_card, "🎮 LT (Freno)", COLORS["error"])
        self.bars['lx'] = self.create_monitor_bar(monitor_card, "🕹️ Stick X", COLORS["accent"], center=True)
        self.bars['ly'] = self.create_monitor_bar(monitor_card, "🕹️ Stick Y", COLORS["accent"], center=True)
        
        # ══════════ SECCIÓN: DEBUG ══════════
        self.build_section_header(scroll, "🔧 DEBUG")
        
        debug_card = ctk.CTkFrame(scroll, fg_color=COLORS["bg_input"], corner_radius=8)
        debug_card.pack(fill="x", padx=10, pady=(0, 15))
        
        self.debug_text = ctk.CTkTextbox(
            debug_card,
            height=100,
            font=("Consolas", 10),
            fg_color=COLORS["bg_dark"],
            text_color=COLORS["text_dim"],
            corner_radius=6
        )
        self.debug_text.pack(fill="x", padx=10, pady=10)
        
        # Botones de acción
        btn_frame = ctk.CTkFrame(debug_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(
            btn_frame,
            text="🔄 Resetear Config",
            font=("Segoe UI", 11),
            fg_color=COLORS["warning"],
            hover_color="#b88a1b",
            width=120,
            height=32,
            command=self.reset_config
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Borrar Mapeos",
            font=("Segoe UI", 11),
            fg_color=COLORS["error"],
            hover_color="#da3633",
            width=120,
            height=32,
            command=self.clear_mappings
        ).pack(side="left")

    def build_section_header(self, parent, text):
        """Crea un encabezado de sección"""
        ctk.CTkLabel(
            parent,
            text=text,
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=15, pady=(15, 8))

    def create_slider(self, parent, label, min_v, max_v, default, key, tooltip=""):
        """Crea un slider con etiqueta"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=8)
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x")
        
        lbl = ctk.CTkLabel(
            header,
            text=label,
            font=("Segoe UI", 11),
            text_color=COLORS["text"]
        )
        lbl.pack(side="left")
        
        val_lbl = ctk.CTkLabel(
            header,
            text=f"{default:.1f}" if isinstance(default, float) else str(int(default)),
            font=("Segoe UI", 11, "bold"),
            text_color=COLORS["accent"]
        )
        val_lbl.pack(side="right")
        
        def callback(v):
            if isinstance(default, float):
                self.settings[key] = round(v, 2)
                val_lbl.configure(text=f"{v:.2f}")
            else:
                self.settings[key] = int(v)
                val_lbl.configure(text=str(int(v)))
            self.save_config()
        
        slider = ctk.CTkSlider(
            frame,
            from_=min_v,
            to=max_v,
            command=callback,
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"]
        )
        slider.set(default)
        slider.pack(fill="x", pady=(5, 0))
        
        if tooltip:
            ctk.CTkLabel(
                frame,
                text=tooltip,
                font=("Segoe UI", 9),
                text_color=COLORS["text_dim"]
            ).pack(anchor="w")
        
        return slider

    def create_monitor_bar(self, parent, label, color, center=False):
        """Crea una barra de monitor"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=5)
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header,
            text=label,
            font=("Segoe UI", 10),
            text_color=COLORS["text_dim"]
        ).pack(side="left")
        
        val_lbl = ctk.CTkLabel(
            header,
            text="0%",
            font=("Segoe UI", 10),
            text_color=color
        )
        val_lbl.pack(side="right")
        
        bar = ctk.CTkProgressBar(
            frame,
            progress_color=color,
            fg_color=COLORS["bg_dark"],
            corner_radius=4,
            height=12
        )
        bar.pack(fill="x", pady=(3, 0))
        bar.set(0.5 if center else 0)
        bar.val_label = val_lbl
        bar.is_center = center
        
        return bar

    # ══════════════════════════════════════════════════════════════════════════
    #                              LÓGICA PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def init_gamepad(self):
        """Inicializa el gamepad virtual"""
        try:
            self.gamepad = vg.VX360Gamepad()
            self.log_debug("✅ Gamepad virtual inicializado")
        except Exception as e:
            self.log_debug(f"❌ Error gamepad: {e}")
            messagebox.showwarning(
                "ViGEmBus",
                "No se pudo inicializar el gamepad virtual.\n"
                "Instala ViGEmBus desde:\nhttps://github.com/ViGEm/ViGEmBus/releases"
            )

    def auto_connect(self):
        """Intenta conectar automáticamente al inicio"""
        if not self.running:
            self.toggle_connection()

    def toggle_connection(self):
        """Conecta o desconecta del teclado"""
        if not self.running:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        """Conecta al teclado HID"""
        try:
            # Cerrar dispositivos anteriores
            for dev in self.devices:
                try:
                    dev["device"].close()
                except:
                    pass
            self.devices = []
            
            # Buscar todas las interfaces del teclado
            device_list = hid.enumerate(TARGET_VID, TARGET_PID)
            
            if not device_list:
                self.update_status("No detectado", COLORS["error"])
                self.log_debug("❌ Teclado no encontrado")
                messagebox.showerror(
                    "Error",
                    "No se detectó el teclado Mchose.\n"
                    "Verifica que esté conectado por cable USB."
                )
                return
            
            self.log_debug(f"🔍 Encontradas {len(device_list)} interfaces")
            
            # Intentar conectar a todas las interfaces excepto la 0 (bloqueada)
            for info in device_list:
                interface = info.get('interface_number', -1)
                
                # Saltar interfaz 0 (Windows la bloquea)
                if interface == 0:
                    continue
                
                try:
                    dev = hid.device()
                    dev.open_path(info['path'])
                    dev.set_nonblocking(1)
                    
                    self.devices.append({
                        "device": dev,
                        "interface": interface,
                        "path": info['path']
                    })
                    self.log_debug(f"  ✅ Interfaz #{interface} conectada")
                except Exception as e:
                    self.log_debug(f"  ❌ Interfaz #{interface}: {e}")
            
            if self.devices:
                self.running = True
                self.update_status("Conectado", COLORS["success"])
                self.btn_connect.configure(text="⏹️ DESCONECTAR", fg_color=COLORS["error"])
                
                # Iniciar hilo de lectura
                threading.Thread(target=self.read_loop, daemon=True).start()
                
                # Iniciar actualizador de UI (en el hilo principal de Tkinter)
                self.start_ui_updater()
                
                self.log_debug(f"🎮 Leyendo {len(self.devices)} interfaces...")
            else:
                self.update_status("Sin acceso", COLORS["error"])
                self.log_debug("❌ No se pudo acceder a ninguna interfaz")
                
        except Exception as e:
            self.log_debug(f"❌ Error: {e}")
            messagebox.showerror("Error", str(e))

    def disconnect(self):
        """Desconecta del teclado"""
        self.running = False
        
        for dev in self.devices:
            try:
                dev["device"].close()
            except:
                pass
        self.devices = []
        
        self.active_keys = {}
        self.key_pressures = defaultdict(int)
        
        self.update_status("Desconectado", COLORS["error"])
        self.btn_connect.configure(text="🔌 CONECTAR", fg_color=COLORS["success"])
        self.mode_label.configure(text="")
        self.log_debug("🔌 Desconectado")
        
        # Reset barras de monitor
        self.update_monitor(0, 0, 0, 0)
        self.refresh_keyboard_visuals()

    def read_loop(self):
        """Bucle principal de lectura de datos HID"""
        while self.running:
            try:
                # Leer datos de todos los dispositivos
                for dev_info in self.devices:
                    dev = dev_info["device"]
                    interface = dev_info["interface"]
                    
                    data = dev.read(64)
                    if data:
                        self.process_hid_data(data, interface)
                
                time.sleep(0.001)  # 1ms polling para menor delay
                
            except Exception as e:
                time.sleep(0.05)
    
    def start_ui_updater(self):
        """Inicia el actualizador periódico de UI"""
        if not self.running:
            return
        
        # Actualizar UI
        rt, lt, lx, ly, rx, ry = self.last_gamepad_values
        
        # Actualizar barras del monitor
        try:
            self.bars['rt'].set(max(0.001, rt / 255))
            self.bars['rt'].val_label.configure(text=f"{int(rt/2.55)}%")
            
            self.bars['lt'].set(max(0.001, lt / 255))
            self.bars['lt'].val_label.configure(text=f"{int(lt/2.55)}%")
            
            norm_lx = (lx + 32767) / 65534
            self.bars['lx'].set(norm_lx)
            self.bars['lx'].val_label.configure(text=f"{int((lx/32767)*100)}%")
            
            norm_ly = (ly + 32767) / 65534
            self.bars['ly'].set(norm_ly)
            self.bars['ly'].val_label.configure(text=f"{int((ly/32767)*100)}%")
        except:
            pass
        
        # Actualizar teclado visual solo para teclas que cambian
        active_set = set(self.active_keys.keys())
        changed_keys = active_set ^ self.prev_active_keys
        if self.selected_key_code:
            changed_keys.add(self.selected_key_code)
        for code in changed_keys:
            btn = self.buttons_ui.get(code)
            if not btn:
                continue
            if code in active_set:
                btn.configure(
                    fg_color=COLORS["key_active"],
                    text_color="white",
                    border_color=COLORS["success"]
                )
            elif code == self.selected_key_code:
                btn.configure(
                    fg_color=COLORS["key_selected"],
                    text_color="white",
                    border_color=COLORS["warning"]
                )
            elif str(code) in self.mappings:
                btn.configure(
                    fg_color=COLORS["key_mapped"],
                    text_color="white",
                    border_color=COLORS["accent"]
                )
            else:
                btn.configure(
                    fg_color=COLORS["key_default"],
                    text_color=COLORS["text"],
                    border_color=COLORS["border"]
                )
        self.prev_active_keys = active_set
        
        # Programar siguiente actualización (8ms ≈ 120 FPS visuales)
        self.after(8, self.start_ui_updater)

    def process_hid_data(self, data, interface):
        """Procesa los datos HID recibidos"""
        
        # ═══════════ MODO 1: Datos analógicos del software Mchose (0xA0) ═══════════
        if len(data) > 6 and data[0] == 0xA0:
            if self.data_mode != "analog_0xA0":
                self.data_mode = "analog_0xA0"
                self.after(0, lambda: self.mode_label.configure(text="[Modo: Analógico 0xA0]"))
            
            key_code = data[3]
            raw_pressure = (data[4] << 8) | data[5]
            
            if raw_pressure > 0:
                self.active_keys[key_code] = True
                self.key_pressures[key_code] = raw_pressure
            else:
                if key_code in self.active_keys:
                    del self.active_keys[key_code]
                    self.key_pressures[key_code] = 0
            
            self.process_gamepad_output()
            return
        
        # ═══════════ MODO 2: HID Estándar de teclado ═══════════
        # Formato típico: [Modifier, Reserved, Key1, Key2, Key3, Key4, Key5, Key6]
        if len(data) >= 8 and interface == 1:
            modifier = data[0]
            keys = data[2:8]
            
            if self.data_mode != "hid_standard":
                self.data_mode = "hid_standard"
                self.after(0, lambda: self.mode_label.configure(text="[Modo: HID Estándar]"))
            
            # Limpiar teclas anteriores
            old_keys = set(self.active_keys.keys())
            new_keys = set()
            
            # Procesar modificadores (Ctrl, Shift, Alt, Win)
            modifier_map = {
                0x01: 0xE0,  # Left Ctrl
                0x02: 0xE1,  # Left Shift
                0x04: 0xE3,  # Left Alt
                0x08: 0xE2,  # Left Win
                0x10: 0xE4,  # Right Ctrl
                0x20: 0xE5,  # Right Shift
                0x40: 0xE6,  # Right Alt
                0x80: 0xE7,  # Right Win
            }
            
            for mask, code in modifier_map.items():
                if modifier & mask:
                    new_keys.add(code)
                    self.active_keys[code] = True
                    self.key_pressures[code] = self.settings["max_pressure"]
            
            # Procesar teclas normales
            for key in keys:
                if key > 0:
                    new_keys.add(key)
                    self.active_keys[key] = True
                    self.key_pressures[key] = self.settings["max_pressure"]
            
            # Eliminar teclas que ya no están presionadas
            for old_key in old_keys - new_keys:
                if old_key in self.active_keys:
                    del self.active_keys[old_key]
                self.key_pressures[old_key] = 0
            
            self.process_gamepad_output()
            return
        
        # ═══════════ MODO 3: Datos desconocidos ═══════════
        # No hacer nada con datos desconocidos para evitar spam
        pass

    def process_gamepad_output(self):
        """Convierte las teclas activas en salida de gamepad"""
        if not self.gamepad:
            return
        
        lx, ly, rx, ry = 0, 0, 0, 0
        lt, rt = 0, 0
        buttons = 0
        
        for key_code in list(self.active_keys.keys()):
            str_code = str(key_code)
            
            if str_code not in self.mappings:
                continue
            
            action = self.mappings[str_code]
            raw_pressure = self.key_pressures.get(key_code, 0)
            
            # Calcular valor procesado
            val = self.process_analog_value(raw_pressure)
            trigger_val = min(255, int((val / 32767) * 255))
            
            # Aplicar acción
            if "RT" in action:
                rt = max(rt, trigger_val)
            elif "LT" in action:
                lt = max(lt, trigger_val)
            elif "Stick Izq: ARRIBA" in action:
                ly = min(32767, ly + val)
            elif "Stick Izq: ABAJO" in action:
                ly = max(-32767, ly - val)
            elif "Stick Izq: DERECHA" in action:
                lx = min(32767, lx + val)
            elif "Stick Izq: IZQUIERDA" in action:
                lx = max(-32767, lx - val)
            elif "Stick Der: ARRIBA" in action:
                ry = min(32767, ry + val)
            elif "Stick Der: ABAJO" in action:
                ry = max(-32767, ry - val)
            elif "Stick Der: DERECHA" in action:
                rx = min(32767, rx + val)
            elif "Stick Der: IZQUIERDA" in action:
                rx = max(-32767, rx - val)
            elif "Botón A" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_A
            elif "Botón B" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_B
            elif "Botón X" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_X
            elif "Botón Y" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_Y
            elif "LB" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER
            elif "RB" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER
            elif "Start" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_START
            elif "Back" in action and trigger_val > 100:
                buttons |= vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK
        
        # Guardar valores para actualización UI throttled
        self.last_gamepad_values = (rt, lt, lx, ly, rx, ry)
        
        # Enviar al gamepad virtual (esto es rápido, no afecta UI)
        try:
            self.gamepad.reset()
            self.gamepad.left_joystick(x_value=lx, y_value=ly)
            self.gamepad.right_joystick(x_value=rx, y_value=ry)
            self.gamepad.left_trigger(lt)
            self.gamepad.right_trigger(rt)
            
            if buttons:
                for btn_flag in [
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                ]:
                    if buttons & btn_flag:
                        self.gamepad.press_button(btn_flag)
            
            self.gamepad.update()
        except:
            pass

    def process_analog_value(self, raw):
        """Procesa un valor analógico crudo aplicando ajustes"""
        dz = self.settings["deadzone"]
        sens = self.settings["sensitivity"]
        max_p = self.settings["max_pressure"]
        curve = self.settings["curve"]
        
        # Modo binario
        if not self.settings["analog_mode"]:
            return 32767 if raw > dz else 0
        
        # Aplicar deadzone
        if raw < dz:
            return 0
        
        # Normalizar al rango 0-1
        normalized = min(1.0, (raw - dz) / (max_p - dz))
        
        # Aplicar curva
        if curve == "aggressive":
            normalized = normalized ** 0.5  # Raíz cuadrada = más sensible
        elif curve == "smooth":
            normalized = normalized ** 2    # Cuadrado = más suave
        
        # Aplicar sensibilidad y escalar
        val = int(normalized * sens * 32767)
        
        return min(32767, max(0, val))

    def update_monitor(self, rt, lt, lx, ly):
        """Actualiza las barras del monitor"""
        try:
            # RT/LT: 0-255 -> 0-1
            self.bars['rt'].set(rt / 255)
            self.bars['rt'].val_label.configure(text=f"{int(rt/2.55)}%")
            
            self.bars['lt'].set(lt / 255)
            self.bars['lt'].val_label.configure(text=f"{int(lt/2.55)}%")
            
            # Sticks: -32767 a 32767 -> 0-1 (0.5 es centro)
            self.bars['lx'].set((lx + 32767) / 65534)
            self.bars['lx'].val_label.configure(text=f"{int((lx/32767)*100)}%")
            
            self.bars['ly'].set((ly + 32767) / 65534)
            self.bars['ly'].val_label.configure(text=f"{int((ly/32767)*100)}%")
        except:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #                              UI HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def select_key(self, code, name):
        """Selecciona una tecla para configurar"""
        self.selected_key_code = code
        self.lbl_selected_key.configure(text=f"🎯 {name}", text_color=COLORS["accent"])
        self.combo_action.configure(state="normal")
        self.action_var.set(self.mappings.get(str(code), "Ninguna"))
        self.refresh_keyboard_visuals()

    def on_action_change(self, choice):
        """Callback cuando cambia la acción seleccionada"""
        if self.selected_key_code:
            if choice == "Ninguna":
                if str(self.selected_key_code) in self.mappings:
                    del self.mappings[str(self.selected_key_code)]
            else:
                self.mappings[str(self.selected_key_code)] = choice
            
            self.save_config()
            self.refresh_keyboard_visuals()
            self.update_mapped_count()

    def refresh_keyboard_visuals(self):
        """Actualiza los colores de las teclas del teclado"""
        for code, btn in self.buttons_ui.items():
            if code in self.active_keys:
                btn.configure(
                    fg_color=COLORS["key_active"],
                    text_color="white",
                    border_color=COLORS["success"]
                )
            elif code == self.selected_key_code:
                btn.configure(
                    fg_color=COLORS["key_selected"],
                    text_color="white",
                    border_color=COLORS["warning"]
                )
            elif str(code) in self.mappings:
                btn.configure(
                    fg_color=COLORS["key_mapped"],
                    text_color="white",
                    border_color=COLORS["accent"]
                )
            else:
                btn.configure(
                    fg_color=COLORS["key_default"],
                    text_color=COLORS["text"],
                    border_color=COLORS["border"]
                )

    def update_status(self, text, color):
        """Actualiza el indicador de estado"""
        self.status_label.configure(text=text)
        self.status_dot.configure(text_color=color)

    def update_mapped_count(self):
        """Actualiza el contador de teclas mapeadas"""
        count = len(self.mappings)
        self.lbl_mapped_count.configure(text=f"📋 {count} tecla{'s' if count != 1 else ''} mapeada{'s' if count != 1 else ''}")

    def toggle_analog_mode(self):
        """Alterna entre modo analógico y binario"""
        self.settings["analog_mode"] = self.analog_switch.get()
        self.save_config()
        mode = "analógico" if self.settings["analog_mode"] else "binario"
        self.log_debug(f"🔄 Modo cambiado a: {mode}")

    def update_setting(self, key, value):
        """Actualiza una configuración"""
        self.settings[key] = value
        self.save_config()

    def log_debug(self, message):
        """Añade un mensaje al panel de debug"""
        try:
            timestamp = time.strftime("%H:%M:%S")
            self.debug_text.insert("end", f"[{timestamp}] {message}\n")
            self.debug_text.see("end")
            
            # Limitar líneas
            lines = int(self.debug_text.index("end-1c").split(".")[0])
            if lines > 100:
                self.debug_text.delete("1.0", "2.0")
        except:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #                           PERSISTENCIA
    # ══════════════════════════════════════════════════════════════════════════

    def load_config(self):
        """Carga la configuración desde archivo"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.mappings = data.get("mappings", {})
                    saved_settings = data.get("settings", {})
                    self.settings.update(saved_settings)
            except Exception as e:
                print(f"Error cargando config: {e}")

    def save_config(self):
        """Guarda la configuración a archivo"""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "mappings": self.mappings,
                    "settings": self.settings
                }, f, indent=2)
        except Exception as e:
            print(f"Error guardando config: {e}")

    def reset_config(self):
        """Resetea los ajustes a valores por defecto"""
        self.settings = {
            "deadzone": 30,
            "sensitivity": 1.0,
            "max_pressure": 600,
            "analog_mode": True,
            "curve": "linear",
        }
        self.save_config()
        
        # Actualizar UI
        self.deadzone_slider.set(30)
        self.sensitivity_slider.set(1.0)
        self.max_pressure_slider.set(600)
        self.analog_switch.select()
        self.curve_var.set("linear")
        
        self.log_debug("🔄 Ajustes reseteados")
        messagebox.showinfo("Reset", "Ajustes restaurados a valores por defecto")

    def clear_mappings(self):
        """Borra todos los mapeos"""
        if messagebox.askyesno("Confirmar", "¿Borrar todos los mapeos de teclas?"):
            self.mappings = {}
            self.save_config()
            self.refresh_keyboard_visuals()
            self.update_mapped_count()
            self.log_debug("🗑️ Mapeos borrados")


# ══════════════════════════════════════════════════════════════════════════════
#                                   MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = MchoseStudioPro()
    app.mainloop()
