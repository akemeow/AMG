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
    # ── 明るい系 ──────────────────────────────
    'Major':             [0, 2, 4, 5, 7, 9, 11],
    'Lydian':            [0, 2, 4, 6, 7, 9, 11],   # #4 が浮遊感
    'Lydian Dominant':   [0, 2, 4, 6, 7, 9, 10],   # Lydian + ♭7 幻想的
    'Mixolydian':        [0, 2, 4, 5, 7, 9, 10],   # ♭7 ロック/ポップ
    'Pentatonic Major':  [0, 2, 4, 7, 9],
    # ── 暗い系 ──────────────────────────────
    'Minor':             [0, 2, 3, 5, 7, 8, 10],   # 自然短音階
    'Dorian':            [0, 2, 3, 5, 7, 9, 10],   # ♮6 が特徴
    'Phrygian':          [0, 1, 3, 5, 7, 8, 10],   # ♭2 スペイン風
    'Locrian':           [0, 1, 3, 5, 6, 8, 10],   # ♭5 非常に暗い
    'Harmonic Minor':    [0, 2, 3, 5, 7, 8, 11],   # ♮7 ドラマチック
    'Melodic Minor':     [0, 2, 3, 5, 7, 9, 11],   # 滑らかなマイナー
    'Pentatonic Minor':  [0, 3, 5, 7, 10],
    'Blues':             [0, 3, 5, 6, 7, 10],
    # ── エキゾチック系 ──────────────────────
    'Phrygian Dominant': [0, 1, 4, 5, 7, 8, 10],   # 中東・フラメンコ
    'Hungarian Minor':   [0, 2, 3, 6, 7, 8, 11],   # ダーク＆エキゾチック
    'Double Harmonic':   [0, 1, 4, 5, 7, 8, 11],   # ビザンチン 非常に独特
    'Hirajoshi':         [0, 2, 3, 7, 8],           # 日本五音音階
    # ── 浮遊・無調系 ────────────────────────
    'Whole Tone':        [0, 2, 4, 6, 8, 10],       # 全音音階 印象派
    'Diminished':        [0, 2, 3, 5, 6, 8, 9, 11], # 半音全音交互
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
        self.layers     = {'drone': True, 'melody': True, 'sparkle': True, 'chord': True}
        self.vel        = {'drone': 45, 'melody': 38, 'sparkle': 28, 'chord': 55}
        self.drone_octave = 3  # ドローン絶対オクターブ (1〜5)、ルートと独立
        # 変化量 0.0〜1.0 : 低=ステップワイズ、高=大跳躍多め
        self.variation  = {'drone': 0.2,   'melody': 0.3,   'sparkle': 0.6,   'chord': 0.3}
        # 休符率 0.0〜1.0
        self.rest_prob    = {'drone': 0.0,   'melody': 0.35,  'sparkle': 0.60,  'chord': 0.20}
        # アルペジエーター
        self.arp_on          = True
        self.arp_mode        = 'up'    # 'up' / 'down' / 'zigzag' / 'random'
        self.arp_rate        = 0.25   # beats/step (BPM同期ノート値)
        self.arp_rate_random = False  # Trueのとき毎サイクルランダム選択
        self.chord_octave    = 1      # ベースオクターブオフセット (+1〜+3)
        self.chord_oct_range  = 1      # 何オクターブ分アルペジオを広げるか (1〜3)
        self.chord_degree  = 0           # Ⅰ (semitone offset)
        self.chord_quality = [0, 4, 7]  # maj
        self.chord_auto    = False
        self.chord_auto_bars = 8
        self.chord_rest_bars        = 4      # 休符の長さ（小節数）
        self.chord_rest_bars_random = False  # Trueのとき休符ごとにランダム選択
        # 全パラメーター自動ランダム切り替え
        self.arp_auto      = False
        self.arp_auto_bars = 4        # 何小節ごとに切り替えるか
        # 展開の深さ 0.0〜1.0 (転調幅・変化の大きさ)
        self.evolve_depth = 0.5
        # 展開の速さ 0.0〜1.0 (変化の頻度)
        self.evolve_speed = 0.5
        # ルートのランダム自動変化
        self.auto_root      = False
        self.auto_root_bars = 16     # 変化する小節数
        # スケールのランダム自動変化
        self.auto_scale      = False
        self.auto_scale_bars = 16

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
                auto_evolve      = self.auto_evolve,
                drone_octave     = self.drone_octave,
                evolve_depth     = self.evolve_depth,
                evolve_speed     = self.evolve_speed,
                auto_root       = self.auto_root,
                auto_root_bars  = self.auto_root_bars,
                auto_scale      = self.auto_scale,
                auto_scale_bars = self.auto_scale_bars,
                arp_on          = self.arp_on,
                arp_mode        = self.arp_mode,
                arp_rate        = self.arp_rate,
                arp_rate_random = self.arp_rate_random,
                chord_octave    = self.chord_octave,
                chord_oct_range = self.chord_oct_range,
                chord_degree  = self.chord_degree,
                chord_quality = list(self.chord_quality),
                chord_auto    = self.chord_auto,
                chord_auto_bars = self.chord_auto_bars,
                arp_auto        = self.arp_auto,
                arp_auto_bars   = self.arp_auto_bars,
                chord_rest_bars        = self.chord_rest_bars,
                chord_rest_bars_random = self.chord_rest_bars_random,
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

# ── シグナルランプ ────────────────────────────────────────
_lamp_root  = None          # tkinter root (App 起動後にセット)
_lamp_fns   = {}            # ch (0-3) → callable(on: bool)
_lamp_notes = [0, 0, 0, 0]  # チャンネルごとのアクティブノート数


class MidiClockSender:
    """AMG から Logic Pro へ MIDI クロックを送信する（AMG = マスター）"""

    def __init__(self):
        self._running = False

    def start(self):
        self._running = True
        try:
            get_midi().send_message([0xFA])   # MIDI Start
        except Exception:
            pass
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        try:
            get_midi().send_message([0xFC])   # MIDI Stop
        except Exception:
            pass

    def _loop(self):
        next_t = time.perf_counter()
        while self._running:
            bpm      = STATE.bpm
            interval = 60.0 / bpm / 24       # 24パルス/拍
            next_t  += interval
            try:
                get_midi().send_message([0xF8])   # MIDI Clock
            except Exception:
                pass
            sleep_t = next_t - time.perf_counter()
            if sleep_t > 0:
                time.sleep(sleep_t)          # 必ず sleep → GIL を解放
            else:
                next_t = time.perf_counter() # 遅れすぎたらリセット
                time.sleep(0)


