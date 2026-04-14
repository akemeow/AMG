#!/usr/bin/env python3
"""
Ambient MIDI Generator — GUI App
"""

import tkinter as tk
from tkinter import ttk
import threading
import rtmidi
import time
import random
import math

# ================================================================
# スケール定義
# ================================================================
SCALES = {
    'Lydian':            [0, 2, 4, 6, 7, 9, 11],
    'Dorian':            [0, 2, 3, 5, 7, 9, 10],
    'Pentatonic Minor':  [0, 3, 5, 7, 10],
    'Pentatonic Major':  [0, 2, 4, 7, 9],
    'Phrygian':          [0, 1, 3, 5, 7, 8, 10],
    'Major':             [0, 2, 4, 5, 7, 9, 11],
    'Minor':             [0, 2, 3, 5, 7, 8, 10],
    'Blues':             [0, 3, 5, 6, 7, 10],
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MODULATION_INTERVALS = [-5, -2, 2, 5, 7]

# ================================================================
# グローバルステート
# ================================================================
class GlobalState:
    def __init__(self):
        self._lock      = threading.Lock()
        self.root       = 48
        self.scale_name = 'Lydian'
        self.bpm        = 52
        self.density    = 'normal'
        self.dynamic    = 1.0
        self.auto_evolve = True
        self.layers     = {'drone': True,  'melody': True,  'sparkle': True}
        self.vel        = {'drone': 45,    'melody': 38,    'sparkle': 28}
        # 変化量 0.0〜1.0 : 低=ステップワイズ、高=大跳躍多め
        self.variation  = {'drone': 0.2,   'melody': 0.3,   'sparkle': 0.6}
        # 休符率 0.0〜1.0
        self.rest_prob    = {'drone': 0.0,   'melody': 0.35,  'sparkle': 0.60}
        # 展開の深さ 0.0〜1.0 (転調幅・変化の大きさ)
        self.evolve_depth = 0.5
        # 展開の速さ 0.0〜1.0 (変化の頻度)
        self.evolve_speed = 0.5
        # ルートのランダム自動変化
        self.auto_root       = False
        self.auto_root_speed = 0.5   # 0.0〜1.0 (遅い〜速い)

    def get(self):
        with self._lock:
            return dict(
                root          = self.root,
                scale_name    = self.scale_name,
                bpm           = self.bpm,
                density       = self.density,
                dynamic       = self.dynamic,
                layers        = dict(self.layers),
                vel           = dict(self.vel),
                variation     = dict(self.variation),
                rest_prob     = dict(self.rest_prob),
                evolve_depth     = self.evolve_depth,
                evolve_speed     = self.evolve_speed,
                auto_root        = self.auto_root,
                auto_root_speed  = self.auto_root_speed,
            )

STATE = GlobalState()

# ================================================================
# Markov (variation 0.0〜1.0 で遷移幅を制御)
# ================================================================
def build_matrix(n, variation=0.3):
    """
    variation=0.0 : 隣接音優先（ステップワイズ）
    variation=1.0 : 均等ランダム（跳躍多め）
    """
    tight  = [0.5, 8.0, 3.0, 1.0, 0.3, 0.1]  # variation=0 のウェイト
    loose  = [1.0, 2.0, 2.0, 2.0, 2.0, 2.0]  # variation=1 のウェイト
    v = max(0.0, min(1.0, variation))
    blended = [tight[i] * (1 - v) + loose[i] * v for i in range(6)]
    m = []
    for i in range(n):
        row = []
        for j in range(n):
            d = min(abs(i - j), 5)
            row.append(blended[d])
        s = sum(row)
        m.append([w / s for w in row])
    return m

def next_deg(cur, mat):
    r, c = random.random(), 0.0
    for i, w in enumerate(mat[cur]):
        c += w
        if r < c:
            return i
    return len(mat) - 1

def wchoice(d):
    ks, ws = list(d.keys()), list(d.values())
    r, c = random.uniform(0, sum(ws)), 0.0
    for k, w in zip(ks, ws):
        c += w
        if r < c:
            return k
    return ks[-1]

# ================================================================
# MIDI接続
# ================================================================
_midiout = None
_midi_muted = False   # True のときノートオンを完全ブロック

def get_midi():
    global _midiout
    if _midiout is None:
        _midiout = rtmidi.MidiOut()
        ports = _midiout.get_ports()
        iac = next((i for i, p in enumerate(ports) if 'IAC' in p), 0)
        _midiout.open_port(iac)
    return _midiout

def midi_on(ch, note, vel):
    if _midi_muted:
        return
    get_midi().send_message([0x90 | ch, note, max(1, min(127, int(vel)))])

def midi_off(ch, note):
    get_midi().send_message([0x80 | ch, note, 0])

def midi_all_off(ch):
    get_midi().send_message([0xB0 | ch, 123, 0])

def midi_panic():
    """全チャンネル即時消音"""
    for ch in range(16):
        get_midi().send_message([0xB0 | ch, 120, 0])  # All Sound Off
        get_midi().send_message([0xB0 | ch, 123, 0])  # All Notes Off
        for n in range(128):
            get_midi().send_message([0x80 | ch, n, 0])

# ================================================================
# レイヤースレッド
# ================================================================
class DroneLayer:
    def __init__(self, log_fn):
        self.log      = log_fn
        self.ch       = 0
        self._running = False
        self._active  = []

    def _loop(self):
        last_root = None
        while self._running:
            s = STATE.get()
            if not s['layers']['drone']:
                midi_all_off(self.ch)
                last_root = None
                time.sleep(0.2)
                continue
            beat = 60.0 / s['bpm']
            root = s['root']
            var  = s['variation']['drone']

            if root != last_root:
                midi_all_off(self.ch)
                last_root = root

            midi_all_off(self.ch)

            base_notes = [root, root + 7]
            if var > 0.5 and random.random() < var - 0.3:
                extra = random.choice([3, 4, 10, 12])
                base_notes.append(root + extra)

            if not self._running:
                break

            vel = int(s['vel']['drone'] * s['dynamic'])
            self._active = base_notes[:]
            for n in base_notes:
                if 0 <= n <= 127:
                    midi_on(self.ch, n, vel)

            names = [NOTE_NAMES[n % 12] for n in base_notes]
            self.log(f"Drone   {names}  vel={vel}  var={int(var*100)}%")

            base_dur = 16
            if var > 0.4:
                base_dur = int(base_dur * (1.0 - var * 0.5))
                base_dur = max(4, base_dur)

            # 0.1秒刻みで待機 → STOPで即座に抜けられる
            elapsed = 0.0
            total = base_dur * beat
            while self._running and elapsed < total:
                time.sleep(0.1)
                elapsed += 0.1

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        midi_all_off(self.ch)


class MelodyLayer:
    DENSITY_DUR = {
        'sparse': {4.0: 2, 6.0: 3, 8.0: 2},
        'normal': {2.0: 2, 4.0: 4, 6.0: 2},
        'dense':  {1.0: 2, 2.0: 4, 4.0: 2},
    }

    def __init__(self, ch, octave, layer_key, gate, label, log_fn):
        self.ch         = ch
        self.octave     = octave
        self.layer_key  = layer_key
        self.gate       = gate
        self.label      = label
        self.log        = log_fn
        self._running   = False
        self._deg       = 0
        self._cur_scale = None
        self._cur_var   = None
        self._matrix    = None
        self._notes     = []

    def _rebuild(self, root, scale_name, variation):
        ivs = SCALES[scale_name]
        self._notes = [root + self.octave * 12 + iv for iv in ivs
                       if 0 <= root + self.octave * 12 + iv <= 127]
        self._matrix    = build_matrix(len(ivs), variation)
        self._deg       = min(self._deg, max(0, len(ivs) - 1))
        self._cur_scale = scale_name
        self._cur_var   = variation

    def _loop(self):
        while self._running:
            s   = STATE.get()
            key = self.layer_key

            if not s['layers'][key]:
                midi_all_off(self.ch)
                time.sleep(0.5)
                continue

            beat      = 60.0 / s['bpm']
            var       = s['variation'][key]
            rest_prob = s['rest_prob'][key]

            if s['scale_name'] != self._cur_scale \
                    or abs(var - (self._cur_var or -1)) > 0.05 \
                    or not self._notes:
                self._rebuild(s['root'], s['scale_name'], var)

            self._deg = next_deg(self._deg, self._matrix)
            if self._deg >= len(self._notes):
                self._deg = 0

            note  = self._notes[self._deg]
            dur_b = wchoice(self.DENSITY_DUR[s['density']])
            dur_s = dur_b * beat
            vel   = int((s['vel'][key] + random.randint(-15, 15)) * s['dynamic'])

            if random.random() < rest_prob:
                self._interruptible_sleep(dur_s)
                continue

            name = NOTE_NAMES[note % 12]
            self.log(f"{self.label}  {name}{note//12-1}  "
                     f"vel={vel}  var={int(var*100)}%  rest={int(rest_prob*100)}%")
            midi_on(self.ch, note, vel)
            self._interruptible_sleep(dur_s * self.gate)
            midi_off(self.ch, note)
            self._interruptible_sleep(dur_s * (1.0 - self.gate))

    def _interruptible_sleep(self, seconds):
        elapsed = 0.0
        while self._running and elapsed < seconds:
            time.sleep(0.05)
            elapsed += 0.05

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        midi_all_off(self.ch)


class EvolutionController:
    def __init__(self, log_fn):
        self.log      = log_fn
        self._running = False
        self._phase   = 0.0

    def _loop(self):
        t_mod       = time.time() + random.uniform(30, 60)
        t_scale     = time.time() + random.uniform(45, 90)
        t_dens      = time.time() + random.uniform(20, 50)
        t_auto_root = time.time() + 5.0

        while self._running:
            s   = STATE.get()
            now = time.time()

            if s['auto_evolve']:
                depth = s['evolve_depth']   # 0.0〜1.0
                spd   = s['evolve_speed']   # 0.0〜1.0

                # ダイナミクス波: depthで振れ幅を制御
                sin_speed = 0.002 + spd * 0.01
                self._phase += sin_speed
                swing = 0.15 + depth * 0.4
                STATE.dynamic = max(0.2, min(1.0, 0.6 + swing * math.sin(self._phase)))

                # 転調インターバル: depthで幅を制御
                if now >= t_mod:
                    if depth < 0.3:
                        iv_pool = [-2, 2]           # 小さな転調
                    elif depth < 0.7:
                        iv_pool = [-5, -2, 2, 5]    # 中程度
                    else:
                        iv_pool = MODULATION_INTERVALS  # 全範囲
                    iv  = random.choice(iv_pool)
                    new = max(36, min(60, s['root'] + iv))
                    with STATE._lock: STATE.root = new
                    self.log(f"[展開] 転調 → {NOTE_NAMES[new % 12]}{new//12-1}  (depth={int(depth*100)}%)")
                    interval = 90 - spd * 75   # speed=0→90s, speed=1→15s
                    t_mod = now + random.uniform(interval * 0.6, interval * 1.4)

                # スケール切り替え: depthが低いと関連スケールのみ
                if now >= t_scale:
                    RELATED = {
                        'Lydian': ['Major', 'Dorian'],
                        'Dorian': ['Minor', 'Phrygian', 'Lydian'],
                        'Pentatonic Minor': ['Minor', 'Blues', 'Dorian'],
                        'Pentatonic Major': ['Major', 'Lydian'],
                        'Phrygian': ['Minor', 'Dorian'],
                        'Major': ['Lydian', 'Pentatonic Major'],
                        'Minor': ['Dorian', 'Pentatonic Minor', 'Blues'],
                        'Blues': ['Pentatonic Minor', 'Minor'],
                    }
                    cur = s['scale_name']
                    if depth < 0.5:
                        opts = RELATED.get(cur, list(SCALES.keys()))
                    else:
                        opts = [k for k in SCALES if k != cur]
                    new = random.choice(opts)
                    with STATE._lock: STATE.scale_name = new
                    self.log(f"[展開] スケール → {new}  (depth={int(depth*100)}%)")
                    interval = 120 - spd * 100  # speed=0→120s, speed=1→20s
                    t_scale = now + random.uniform(interval * 0.6, interval * 1.4)

                # 密度変化
                if now >= t_dens:
                    opts = [d for d in ['sparse', 'normal', 'dense'] if d != s['density']]
                    new  = random.choice(opts)
                    with STATE._lock: STATE.density = new
                    self.log(f"[展開] 密度 → {new}")
                    interval = 60 - spd * 50   # speed=0→60s, speed=1→10s
                    t_dens = now + random.uniform(interval * 0.6, interval * 1.4)

            # Auto Root (Auto Evolveとは独立して動作)
            if s['auto_root'] and now >= t_auto_root:
                rspd = s['auto_root_speed']
                new_root = random.choice(list(range(36, 61)))  # C2〜C4
                with STATE._lock: STATE.root = new_root
                name = NOTE_NAMES[new_root % 12]
                self.log(f"[Root] → {name}{new_root//12-1}")
                interval = 30 - rspd * 25   # speed=0→30s, speed=1→5s
                t_auto_root = now + random.uniform(interval * 0.6, interval * 1.4)

            time.sleep(0.1)

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

# ================================================================
# GUI
# ================================================================
C_BG     = '#0f0f1e'
C_PANEL  = '#1a1a2e'
C_ACCENT = '#7c6fe0'
C_ON     = '#00c896'
C_OFF    = '#555577'
C_TEXT   = '#dde0ff'
C_MUTED  = '#8888aa'
C_TRACK  = '#2a2a4a'
C_SLIDER = '#4a4a6a'
C_VAR    = '#e07c9a'
C_REST   = '#e0a03a'
C_EVO    = '#a0c4ff'

def section(parent, title):
    frame = tk.Frame(parent, bg=C_PANEL, padx=12, pady=8)
    tk.Label(frame, text=title.upper(), bg=C_PANEL, fg=C_ACCENT,
             font=('Helvetica', 8, 'bold')).pack(anchor='w', pady=(0, 6))
    return frame

# ================================================================
# Knob ウィジェット
# ================================================================
class Knob(tk.Canvas):
    """
    ドラッグ操作で回転するノブウィジェット。
    上ドラッグ→値増加、下ドラッグ→値減少。
    """
    SIZE = 46

    def __init__(self, parent, from_=0, to=100, default=50,
                 color=C_TEXT, bg=C_PANEL, command=None, label='', **kw):
        super().__init__(parent, width=self.SIZE, height=self.SIZE + 16,
                         bg=bg, highlightthickness=0, **kw)
        self.from_    = from_
        self.to       = to
        self._val     = float(default)
        self.color    = color
        self._bg      = bg
        self._cmd     = command
        self._label   = label
        self._drag_y  = None
        self._draw()
        self.bind('<Button-1>',      self._press)
        self.bind('<B1-Motion>',     self._drag)
        self.bind('<ButtonRelease-1>', self._release)
        self.bind('<MouseWheel>',    self._wheel)

    def _ratio(self):
        return (self._val - self.from_) / max(self.to - self.from_, 1)

    def _draw(self):
        self.delete('all')
        s   = self.SIZE
        cx  = s // 2
        cy  = s // 2
        r   = s // 2 - 4
        gap = 60          # degrees left at bottom
        full_extent = 360 - gap
        start_angle = 270 - full_extent / 2   # tkinter: 0=right, CCW

        # トラック弧
        self.create_arc(cx-r, cy-r, cx+r, cy+r,
                        start=start_angle, extent=full_extent,
                        outline=C_TRACK, width=4, style='arc')

        # 値弧
        val_extent = self._ratio() * full_extent
        if val_extent > 0:
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=start_angle, extent=val_extent,
                            outline=self.color, width=4, style='arc')

        # インジケーター
        angle_deg = start_angle + val_extent
        angle_rad = math.radians(angle_deg)
        ix = cx + (r - 6) * math.cos(angle_rad)
        iy = cy - (r - 6) * math.sin(angle_rad)
        self.create_oval(ix-3, iy-3, ix+3, iy+3,
                         fill=self.color, outline='')

        # 中央円
        self.create_oval(cx-6, cy-6, cx+6, cy+6,
                         fill='#2a2a4a', outline=C_TRACK, width=1)

        # 値ラベル
        self.create_text(cx, s + 6, text=self._fmt(),
                         fill=self.color, font=('Helvetica', 7, 'bold'), anchor='center')

    def _fmt(self):
        r = self._ratio()
        if self.to <= 1.0:
            return f'{int(r*100)}%'
        elif self.to <= 127:
            return str(int(self._val))
        else:
            return f'{int(r*100)}%'

    def _press(self, e):
        self._drag_y = e.y

    def _drag(self, e):
        if self._drag_y is None:
            return
        dy = self._drag_y - e.y
        self._drag_y = e.y
        delta = dy * (self.to - self.from_) / 80.0
        self._val = max(self.from_, min(self.to, self._val + delta))
        self._draw()
        if self._cmd:
            self._cmd(self._val)

    def _release(self, e):
        self._drag_y = None

    def _wheel(self, e):
        delta = (self.to - self.from_) / 40.0
        self._val = max(self.from_, min(self.to,
                        self._val + (delta if e.delta > 0 else -delta)))
        self._draw()
        if self._cmd:
            self._cmd(self._val)

    def set(self, v):
        self._val = max(self.from_, min(self.to, float(v)))
        self._draw()

    def get(self):
        return self._val


