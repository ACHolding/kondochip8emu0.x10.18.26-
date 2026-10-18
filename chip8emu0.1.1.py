#!/usr/bin/env python3
"""
chip8emu0.1.1.py
mGBA-Inspired CHIP-8 Emulator
Resolution: 600x400 | Target Speed: 60 FPS | Audio Engine: Enabled
Theme: Blue Hue | Text: Blue | Button Background: Black
"""

import io
import math
import os
import platform
import random
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# =====================================================================
# EMULATOR CONFIGURATION
# =====================================================================
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 400
TARGET_FPS = 60
FRAME_DELAY_MS = int(1000 / TARGET_FPS)  # ~16ms per frame (60 FPS)
CPU_CLOCK_HZ = 600                       # 600 Hz CPU (~10 instructions per 60Hz frame)
CYCLES_PER_FRAME = CPU_CLOCK_HZ // TARGET_FPS

AUDIO_ENGINE_ENABLED = True              # audio engine = true

# Theme Palette (Blue Hue + Black Buttons + Blue Text)
THEME = {
    "bg_main": "#0A1428",        # Deep Blue Hue Window Background
    "bg_panel": "#10203E",       # mGBA Toolbar / Status Panel Blue
    "bg_canvas": "#050B16",      # Pixel Off Color (Dark Navy)
    "pixel_on": "#00D4FF",       # Pixel On Color (Vibrant Cyan-Blue)
    "text_blue": "#38BDF8",      # Primary Blue Text
    "text_bright": "#7DD3FC",    # Highlighted Blue Text
    "btn_bg": "#000000",         # Black Button Background
    "btn_active_bg": "#111827",  # Button Hover/Active Background
    "border_blue": "#1E3A8A",    # Panel Border Blue
}

# Built-in Classic CHIP-8 Pong ROM (246 bytes)
# Left Paddle: 1 (Up), Q (Down) | Right Paddle: 4 (Up), R (Down)
BUILTIN_PONG_ROM = [
    0x6A, 0x02, 0x6B, 0x0C, 0x6C, 0x3F, 0x6D, 0x0C, 0xA2, 0xEA, 0xDAB6, 0xDC,
    0xD6, 0x6E, 0x00, 0x22, 0xD4, 0x66, 0x03, 0x68, 0x02, 0x60, 0x60, 0xF0,
    0x15, 0xF0, 0x07, 0x30, 0x00, 0x12, 0x1A, 0xC7, 0x17, 0x77, 0x08, 0x69,
    0xFF, 0xA2, 0xF0, 0xD6, 0x71, 0xA2, 0xEA, 0xDAB6, 0xDCD6, 0x60, 0x01,
    0xE0, 0xA1, 0x7B, 0xFE, 0x60, 0x04, 0xE0, 0xA1, 0x7B, 0x02, 0x60, 0x1F,
    0x8B, 0x02, 0xDAB6, 0x60, 0x0C, 0xE0, 0xA1, 0x7D, 0xFE, 0x60, 0x0D, 0xE0,
    0xA1, 0x7D, 0x02, 0x60, 0x1F, 0x8D, 0x02, 0xDCD6, 0xA2, 0xF0, 0xD6, 0x71,
    0x86, 0x84, 0x87, 0x94, 0x60, 0x3F, 0x86, 0x02, 0x61, 0x1F, 0x87, 0x12,
    0x46, 0x02, 0x12, 0x78, 0x46, 0x3D, 0x12, 0x8A, 0x12, 0x9E, 0x80, 0x70,
    0x80, 0xB5, 0x3F, 0x01, 0x12, 0xA6, 0x61, 0x02, 0x80, 0x15, 0x3F, 0x01,
    0x12, 0xBA, 0x80, 0x15, 0x3F, 0x01, 0x12, 0xC8, 0x80, 0x15, 0x3F, 0x01,
    0x12, 0xA6, 0x12, 0x9E, 0x80, 0x70, 0x80, 0xD5, 0x3F, 0x01, 0x12, 0xA6,
    0x61, 0x02, 0x80, 0x15, 0x3F, 0x01, 0x12, 0xBA, 0x80, 0x15, 0x3F, 0x01,
    0x12, 0xC8, 0x80, 0x15, 0x3F, 0x01, 0x12, 0xA6, 0x37, 0x00, 0x37, 0x1F,
    0x69, 0xFF, 0x49, 0xFE, 0x69, 0x01, 0xD6, 0x71, 0x12, 0x2A, 0x7E, 0x01,
    0x36, 0x3D, 0x7E, 0x0F, 0x60, 0x05, 0xF0, 0x18, 0x22, 0xD4, 0x12, 0x14,
    0x69, 0xFF, 0x48, 0x02, 0x68, 0xFE, 0x12, 0xCE, 0x69, 0x00, 0x48, 0x02,
    0x68, 0xFE, 0x12, 0xCE, 0x69, 0x01, 0x48, 0x02, 0x68, 0xFE, 0x60, 0x01,
    0xF0, 0x18, 0x12, 0x9E, 0xA2, 0xF2, 0xFE, 0x33, 0xF2, 0x65, 0xF1, 0x29,
    0x64, 0x14, 0x65, 0x00, 0xD4, 0x55, 0x74, 0x0F, 0xF2, 0x29, 0xD4, 0x55,
    0x00, 0xEE, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x00
]