class MidiClockReceiver:
    """Logic Pro から MIDI クロックを受信して BPM を同期する"""

    def __init__(self, on_bpm_change):
        self._on_bpm_change = on_bpm_change
        self._midi_in  = None
        self._running  = False
        self._last_t   = None
        self._intervals = []
        self._N        = 24   # 平均化パルス数（1拍分）

    def start(self):
        try:
            self._midi_in = rtmidi.MidiIn()
            ports = self._midi_in.get_ports()
            iac = next((i for i, p in enumerate(ports) if 'IAC' in p), None)
            if iac is None:
                return False
            self._midi_in.open_port(iac)
            # timing=False にするとクロックを無視してしまうので False を渡す
            self._midi_in.ignore_types(sysex=True, timing=False, active_sense=True)
            self._running = True
            self._midi_in.set_callback(self._callback)
            return True
        except Exception as e:
            print(f"MidiClockReceiver start error: {e}")
            return False

    def stop(self):
        self._running = False
        self._intervals.clear()
        self._last_t = None
        if self._midi_in:
            try:
                self._midi_in.cancel_callback()
                self._midi_in.close_port()
            except Exception:
                pass
            self._midi_in = None

    def _callback(self, message, data=None):
        if not self._running:
            return
        msg, _ = message
        if msg[0] == 0xF8:   # MIDI Clock (24 pulses per quarter note)
            now = time.time()
            if self._last_t is not None:
                interval = now - self._last_t
                # BPM 20〜300 の範囲外は無視
                if 0.005 < interval < 0.15:
                    self._intervals.append(interval)
                    if len(self._intervals) > self._N:
                        self._intervals.pop(0)
                    if len(self._intervals) >= 8:
                        avg = sum(self._intervals) / len(self._intervals)
                        bpm = int(round(60.0 / (avg * 24)))
                        bpm = max(20, min(300, bpm))
                        self._on_bpm_change(bpm)
            self._last_t = now
        elif msg[0] == 0xFC:  # MIDI Stop — クロックリセット
            self._intervals.clear()
            self._last_t = None

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
    if ch < 4 and ch in _lamp_fns and _lamp_root:
        _lamp_notes[ch] += 1
        if _lamp_notes[ch] == 1:   # 最初のノートオン → ランプ点灯
            _lamp_root.after(0, lambda c=ch: _lamp_fns[c](True))

def midi_off(ch, note):
    get_midi().send_message([0x80 | ch, note, 0])
    if ch < 4 and ch in _lamp_fns and _lamp_root:
        _lamp_notes[ch] = max(0, _lamp_notes[ch] - 1)
        if _lamp_notes[ch] == 0:   # 全ノートオフ → ランプ消灯
            _lamp_root.after(0, lambda c=ch: _lamp_fns[c](False))