def labeled_knob(parent, label, from_, to, default, color, bg, command):
    """ノブ + 上ラベルをまとめたフレームを返す"""
    f = tk.Frame(parent, bg=bg)
    tk.Label(f, text=label, bg=bg, fg=color,
             font=('Helvetica', 7), anchor='center').pack()
    k = Knob(f, from_=from_, to=to, default=default,
             color=color, bg=bg, command=command)
    k.pack()
    return f, k

class AmbientApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Ambient Generator')
        self.root.configure(bg=C_BG)
        self.root.resizable(False, False)

        self._playing = False
        self._drone = self._melody = self._sparkle = self._evo = None
        self._build_ui()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ---- UI構築 ----------------------------------------
    def _build_ui(self):
        # タイトルバー
        title_bar = tk.Frame(self.root, bg=C_BG, pady=12)
        title_bar.pack(fill='x', padx=16)
        tk.Label(title_bar, text='AMBIENT GENERATOR',
                 bg=C_BG, fg=C_TEXT,
                 font=('Helvetica', 15, 'bold')).pack(side='left')
        self._status_lbl = tk.Label(title_bar, text='● STOPPED',
                                    bg=C_BG, fg=C_OFF,
                                    font=('Helvetica', 9, 'bold'))
        self._status_lbl.pack(side='right')

        cols = tk.Frame(self.root, bg=C_BG)
        cols.pack(fill='both', padx=12, pady=4)

        left  = tk.Frame(cols, bg=C_BG)
        right = tk.Frame(cols, bg=C_BG)
        left.pack(side='left', fill='both', expand=True, padx=(0, 6))
        right.pack(side='left', fill='both', expand=True)

        self._build_transport(left)
        self._build_key(left)
        self._build_scale(left)
        self._build_density(left)
        self._build_layers(right)
        self._build_log(right)

    def _build_transport(self, parent):
        f = section(parent, 'Transport')
        f.pack(fill='x', pady=(0, 6))
        row = tk.Frame(f, bg=C_PANEL)
        row.pack(fill='x')

        self._play_btn = tk.Button(
            row, text='  ▶  START  ', command=self._toggle_play,
            bg=C_ON, fg='#0f0f1e', relief='flat',
            font=('Helvetica', 11, 'bold'), padx=8, pady=6,
            activebackground='#00a87d', cursor='hand2')
        self._play_btn.pack(side='left')

        _, self._bpm_knob = labeled_knob(
            row, 'BPM', 30, 140, 52, C_TEXT, C_PANEL,
            command=self._on_bpm)
        self._bpm_knob.master.pack(side='right', padx=(12, 0))

    def _build_key(self, parent):
        f = section(parent, 'Root Note')
        f.pack(fill='x', pady=(0, 6))
        self._root_var = tk.IntVar(value=48)
        self._note_btns = {}
        for row_notes in [['C','C#','D','D#','E','F'], ['F#','G','G#','A','A#','B']]:
            r = tk.Frame(f, bg=C_PANEL)
            r.pack(fill='x', pady=1)
            for n in row_notes:
                idx = NOTE_NAMES.index(n)
                btn = tk.Button(
                    r, text=n, width=3,
                    bg='#2a2a3e' if '#' in n else '#3a3a5a',
                    fg=C_TEXT, relief='flat',
                    font=('Helvetica', 8, 'bold'), pady=3,
                    activebackground=C_ACCENT,
                    command=lambda i=idx: self._on_root(i),
                    cursor='hand2')
                btn.pack(side='left', padx=1)
                self._note_btns[n] = btn
        oct_f = tk.Frame(f, bg=C_PANEL)
        oct_f.pack(fill='x', pady=(6, 0))
        tk.Label(oct_f, text='Octave', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 9)).pack(side='left')
        self._oct_var = tk.IntVar(value=3)
        for o in [2, 3, 4, 5]:
            tk.Radiobutton(oct_f, text=str(o), variable=self._oct_var, value=o,
                           bg=C_PANEL, fg=C_TEXT, selectcolor=C_ACCENT,
                           activebackground=C_PANEL,
                           command=self._on_octave).pack(side='left', padx=4)
        self._update_root_buttons()

        # Randomize ボタン + Auto Root + Speed ノブ
        rand_row = tk.Frame(f, bg=C_PANEL)
        rand_row.pack(fill='x', pady=(8, 0))

        tk.Button(rand_row, text='RANDOM', command=self._on_random_root,
                  bg='#3a3a6a', fg=C_TEXT, relief='flat',
                  font=('Helvetica', 8, 'bold'), padx=8, pady=3,
                  activebackground=C_ACCENT, cursor='hand2').pack(side='left')

        self._auto_root_var = tk.BooleanVar(value=False)
        tk.Checkbutton(rand_row, text='Auto', variable=self._auto_root_var,
                       bg=C_PANEL, fg=C_TEXT, selectcolor=C_PANEL,
                       activebackground=C_PANEL, font=('Helvetica', 9, 'bold'),
                       command=self._on_auto_root).pack(side='left', padx=(10, 4))

        _, self._root_speed_knob = labeled_knob(
            rand_row, 'Speed', 0, 100, 50, C_EVO, C_PANEL,
            command=self._on_root_speed)
        self._root_speed_knob.master.pack(side='right')

    def _build_scale(self, parent):
        f = section(parent, 'Scale')
        f.pack(fill='x', pady=(0, 6))
        self._scale_var = tk.StringVar(value='Lydian')
        menu = ttk.Combobox(f, textvariable=self._scale_var,
                            values=list(SCALES.keys()),
                            state='readonly', width=20)
        menu.pack(anchor='w')
        menu.bind('<<ComboboxSelected>>', self._on_scale)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TCombobox',
                        fieldbackground=C_SLIDER, background=C_SLIDER,
                        foreground=C_TEXT, selectbackground=C_ACCENT,
                        arrowcolor=C_TEXT)

    def _build_density(self, parent):
        f = section(parent, 'Density')
        f.pack(fill='x', pady=(0, 6))
        self._density_var = tk.StringVar(value='normal')
        row = tk.Frame(f, bg=C_PANEL)
        row.pack()
        for label, val in [('Sparse', 'sparse'), ('Normal', 'normal'), ('Dense', 'dense')]:
            tk.Radiobutton(row, text=label, variable=self._density_var,
                           value=val, bg=C_PANEL, fg=C_TEXT,
                           selectcolor=C_ACCENT, activebackground=C_PANEL,
                           command=self._on_density).pack(side='left', padx=6)
        # Auto Evolve + Depth/Speed ノブ
        evo_row = tk.Frame(f, bg=C_PANEL)
        evo_row.pack(fill='x', pady=(8, 0))
        self._evolve_var = tk.BooleanVar(value=True)
        tk.Checkbutton(evo_row, text='Auto Evolve',
                       variable=self._evolve_var,
                       bg=C_PANEL, fg=C_TEXT, selectcolor=C_PANEL,
                       activebackground=C_PANEL, font=('Helvetica', 9, 'bold'),
                       command=self._on_evolve).pack(side='left')

        knob_row = tk.Frame(f, bg=C_PANEL)
        knob_row.pack(fill='x', pady=(4, 0))
        _, self._depth_knob = labeled_knob(
            knob_row, 'Depth', 0, 100, 50, C_EVO, C_PANEL, self._on_depth)
        self._depth_knob.master.pack(side='left', padx=(0, 16))
        _, self._speed_knob = labeled_knob(
            knob_row, 'Speed', 0, 100, 50, C_EVO, C_PANEL, self._on_speed)
        self._speed_knob.master.pack(side='left')

    def _build_layers(self, parent):
        f = section(parent, 'Layers')
        f.pack(fill='x', pady=(0, 6))

        layers_cfg = [
            ('drone',   'DRONE',   'Ch.1', 45, 0.20, 0.00),
            ('melody',  'MELODY',  'Ch.2', 38, 0.30, 0.35),
            ('sparkle', 'SPARKLE', 'Ch.3', 28, 0.60, 0.60),
        ]
        self._layer_vars = {}

        for key, label, ch_label, def_vel, def_var, def_rest in layers_cfg:
            BG = '#141428'
            block = tk.Frame(f, bg=BG, padx=10, pady=8)
            block.pack(fill='x', pady=3)

            # ヘッダー
            header = tk.Frame(block, bg=BG)
            header.pack(fill='x', pady=(0, 6))
            lvar = tk.BooleanVar(value=True)
            self._layer_vars[key] = lvar
            tk.Checkbutton(header, text=label, variable=lvar,
                           bg=BG, fg=C_TEXT, selectcolor=BG,
                           activebackground=BG,
                           font=('Helvetica', 10, 'bold'),
                           command=lambda k=key: self._on_layer(k)).pack(side='left')
            tk.Label(header, text=ch_label, bg=BG, fg=C_MUTED,
                     font=('Helvetica', 8)).pack(side='left', padx=(6, 0))

            # ノブ3つ横並び
            knob_row = tk.Frame(block, bg=BG)
            knob_row.pack()

            _, kv = labeled_knob(knob_row, 'Vel', 1, 127, def_vel,
                                  C_TEXT, BG, lambda v, k=key: self._on_vel(k, v))
            kv.master.pack(side='left', padx=10)

            _, kvar = labeled_knob(knob_row, 'Variation', 0, 100, int(def_var*100),
                                    C_VAR, BG, lambda v, k=key: self._on_variation(k, v))
            kvar.master.pack(side='left', padx=10)

            _, krest = labeled_knob(knob_row, 'Rest', 0, 100, int(def_rest*100),
                                     C_REST, BG, lambda v, k=key: self._on_rest(k, v))
            krest.master.pack(side='left', padx=10)

    def _build_log(self, parent):
        f = section(parent, 'Log')
        f.pack(fill='both', expand=True)
        self._log_text = tk.Text(f, height=10, bg='#0a0a18', fg='#6677aa',
                                  font=('Menlo', 8), relief='flat',
                                  state='disabled', wrap='none')
        self._log_text.pack(fill='both', expand=True)

    # ---- イベントハンドラ --------------------------------
    def _on_bpm(self, val):
        with STATE._lock: STATE.bpm = int(val)

    def _on_root(self, semitone):
        new_root = semitone + self._oct_var.get() * 12
        self._root_var.set(new_root)
        with STATE._lock: STATE.root = new_root
        self._update_root_buttons()

    def _on_octave(self):
        new_root = STATE.root % 12 + self._oct_var.get() * 12
        with STATE._lock: STATE.root = new_root

    def _on_random_root(self):
        new_root = random.choice(list(range(36, 61)))
        with STATE._lock: STATE.root = new_root
        self._update_root_buttons()
        self._log(f"[Root] → {NOTE_NAMES[new_root % 12]}{new_root//12-1}")

    def _on_auto_root(self):
        with STATE._lock: STATE.auto_root = self._auto_root_var.get()

    def _on_root_speed(self, val):
        with STATE._lock: STATE.auto_root_speed = int(val) / 100.0

    def _on_scale(self, _=None):
        with STATE._lock: STATE.scale_name = self._scale_var.get()

    def _on_density(self):
        with STATE._lock: STATE.density = self._density_var.get()

    def _on_evolve(self):
        with STATE._lock: STATE.auto_evolve = self._evolve_var.get()

    def _on_depth(self, val):
        with STATE._lock: STATE.evolve_depth = int(val) / 100.0

    def _on_speed(self, val):
        with STATE._lock: STATE.evolve_speed = int(val) / 100.0

    def _on_layer(self, key):
        with STATE._lock: STATE.layers[key] = self._layer_vars[key].get()

    def _on_vel(self, key, val):
        with STATE._lock: STATE.vel[key] = int(val)

    def _on_variation(self, key, val):
        with STATE._lock: STATE.variation[key] = int(val) / 100.0

    def _on_rest(self, key, val):
        with STATE._lock: STATE.rest_prob[key] = int(val) / 100.0

    def _update_root_buttons(self):
        current_name = NOTE_NAMES[STATE.root % 12]
        for name, btn in self._note_btns.items():
            is_sharp = '#' in name
            btn.config(bg=C_ACCENT if name == current_name
                       else ('#2a2a3e' if is_sharp else '#3a3a5a'))

    # ---- 再生 / 停止 ------------------------------------
    def _toggle_play(self):
        if self._playing: self._stop()
        else: self._start()

    def _start(self):
        global _midi_muted
        _midi_muted = False
        self._playing = True
        self._play_btn.config(text='  ■  STOP   ', bg='#cc4455',
                               activebackground='#aa3344')
        self._status_lbl.config(text='● PLAYING', fg=C_ON)
        self._log('--- 演奏開始 ---')

        self._drone   = DroneLayer(self._log)
        self._melody  = MelodyLayer(1, 1, 'melody',  0.75, 'Melody ', self._log)
        self._sparkle = MelodyLayer(2, 3, 'sparkle', 0.55, 'Sparkle', self._log)
        self._evo     = EvolutionController(self._log)

        self._drone.start()
        threading.Timer(2.0, self._melody.start).start()
        threading.Timer(4.0, self._sparkle.start).start()
        threading.Timer(5.0, self._evo.start).start()
        self.root.after(500, self._sync_ui)

    def _stop(self):
        global _midi_muted
        _midi_muted = True          # まずノートオンを即ブロック
        midi_panic()                # 今鳴っている音を即消音
        self._playing = False
        self._play_btn.config(text='  ▶  START  ', bg=C_ON,
                               activebackground='#00a87d')
        self._status_lbl.config(text='● STOPPED', fg=C_OFF)
        self._log('--- 演奏停止 ---')
        for layer in [self._drone, self._melody, self._sparkle, self._evo]:
            if layer: layer.stop()
        self.root.after(400, midi_panic)  # 念のため再度消音

    def _sync_ui(self):
        if not self._playing: return
        s = STATE.get()
        if self._scale_var.get() != s['scale_name']:
            self._scale_var.set(s['scale_name'])
        if self._density_var.get() != s['density']:
            self._density_var.set(s['density'])
        self._update_root_buttons()
        self.root.after(500, self._sync_ui)

    # ---- ログ -------------------------------------------
    def _log(self, msg):
        def _insert():
            self._log_text.config(state='normal')
            self._log_text.insert('end', msg + '\n')
            self._log_text.see('end')
            if int(self._log_text.index('end-1c').split('.')[0]) > 200:
                self._log_text.delete('1.0', '50.0')
            self._log_text.config(state='disabled')
        self.root.after(0, _insert)

    def _on_close(self):
        self._stop()
        self.root.after(300, self.root.destroy)

    def run(self):
        self.root.mainloop()

# ================================================================
if __name__ == '__main__':
    AmbientApp().run()