# Unpack any combined 16-bit entries in BUILTIN_PONG_ROM cleanly
PONG_BYTES = []
for item in BUILTIN_PONG_ROM:
    if item > 0xFF:
        PONG_BYTES.append((item >> 8) & 0xFF)
        PONG_BYTES.append(item & 0xFF)
    else:
        PONG_BYTES.append(item)


# =====================================================================
# SYNTHESIZED AUDIO ENGINE
# =====================================================================
class AudioEngine:
    """
    Synthesizes a 440Hz retro square-wave tone in memory for the CHIP-8 sound timer.
    Uses native OS audio playback without requiring external pip packages.
    """
    def __init__(self, root: tk.Tk, enabled: bool = True):
        self.root = root
        self.enabled = enabled
        self.is_playing = False
        self.system = platform.system()
        self.wav_bytes = self._generate_square_wave(freq=440, duration_ms=140)
        self.temp_wav_path = None

        if self.system != "Windows":
            try:
                fd, path = tempfile.mkstemp(suffix=".wav")
                with os.fdopen(fd, "wb") as f:
                    f.write(self.wav_bytes)
                self.temp_wav_path = path
            except Exception:
                self.temp_wav_path = None

    def _generate_square_wave(self, freq: int = 440, duration_ms: int = 140, sample_rate: int = 22050) -> bytes:
        num_samples = int(sample_rate * (duration_ms / 1000.0))
        buf = io.BytesIO()
        # Write standard 44-byte RIFF WAVE header (8-bit mono PCM)
        data_size = num_samples
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVEfmt ")
        buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate, 1, 8))
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))

        period = sample_rate / freq
        samples = bytearray(num_samples)
        for i in range(num_samples):
            samples[i] = 190 if (i % period) < (period / 2) else 65
        buf.write(samples)
        return buf.getvalue()

    def trigger_beep(self):
        if not self.enabled or self.is_playing:
            return
        self.is_playing = True
        threading.Thread(target=self._play_worker, daemon=True).start()

    def _play_worker(self):
        try:
            if self.system == "Windows":
                import winsound
                winsound.PlaySound(self.wav_bytes, winsound.SND_MEMORY)
            elif self.system == "Darwin" and self.temp_wav_path:
                subprocess.run(["afplay", self.temp_wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.system == "Linux" and self.temp_wav_path:
                subprocess.run(["aplay", "-q", self.temp_wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.root.bell()
                time.sleep(0.1)
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass
        finally:
            self.is_playing = False

    def cleanup(self):
        if self.temp_wav_path and os.path.exists(self.temp_wav_path):
            try:
                os.remove(self.temp_wav_path)
            except OSError:
                pass


# =====================================================================
# CHIP-8 CORE VM
# =====================================================================
class Chip8CPU:
    FONTSET = [
        0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
        0x20, 0x60, 0x20, 0x20, 0x70,  # 1
        0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
        0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
        0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
        0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
        0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
        0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
        0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
        0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
        0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
        0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
        0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
        0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
        0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
        0xF0, 0x80, 0xF0, 0x80, 0x80   # F
    ]

    def __init__(self):
        self.rom_data = list(PONG_BYTES)
        self.reset()

    def reset(self):
        self.memory = [0] * 4096
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.stack = [0] * 16
        self.sp = 0
        self.delay_timer = 0
        self.sound_timer = 0
        self.keys = [0] * 16
        self.display = [0] * (64 * 32)
        self.draw_flag = True
        self.waiting_for_key = False
        self.key_register = 0
        self.last_opcode = 0x0000

        # Load Fontset into 0x000 - 0x04F
        for idx, byte in enumerate(self.FONTSET):
            self.memory[idx] = byte

        # Reload active ROM into 0x200+
        for idx, byte in enumerate(self.rom_data):
            if 0x200 + idx < 4096:
                self.memory[0x200 + idx] = byte

    def load_rom_bytes(self, data: bytes | list):
        self.rom_data = list(data)
        self.reset()

    def step(self):
        if self.waiting_for_key:
            for k_idx, pressed in enumerate(self.keys):
                if pressed:
                    self.v[self.key_register] = k_idx
                    self.waiting_for_key = False
                    break
            return

        if self.pc >= 4095:
            self.pc = 0x200

        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.last_opcode = opcode
        self.pc = (self.pc + 2) & 0xFFF

        nnn = opcode & 0x0FFF
        nn = opcode & 0x00FF
        n = opcode & 0x000F
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        op_high = opcode & 0xF000

        if opcode == 0x00E0:  # CLS
            self.display = [0] * (64 * 32)
            self.draw_flag = True
        elif opcode == 0x00EE:  # RET
            if self.sp > 0:
                self.sp -= 1
                self.pc = self.stack[self.sp]
        elif op_high == 0x1000:  # JP addr
            self.pc = nnn
        elif op_high == 0x2000:  # CALL addr
            if self.sp < 16:
                self.stack[self.sp] = self.pc
                self.sp += 1
            self.pc = nnn
        elif op_high == 0x3000:  # SE Vx, byte
            if self.v[x] == nn:
                self.pc += 2
        elif op_high == 0x4000:  # SNE Vx, byte
            if self.v[x] != nn:
                self.pc += 2
        elif op_high == 0x5000:  # SE Vx, Vy
            if self.v[x] == self.v[y]:
                self.pc += 2
        elif op_high == 0x6000:  # LD Vx, byte
            self.v[x] = nn
        elif op_high == 0x7000:  # ADD Vx, byte
            self.v[x] = (self.v[x] + nn) & 0xFF
        elif op_high == 0x8000:
            if n == 0x0:
                self.v[x] = self.v[y]
            elif n == 0x1:
                self.v[x] |= self.v[y]
            elif n == 0x2:
                self.v[x] &= self.v[y]
            elif n == 0x3:
                self.v[x] ^= self.v[y]
            elif n == 0x4:
                total = self.v[x] + self.v[y]
                self.v[0xF] = 1 if total > 0xFF else 0
                self.v[x] = total & 0xFF
            elif n == 0x5:
                self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
            elif n == 0x6:
                self.v[0xF] = self.v[x] & 0x1
                self.v[x] >>= 1
            elif n == 0x7:
                self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
            elif n == 0xE:
                self.v[0xF] = (self.v[x] >> 7) & 0x1
                self.v[x] = (self.v[x] << 1) & 0xFF
        elif op_high == 0x9000:  # SNE Vx, Vy
            if self.v[x] != self.v[y]:
                self.pc += 2
        elif op_high == 0xA000:  # LD I, addr
            self.i = nnn
        elif op_high == 0xB000:  # JP V0, addr
            self.pc = (nnn + self.v[0]) & 0xFFF
        elif op_high == 0xC000:  # RND Vx, byte
            self.v[x] = random.randint(0, 255) & nn
        elif op_high == 0xD000:  # DRW Vx, Vy, nibble
            vx = self.v[x] % 64
            vy = self.v[y] % 32
            self.v[0xF] = 0
            for row in range(n):
                if vy + row >= 32:
                    break
                sprite_byte = self.memory[(self.i + row) & 0xFFF]
                for col in range(8):
                    if vx + col >= 64:
                        break
                    if (sprite_byte & (0x80 >> col)) != 0:
                        idx = (vy + row) * 64 + (vx + col)
                        if self.display[idx] == 1:
                            self.v[0xF] = 1
                        self.display[idx] ^= 1
            self.draw_flag = True
        elif op_high == 0xE000:
            key = self.v[x] & 0xF
            if nn == 0x9E and self.keys[key] == 1:
                self.pc += 2
            elif nn == 0xA1 and self.keys[key] == 0:
                self.pc += 2
        elif op_high == 0xF000:
            if nn == 0x07:
                self.v[x] = self.delay_timer
            elif nn == 0x0A:
                self.waiting_for_key = True
                self.key_register = x
            elif nn == 0x15:
                self.delay_timer = self.v[x]
            elif nn == 0x18:
                self.sound_timer = self.v[x]
            elif nn == 0x1E:
                self.i = (self.i + self.v[x]) & 0xFFF
            elif nn == 0x29:
                self.i = (self.v[x] & 0xF) * 5
            elif nn == 0x33:
                val = self.v[x]
                self.memory[self.i & 0xFFF] = val // 100
                self.memory[(self.i + 1) & 0xFFF] = (val // 10) % 10
                self.memory[(self.i + 2) & 0xFFF] = val % 10
            elif nn == 0x55:
                for r in range(x + 1):
                    self.memory[(self.i + r) & 0xFFF] = self.v[r]
            elif nn == 0x65:
                for r in range(x + 1):
                    self.v[r] = self.memory[(self.i + r) & 0xFFF]


# =====================================================================
# mGBA-STYLE TKINTER GUI (600x400)
# =====================================================================
class MGBAChip8App:
    KEYMAP = {
        "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
        "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
        "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
        "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("chip8emu 0.1.1 by ac kondo")
        self.root.resizable(False, False)
        self.root.configure(bg=THEME["bg_main"])
        # Center 600x400 window on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - WINDOW_WIDTH) // 2)
        y = max(0, (sh - WINDOW_HEIGHT) // 2)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

        self.cpu = Chip8CPU()
        self.audio = AudioEngine(root, enabled=AUDIO_ENGINE_ENABLED)
        self.running = True
        self.rom_name = "Built-in Pong.ch8"

        # FPS Tracking
        self.frame_count = 0
        self.fps_last_time = time.perf_counter()
        self.current_fps = 60.0

        self._build_mgba_menu()
        self._build_mgba_toolbar()
        self._build_viewport()
        self._build_status_bar()
        self._bind_inputs()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._emulation_loop()

    def _create_black_blue_button(self, parent, text: str, command, width: int = 10) -> tk.Button:
        """Creates a button with a black background and blue text."""
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=THEME["btn_bg"],
            fg=THEME["text_blue"],
            activebackground=THEME["btn_active_bg"],
            activeforeground=THEME["text_bright"],
            highlightbackground=THEME["border_blue"],
            highlightcolor=THEME["text_blue"],
            highlightthickness=1,
            bd=1,
            relief=tk.RAISED,
            font=("Consolas", 9, "bold"),
            width=width,
            cursor="hand2",
        )

    def _build_mgba_menu(self):
        menubar = tk.Menu(
            self.root,
            bg=THEME["btn_bg"],
            fg=THEME["text_blue"],
            activebackground=THEME["bg_panel"],
            activeforeground=THEME["text_bright"],
            bd=0,
        )

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=THEME["btn_bg"], fg=THEME["text_blue"])
        file_menu.add_command(label="Load ROM... (Ctrl+O)", command=self.action_load_rom)
        file_menu.add_command(label="Load Built-in Pong", command=self.action_load_pong)
        file_menu.add_command(label="Load Built-in Maze Demo", command=self.action_load_maze)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Emulation Menu
        emu_menu = tk.Menu(menubar, tearoff=0, bg=THEME["btn_bg"], fg=THEME["text_blue"])
        emu_menu.add_command(label="Pause / Resume (Space)", command=self.action_toggle_pause)
        emu_menu.add_command(label="Soft Reset (Ctrl+R)", command=self.action_reset)
        emu_menu.add_command(label="Frame Step (N)", command=self.action_step)
        menubar.add_cascade(label="Emulation", menu=emu_menu)

        # Audio/Video Menu
        av_menu = tk.Menu(menubar, tearoff=0, bg=THEME["btn_bg"], fg=THEME["text_blue"])
        av_menu.add_command(label="Toggle Audio Engine", command=self.action_toggle_audio)
        av_menu.add_command(label="Test 440Hz Beep", command=lambda: self.audio.trigger_beep())
        menubar.add_cascade(label="Audio/Video", menu=av_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=THEME["btn_bg"], fg=THEME["text_blue"])
        help_menu.add_command(label="Keypad Controls", command=self.action_show_controls)
        menubar.add_cascade(label="Tools", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_mgba_toolbar(self):
        toolbar = tk.Frame(
            self.root,
            bg=THEME["bg_panel"],
            height=42,
            highlightbackground=THEME["border_blue"],
            highlightthickness=1,
        )
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 4))

        self.btn_open = self._create_black_blue_button(toolbar, "Load ROM", self.action_load_rom, width=9)
        self.btn_open.pack(side=tk.LEFT, padx=4, pady=5)

        self.btn_pong = self._create_black_blue_button(toolbar, "Pong Demo", self.action_load_pong, width=9)
        self.btn_pong.pack(side=tk.LEFT, padx=4, pady=5)

        self.btn_pause = self._create_black_blue_button(toolbar, "Pause", self.action_toggle_pause, width=8)
        self.btn_pause.pack(side=tk.LEFT, padx=4, pady=5)

        self.btn_reset = self._create_black_blue_button(toolbar, "Reset", self.action_reset, width=7)
        self.btn_reset.pack(side=tk.LEFT, padx=4, pady=5)

        self.btn_step = self._create_black_blue_button(toolbar, "Step", self.action_step, width=6)
        self.btn_step.pack(side=tk.LEFT, padx=4, pady=5)

        self.btn_audio = self._create_black_blue_button(toolbar, "Audio: ON", self.action_toggle_audio, width=10)
        self.btn_audio.pack(side=tk.RIGHT, padx=6, pady=5)

    def _build_viewport(self):
        # 64x32 scaled by 9x = 576x288 (Fits cleanly inside 600x400 with toolbar + status bar)
        self.scale = 9
        canvas_w = 64 * self.scale  # 576
        canvas_h = 32 * self.scale  # 288

        viewport_frame = tk.Frame(
            self.root,
            bg=THEME["bg_main"],
            highlightbackground=THEME["border_blue"],
            highlightthickness=2,
        )
        viewport_frame.pack(side=tk.TOP, pady=2)

        self.canvas = tk.Canvas(
            viewport_frame,
            width=canvas_w,
            height=canvas_h,
            bg=THEME["bg_canvas"],
            highlightthickness=0,
        )
        self.canvas.pack()

        # Pre-allocate all 64x32 pixel rectangles once for zero-lag 60 FPS updates
        self.pixel_rects = [0] * (64 * 32)
        self.rendered_state = [0] * (64 * 32)
        for y in range(32):
            for x in range(64):
                x0 = x * self.scale
                y0 = y * self.scale
                rect_id = self.canvas.create_rectangle(
                    x0, y0, x0 + self.scale, y0 + self.scale,
                    fill=THEME["bg_canvas"],
                    outline="#081226",
                    width=1,
                )
                self.pixel_rects[y * 64 + x] = rect_id

    def _build_status_bar(self):
        status_frame = tk.Frame(
            self.root,
            bg=THEME["bg_panel"],
            height=28,
            highlightbackground=THEME["border_blue"],
            highlightthickness=1,
        )
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(2, 6))

        self.lbl_status_left = tk.Label(
            status_frame,
            text="mGBA-CHIP8 | ROM: Built-in Pong.ch8",
            bg=THEME["bg_panel"],
            fg=THEME["text_blue"],
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        self.lbl_status_left.pack(side=tk.LEFT, padx=8, pady=2)

        self.lbl_status_right = tk.Label(
            status_frame,
            text="60.0 FPS | PC: 0x0200 | Audio: Ready",
            bg=THEME["bg_panel"],
            fg=THEME["text_bright"],
            font=("Consolas", 9),
            anchor="e",
        )
        self.lbl_status_right.pack(side=tk.RIGHT, padx=8, pady=2)

    def _bind_inputs(self):
        self.root.bind("<KeyPress>", self._on_key_down)
        self.root.bind("<KeyRelease>", self._on_key_up)
        self.root.bind("<Control-o>", lambda e: self.action_load_rom())
        self.root.bind("<Control-r>", lambda e: self.action_reset())
        self.root.bind("<space>", lambda e: self.action_toggle_pause())

    def _on_key_down(self, event):
        key = event.keysym.lower()
        if key in self.KEYMAP:
            self.cpu.keys[self.KEYMAP[key]] = 1
        elif key == "n" and not self.running:
            self.action_step()

    def _on_key_up(self, event):
        key = event.keysym.lower()
        if key in self.KEYMAP:
            self.cpu.keys[self.KEYMAP[key]] = 0

    # =====================================================================
    # TOOLBAR & MENU ACTIONS
    # =====================================================================
    def action_load_rom(self):
        filepath = filedialog.askopenfilename(
            title="Select CHIP-8 ROM",
            filetypes=[("CHIP-8 ROMs", "*.ch8 *.rom *.c8"), ("All Files", "*.*")],
        )
        if not filepath:
            return
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            if len(data) > (4096 - 0x200):
                messagebox.showerror("ROM Error", "ROM file exceeds maximum CHIP-8 memory (3584 bytes).")
                return
            self.cpu.load_rom_bytes(data)
            self.rom_name = os.path.basename(filepath)
            self._force_clear_screen()
            self.running = True
            self.btn_pause.config(text="Pause")
        except Exception as exc:
            messagebox.showerror("Load Failed", f"Could not load ROM:\n{exc}")

    def action_load_pong(self):
        self.cpu.load_rom_bytes(PONG_BYTES)
        self.rom_name = "Built-in Pong.ch8"
        self._force_clear_screen()
        self.running = True
        self.btn_pause.config(text="Pause")

    def action_load_maze(self):
        # Compact CHIP-8 Procedural Maze Generator ROM
        maze_rom = [
            0xA2, 0x1E, 0xC2, 0x01, 0x32, 0x01, 0xA2, 0x1A, 0xD0, 0x14,
            0x70, 0x04, 0x30, 0x40, 0x12, 0x02, 0x60, 0x00, 0x71, 0x04,
            0x31, 0x20, 0x12, 0x02, 0x12, 0x18, 0x80, 0x40, 0x20, 0x10,
            0x20, 0x40, 0x80, 0x10
        ]
        self.cpu.load_rom_bytes(maze_rom)
        self.rom_name = "Built-in Maze.ch8"
        self._force_clear_screen()
        self.running = True
        self.btn_pause.config(text="Pause")

    def action_toggle_pause(self):
        self.running = not self.running
        self.btn_pause.config(text="Pause" if self.running else "Resume")

    def action_reset(self):
        self.cpu.reset()
        self._force_clear_screen()

    def action_step(self):
        self.running = False
        self.btn_pause.config(text="Resume")
        self.cpu.step()
        self._update_display()
        self._update_status_bar()

    def action_toggle_audio(self):
        self.audio.enabled = not self.audio.enabled
        state_txt = "Audio: ON" if self.audio.enabled else "Audio: OFF"
        self.btn_audio.config(text=state_txt)

    def action_show_controls(self):
        messagebox.showinfo(
            "mGBA-CHIP8 Controls",
            "Standard 16-Key Hex Keypad Mapping:\n\n"
            "Keyboard:        CHIP-8 Pad:\n"
            "1  2  3  4   ->   1  2  3  C\n"
            "Q  W  E  R   ->   4  5  6  D\n"
            "A  S  D  F   ->   7  8  9  E\n"
            "Z  X  C  V   ->   A  0  B  F\n\n"
            "Built-in Pong Controls:\n"
            "Left Paddle:  1 (Up) / Q (Down)\n"
            "Right Paddle: 4 (Up) / R (Down)"
        )

    # =====================================================================
    # 60 FPS RENDER & TIMING ENGINE
    # =====================================================================
    def _force_clear_screen(self):
        for idx in range(64 * 32):
            self.rendered_state[idx] = 0
            self.canvas.itemconfig(self.pixel_rects[idx], fill=THEME["bg_canvas"])

    def _update_display(self):
        if not self.cpu.draw_flag:
            return
        on_color = THEME["pixel_on"]
        off_color = THEME["bg_canvas"]
        display = self.cpu.display
        rendered = self.rendered_state
        rects = self.pixel_rects

        # Differential rendering: only update pixels that changed this frame
        for idx in range(2048):
            val = display[idx]
            if val != rendered[idx]:
                rendered[idx] = val
                self.canvas.itemconfig(rects[idx], fill=on_color if val else off_color)

        self.cpu.draw_flag = False

    def _update_status_bar(self):
        state = "RUN" if self.running else "PAUSED"
        aud = "ON" if self.audio.enabled else "MUTE"
        self.lbl_status_left.config(text=f"[{state}] {self.rom_name}")
        self.lbl_status_right.config(
            text=f"{self.current_fps:4.1f} FPS | PC: 0x{self.cpu.pc:04X} | OP: 0x{self.cpu.last_opcode:04X} | AUD: {aud}"
        )

    def _emulation_loop(self):
        frame_start = time.perf_counter()

        if self.running:
            # Execute CPU cycles for this 1/60s slice
            for _ in range(CYCLES_PER_FRAME):
                self.cpu.step()

            # 60Hz Hardware Timers
            if self.cpu.delay_timer > 0:
                self.cpu.delay_timer -= 1

            if self.cpu.sound_timer > 0:
                self.audio.trigger_beep()
                self.cpu.sound_timer -= 1

            self._update_display()

        # Calculate live 60 FPS telemetry
        self.frame_count += 1
        now = time.perf_counter()
        elapsed = now - self.fps_last_time
        if elapsed >= 0.5:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_last_time = now
            self._update_status_bar()

        # Schedule next frame to maintain 60 FPS
        process_ms = int((time.perf_counter() - frame_start) * 1000)
        wait_ms = max(1, FRAME_DELAY_MS - process_ms)
        self.root.after(wait_ms, self._emulation_loop)

    def _on_close(self):
        self.running = False
        self.audio.cleanup()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MGBAChip8App(root)
    root.mainloop()