def midi_all_off(ch):
    get_midi().send_message([0xB0 | ch, 123, 0])
    if ch < 4 and ch in _lamp_fns and _lamp_root:
        _lamp_notes[ch] = 0
        _lamp_root.after(0, lambda c=ch: _lamp_fns[c](False))

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
            # ルートの音名（ピッチクラス）のみ使用 → ドローン独自のオクターブを適用
            root = (s['root'] % 12) + s['drone_octave'] * 12
            root = max(0, min(115, root))
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
        t_mod        = time.time() + random.uniform(30, 60)
        t_scale      = time.time() + random.uniform(45, 90)
        t_dens       = time.time() + random.uniform(20, 50)
        t_auto_root  = time.time() + 1.0
        t_auto_scale = time.time() + 1.0

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

                # 転調インターバル: depthで幅を制御 (auto_root=Falseならスキップ)
                if now >= t_mod:
                    if s['auto_root']:
                        if depth < 0.3:
                            iv_pool = [-2, 2]
                        elif depth < 0.7:
                            iv_pool = [-5, -2, 2, 5]
                        else:
                            iv_pool = MODULATION_INTERVALS
                        iv  = random.choice(iv_pool)
                        new = max(36, min(60, s['root'] + iv))
                        with STATE._lock: STATE.root = new
                        self.log(f"[展開] 転調 → {NOTE_NAMES[new % 12]}{new//12-1}  (depth={int(depth*100)}%)")
                    interval = 90 - spd * 75
                    t_mod = now + random.uniform(interval * 0.6, interval * 1.4)

                # スケール切り替え: depthが低いと関連スケールのみ
                if now >= t_scale:
                    RELATED = {
                        'Major':             ['Lydian', 'Mixolydian', 'Pentatonic Major'],
                        'Lydian':            ['Major', 'Lydian Dominant', 'Pentatonic Major'],
                        'Lydian Dominant':   ['Lydian', 'Mixolydian', 'Whole Tone'],
                        'Mixolydian':        ['Major', 'Dorian', 'Lydian Dominant'],
                        'Pentatonic Major':  ['Major', 'Lydian', 'Mixolydian'],
                        'Minor':             ['Dorian', 'Harmonic Minor', 'Pentatonic Minor', 'Blues'],
                        'Dorian':            ['Minor', 'Phrygian', 'Melodic Minor'],
                        'Phrygian':          ['Minor', 'Phrygian Dominant', 'Locrian'],
                        'Locrian':           ['Phrygian', 'Diminished'],
                        'Harmonic Minor':    ['Minor', 'Phrygian Dominant', 'Hungarian Minor'],
                        'Melodic Minor':     ['Minor', 'Dorian', 'Lydian Dominant'],
                        'Pentatonic Minor':  ['Minor', 'Blues', 'Dorian', 'Hirajoshi'],
                        'Blues':             ['Pentatonic Minor', 'Minor', 'Dorian'],
                        'Phrygian Dominant': ['Phrygian', 'Harmonic Minor', 'Double Harmonic'],
                        'Hungarian Minor':   ['Harmonic Minor', 'Double Harmonic'],
                        'Double Harmonic':   ['Hungarian Minor', 'Phrygian Dominant'],
                        'Hirajoshi':         ['Pentatonic Minor', 'Phrygian'],
                        'Whole Tone':        ['Lydian Dominant', 'Diminished'],
                        'Diminished':        ['Whole Tone', 'Locrian', 'Phrygian'],
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


            time.sleep(0.1)

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False


class ChordLayer:
    """Ch.4 — コード / アルペジエーター"""

    def __init__(self, log_fn):
        self.log             = log_fn
        self.ch              = 3
        self._running        = False
        self._cur_root       = None
        self._cur_oct_offset = None
        self._cur_oct_range  = None
        self._cur_degree     = None
        self._cur_quality    = None
        self._chord_notes    = []

    def _build_chord(self, root, oct_offset=1, oct_range=1, degree=0, quality=None):
        if quality is None:
            quality = [0, 4, 7]
        base = root + oct_offset * 12 + degree
        notes = []
        for oct in range(oct_range):
            for iv in quality:
                n = base + oct * 12 + iv
                if 0 <= n <= 127:
                    notes.append(n)
        return notes

    def _loop(self):
        while self._running:
            s = STATE.get()
            if not s['layers'].get('chord', True):
                midi_all_off(self.ch)
                time.sleep(0.2)
                continue

            beat      = 60.0 / s['bpm']
            root      = s['root']
            arp_on    = s['arp_on']
            arp_mode  = s['arp_mode']
            if s['arp_rate_random']:
                arp_rate = random.choice([0.125, 0.25, 0.5, 1.0, 2.0, 4.0])
            else:
                arp_rate = s['arp_rate']
            rest_prob  = s['rest_prob']['chord']
            vel_base   = s['vel']['chord']
            dynamic    = s['dynamic']
            oct_offset = s['chord_octave']
            oct_range  = s['chord_oct_range']
            degree     = s['chord_degree']
            quality    = s['chord_quality']

            if (root       != self._cur_root
                    or oct_offset != self._cur_oct_offset
                    or oct_range  != self._cur_oct_range
                    or degree     != self._cur_degree
                    or quality    != self._cur_quality):
                self._chord_notes    = self._build_chord(root, oct_offset, oct_range, degree, quality)
                self._cur_root       = root
                self._cur_oct_offset = oct_offset
                self._cur_oct_range  = oct_range
                self._cur_degree     = degree
                self._cur_quality    = quality

            if not self._chord_notes:
                time.sleep(0.2)
                continue

            # rest_bars == 0 はレストなし
            rest_bars = s['chord_rest_bars']
            if rest_bars > 0 and random.random() < rest_prob:
                if s['chord_rest_bars_random']:
                    rest_bars = random.choice([1, 2, 4, 8, 16])
                self._interruptible_sleep(beat * 4 * rest_bars)
                continue

            notes = list(self._chord_notes)
            vel   = max(1, min(127, int((vel_base + random.randint(-10, 10)) * dynamic)))

            if arp_on:
                if arp_mode == 'up':
                    seq = notes
                elif arp_mode == 'down':
                    seq = list(reversed(notes))
                elif arp_mode == 'zigzag':
                    seq = notes + list(reversed(notes[1:max(1, len(notes) - 1)]))
                else:
                    seq = notes[:]
                    random.shuffle(seq)

                names = [NOTE_NAMES[n % 12] for n in notes]
                self.log(f"Chord   {names}  [{arp_mode}]  {arp_rate:.2f}beat/step")
                step = arp_rate * beat
                for note in seq:
                    if not self._running:
                        break
                    midi_on(self.ch, note, vel)
                    self._interruptible_sleep(step * 0.82)
                    midi_off(self.ch, note)
                    self._interruptible_sleep(step * 0.18)
            else:
                names = [NOTE_NAMES[n % 12] for n in notes]
                dur   = wchoice({4.0: 2, 8.0: 3, 16.0: 1})
                self.log(f"Chord   {names}  [block]  {dur}拍")
                for note in notes:
                    midi_on(self.ch, note, vel)
                self._interruptible_sleep(beat * dur * 0.88)
                for note in notes:
                    midi_off(self.ch, note)

    def _interruptible_sleep(self, duration):
        end = time.time() + duration
        while self._running and time.time() < end:
            time.sleep(0.02)

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        midi_all_off(self.ch)



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
        # 0=7時 (225°) → max=5時 (315°)、時計回り
        start_angle  = 225          # 7時の位置
        full_extent  = -270         # 時計回り270°

        # トラック弧
        self.create_arc(cx-r, cy-r, cx+r, cy+r,
                        start=start_angle, extent=full_extent,
                        outline=C_TRACK, width=4, style='arc')

        # 値弧
        val_extent = self._ratio() * full_extent
        if abs(val_extent) > 0:
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
        if self.to <= 1.0:
            return f'{int(self._ratio()*100)}%'
        else:
            return str(int(self._val))

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


BAR_OPTIONS = [1, 2, 4, 8, 16, 32, 64]

# アルペジエーター ノート値 (beats/step)
ARP_RATES = [
    ('1/32', 0.125),
    ('1/16', 0.25),
    ('1/8',  0.5),
    ('1/4',  1.0),
    ('1/2',  2.0),
    ('1',    4.0),
]
ARP_RATE_COLORS = {
    0.125: '#ff6b6b',
    0.25:  '#ffa94d',
    0.5:   '#ffe066',
    1.0:   '#69db7c',
    2.0:   '#4dabf7',
    4.0:   '#cc5de8',
}

CHORD_DEGREES = [
    ('Ⅰ',   0),
    ('Ⅱ',   2),
    ('♭Ⅲ',  3),
    ('Ⅲ',   4),
    ('Ⅳ',   5),
    ('Ⅴ',   7),
    ('♭Ⅶ',  10),
    ('Ⅶ',   11),
]

CHORD_QUALITIES = [
    ('maj',   [0, 4, 7]),
    ('m',     [0, 3, 7]),
    ('M7',    [0, 4, 7, 11]),
    ('m7',    [0, 3, 7, 10]),
    ('sus4',  [0, 5, 7]),
    ('7',     [0, 4, 7, 10]),
    ('dim',   [0, 3, 6]),
    ('m7♭5',  [0, 3, 6, 10]),
]

CHORD_DEGREE_COLOR = {
    0:  '#ff6b6b',
    2:  '#ffd166',
    3:  '#c9f07a',
    4:  '#69db7c',
    5:  '#4dabf7',
    7:  '#748ffc',
    10: '#ffa94d',
    11: '#f783ac',
}

CHORD_QUALITY_COLOR = {
    'maj':   '#e0e0ff',
    'm':     '#a9e4ff',
    'M7':    '#ffd166',
    'm7':    '#69db7c',
    'sus4':  '#ff9f43',
    '7':     '#ff6b6b',
    'dim':   '#f783ac',
    'm7♭5':  '#da77f2',
}


def midi_note_name(n):
    # Logic Pro convention: MIDI 0 = C-2, MIDI 24 = C0, MIDI 36 = C1
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 2}"


def bars_to_ms(bars, bpm):
    """小節数をミリ秒に変換 (4/4拍子)"""
    return int(bars * 4 * 60 / bpm * 1000)

def labeled_knob(parent, label, from_, to, default, color, bg, command):
    """ノブ + 上ラベルをまとめたフレームを返す"""
    f = tk.Frame(parent, bg=bg)
    tk.Label(f, text=label, bg=bg, fg=color,
             font=('Helvetica', 7), anchor='center').pack()
    k = Knob(f, from_=from_, to=to, default=default,
             color=color, bg=bg, command=command)
    k.pack()
    return f, k


def pwr_btn(parent, text, bg, initial=False,
            fg_on='#00c896', fg_off='#555577', command=None):
    """⏻ アイコン付きトグルボタン。(BooleanVar, Frame) を返す"""
    var = tk.BooleanVar(value=initial)
    f   = tk.Frame(parent, bg=bg)
    ico = tk.Label(f, text='⏻', bg=bg,
                   fg=fg_on if initial else fg_off,
                   font=('Helvetica', 11), cursor='hand2')
    ico.pack(side='left')
    lbl = tk.Label(f, text=text, bg=bg,
                   fg=fg_on if initial else fg_off,
                   font=('Helvetica', 9, 'bold'), cursor='hand2')
    lbl.pack(side='left', padx=(2, 0))

    def _set_visual(v):
        c = fg_on if v else fg_off
        ico.config(fg=c)
        lbl.config(fg=c)

    def _toggle(e=None):
        v = not var.get()
        var.set(v)
        _set_visual(v)
        if command:
            command()

    ico.bind('<Button-1>', _toggle)
    lbl.bind('<Button-1>', _toggle)
    # 外部から var.set() されても自動でビジュアル更新
    var.trace_add('write', lambda *_: _set_visual(var.get()))
    return var, f

class AmbientApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Ambient Generator')
        self.root.configure(bg=C_BG)
        self.root.resizable(False, False)

        self._playing = False
        self._drone = self._melody = self._sparkle = self._evo = self._chord = None
        self._current_root_lbl  = None
        self._current_scale_lbl = None
        self._current_chord_lbl = None
        self._clock_receiver    = None   # MidiClockReceiver (slave)
        self._clock_sender      = None   # MidiClockSender   (master)
        self._sync_mode         = 'off'  # 'off' / 'slave' / 'master'
        self._build_ui()
        global _lamp_root
        _lamp_root = self.root   # シグナルランプ用 after() ターゲット
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
        self._build_chord_type(left)
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

        # MIDI Clock SYNC ボタン
        self._sync_btn = tk.Label(
            row, text='SYNC', bg='#1e1e38', fg='#4a9eff',
            font=('Helvetica', 9, 'bold'), relief='flat',
            padx=8, pady=4, cursor='hand2')
        self._sync_btn.pack(side='right', padx=(0, 6))
        self._sync_btn.bind('<Button-1>', lambda e: self._toggle_bpm_sync())
        self._clock_receiver = None

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
                lbl = tk.Label(
                    r, text=n, width=3,
                    bg='#1e1e38' if '#' in n else '#1e2030',
                    fg='#4a9eff', relief='flat',
                    font=('Helvetica', 8, 'bold'), pady=4,
                    cursor='hand2')
                lbl.bind('<Button-1>', lambda e, i=idx: self._on_root(i))
                lbl.pack(side='left', padx=1)
                self._note_btns[n] = lbl
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

        # 現在のルート音表示
        self._current_root_lbl = tk.Label(
            f, text='', bg=C_PANEL, fg=C_ON,
            font=('Helvetica', 18, 'bold'), anchor='center')
        self._current_root_lbl.pack(fill='x', pady=(6, 0))

        # Randomize ボタン + Auto Root + Speed ノブ
        rand_row = tk.Frame(f, bg=C_PANEL)
        rand_row.pack(fill='x', pady=(8, 0))

        tk.Button(rand_row, text='RANDOM', command=self._on_random_root,
                  bg='#3a3a6a', fg=C_TEXT, relief='flat',
                  font=('Helvetica', 8, 'bold'), padx=8, pady=3,
                  activebackground=C_ACCENT, cursor='hand2').pack(side='left')

        self._auto_root_var, _pb = pwr_btn(rand_row, 'Auto', C_PANEL,
                                            initial=False, command=self._on_auto_root)
        _pb.pack(side='left', padx=(10, 4))

        # 小節数ボタン
        bar_row = tk.Frame(f, bg=C_PANEL)
        bar_row.pack(fill='x', pady=(4, 0))
        tk.Label(bar_row, text='毎', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left')
        self._root_bar_btns = {}
        self._root_bars_var = tk.IntVar(value=16)
        for b in BAR_OPTIONS:
            lbl = tk.Label(bar_row, text=str(b),
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=6, pady=3,
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=b: self._on_root_bars(v))
            lbl.pack(side='left', padx=1)
            self._root_bar_btns[b] = lbl
        tk.Label(bar_row, text='小節', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(2, 0))
        self._update_bar_buttons(self._root_bar_btns, 16)

    def _build_scale(self, parent):
        f = section(parent, 'Scale')
        f.pack(fill='x', pady=(0, 6))
        self._scale_var = tk.StringVar(value='Lydian')
        menu = ttk.Combobox(f, textvariable=self._scale_var,
                            values=list(SCALES.keys()),
                            state='readonly', width=22)
        menu.pack(anchor='w')
        menu.bind('<<ComboboxSelected>>', self._on_scale)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TCombobox',
                        fieldbackground=C_SLIDER, background=C_SLIDER,
                        foreground=C_TEXT, selectbackground=C_ACCENT,
                        arrowcolor=C_TEXT)

        # 現在のスケール表示
        self._current_scale_lbl = tk.Label(
            f, text='', bg=C_PANEL, fg=C_ON,
            font=('Helvetica', 13, 'bold'), anchor='center')
        self._current_scale_lbl.pack(fill='x', pady=(4, 0))

        # Auto Scale + Speed ノブ
        auto_row = tk.Frame(f, bg=C_PANEL)
        auto_row.pack(fill='x', pady=(8, 0))
        self._auto_scale_var, _pb = pwr_btn(auto_row, 'Auto Scale', C_PANEL,
                                             initial=False, command=self._on_auto_scale)
        _pb.pack(side='left')

        # 小節数ボタン
        sbar_row = tk.Frame(f, bg=C_PANEL)
        sbar_row.pack(fill='x', pady=(4, 0))
        tk.Label(sbar_row, text='毎', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left')
        self._scale_bar_btns = {}
        for b in BAR_OPTIONS:
            lbl = tk.Label(sbar_row, text=str(b),
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=6, pady=3,
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=b: self._on_scale_bars(v))
            lbl.pack(side='left', padx=1)
            self._scale_bar_btns[b] = lbl
        tk.Label(sbar_row, text='小節', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(2, 0))
        self._update_bar_buttons(self._scale_bar_btns, 16)

    def _build_chord_type(self, parent):
        f = section(parent, 'Chord Type')
        f.pack(fill='x', pady=(0, 6))

        # AUTO CHORD ボタン + 小節選択
        auto_row = tk.Frame(f, bg=C_PANEL)
        auto_row.pack(fill='x', pady=(0, 4))
        self._chord_auto_var = tk.BooleanVar(value=False)
        self._chord_auto_btn = tk.Label(
            auto_row, text='AUTO CHORD', bg='#1e1e38', fg='#4a9eff',
            relief='flat', font=('Helvetica', 9, 'bold'), padx=8, pady=3,
            cursor='hand2')
        self._chord_auto_btn.bind('<Button-1>', lambda e: self._on_chord_auto())
        self._chord_auto_btn.pack(side='left')
        tk.Label(auto_row, text='毎', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(8, 2))
        self._chord_auto_bar_btns = {}
        for b in [2, 4, 8, 16]:
            lbl = tk.Label(auto_row, text=str(b),
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=5, pady=3,
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=b: self._on_chord_auto_bars(v))
            lbl.pack(side='left', padx=1)
            self._chord_auto_bar_btns[b] = lbl
        tk.Label(auto_row, text='小節', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(2, 0))
        self._update_bar_buttons(self._chord_auto_bar_btns, 8)

        # 度数ボタン行
        tk.Label(f, text='Degree', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(anchor='w', padx=2)
        deg_row = tk.Frame(f, bg=C_PANEL)
        deg_row.pack(fill='x', pady=1)
        self._chord_degree_btns = {}
        for lbl_text, semitone in CHORD_DEGREES:
            col = CHORD_DEGREE_COLOR.get(semitone, '#cccccc')
            btn = tk.Label(deg_row, text=lbl_text, width=4,
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 9), pady=4, cursor='hand2')
            btn.bind('<Button-1>', lambda e, s=semitone: self._on_chord_degree(s))
            btn.pack(side='left', padx=1)
            self._chord_degree_btns[semitone] = (btn, col)
        self._update_chord_degree_buttons(0)

        # クオリティボタン行
        tk.Label(f, text='Quality', bg=C_PANEL, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(anchor='w', padx=2, pady=(4, 0))
        qual_row = tk.Frame(f, bg=C_PANEL)
        qual_row.pack(fill='x', pady=1)
        self._chord_quality_btns = {}
        for lbl_text, ivs in CHORD_QUALITIES:
            col = CHORD_QUALITY_COLOR.get(lbl_text, '#cccccc')
            key = lbl_text
            btn = tk.Label(qual_row, text=lbl_text, width=5,
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), pady=4, cursor='hand2')
            btn.bind('<Button-1>', lambda e, q=ivs, k=key: self._on_chord_quality(q, k))
            btn.pack(side='left', padx=1)
            self._chord_quality_btns[key] = (btn, col, ivs)
        self._update_chord_quality_buttons('maj')

        # 現在再生中のコード表示
        self._current_chord_lbl = tk.Label(
            f, text='', bg=C_PANEL, fg=C_ON,
            font=('Helvetica', 14, 'bold'), anchor='center')
        self._current_chord_lbl.pack(fill='x', pady=(4, 0))

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
        self._evolve_var, _pb = pwr_btn(evo_row, 'Auto Evolve', C_PANEL,
                                         initial=True, command=self._on_evolve)
        _pb.pack(side='left')

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
            ('drone',   'DRONE',   'Ch.1', 0, 45, 0.20, 0.00),
            ('melody',  'MELODY',  'Ch.2', 1, 38, 0.30, 0.35),
            ('sparkle', 'SPARKLE', 'Ch.3', 2, 28, 0.60, 0.60),
        ]
        self._layer_vars = {}

        for key, label, ch_label, midi_ch, def_vel, def_var, def_rest in layers_cfg:
            BG = '#141428'
            block = tk.Frame(f, bg=BG, padx=10, pady=8)
            block.pack(fill='x', pady=3)

            # ヘッダー
            header = tk.Frame(block, bg=BG)
            header.pack(fill='x', pady=(0, 6))
            lvar, _pb = pwr_btn(header, label, BG, initial=True,
                                fg_on=C_TEXT, fg_off='#555577',
                                command=lambda k=key: self._on_layer(k))
            self._layer_vars[key] = lvar
            _pb.pack(side='left')
            tk.Label(header, text=ch_label, bg=BG, fg=C_MUTED,
                     font=('Helvetica', 8)).pack(side='left', padx=(6, 0))
            # シグナルランプ
            lamp = tk.Label(header, text='●', bg=BG, fg='#2a2a4a',
                            font=('Helvetica', 10))
            lamp.pack(side='left', padx=(5, 0))
            _lamp_fns[midi_ch] = lambda on, w=lamp: w.config(fg='#00c896' if on else '#2a2a4a')

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

            # Drone のみオクターブ選択を追加
            if key == 'drone':
                oct_row = tk.Frame(block, bg=BG)
                oct_row.pack(fill='x', pady=(6, 0))
                tk.Label(oct_row, text='Oct', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._drone_oct_btns = {}
                for ov in [1, 2, 3, 4, 5]:
                    btn = tk.Label(oct_row, text=str(ov), width=3,
                                   bg='#1e1e38', fg='#4a9eff', relief='flat',
                                   font=('Helvetica', 9), pady=3, cursor='hand2')
                    btn.bind('<Button-1>', lambda e, v=ov: self._on_drone_octave(v))
                    btn.pack(side='left', padx=1)
                    self._drone_oct_btns[ov] = btn
                self._update_drone_oct_buttons(3)

        # ---- CHORD ブロック ----
        C_CHORD = '#7ecfe0'
        BG = '#141428'
        block = tk.Frame(f, bg=BG, padx=10, pady=8)
        block.pack(fill='x', pady=3)

        header = tk.Frame(block, bg=BG)
        header.pack(fill='x', pady=(0, 6))
        lvar, _pb = pwr_btn(header, 'CHORD', BG, initial=True,
                            fg_on='#7ecfe0', fg_off='#555577',
                            command=lambda: self._on_layer('chord'))
        self._layer_vars['chord'] = lvar
        _pb.pack(side='left')
        tk.Label(header, text='Ch.4', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(6, 0))
        # シグナルランプ (Ch.4 = MIDI ch 3)
        chord_lamp = tk.Label(header, text='●', bg=BG, fg='#2a2a4a',
                              font=('Helvetica', 10))
        chord_lamp.pack(side='left', padx=(5, 0))
        _lamp_fns[3] = lambda on, w=chord_lamp: w.config(fg='#00c896' if on else '#2a2a4a')

        # ARP ON/OFF + モード選択
        arp_row = tk.Frame(block, bg=BG)
        arp_row.pack(fill='x', pady=(0, 4))
        self._arp_var, _pb = pwr_btn(arp_row, 'ARP', BG, initial=True,
                                     fg_on=C_CHORD, fg_off='#555577',
                                     command=self._on_arp_on)
        _pb.pack(side='left')

        self._arp_mode_var = tk.StringVar(value='up')
        arp_mode_cb = ttk.Combobox(arp_row, textvariable=self._arp_mode_var,
                                   values=['up', 'down', 'zigzag', 'random'],
                                   state='readonly', width=8)
        arp_mode_cb.pack(side='left', padx=(8, 0))
        arp_mode_cb.bind('<<ComboboxSelected>>', self._on_arp_mode)

        # Rate ボタン行 (BPM同期ノート値)
        rate_row = tk.Frame(block, bg=BG)
        rate_row.pack(fill='x', pady=(0, 2))
        tk.Label(rate_row, text='Rate', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 4))
        self._arp_rate_btns = {}
        for label, val in ARP_RATES:
            lbl = tk.Label(rate_row, text=label,
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=5, pady=3,
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=val: self._on_arp_rate_btn(v))
            lbl.pack(side='left', padx=1)
            self._arp_rate_btns[val] = lbl
        # RAND ボタン
        self._arp_rand_var = tk.BooleanVar(value=False)
        self._arp_rand_btn = tk.Label(rate_row, text='RAND',
                                      bg='#1e1e38', fg='#4a9eff', relief='flat',
                                      font=('Helvetica', 8, 'bold'), padx=6, pady=3,
                                      cursor='hand2')
        self._arp_rand_btn.bind('<Button-1>', lambda e: self._on_arp_rate_random())
        self._arp_rand_btn.pack(side='left', padx=(6, 0))
        self._update_arp_rate_buttons(0.25)

        # AUTO ランダム切り替え行
        auto_row = tk.Frame(block, bg=BG)
        auto_row.pack(fill='x', pady=(2, 4))
        self._arp_auto_var = tk.BooleanVar(value=False)
        self._arp_auto_btn = tk.Label(auto_row, text='AUTO RANDOM',
                                      bg='#1e1e38', fg='#4a9eff', relief='flat',
                                      font=('Helvetica', 9, 'bold'), padx=8, pady=3,
                                      cursor='hand2')
        self._arp_auto_btn.bind('<Button-1>', lambda e: self._on_arp_auto())
        self._arp_auto_btn.pack(side='left')
        tk.Label(auto_row, text='毎', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(8, 2))
        self._arp_auto_bar_btns = {}
        for b in [1, 2, 4, 8, 16]:
            lbl = tk.Label(auto_row, text=str(b),
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=5, pady=3,
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=b: self._on_arp_auto_bars(v))
            lbl.pack(side='left', padx=1)
            self._arp_auto_bar_btns[b] = lbl
        tk.Label(auto_row, text='小節', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(2, 0))
        self._update_bar_buttons(self._arp_auto_bar_btns, 4)

        # オクターブ設定
        oct_row = tk.Frame(block, bg=BG)
        oct_row.pack(fill='x', pady=(0, 4))
        tk.Label(oct_row, text='Oct', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left')
        self._chord_oct_var = tk.IntVar(value=1)
        for o in [1, 2, 3]:
            tk.Radiobutton(oct_row, text=str(o), variable=self._chord_oct_var, value=o,
                           bg=BG, fg=C_TEXT, selectcolor=C_ACCENT,
                           activebackground=BG,
                           command=self._on_chord_octave).pack(side='left', padx=3)
        tk.Label(oct_row, text='  Range', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(8, 0))
        self._chord_oct_range_var = tk.IntVar(value=1)
        for r in [1, 2, 3]:
            tk.Radiobutton(oct_row, text=str(r), variable=self._chord_oct_range_var, value=r,
                           bg=BG, fg=C_TEXT, selectcolor=C_ACCENT,
                           activebackground=BG,
                           command=self._on_chord_oct_range).pack(side='left', padx=3)

        # ノブ3つ
        knob_row = tk.Frame(block, bg=BG)
        knob_row.pack()
        _, kv = labeled_knob(knob_row, 'Vel', 1, 127, 55,
                              C_CHORD, BG, lambda v: self._on_vel('chord', v))
        kv.master.pack(side='left', padx=10)
        _, krest = labeled_knob(knob_row, 'Rest', 0, 100, 20,
                                 C_REST, BG, lambda v: self._on_rest('chord', v))
        krest.master.pack(side='left', padx=10)

        # 休符の長さ（小節数）
        restbar_row = tk.Frame(block, bg=BG)
        restbar_row.pack(fill='x', pady=(4, 0))
        tk.Label(restbar_row, text='Rest len', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 4))
        self._chord_rest_bar_btns = {}
        for b in [0, 1, 2, 4, 8, 16]:
            lbl = tk.Label(restbar_row, text='なし' if b == 0 else str(b),
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=5, pady=3,
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=b: self._on_chord_rest_bars(v))
            lbl.pack(side='left', padx=1)
            self._chord_rest_bar_btns[b] = lbl
        tk.Label(restbar_row, text='小節', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(2, 0))
        self._chord_rest_rand_var = tk.BooleanVar(value=False)
        self._chord_rest_rand_btn = tk.Label(restbar_row, text='RAND',
                                             bg='#1e1e38', fg='#4a9eff', relief='flat',
                                             font=('Helvetica', 8, 'bold'), padx=6, pady=3,
                                             cursor='hand2')
        self._chord_rest_rand_btn.bind('<Button-1>', lambda e: self._on_chord_rest_bars_random())
        self._chord_rest_rand_btn.pack(side='left', padx=(6, 0))
        self._update_bar_buttons(self._chord_rest_bar_btns, 4)

    def _build_log(self, parent):
        f = section(parent, 'Log')
        f.pack(fill='both', expand=True)
        self._log_text = tk.Text(f, height=6, bg='#0a0a18', fg='#6677aa',
                                  font=('Menlo', 8), relief='flat',
                                  state='disabled', wrap='none')
        self._log_text.pack(fill='both', expand=True)

    # ---- イベントハンドラ --------------------------------
    def _toggle_bpm_sync(self):
        """OFF → SLAVE → MASTER → OFF とサイクル"""
        # 現在の状態を停止
        if self._clock_receiver:
            self._clock_receiver.stop()
            self._clock_receiver = None
        if self._clock_sender:
            self._clock_sender.stop()
            self._clock_sender = None

        if self._sync_mode == 'off':
            # → SLAVE: Logic Pro がマスター、AMG が追従
            receiver = MidiClockReceiver(self._on_clock_bpm)
            if receiver.start():
                self._clock_receiver = receiver
                self._sync_mode = 'slave'
                self._sync_btn.config(bg='#00b894', fg='#0f0f1e', text='◀ SLAVE')
                self._bpm_knob.color = '#444466'
                self._bpm_knob._draw()
                self._log('--- SYNC: SLAVE (Logic Pro → AMG) ---')
            else:
                self._sync_mode = 'off'
                self._log('--- SYNC ERROR: IAC Driver が見つかりません ---')

        elif self._sync_mode == 'slave':
            # → MASTER: AMG がマスター、Logic Pro が追従
            self._bpm_knob.color = C_TEXT
            self._bpm_knob._draw()
            sender = MidiClockSender()
            sender.start()
            self._clock_sender = sender
            self._sync_mode = 'master'
            self._sync_btn.config(bg='#ffa94d', fg='#0f0f1e', text='MASTER ▶')
            self._log('--- SYNC: MASTER (AMG → Logic Pro) ---')

        else:
            # → OFF
            self._sync_mode = 'off'
            self._sync_btn.config(bg='#1e1e38', fg='#4a9eff', text='SYNC')
            self._bpm_knob.color = C_TEXT
            self._bpm_knob._draw()
            self._log('--- SYNC OFF ---')

    def _on_clock_bpm(self, bpm):
        """MIDI クロック受信スレッドから呼ばれる → UI スレッドに転送"""
        def _update():
            with STATE._lock:
                STATE.bpm = bpm
            self._bpm_knob.set(bpm)
        self.root.after(0, _update)

    def _on_bpm(self, val):
        if self._clock_receiver is not None:
            return  # SYNC中はノブ操作を無視
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

    def _on_root_bars(self, val):
        with STATE._lock: STATE.auto_root_bars = val
        self._update_bar_buttons(self._root_bar_btns, val)

    def _on_scale_bars(self, val):
        with STATE._lock: STATE.auto_scale_bars = val
        self._update_bar_buttons(self._scale_bar_btns, val)

    def _update_bar_buttons(self, btns, selected):
        colors = {0: '#aaaaaa', 1: '#ff6b6b', 2: '#ffa94d', 4: '#ffe066',
                  8: '#69db7c', 16: '#4dabf7', 32: '#cc5de8', 64: '#f783ac'}
        for b, btn in btns.items():
            if b == selected:
                btn.config(bg=colors.get(b, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 10, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff',
                           font=('Helvetica', 8))

    def _on_scale(self, _=None):
        with STATE._lock: STATE.scale_name = self._scale_var.get()

    def _on_auto_scale(self):
        with STATE._lock: STATE.auto_scale = self._auto_scale_var.get()

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

    def _on_arp_on(self):
        with STATE._lock: STATE.arp_on = self._arp_var.get()

    def _on_arp_mode(self, _=None):
        with STATE._lock: STATE.arp_mode = self._arp_mode_var.get()

    def _on_arp_rate_btn(self, val):
        with STATE._lock:
            STATE.arp_rate        = val
            STATE.arp_rate_random = False
        self._arp_rand_var.set(False)
        self._update_arp_rate_buttons(val)

    def _on_arp_rate_random(self):
        new_state = not self._arp_rand_var.get()
        self._arp_rand_var.set(new_state)
        with STATE._lock: STATE.arp_rate_random = new_state
        self._update_arp_rate_buttons(STATE.arp_rate)

    def _update_arp_rate_buttons(self, selected):
        rand_on = self._arp_rand_var.get() if hasattr(self, '_arp_rand_var') else False
        for val, btn in self._arp_rate_btns.items():
            if not rand_on and val == selected:
                col = ARP_RATE_COLORS.get(val, '#69db7c')
                btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))
        if hasattr(self, '_arp_rand_btn'):
            if rand_on:
                self._arp_rand_btn.config(bg='#da77f2', fg='#0f0f1e',
                                          font=('Helvetica', 8, 'bold'))
            else:
                self._arp_rand_btn.config(bg='#1e1e38', fg='#4a9eff',
                                          font=('Helvetica', 8, 'bold'))

    def _on_drone_octave(self, val):
        with STATE._lock: STATE.drone_octave = val
        self._update_drone_oct_buttons(val)

    def _update_drone_oct_buttons(self, selected):
        colors = {1: '#a9e4ff', 2: '#4dabf7', 3: '#69db7c', 4: '#ffa94d', 5: '#ff6b6b'}
        for ov, btn in self._drone_oct_btns.items():
            if ov == selected:
                btn.config(bg=colors.get(ov, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 9, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff',
                           font=('Helvetica', 9))

    def _on_chord_octave(self):
        with STATE._lock: STATE.chord_octave = self._chord_oct_var.get()

    def _on_chord_oct_range(self):
        with STATE._lock: STATE.chord_oct_range = self._chord_oct_range_var.get()

    def _on_chord_degree(self, semitone):
        with STATE._lock: STATE.chord_degree = semitone
        self._update_chord_degree_buttons(semitone)
        deg_lbl = next((l for l, s in CHORD_DEGREES if s == semitone), str(semitone))
        qual_lbl = next((l for l, ivs in CHORD_QUALITIES if ivs == STATE.chord_quality), '')
        self._log(f"[Chord] → {deg_lbl}{qual_lbl}")

    def _on_chord_quality(self, ivs, key):
        with STATE._lock: STATE.chord_quality = ivs
        self._update_chord_quality_buttons(key)
        deg_lbl = next((l for l, s in CHORD_DEGREES if s == STATE.chord_degree), '')
        self._log(f"[Chord] → {deg_lbl}{key}")

    def _on_chord_auto(self):
        new = not self._chord_auto_var.get()
        self._chord_auto_var.set(new)
        with STATE._lock: STATE.chord_auto = new
        if new:
            self._chord_auto_btn.config(bg='#da77f2', fg='#0f0f1e')
        else:
            self._chord_auto_btn.config(bg='#1e1e38', fg='#4a9eff')

    def _on_chord_auto_bars(self, val):
        with STATE._lock: STATE.chord_auto_bars = val
        self._update_bar_buttons(self._chord_auto_bar_btns, val)

    def _update_chord_degree_buttons(self, selected):
        for semitone, (btn, col) in self._chord_degree_btns.items():
            if semitone == selected:
                btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 9))

    def _update_chord_quality_buttons(self, selected_key):
        for key, (btn, col, ivs) in self._chord_quality_btns.items():
            if key == selected_key:
                btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 8, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))

    def _on_chord_rest_bars(self, val):
        with STATE._lock:
            STATE.chord_rest_bars        = val
            STATE.chord_rest_bars_random = False
        self._chord_rest_rand_var.set(False)
        self._chord_rest_rand_btn.config(bg='#1e1e38', fg='#4a9eff')
        self._update_bar_buttons(self._chord_rest_bar_btns, val)

    def _on_chord_rest_bars_random(self):
        new = not self._chord_rest_rand_var.get()
        self._chord_rest_rand_var.set(new)
        with STATE._lock: STATE.chord_rest_bars_random = new
        if new:
            # RAND ON: ボタンを紫ハイライト、小節ボタンを全て未選択表示
            self._chord_rest_rand_btn.config(bg='#da77f2', fg='#0f0f1e')
            for btn in self._chord_rest_bar_btns.values():
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))
        else:
            self._chord_rest_rand_btn.config(bg='#1e1e38', fg='#4a9eff')
            self._update_bar_buttons(self._chord_rest_bar_btns, STATE.chord_rest_bars)


    def _on_arp_auto(self):
        new = not self._arp_auto_var.get()
        self._arp_auto_var.set(new)
        with STATE._lock: STATE.arp_auto = new
        if new:
            self._arp_auto_btn.config(bg='#da77f2', fg='#0f0f1e')
        else:
            self._arp_auto_btn.config(bg='#1e1e38', fg='#4a9eff')

    def _on_arp_auto_bars(self, val):
        with STATE._lock: STATE.arp_auto_bars = val
        self._update_bar_buttons(self._arp_auto_bar_btns, val)

    def _auto_arp_tick(self):
        """全アルペジエーターパラメーターをランダムに自動切り替え"""
        if not self._playing:
            return
        s = STATE.get()
        if s['arp_auto']:
            new_mode  = random.choice(['up', 'down', 'zigzag', 'random'])
            new_rate  = random.choice([v for _, v in ARP_RATES])
            new_oct   = random.choice([1, 2, 3])
            new_range = random.choice([1, 2, 3])
            with STATE._lock:
                STATE.arp_mode        = new_mode
                STATE.arp_rate        = new_rate
                STATE.arp_rate_random = False
                STATE.chord_octave    = new_oct
                STATE.chord_oct_range = new_range
            # UI 同期
            self._arp_mode_var.set(new_mode)
            self._arp_rand_var.set(False)
            self._chord_oct_var.set(new_oct)
            self._chord_oct_range_var.set(new_range)
            self._update_arp_rate_buttons(new_rate)
            self._log(f"[ARP AUTO] mode={new_mode}  rate={new_rate}  oct={new_oct}  range={new_range}")
            interval = bars_to_ms(s['arp_auto_bars'], s['bpm'])
        else:
            interval = 500
        self.root.after(interval, self._auto_arp_tick)

    # 音名ごとの色（虹順）
    NOTE_COLORS = {
        'C':  '#ff6b6b', 'C#': '#ff8c42',
        'D':  '#ffd166', 'D#': '#c9f07a',
        'E':  '#69db7c',
        'F':  '#4dabf7', 'F#': '#748ffc',
        'G':  '#da77f2', 'G#': '#f783ac',
        'A':  '#ff6b6b', 'A#': '#ff8c42',
        'B':  '#ffd166',
    }

    def _update_root_buttons(self):
        root = STATE.root
        current_name = NOTE_NAMES[root % 12]
        octave = root // 12 - 1
        for name, btn in self._note_btns.items():
            is_sharp = '#' in name
            if name == current_name:
                col = self.NOTE_COLORS.get(name, C_ACCENT)
                btn.config(bg=col, fg='#0f0f1e',
                           font=('Helvetica', 9, 'bold'))
            else:
                btn.config(bg='#1e1e38' if is_sharp else '#1e2030',
                           fg='#4a9eff',
                           font=('Helvetica', 8, 'normal'))
        if self._current_root_lbl:
            col = self.NOTE_COLORS.get(current_name, C_ON)
            self._current_root_lbl.config(
                text=f'{current_name}{octave}', fg=col)

    # ---- 再生 / 停止 ------------------------------------
    def _toggle_play(self):
        if self._playing: self._stop()
        else: self._start()

    def _start(self):
        global _midi_muted
        _midi_muted = False
        self._log_enabled = True
        self._playing = True
        self._play_btn.config(text='  ■  STOP   ', bg='#cc4455',
                               activebackground='#aa3344')
        self._status_lbl.config(text='● PLAYING', fg=C_ON)
        self._log('--- 演奏開始 ---')

        self._drone   = DroneLayer(self._log)
        self._melody  = MelodyLayer(1, 1, 'melody',  0.75, 'Melody ', self._log)
        self._sparkle = MelodyLayer(2, 3, 'sparkle', 0.55, 'Sparkle', self._log)
        self._chord   = ChordLayer(self._log)
        self._evo     = EvolutionController(self._log)

        self._drone.start()
        threading.Timer(2.0, self._melody.start).start()
        threading.Timer(4.0, self._sparkle.start).start()
        threading.Timer(5.5, self._chord.start).start()
        threading.Timer(6.0, self._evo.start).start()
        self.root.after(300, self._sync_ui)
        self.root.after(1000, self._auto_tick)

    def _stop(self):
        global _midi_muted
        _midi_muted = True          # まずノートオンを即ブロック
        midi_panic()                # 今鳴っている音を即消音
        # シグナルランプを全消灯
        for c in range(4):
            _lamp_notes[c] = 0
            if c in _lamp_fns:
                _lamp_fns[c](False)
        self._playing = False
        self._play_btn.config(text='  ▶  START  ', bg=C_ON,
                               activebackground='#00a87d')
        self._status_lbl.config(text='● STOPPED', fg=C_OFF)
        self._log('--- 演奏停止 ---')
        self._log_enabled = False        # 以降のログをブロック
        for layer in [self._drone, self._melody, self._sparkle, self._chord, self._evo]:
            if layer: layer.stop()
        self.root.after(400, midi_panic)  # 念のため再度消音

    def _auto_chord_tick(self):
        """コード度数+クオリティをランダムに自動切り替え"""
        if not self._playing:
            return
        s = STATE.get()
        if s['chord_auto']:
            new_deg_lbl, new_deg  = random.choice(CHORD_DEGREES)
            new_qual_lbl, new_qual = random.choice(CHORD_QUALITIES)
            with STATE._lock:
                STATE.chord_degree  = new_deg
                STATE.chord_quality = new_qual
            self._update_chord_degree_buttons(new_deg)
            self._update_chord_quality_buttons(new_qual_lbl)
            next_bars = random.choice([2, 4, 8, 16])
            with STATE._lock: STATE.chord_auto_bars = next_bars
            self._update_bar_buttons(self._chord_auto_bar_btns, next_bars)
            self._log(f"[Auto Chord] → {new_deg_lbl}{new_qual_lbl}  次: {next_bars}小節後")
            interval = bars_to_ms(next_bars, s['bpm'])
        else:
            interval = 500
        self.root.after(interval, self._auto_chord_tick)

    def _auto_tick(self):
        """起動時に Auto Root / Auto Scale / Auto Arp / Auto Chord の独立タイマーをキックオフ"""
        if not self._playing:
            return
        self.root.after(500, self._auto_root_tick)
        self.root.after(500, self._auto_scale_tick)
        self.root.after(500, self._auto_arp_tick)
        self.root.after(500, self._auto_chord_tick)

    def _auto_root_tick(self):
        if not self._playing:
            return
        s = STATE.get()
        if s['auto_root']:
            new_root = random.choice(list(range(36, 61)))
            with STATE._lock: STATE.root = new_root
            name = NOTE_NAMES[new_root % 12]
            # 次の小節数をランダム選択
            next_bars = random.choice(BAR_OPTIONS)
            with STATE._lock: STATE.auto_root_bars = next_bars
            self._update_bar_buttons(self._root_bar_btns, next_bars)
            self._log(f"[Auto Root] → {name}{new_root//12-1}  次: {next_bars}小節後")
            self._update_root_buttons()
            interval = bars_to_ms(next_bars, s['bpm'])
        else:
            interval = 500
        self.root.after(interval, self._auto_root_tick)

    def _auto_scale_tick(self):
        if not self._playing:
            return
        s = STATE.get()
        if s['auto_scale']:
            opts = [k for k in SCALES if k != s['scale_name']]
            new = random.choice(opts)
            with STATE._lock: STATE.scale_name = new
            self._scale_var.set(new)
            if self._current_scale_lbl:
                self._current_scale_lbl.config(text=new)
            # 次の小節数をランダム選択
            next_bars = random.choice(BAR_OPTIONS)
            with STATE._lock: STATE.auto_scale_bars = next_bars
            self._update_bar_buttons(self._scale_bar_btns, next_bars)
            self._log(f"[Auto Scale] → {new}  次: {next_bars}小節後")
            interval = bars_to_ms(next_bars, s['bpm'])
        else:
            interval = 500
        self.root.after(interval, self._auto_scale_tick)

    def _sync_ui(self):
        if not self._playing: return
        s = STATE.get()
        if self._scale_var.get() != s['scale_name']:
            self._scale_var.set(s['scale_name'])
        if self._auto_scale_var.get() != s['auto_scale']:
            self._auto_scale_var.set(s['auto_scale'])
        if self._density_var.get() != s['density']:
            self._density_var.set(s['density'])
        self._current_scale_lbl.config(text=s['scale_name'])
        self._update_root_buttons()
        # コード表示更新
        deg  = s['chord_degree']
        qual = s['chord_quality']
        deg_lbl  = next((l for l, st in CHORD_DEGREES   if st == deg),  str(deg))
        qual_lbl = next((l for l, ivs in CHORD_QUALITIES if ivs == qual), '')
        deg_col  = CHORD_DEGREE_COLOR.get(deg, C_ON)
        if self._current_chord_lbl:
            prefix = 'AUTO  ' if s['chord_auto'] else ''
            self._current_chord_lbl.config(
                text=f'{prefix}{deg_lbl}{qual_lbl}', fg=deg_col)
        self._update_chord_degree_buttons(deg)
        qual_key = next((l for l, ivs in CHORD_QUALITIES if ivs == qual), 'maj')
        self._update_chord_quality_buttons(qual_key)
        self.root.after(300, self._sync_ui)

    # ---- ログ -------------------------------------------
    def _log(self, msg):
        if not getattr(self, '_log_enabled', True):
            return
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
        if self._clock_receiver:
            self._clock_receiver.stop()
            self._clock_receiver = None
        if self._clock_sender:
            self._clock_sender.stop()
            self._clock_sender = None
        self.root.after(300, self.root.destroy)

    def run(self):
        self.root.mainloop()

# ================================================================
if __name__ == '__main__':
    AmbientApp().run()
