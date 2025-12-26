"""
Hall Effect Analog Mapper
Generic Hall keyboard-to-gamepad mapper with response curves

USAGE:
    python HallAnalogMapper.py          # Full UI
    python HallAnalogMapper.py --noui   # Headless (minimal overhead)
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog
import hid
import vgamepad as vg
import threading
import time
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict

CONFIG_FILE = "hall_config.json"
LEGACY_CONFIG_FILE = "mchose_config.json"

# --- MAPA DE TECLAS ---
HID_MAP = {
    0x29: "ESC", 0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4", 0x3E: "F5", 0x3F: "F6", 0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10", 0x44: "F11", 0x45: "F12",
    0x35: "`", 0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5", 0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0", 0x2D: "-", 0x2E: "=", 0x2A: "BACK",
    0x2B: "TAB", 0x14: "Q", 0x1A: "W", 0x08: "E", 0x15: "R", 0x17: "T", 0x1C: "Y", 0x18: "U", 0x0C: "I", 0x12: "O", 0x13: "P", 0x2F: "[", 0x30: "]", 0x31: "\\",
    0x39: "CAPS", 0x04: "A", 0x16: "S", 0x07: "D", 0x09: "F", 0x0A: "G", 0x0B: "H", 0x0D: "J", 0x0E: "K", 0x0F: "L", 0x33: ";", 0x34: "'", 0x28: "ENTER",
    0xE1: "LSHFT", 0x1D: "Z", 0x1B: "X", 0x06: "C", 0x19: "V", 0x05: "B", 0x11: "N", 0x10: "M", 0x36: ",", 0x37: ".", 0x38: "/", 0xE5: "RSHFT",
    0xE0: "CTRL", 0xE2: "WIN", 0xE3: "ALT", 0x2C: "SPACE", 0xE6: "RALT", 0xE7: "FN", 0x65: "MENU", 0xE4: "RCTRL"
}
NAME_TO_HID = {v: k for k, v in HID_MAP.items()}

CONTROLLER_ACTIONS = [
    "None",
    "Right Trigger (RT) - Accelerate",
    "Left Trigger (LT) - Brake",
    "Left Stick: UP (Y+)",
    "Left Stick: DOWN (Y-)",
    "Left Stick: LEFT (X-)",
    "Left Stick: RIGHT (X+)",
    "Right Stick: UP",
    "Right Stick: DOWN",
    "Right Stick: LEFT",
    "Right Stick: RIGHT",
    "Button A", "Button B", "Button X", "Button Y"
]

LEGACY_TO_ENGLISH = {
    "Ninguna": "None",
    "Gatillo Derecho (RT) - Acelerar": "Right Trigger (RT) - Accelerate",
    "Gatillo Izquierdo (LT) - Frenar": "Left Trigger (LT) - Brake",
    "Stick Izquierdo: ARRIBA (Y+)": "Left Stick: UP (Y+)",
    "Stick Izquierdo: ABAJO (Y-)": "Left Stick: DOWN (Y-)",
    "Stick Izquierdo: IZQUIERDA (X-)": "Left Stick: LEFT (X-)",
    "Stick Izquierdo: DERECHA (X+)": "Left Stick: RIGHT (X+)",
    "Stick Derecho: ARRIBA": "Right Stick: UP",
    "Stick Derecho: ABAJO": "Right Stick: DOWN",
    "Stick Derecho: IZQUIERDA": "Right Stick: LEFT",
    "Stick Derecho: DERECHA": "Right Stick: RIGHT",
    "Bot?n A": "Button A",
    "Bot?n B": "Button B",
    "Bot?n X": "Button X",
    "Bot?n Y": "Button Y",
}


def translate_actions(mapping: Dict[str, str]) -> Dict[str, str]:
    """Map legacy Spanish action labels to English equivalents."""
    return {k: LEGACY_TO_ENGLISH.get(v, v) for k, v in mapping.items()}


# ============================================================================
# PROCESAMIENTO DIRECTO - Sin filtros que a?adan latencia
# ============================================================================
@dataclass
class KeyState:
    """Estado de una tecla."""
    raw: int = 0
    filtered: float = 0.0


class SignalProcessor:
    """Procesador de se?ales DIRECTO - m?nima latencia."""
    
    def __init__(self):
        self.keys: Dict[int, KeyState] = {}
        self.curve = "linear"
        self.deadzone = 30
        self.sensitivity = 1.0
        self.max_pressure = 600
        
    def get_state(self, key: int) -> KeyState:
        if key not in self.keys:
            self.keys[key] = KeyState()
        return self.keys[key]
    
    def process(self, key: int, raw: int) -> float:
        """
        Procesamiento DIRECTO sin filtros:
        1. Aplica deadzone
        2. Normaliza [0, 1]
        3. Aplica curva
        4. Retorna inmediatamente
        """
        state = self.get_state(key)
        state.raw = raw
        
        # Deadzone (opcional). Por defecto 0 para m?ximo recorrido.
        if raw <= self.deadzone:
            state.filtered = 0.0
            return 0.0

        # Normalizar directo al rango completo (0..max_pressure)
        # Permite valores mayores a max_pressure pero se saturan al 100%.
        norm = raw / self.max_pressure if self.max_pressure > 0 else 1.0
        norm = min(1.0, max(0.0, norm))
        
        # Curva de respuesta
        curved = self.apply_curve(norm)
        
        # Sensibilidad
        final = min(1.0, curved * self.sensitivity)
        state.filtered = final
        return final
    
    def apply_curve(self, x: float) -> float:
        if self.curve == "linear":
            return x
        elif self.curve == "exponential":
            return x * x
        elif self.curve == "scurve":
            return 3*x*x - 2*x*x*x
        elif self.curve == "fast":
            return 1 - (1-x)*(1-x)
        elif self.curve == "aggressive":
            return min(1.0, x * 1.5) if x < 0.7 else 1.0
        return x
    
    def clear(self, key: int):
        if key in self.keys:
            self.keys[key].raw = 0
            self.keys[key].filtered = 0.0


# ============================================================================
# APLICACI?N PRINCIPAL
# ============================================================================

class HallMapperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hall Analog Mapper")
        self.geometry("1400x820")
        self.minsize(1180, 720)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")

        self.running = False
        self.device = None
        self.gamepad = None
        self.mappings = {}
        self.active_keys = {}
        self.buttons_ui = {}
        self.selected_key_code = None
        self.device_info = None  # {'vid': int, 'pid': int, 'iface': int}
        
        # Low-latency signal processor
        self.processor = SignalProcessor()
        
        self.settings = {
            "deadzone": 0,
            "sensitivity": 1.0,
            "max_pressure": 1600,
            "curve": "linear"
        }
        # Fast mode: skip most UI refresh work
        self.fast_mode = ("--fast" in sys.argv) or ("-f" in sys.argv)
        # Previous state for micro-interpolation
        self.prev_axes = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
        # Target state for the gamepad thread
        self.target_axes = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
        self.pad_event = threading.Event()
        self.pad_thread = None
        self._last_visual_sig = None
        self.load_config()
        self.sync_processor()

        # Layout: left fixed panel, right vertically scrollable panel (mouse wheel), no visible bar
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)

        self.right_canvas = tk.Canvas(self, highlightthickness=0, bg="#16213e")
        self.right_canvas.grid(row=0, column=1, sticky="nsew")
        self.right_frame = ctk.CTkFrame(self.right_canvas, fg_color="#16213e", corner_radius=0)
        self.right_window = self.right_canvas.create_window((0, 0), window=self.right_frame, anchor="nw")
        self.right_frame.bind("<Configure>", self._on_right_configure)
        self.right_canvas.bind("<Configure>", self._on_right_canvas_configure)
        self.right_canvas.bind("<Enter>", lambda _: setattr(self, "_scroll_over_right", True))
        self.right_canvas.bind("<Leave>", lambda _: setattr(self, "_scroll_over_right", False))
        self.right_canvas.bind_all("<MouseWheel>", self._on_mousewheel_right)
        self._scroll_over_right = False

        self.build_left()
        self.build_right()
        
        try:
            self.gamepad = vg.VX360Gamepad()
        except Exception as e:
            print(f"ViGEm error: {e}")

        # Auto connect shortly after boot
        self.after(200, self.auto_connect)

    def _on_right_configure(self, event):
        self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

    def _on_right_canvas_configure(self, event):
        # Keep width in sync while scrolling vertically
        self.right_canvas.itemconfigure(self.right_window, width=event.width)

    def _on_mousewheel_right(self, event):
        if not self._scroll_over_right:
            return
        delta = -1 * int(event.delta / 120)
        self.right_canvas.yview_scroll(delta, "units")

    def sync_processor(self):
        """Sincroniza settings con el procesador de se?ales."""
        self.processor.deadzone = self.settings["deadzone"]
        self.processor.sensitivity = self.settings["sensitivity"]
        self.processor.max_pressure = self.settings["max_pressure"]
        self.processor.curve = self.settings.get("curve", "linear")

    def auto_connect(self):
        if not self.running:
            self.connect(auto=True)

    def build_left(self):
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        self.btn_connect = ctk.CTkButton(
            header, text=" CONNECT", 
            command=self.toggle_connection,
            fg_color="#c0392b", 
            font=("Arial", 13, "bold"), 
            width=140
        )
        self.btn_connect.pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(
            header, text=" Disconnected", 
            text_color="gray", 
            font=("Arial", 12), 
            padx=15
        )
        self.lbl_status.pack(side="left")
        
        self.lbl_stats = ctk.CTkLabel(
            header, text="", 
            text_color="#888", 
            font=("Consolas", 10)
        )
        self.lbl_stats.pack(side="right", padx=10)

        ctk.CTkLabel(
            header,
            text="UI may feel a bit laggy; gamepad output stays low-latency.",
            font=("Consolas", 9),
            text_color="#bbbbbb"
        ).pack(side="right", padx=10)

        self.btn_calibrate = ctk.CTkButton(
            header, text=" Calibrate", 
            command=self.manual_discover,
            fg_color="#2980b9",
            font=("Arial", 11, "bold"),
            width=110
        )
        self.btn_calibrate.pack(side="right", padx=6)

        self.keyboard_frame = ctk.CTkFrame(self.left_panel, fg_color="#1a1a2e", corner_radius=15)
        self.keyboard_frame.pack(expand=True, fill="both")
        self.draw_keyboard()

    def build_right(self):
        self.right_panel = self.right_frame

        ctk.CTkLabel(
            self.right_panel, 
            text=" SETTINGS", 
            font=("Arial", 18, "bold")
        ).pack(pady=(20, 10))
        
        self.lbl_selected_key = ctk.CTkLabel(
            self.right_panel, 
            text="Select a key", 
            font=("Arial", 14), 
            text_color="#f1c40f"
        )
        self.lbl_selected_key.pack(pady=5)
        
        self.action_var = ctk.StringVar(value="None")
        self.combo_action = ctk.CTkComboBox(
            self.right_panel, 
            values=CONTROLLER_ACTIONS, 
            variable=self.action_var, 
            command=self.on_action_change, 
            width=250
        )
        self.combo_action.pack(pady=10)
        self.combo_action.configure(state="disabled")

        ctk.CTkFrame(self.right_panel, height=2, fg_color="#333").pack(fill="x", padx=20, pady=15)
        
        # Config sliders
        self.create_slider(" Deadzone", 0, 200, self.settings["deadzone"], "deadzone", int)
        self.create_slider(" Sensitivity", 0.5, 2.0, self.settings["sensitivity"], "sensitivity", float)
        self.create_slider(" Max Pressure", 200, 2000, self.settings["max_pressure"], "max_pressure", int)
        
        ctk.CTkFrame(self.right_panel, height=2, fg_color="#333").pack(fill="x", padx=20, pady=15)
        
        # Response curve
        ctk.CTkLabel(
            self.right_panel, 
            text=" Response Curve", 
            font=("Arial", 12, "bold")
        ).pack(pady=5)
        
        self.curve_var = ctk.StringVar(value=self.settings.get("curve", "linear"))
        curves = [
            ("Linear (1:1)", "linear"),
            ("Exponential (precise)", "exponential"),
            ("S-curve (smooth)", "scurve"),
            ("Fast (aggressive)", "fast"),
            ("Aggressive (near digital)", "aggressive")
        ]
        for text, val in curves:
            ctk.CTkRadioButton(
                self.right_panel, 
                text=text, 
                variable=self.curve_var, 
                value=val,
                command=self.on_curve_change
            ).pack(anchor="w", padx=30, pady=2)

        ctk.CTkFrame(self.right_panel, height=2, fg_color="#333").pack(fill="x", padx=20, pady=15)
        
        # Live monitor
        ctk.CTkLabel(
            self.right_panel, 
            text=" LIVE MONITOR", 
            font=("Arial", 14, "bold")
        ).pack(pady=5)
        
        self.bars = {}
        self.bars['rt'] = self.create_bar(" Throttle (RT)", "#27ae60")
        self.bars['lt'] = self.create_bar(" Brake (LT)", "#e74c3c")
        self.bars['lx'] = self.create_bar(" Steering", "#3498db", center=True)

        # Quick test area to measure real lag
        test_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        test_frame.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(test_frame, text=" Test zone", font=("Arial", 12, "bold")).pack(anchor="w")
        self.lbl_benchmark = ctk.CTkLabel(test_frame, text="Ready (scroll here if hidden)", font=("Consolas", 10), text_color="#8e8e8e")
        self.lbl_benchmark.pack(anchor="w", pady=2)
        ctk.CTkButton(test_frame, text="Run stress test", command=self.run_stress_test, width=200, fg_color="#8e44ad").pack(anchor="w", pady=2)
        
        self.lbl_debug = ctk.CTkLabel(
            self.right_panel, 
            text="", 
            font=("Consolas", 9), 
            text_color="#666"
        )
        self.lbl_debug.pack(pady=10)

    def create_slider(self, text, min_v, max_v, default, key, dtype):
        frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=5)
        
        fmt = "{:.0f}" if dtype == int else "{:.2f}"
        lbl = ctk.CTkLabel(
            frame, 
            text=f"{text}: {fmt.format(default)}", 
            font=("Arial", 11), 
            anchor="w"
        )
        lbl.pack(fill="x")
        
        def cb(v):
            val = dtype(v)
            self.settings[key] = val
            lbl.configure(text=f"{text}: {fmt.format(val)}")
            self.sync_processor()
            self.save_config()
        
        slider = ctk.CTkSlider(frame, from_=min_v, to=max_v, command=cb)
        slider.set(default)
        slider.pack(fill="x")

    def create_bar(self, text, color, center=False):
        frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=4)
        
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")
        
        ctk.CTkLabel(row, text=text, font=("Arial", 10), width=100, anchor="w").pack(side="left")
        lbl = ctk.CTkLabel(row, text="0%", font=("Consolas", 10), width=50)
        lbl.pack(side="right")
        
        bar = ctk.CTkProgressBar(frame, progress_color=color, height=12)
        bar.pack(fill="x", pady=(2, 0))
        bar.set(0.5 if center else 0)
        
        return {"bar": bar, "label": lbl, "center": center}

    def draw_keyboard(self):
        container = ctk.CTkFrame(self.keyboard_frame, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        rows = [
            ["ESC", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "BACK"],
            ["TAB", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
            ["CAPS", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "ENTER"],
            ["LSHFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "RSHFT"],
            ["CTRL", "WIN", "ALT", "SPACE", "RALT", "FN", "MENU", "RCTRL"]
        ]
        
        for row in rows:
            rf = ctk.CTkFrame(container, fg_color="transparent")
            rf.pack(pady=3)
            for k in row:
                code = NAME_TO_HID.get(k, 0)
                w = 250 if k == "SPACE" else (70 if len(k) > 1 else 50)
                btn = ctk.CTkButton(
                    rf, text=k, width=w, height=42, 
                    fg_color="#2c3e50", 
                    hover_color="#34495e",
                    command=lambda c=code, n=k: self.select_key(c, n)
                )
                btn.pack(side="left", padx=2)
                if code:
                    self.buttons_ui[code] = btn
        
        self.refresh_visuals(force=True)

    def select_key(self, code, name):
        self.selected_key_code = code
        self.lbl_selected_key.configure(text=f" Editing: {name}")
        self.combo_action.configure(state="normal")
        self.action_var.set(self.mappings.get(str(code), "None"))
        self.refresh_visuals(force=True)

    def on_action_change(self, choice):
        if self.selected_key_code:
            if choice == "None":
                self.mappings.pop(str(self.selected_key_code), None)
            else:
                self.mappings[str(self.selected_key_code)] = choice
            self.save_config()
            self.refresh_visuals(force=True)

    def on_curve_change(self):
        self.settings["curve"] = self.curve_var.get()
        self.sync_processor()
        self.save_config()

    def refresh_visuals(self, force: bool = False):
        sig = (
            self.selected_key_code,
            tuple(sorted(self.mappings.keys())),
            tuple(sorted((code, min(255, int(val // 8))) for code, val in self.active_keys.items()))
        )
        if not force and sig == self._last_visual_sig:
            return
        self._last_visual_sig = sig

        for code, btn in self.buttons_ui.items():
            if code in self.active_keys:
                intensity = min(1.0, self.active_keys[code] / 400)
                r = int(46 + intensity * 46)
                g = int(204 - intensity * 50)
                b = int(113 - intensity * 50)
                btn.configure(fg_color=f"#{r:02x}{g:02x}{b:02x}", text_color="black")
            elif code == self.selected_key_code:
                btn.configure(fg_color="#f39c12", text_color="black")
            elif str(code) in self.mappings:
                btn.configure(fg_color="#2980b9", text_color="white")
            else:
                btn.configure(fg_color="#2c3e50", text_color="white")

    def load_config(self):
        try:
            cfg_path = CONFIG_FILE if os.path.exists(CONFIG_FILE) else LEGACY_CONFIG_FILE
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    d = json.load(f)
                    self.mappings = translate_actions(d.get("mappings", d.get("Mappings", {})))
                    s = d.get("settings", d.get("Settings", {}))
                    self.settings["deadzone"] = s.get("deadzone", s.get("Deadzone", 30))
                    self.settings["sensitivity"] = s.get("sensitivity", s.get("Sensitivity", 1.0))
                    self.settings["max_pressure"] = s.get("max_pressure", s.get("MaxPressure", 600))
                    self.settings["curve"] = s.get("curve", s.get("Curve", "linear"))
                    di = d.get("device_info")
                    if di:
                        self.device_info = {
                            "vid": di.get("vid"),
                            "pid": di.get("pid"),
                            "iface": di.get("iface"),
                        }
        except Exception as e:
            print(f"Config load error: {e}")

    def save_config(self):
        try:
            di = None
            if self.device_info:
                di = {
                    "vid": int(self.device_info.get("vid") or 0),
                    "pid": int(self.device_info.get("pid") or 0),
                    "iface": self.device_info.get("iface"),
                }
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "mappings": self.mappings,
                    "settings": self.settings,
                    "device_info": di,
                }, f, indent=2)
        except Exception as e:
            print(f"Config save error: {e}")

    def toggle_connection(self):
        if not self.running:
            self.connect()
        else:
            self.disconnect()

    def manual_discover(self):
        self.disconnect()
        self.after(150, lambda: self.connect(auto=False, force_wizard=True))

    def connect(self, auto: bool = False, force_wizard: bool = False):
        try:
            path = self.discover_device_path(auto=auto, force_wizard=force_wizard)
            if not path:
                if not auto:
                    messagebox.showerror("Connection", "No analog HID keyboard detected")
                return
            
            self.device = hid.device()
            self.device.open_path(path)
            self.device.set_nonblocking(True)
            
            self.running = True
            self.btn_connect.configure(text=" DISCONNECT", fg_color="#27ae60")
            self.lbl_status.configure(text=" Connected", text_color="#2ecc71")
            
            threading.Thread(target=self.read_loop, daemon=True).start()
            if not self.pad_thread or not self.pad_thread.is_alive():
                self.pad_thread = threading.Thread(target=self.gamepad_loop, daemon=True)
                self.pad_thread.start()
            
        except Exception as e:
            if not auto:
                messagebox.showerror("Connection error", str(e))

    def disconnect(self):
        self.running = False
        
        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None
        
        self.active_keys.clear()
        self.processor.keys.clear()
        self._last_visual_sig = None
        
        if self.gamepad:
            try:
                self.gamepad.left_trigger(0)
                self.gamepad.right_trigger(0)
                self.gamepad.left_joystick(0, 0)
                self.gamepad.right_joystick(0, 0)
                self.gamepad.update()
            except:
                pass
        self.target_axes = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
        self.pad_event.set()
        
        self.btn_connect.configure(text=" CONNECT", fg_color="#c0392b")
        self.lbl_status.configure(text=" Disconnected", text_color="gray")
        self.after(0, self.refresh_visuals)

    def discover_device_path(self, auto: bool = False, force_wizard: bool = False):
        # 1) If we have saved device info, try it first
        if self.device_info and not force_wizard:
            path = self._match_saved_device(self.device_info)
            if path:
                return path

        # 2) Silent auto-scan (no prompts) when auto connect is requested
        if auto and not force_wizard:
            best = self._auto_detect_by_scan()
            if best:
                self.device_info = best
                self.save_config()
                return self._match_saved_device(best)

        # 3) Assisted wizard (auto-detect by press or manual list)
        use_press = messagebox.askyesno(
            "Detect keyboard",
            "Press any analog Hall key on your keyboard.\n\n"
            "Do you want automatic detection by that keypress?",
            parent=self
        )
        info = None
        if use_press:
            info = self._auto_detect_by_press()
        if not info:
            info = self._wizard_select_device()
        if info:
            self.device_info = {
                "vid": info.get("vid"),
                "pid": info.get("pid"),
                "iface": info.get("iface"),
            }
            self.save_config()
            return self._match_saved_device(self.device_info)

        return None

    def _match_saved_device(self, info):
        for d in hid.enumerate(info.get('vid'), info.get('pid')):
            iface = d.get('interface_number', -1)
            if iface == info.get('iface') or info.get('iface') is None:
                return d['path']
        return None

    def _auto_detect_by_scan(self):
        """Headless-friendly scan that scores devices by analog header presence."""
        scored = []
        for d in hid.enumerate():
            item = {
                'vid': d.get('vendor_id'),
                'pid': d.get('product_id'),
                'iface': d.get('interface_number', -1),
                'path': d.get('path'),
            }
            score = 0
            try:
                dev = hid.device()
                dev.open_path(item['path'])
                dev.set_nonblocking(True)
                data = dev.read(64)
                dev.close()
                if data and len(data) > 0 and data[0] == 0xA0:
                    score += 10
            except:
                pass
            scored.append((score, item))

        scored.sort(key=lambda x: (-x[0], x[1]['vid'], x[1]['pid'], x[1]['iface']))
        if scored and scored[0][0] > 0:
            top = scored[0][1]
            return {"vid": top['vid'], "pid": top['pid'], "iface": top['iface']}
        return None

    def _wizard_select_device(self):
        devices = []
        for d in hid.enumerate():
            devices.append({
                'vid': d.get('vendor_id'),
                'pid': d.get('product_id'),
                'iface': d.get('interface_number', -1),
                'path': d.get('path'),
                'product': d.get('product_string') or "",
                'manufacturer': d.get('manufacturer_string') or "",
            })

        scored = []
        for item in devices:
            score = 0
            try:
                dev = hid.device()
                dev.open_path(item['path'])
                dev.set_nonblocking(True)
                data = dev.read(64)
                dev.close()
                if data and len(data) > 0 and data[0] == 0xA0:
                    score += 10  # Has the analog header we expect
            except:
                pass
            scored.append((score, item))

        if not scored:
            messagebox.showerror("No devices", "No HID devices detected")
            return None

        scored.sort(key=lambda x: (-x[0], x[1]['vid'], x[1]['pid'], x[1]['iface']))

        options = []
        for idx, (_, it) in enumerate(scored):
            options.append(f"{idx}: VID 0x{it['vid']:04X} PID 0x{it['pid']:04X} iface {it['iface']} - {it['manufacturer']} {it['product']}")

        if scored[0][0] >= 10 and len(scored) == 1:
            top = scored[0][1]
            return {"vid": top['vid'], "pid": top['pid'], "iface": top['iface']}

        sel = simpledialog.askinteger(
            "Pick your keyboard",
            "Choose the Hall Effect keyboard (enter index)\n\n" + "\n".join(options),
            parent=self
        )
        if sel is None:
            return None
        if sel < 0 or sel >= len(scored):
            messagebox.showerror("Invalid index", "Selection out of range")
            return None
        chosen = scored[sel][1]
        return {"vid": chosen['vid'], "pid": chosen['pid'], "iface": chosen['iface']}

    def _auto_detect_by_press(self, timeout: float = 5.0):
        messagebox.showinfo(
            "Detect keyboard",
            "Press any analog key now (5s window)...",
            parent=self
        )

        candidates = []
        for d in hid.enumerate():
            candidates.append({
                'vid': d.get('vendor_id'),
                'pid': d.get('product_id'),
                'iface': d.get('interface_number', -1),
                'path': d.get('path'),
            })

        dev_handles = []
        for c in candidates:
            try:
                dev = hid.device()
                dev.open_path(c['path'])
                dev.set_nonblocking(True)
                dev_handles.append((c, dev))
            except:
                pass

        hits = {}
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            for c, dev in dev_handles:
                try:
                    data = dev.read(64)
                    if data and len(data) > 0 and data[0] == 0xA0:
                        hits[c['path']] = hits.get(c['path'], 0) + 1
                except:
                    continue
            self.update_idletasks()
            time.sleep(0.01)

        for _, dev in dev_handles:
            try:
                dev.close()
            except:
                pass

        if not hits:
            messagebox.showerror("No pulses", "No analog presses detected")
            return None

        hits_typed: Dict[str, int] = hits
        best_path = max(hits_typed.items(), key=lambda kv: kv[1])[0]
        for c in candidates:
            if c['path'] == best_path:
                return {"vid": c['vid'], "pid": c['pid'], "iface": c['iface']}
        return None

    def read_loop(self):
        last_stats = time.perf_counter()
        last_ui = 0
        pcount = 0
        if not self.device:
            return
        
        while self.running:
            try:
                data = self.device.read(64)
                
                if not data:
                    if not self.fast_mode:
                        time.sleep(0.00005)
                    continue
                
                pcount += 1
                
                if len(data) < 7 or data[0] != 0xA0:
                    continue
                
                key = data[3]
                raw = (data[4] << 8) | data[5]
                
                self.processor.process(key, raw)
                
                if raw > self.processor.deadzone:
                    self.active_keys[key] = raw
                elif key in self.active_keys:
                    del self.active_keys[key]
                    self.processor.clear(key)
                
                self.update_gamepad()
                
                now = time.perf_counter()

                if not self.fast_mode:
                    if now - last_ui > 0.016:
                        last_ui = now
                        self.after(0, self.update_ui)

                    if now - last_stats > 1.0:
                        pps = pcount
                        pcount = 0
                        last_stats = now
                        self.after(0, lambda p=pps: self.lbl_stats.configure(
                            text=f" {p} pkt/s | {len(self.active_keys)} keys"
                        ))
                
            except Exception as e:
                if self.running:
                    print(f"Read error: {e}")
                    time.sleep(0.1)

    def update_gamepad(self):
        if not self.gamepad:
            return

        lx_raw, ly_raw = 0.0, 0.0
        rx_raw, ry_raw = 0.0, 0.0
        lt_raw, rt_raw = 0.0, 0.0

        for key in list(self.active_keys.keys()):
            ks = str(key)
            if ks not in self.mappings:
                continue

            action = self.mappings[ks]
            val = self.processor.get_state(key).filtered

            if "Right Trigger" in action:
                rt_raw = max(rt_raw, val)
            elif "Left Trigger" in action:
                lt_raw = max(lt_raw, val)
            elif "Left Stick" in action and "UP" in action:
                ly_raw = max(ly_raw, val)
            elif "Left Stick" in action and "DOWN" in action:
                ly_raw = min(ly_raw, -val)
            elif "Left Stick" in action and "RIGHT" in action:
                lx_raw = max(lx_raw, val)
            elif "Left Stick" in action and "LEFT" in action:
                lx_raw = min(lx_raw, -val)
            elif "Right Stick" in action and "UP" in action:
                ry_raw = max(ry_raw, val)
            elif "Right Stick" in action and "DOWN" in action:
                ry_raw = min(ry_raw, -val)
            elif "Right Stick" in action and "RIGHT" in action:
                rx_raw = max(rx_raw, val)
            elif "Right Stick" in action and "LEFT" in action:
                rx_raw = min(rx_raw, -val)

        targets = {
            "lx": lx_raw,
            "ly": ly_raw,
            "rx": rx_raw,
            "ry": ry_raw,
            "lt": lt_raw,
            "rt": rt_raw,
        }

        if all(abs(targets[k] - self.target_axes[k]) < 1e-4 for k in targets):
            return

        self.target_axes = targets
        self.pad_event.set()

    def gamepad_loop(self):
        while True:
            self.pad_event.wait(0.005)
            self.pad_event.clear()

            if not self.gamepad:
                time.sleep(0.01)
                continue

            targets = self.target_axes
            prev = self.prev_axes

            max_delta = max(abs(targets[k] - prev[k]) for k in targets)
            if max_delta < 1e-4:
                if not self.running:
                    time.sleep(0.01)
                continue

            steps = 1
            if max_delta > 0.35:
                steps = 3
            elif max_delta > 0.2:
                steps = 2

            for i in range(1, steps + 1):
                t = i / steps
                lx = prev["lx"] + (targets["lx"] - prev["lx"]) * t
                ly = prev["ly"] + (targets["ly"] - prev["ly"]) * t
                rx = prev["rx"] + (targets["rx"] - prev["rx"]) * t
                ry = prev["ry"] + (targets["ry"] - prev["ry"]) * t
                lt = prev["lt"] + (targets["lt"] - prev["lt"]) * t
                rt = prev["rt"] + (targets["rt"] - prev["rt"]) * t

                try:
                    self.gamepad.left_trigger(int(lt * 255))
                    self.gamepad.right_trigger(int(rt * 255))
                    self.gamepad.left_joystick(int(lx * 32767), int(ly * 32767))
                    self.gamepad.right_joystick(int(rx * 32767), int(ry * 32767))
                    self.gamepad.update()
                except:
                    pass

            self.prev_axes.update(targets)

    def run_stress_test(self):
        self.lbl_benchmark.configure(text="Running")

        def worker():
            fake_proc = SignalProcessor()
            fake_proc.deadzone = self.processor.deadzone
            fake_proc.max_pressure = self.processor.max_pressure
            fake_proc.sensitivity = self.processor.sensitivity
            fake_proc.curve = self.processor.curve

            fake_active = {}
            fake_map = {
                str(NAME_TO_HID.get("W", 0)): "Left Stick: UP (Y+)",
                str(NAME_TO_HID.get("S", 0)): "Left Stick: DOWN (Y-)",
                str(NAME_TO_HID.get("A", 0)): "Left Stick: LEFT (X-)",
                str(NAME_TO_HID.get("D", 0)): "Left Stick: RIGHT (X+)",
                str(NAME_TO_HID.get("Q", 0)): "Left Trigger (LT) - Brake",
                str(NAME_TO_HID.get("E", 0)): "Right Trigger (RT) - Accelerate",
            }

            keys = list(fake_map.keys())
            loops = 40000
            start = time.perf_counter()

            for i in range(loops):
                k = keys[i % len(keys)]
                key_int = int(k)
                raw = (i * 37) % int(fake_proc.max_pressure)
                fake_proc.process(key_int, raw)

                if raw > fake_proc.deadzone:
                    fake_active[key_int] = raw
                elif key_int in fake_active:
                    del fake_active[key_int]

                action = fake_map.get(k)
                if not action:
                    continue
                val = fake_proc.get_state(key_int).filtered
                # No-op: we only benchmark processing speed here
                pass

            elapsed = time.perf_counter() - start
            rate = loops / elapsed if elapsed else 0
            msg = f"{rate:,.0f} iter/s | {elapsed*1000/loops:.3f} ms/iter"
            self.after(0, lambda: self.lbl_benchmark.configure(text=msg))

        threading.Thread(target=worker, daemon=True).start()

    def update_ui(self):
        self.refresh_visuals()
        
        rt_v, lt_v, lx_v = 0.0, 0.0, 0.0
        
        for key in self.active_keys:
            ks = str(key)
            if ks not in self.mappings:
                continue
            
            val = self.processor.get_state(key).filtered
            action = self.mappings[ks]
            
            if "Right Trigger" in action:
                rt_v = max(rt_v, val)
            elif "Left Trigger" in action:
                lt_v = max(lt_v, val)
            elif "Left Stick" in action and "RIGHT" in action:
                lx_v = max(lx_v, val)
            elif "Left Stick" in action and "LEFT" in action:
                lx_v = min(lx_v, -val)
        
        try:
            self.bars['rt']['bar'].set(rt_v)
            self.bars['rt']['label'].configure(text=f"{int(rt_v*100)}%")
            self.bars['lt']['bar'].set(lt_v)
            self.bars['lt']['label'].configure(text=f"{int(lt_v*100)}%")
            self.bars['lx']['bar'].set((lx_v + 1) / 2)
            self.bars['lx']['label'].configure(text=f"{int(lx_v*100):+d}%")
        except:
            pass
        
        if self.active_keys:
            key = list(self.active_keys.keys())[0]
            state = self.processor.get_state(key)
            pct = int(state.filtered * 100)
            lt_dbg = int(self.prev_axes.get("lt", 0.0) * 255)
            rt_dbg = int(self.prev_axes.get("rt", 0.0) * 255)
            self.lbl_debug.configure(
                text=f"raw={state.raw}  {pct}% | LT/RT={lt_dbg}/{rt_dbg}"
            )


class HallMapperHeadless:
    def __init__(self):
        self.running = False
        self.device = None
        self.gamepad = None
        self.mappings = {}
        self.active_keys = {}
        self.processor = SignalProcessor()
        self.device_info = None
        self.settings = {
            "deadzone": 0,
            "sensitivity": 1.0,
            "max_pressure": 1600,
            "curve": "linear"
        }
        self.load_config()
        self.sync_processor()
        
        try:
            self.gamepad = vg.VX360Gamepad()
            print(" ViGEm gamepad ready")
        except Exception as e:
            print(f" ViGEm error: {e}")
            sys.exit(1)

    def sync_processor(self):
        self.processor.deadzone = self.settings["deadzone"]
        self.processor.sensitivity = self.settings["sensitivity"]
        self.processor.max_pressure = self.settings["max_pressure"]
        self.processor.curve = self.settings.get("curve", "linear")

    def load_config(self):
        try:
            cfg_path = CONFIG_FILE if os.path.exists(CONFIG_FILE) else LEGACY_CONFIG_FILE
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    d = json.load(f)
                    self.mappings = translate_actions(d.get("mappings", d.get("Mappings", {})))
                    s = d.get("settings", d.get("Settings", {}))
                    self.settings["deadzone"] = s.get("deadzone", s.get("Deadzone", 30))
                    self.settings["sensitivity"] = s.get("sensitivity", s.get("Sensitivity", 1.0))
                    self.settings["max_pressure"] = s.get("max_pressure", s.get("MaxPressure", 600))
                    self.settings["curve"] = s.get("curve", s.get("Curve", "linear"))
                    di = d.get("device_info")
                    if di:
                        self.device_info = {
                            "vid": di.get("vid"),
                            "pid": di.get("pid"),
                            "iface": di.get("iface"),
                        }
                print(f" Config loaded: {len(self.mappings)} mappings")
        except Exception as e:
            print(f" Config error: {e}")

    def save_config(self):
        try:
            di = None
            if self.device_info:
                di = {
                    "vid": int(self.device_info.get("vid") or 0),
                    "pid": int(self.device_info.get("pid") or 0),
                    "iface": self.device_info.get("iface"),
                }
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "mappings": self.mappings,
                    "settings": self.settings,
                    "device_info": di,
                }, f, indent=2)
        except Exception as e:
            print(f" Config save error: {e}")

    def connect(self):
        try:
            path = None

            if self.device_info:
                path = self._match_saved_device(self.device_info)

            if not path:
                # score devices by presence of analog header 0xA0
                scored = []
                for d in hid.enumerate():
                    item = {
                        'vid': d.get('vendor_id'),
                        'pid': d.get('product_id'),
                        'iface': d.get('interface_number', -1),
                        'path': d.get('path'),
                    }
                    score = 0
                    try:
                        dev = hid.device()
                        dev.open_path(item['path'])
                        dev.set_nonblocking(True)
                        data = dev.read(64)
                        dev.close()
                        if data and len(data) > 0 and data[0] == 0xA0:
                            score += 10
                    except:
                        pass
                    scored.append((score, item))

                scored.sort(key=lambda x: (-x[0], x[1]['vid'], x[1]['pid'], x[1]['iface']))
                if scored:
                    path = scored[0][1]['path']
                    self.device_info = {
                        'vid': scored[0][1]['vid'],
                        'pid': scored[0][1]['pid'],
                        'iface': scored[0][1]['iface'],
                    }
                    self.save_config()

            if not path:
                print(" Hall-effect keyboard not detected")
                return False
            
            self.device = hid.device()
            self.device.open_path(path)
            self.device.set_nonblocking(True)
            print(" Keyboard connected")
            return True
            
        except Exception as e:
            print(f" Connection error: {e}")
            return False

    def _match_saved_device(self, info):
        for d in hid.enumerate(info.get('vid'), info.get('pid')):
            iface = d.get('interface_number', -1)
            if iface == info.get('iface') or info.get('iface') is None:
                return d['path']
        return None

    def update_gamepad(self):
        if not self.gamepad:
            return
        
        lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
        lt, rt = 0.0, 0.0
        
        for key in list(self.active_keys.keys()):
            ks = str(key)
            if ks not in self.mappings:
                continue
            
            action = self.mappings[ks]
            val = self.processor.get_state(key).filtered
            
            if "Right Trigger" in action:
                rt = max(rt, val)
            elif "Left Trigger" in action:
                lt = max(lt, val)
            elif "Left Stick" in action and "UP" in action:
                ly = max(ly, val)
            elif "Left Stick" in action and "DOWN" in action:
                ly = min(ly, -val)
            elif "Left Stick" in action and "RIGHT" in action:
                lx = max(lx, val)
            elif "Left Stick" in action and "LEFT" in action:
                lx = min(lx, -val)
            elif "Right Stick" in action and "UP" in action:
                ry = max(ry, val)
            elif "Right Stick" in action and "DOWN" in action:
                ry = min(ry, -val)
            elif "Right Stick" in action and "RIGHT" in action:
                rx = max(rx, val)
            elif "Right Stick" in action and "LEFT" in action:
                rx = min(rx, -val)
        
        try:
            self.gamepad.left_trigger(int(lt * 255))
            self.gamepad.right_trigger(int(rt * 255))
            self.gamepad.left_joystick(int(lx * 32767), int(ly * 32767))
            self.gamepad.right_joystick(int(rx * 32767), int(ry * 32767))
            self.gamepad.update()
        except:
            pass

    def run(self):
        if not self.connect():
            return
        
        self.running = True
        print("\n" + "="*50)
        print("  Hall Analog Mapper - Headless mode (no UI)")
        print("  Press Ctrl+C to exit")
        print("="*50 + "\n")
        
        last_stats = time.perf_counter()
        pcount = 0
        
        try:
            while self.running:
                if not self.device:
                    break
                data = self.device.read(64)
                
                if not data:
                    time.sleep(0.0001)
                    continue
                
                pcount += 1
                
                if len(data) < 7 or data[0] != 0xA0:
                    continue
                
                key = data[3]
                raw = (data[4] << 8) | data[5]
                
                self.processor.process(key, raw)
                
                if raw > self.processor.deadzone:
                    self.active_keys[key] = raw
                elif key in self.active_keys:
                    del self.active_keys[key]
                    self.processor.clear(key)
                
                self.update_gamepad()
                
                now = time.perf_counter()
                if now - last_stats > 2.0:
                    pps = pcount / 2
                    pcount = 0
                    last_stats = now
                    keys_str = ", ".join([HID_MAP.get(k, f"0x{k:02X}") for k in self.active_keys.keys()])
                    print(f"\r {pps:.0f} pkt/s | Active: {keys_str or 'none'}      ", end="", flush=True)
                    
        except KeyboardInterrupt:
            print("\n\n Stopped by user")
        finally:
            self.running = False
            if self.device:
                self.device.close()
            if self.gamepad:
                self.gamepad.left_trigger(0)
                self.gamepad.right_trigger(0)
                self.gamepad.left_joystick(0, 0)
                self.gamepad.right_joystick(0, 0)
                self.gamepad.update()
            print(" Cleanup done")


if __name__ == "__main__":
    if "--noui" in sys.argv or "-h" in sys.argv:
        app = HallMapperHeadless()
        app.run()
    else:
        app = HallMapperApp()
        app.mainloop()
