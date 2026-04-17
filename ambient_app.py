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
import sys

# ================================================================
# スケール定義
# ================================================================
# ================================================================
# メロディ リズムフィギュア（beats単位、speed倍率前）
# ================================================================
MELODY_RHYTHM_PATTERNS = {
    # Free: 従来のランダム per-note（None = 既存ロジック）
    'free': None,
    # Flowing: なめらかな流れ、スラーっぽい
    'flowing': [
        [2.0, 1.0, 1.0, 2.0],
        [1.0, 1.0, 2.0, 2.0],
        [2.0, 2.0, 1.0, 1.0],
        [1.0, 2.0, 1.0, 2.0],
        [2.0, 1.0, 2.0, 1.0],
        [4.0, 2.0, 2.0],
    ],
    # Dotted: 付点リズム、跳ねる感覚
    'dotted': [
        [1.5, 0.5, 1.5, 0.5, 2.0],
        [3.0, 1.0, 2.0],
        [0.5, 1.5, 0.5, 1.5, 2.0],
        [1.5, 0.5, 2.0, 2.0],
        [0.5, 1.5, 2.0, 1.0, 1.0],
        [3.0, 0.5, 0.5, 2.0],
    ],
    # Synco: シンコペーション、オフビートの緊張
    'synco': [
        [0.5, 1.5, 1.0, 1.0, 2.0],
        [1.0, 0.5, 0.5, 2.0, 2.0],
        [1.5, 0.5, 1.5, 0.5, 2.0],
        [0.5, 0.5, 1.0, 1.0, 3.0],
        [1.0, 1.5, 0.5, 1.0, 2.0],
        [0.5, 1.0, 1.5, 1.0, 2.0],
    ],
    # Staccato: 細かい音符の連続、パッセージ感
    'staccato': [
        [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.5],
        [1.0, 0.5, 0.5, 1.0, 1.0, 2.0],
        [0.5, 0.5, 0.5, 0.5, 1.0, 1.0, 2.0],
        [0.5, 0.5, 1.0, 0.5, 0.5, 3.0],
        [0.5, 0.5, 0.5, 1.5, 1.0, 2.0],
    ],
    # Breath: 長い音とスペース、ゆったり
    'breath': [
        [4.0, 4.0],
        [6.0, 2.0],
        [3.0, 1.0, 4.0],
        [4.0, 2.0, 2.0],
        [8.0],
        [2.0, 6.0],
    ],
}

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
        self.auto_evolve = False
        self.layers     = {'drone': True, 'melody': True, 'sparkle': True, 'chord': True}
        self.vel        = {'drone': 45, 'melody': 38, 'sparkle': 28, 'chord': 55}
        self.drone_octave = 3  # ドローン絶対オクターブ (1〜5)、ルートと独立
        # 変化量 0.0〜1.0 : 低=ステップワイズ、高=大跳躍多め
        self.variation        = {'drone': 0.2,   'melody': 0.3,   'sparkle': 0.6,   'chord': 0.3}
        self.variation_random = {'drone': False,  'melody': False,  'sparkle': False,  'chord': False}
        # 休符率 0.0〜1.0
        self.rest_prob    = {'drone': 0.0,   'melody': 0.35,  'sparkle': 0.60,  'chord': 0.20}
        # アルペジエーター
        self.arp_on          = True
        self.arp_mode        = 'up'    # 'up' / 'down' / 'zigzag' / 'random'
        self.arp_rate          = 0.25   # beats/step (BPM同期ノート値)
        self.arp_rate_random   = False  # Trueのとき毎サイクルランダム選択
        self.arp_rate_rand_min = 0.125  # ランダム範囲 下限
        self.arp_rate_rand_max = 4.0    # ランダム範囲 上限
        self.chord_octave    = 1      # ベースオクターブオフセット (+1〜+3)
        self.chord_oct_range  = 1      # 何オクターブ分アルペジオを広げるか (1〜3)
        self.chord_degree  = 0           # Ⅰ (semitone offset)
        self.chord_quality = [0, 4, 7]  # maj
        self.chord_auto    = False
        self.chord_auto_bars = 8
        # AUTO CHORD 用ランダムプール（デフォルト全選択）
        self.chord_auto_degrees_pool  = [s for _, s in CHORD_DEGREES]
        self.chord_auto_qualities_pool = [k for k, _ in CHORD_QUALITIES]
        self.chord_rest_bars        = 4      # 休符の長さ（小節数）
        self.chord_rest_bars_random = False  # Trueのとき休符ごとにランダム選択
        self.arp_swing          = 0.5    # 0.5=ストレート, 0.75=ヘビースイング
        self.melody_speed         = 1.0    # メロディーノート長倍率
        self.melody_speed_random  = False  # Trueのとき自動ランダム切り替え
        self.melody_speed_rand_min = 0.25  # ランダム範囲 下限
        self.melody_speed_rand_max = 4.0   # ランダム範囲 上限
        self.sparkle_octave       = 3      # スパークル基準オクターブ (1〜5)
        self.sparkle_range        = 1      # スパークル音域レンジ（1〜3）
        self.melody_octave        = 1      # 基準オクターブ (1〜5)
        self.melody_range         = 1      # 音域レンジ（オクターブ数 1〜3）
        self.melody_character     = []     # 'contour','phrase','motif' の組み合わせ
        self.melody_rhythm        = 'free' # リズムスタイル
        # 全パラメーター自動ランダム切り替え
        self.arp_auto      = False
        self.arp_auto_bars = 4        # 何小節ごとに切り替えるか
        # 展開の深さ 0.0〜1.0 (転調幅・変化の大きさ)
        self.evolve_depth = 0.5
        # 展開の速さ 0.0〜1.0 (変化の頻度)
        self.evolve_speed = 0.5
        # ルートのランダム自動変化
        self.auto_root          = False
        self.auto_root_bars     = 16    # 現在の変化小節数
        self.auto_root_bars_min = 1     # 小節数ランダム範囲 下限
        self.auto_root_bars_max = 64    # 小節数ランダム範囲 上限
        self.auto_root_pool     = list(range(12))  # ランダム範囲：ピッチクラス 0〜11
        self.drone_follow       = 'root'           # ドローン追従先: 'root' or 'chord'
        # スケールのランダム自動変化
        self.auto_scale      = False
        self.auto_scale_bars = 16
        # コード自動変化 小節数ランダム範囲
        self.chord_auto_bars_min = 2
        self.chord_auto_bars_max = 16

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
                variation        = dict(self.variation),
                variation_random = dict(self.variation_random),
                rest_prob     = dict(self.rest_prob),
                auto_evolve      = self.auto_evolve,
                drone_octave     = self.drone_octave,
                evolve_depth     = self.evolve_depth,
                evolve_speed     = self.evolve_speed,
                auto_root           = self.auto_root,
                auto_root_bars      = self.auto_root_bars,
                auto_root_bars_min  = self.auto_root_bars_min,
                auto_root_bars_max  = self.auto_root_bars_max,
                auto_root_pool      = list(self.auto_root_pool),
                drone_follow        = self.drone_follow,
                chord_auto_bars_min = self.chord_auto_bars_min,
                chord_auto_bars_max = self.chord_auto_bars_max,
                auto_scale      = self.auto_scale,
                auto_scale_bars = self.auto_scale_bars,
                arp_on          = self.arp_on,
                arp_mode        = self.arp_mode,
                arp_rate          = self.arp_rate,
                arp_rate_random   = self.arp_rate_random,
                arp_rate_rand_min = self.arp_rate_rand_min,
                arp_rate_rand_max = self.arp_rate_rand_max,
                chord_octave    = self.chord_octave,
                chord_oct_range = self.chord_oct_range,
                chord_degree  = self.chord_degree,
                chord_quality = list(self.chord_quality),
                chord_auto    = self.chord_auto,
                chord_auto_bars = self.chord_auto_bars,
                chord_auto_degrees_pool   = list(self.chord_auto_degrees_pool),
                chord_auto_qualities_pool = list(self.chord_auto_qualities_pool),
                arp_auto        = self.arp_auto,
                arp_auto_bars   = self.arp_auto_bars,
                chord_rest_bars        = self.chord_rest_bars,
                chord_rest_bars_random = self.chord_rest_bars_random,
                arp_swing             = self.arp_swing,
                melody_speed           = self.melody_speed,
                melody_speed_random    = self.melody_speed_random,
                melody_speed_rand_min  = self.melody_speed_rand_min,
                melody_speed_rand_max  = self.melody_speed_rand_max,
                sparkle_octave         = self.sparkle_octave,
                sparkle_range          = self.sparkle_range,
                melody_octave          = self.melody_octave,
                melody_range           = self.melody_range,
                melody_character       = list(self.melody_character),
                melody_rhythm         = self.melody_rhythm,
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

def apply_chord_boost(matrix, notes, chord_tone_pcs, boost=2.5):
    """コードトーン列を boost 倍してから行ごとに正規化"""
    m = []
    for row in matrix:
        new_row = [w * (boost if notes[j] % 12 in chord_tone_pcs else 1.0)
                   for j, w in enumerate(row)]
        s = sum(new_row)
        m.append([w / s for w in new_row])
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
        self._midi_in   = None
        self._running   = False
        self._last_t    = None
        self._intervals = []
        self._N         = 24   # 1拍分（ジッター平均化に十分なサンプル数）
        self._ema_bpm   = None  # 指数移動平均BPM（内部用float）
        self._last_fired = None # 最後に通知したBPM整数値（ヒステリシス用）

    def start(self, log_fn=None):
        self._log = log_fn or print
        try:
            self._midi_in = rtmidi.MidiIn()
            ports = self._midi_in.get_ports()
            self._log(f"[SLAVE] MidiIn ports: {ports}")
            iac = next((i for i, p in enumerate(ports) if 'IAC' in p), None)
            if iac is None:
                self._log("[SLAVE] IAC port not found!")
                return False
            self._midi_in.open_port(iac)
            self._log(f"[SLAVE] Opened: {ports[iac]}")
            self._midi_in.ignore_types(sysex=True, timing=False, active_sense=True)
            self._running = True
            self._midi_in.set_callback(self._callback)
            return True
        except Exception as e:
            self._log(f"[SLAVE] start error: {e}")
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
            self._pulse_count = getattr(self, '_pulse_count', 0) + 1
            if self._pulse_count == 1:
                self._log("[SLAVE] クロック受信開始 ✓")
            elif self._pulse_count == self._N + 1:
                self._log(f"[SLAVE] クロック安定 ({self._N}+ pulses)")
            now = time.time()
            if self._last_t is not None:
                interval = now - self._last_t
                # BPM 20〜300 の範囲外は無視（異常なスパイクを除外）
                if 0.005 < interval < 0.15:
                    self._intervals.append(interval)
                    if len(self._intervals) > self._N:
                        self._intervals.pop(0)
                    if len(self._intervals) >= self._N:
                        # 単純平均で生BPMを算出
                        avg     = sum(self._intervals) / len(self._intervals)
                        raw_bpm = 60.0 / (avg * 24)
                        raw_bpm = max(20.0, min(300.0, raw_bpm))

                        # EMA（指数移動平均）でなだらかに追従 α=0.15
                        if self._ema_bpm is None:
                            self._ema_bpm = raw_bpm
                        else:
                            self._ema_bpm = 0.15 * raw_bpm + 0.85 * self._ema_bpm

                        # ヒステリシス: 前回と1BPM以上変化した時だけ通知
                        new_int = int(round(self._ema_bpm))
                        if self._last_fired is None or abs(new_int - self._last_fired) >= 1:
                            self._last_fired = new_int
                            self._on_bpm_change(new_int)
            self._last_t = now
        elif msg[0] == 0xFC:  # MIDI Stop — クロックリセット
            self._log("[SLAVE] MIDI Stop 受信 → クロックリセット")
            self._intervals.clear()
            self._last_t    = None
            self._ema_bpm   = None
            self._last_fired = None
            self._pulse_count = 0
        else:
            # 最初の5件だけ未知メッセージを記録
            count = getattr(self, '_unknown_count', 0)
            if count < 5:
                self._log(f"[SLAVE] other msg: {[hex(b) for b in msg]}")
            self._unknown_count = count + 1

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
        self.log          = log_fn
        self.ch           = 0
        self._running     = False
        self._active      = []          # 現在鳴らしているノート
        self._pending_off = []          # [(notes, off_at)] 旧ノートの遅延off

    def _compute_root(self, s):
        if s['drone_follow'] == 'chord':
            root_pc = (s['root'] % 12 + s['chord_degree']) % 12
        else:
            root_pc = s['root'] % 12
        root = root_pc + s['drone_octave'] * 12
        return max(0, min(115, root))

    def _flush_pending(self, force=False):
        """期限切れ（またはforce時は全）の旧ノートをnote-offする"""
        now = time.perf_counter()
        remaining = []
        for notes, off_at in self._pending_off:
            if force or now >= off_at:
                for n in notes:
                    midi_off(self.ch, n)
            else:
                remaining.append((notes, off_at))
        self._pending_off = remaining

    def _stop_all(self):
        self._flush_pending(force=True)
        for n in self._active:
            midi_off(self.ch, n)
        self._active = []

    def _loop(self):
        last_root = None
        while self._running:
            s = STATE.get()
            if not s['layers']['drone']:
                self._stop_all()
                last_root = None
                time.sleep(0.2)
                continue

            beat = 60.0 / s['bpm']
            root = self._compute_root(s)
            var  = s['variation']['drone']

            # ルートが変化 or 初回: 旧ノートは4拍後にoff、新ノートを即開始
            if root != last_root:
                if self._active:
                    off_at = time.perf_counter() + 10 * beat
                    self._pending_off.append((list(self._active), off_at))
                    self._active = []
                last_root = root

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

            # 0.1秒刻みでポーリング：期限切れpendingをoff、ルート変化を検知
            while self._running:
                time.sleep(0.1)
                self._flush_pending()
                s2    = STATE.get()
                new_r = self._compute_root(s2)
                if new_r != last_root:
                    break
                # レイヤーOFF
                if not s2['layers']['drone']:
                    break

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        self._stop_all()


class MelodyLayer:
    DENSITY_DUR = {
        'sparse': {4.0: 2, 6.0: 3, 8.0: 2},
        'normal': {2.0: 2, 4.0: 4, 6.0: 2},
        'dense':  {1.0: 2, 2.0: 4, 4.0: 2},
    }

    def __init__(self, ch, octave, layer_key, gate, label, log_fn):
        self.ch          = ch
        self.octave      = octave      # sparkle など固定オクターブ用
        self.layer_key   = layer_key
        self.gate        = gate
        self.label       = label
        self.log         = log_fn
        self._running    = False
        self._deg              = 0
        self._cur_scale        = None
        self._cur_var          = None
        self._cur_root         = None
        self._cur_oct          = None
        self._cur_range        = None
        self._cur_chord_degree = None
        self._cur_chord_qual   = None
        self._chord_tone_idxs  = []   # self._notes 内のコードトーン index
        self._matrix           = None
        self._notes            = []
        # キャラクター A: コンター重力
        self._contour_bias     = 0.0   # -1.0(下降中) 〜 +1.0(上昇中)
        # キャラクター B: フレーズビルダー
        self._phrase_target    = None  # ターゲット index
        self._phrase_len       = 6
        self._phrase_pos       = 0
        # キャラクター C: モチーフ
        self._motif            = []    # 相対ステップのリスト
        self._motif_pos        = 0
        self._motif_count      = 0
        self._motif_max        = 3
        # リズムフィギュア
        self._rhythm_pattern   = []
        self._rhythm_pos       = 0

    def _rebuild(self, root, scale_name, variation, base_oct, n_range,
                 chord_degree, chord_quality):
        ivs = SCALES[scale_name]
        notes = []
        for oct_offset in range(n_range):
            for iv in ivs:
                n = root + (base_oct + oct_offset) * 12 + iv
                if 0 <= n <= 127:
                    notes.append(n)
        self._notes = sorted(set(notes))
        # 行列は self._notes の実サイズで作る（n_range > 1 でも正しく動作）
        base_mat = build_matrix(len(self._notes), variation)
        # コードトーン（ピッチクラス）を計算してブースト
        chord_root_pc  = (root % 12 + chord_degree) % 12
        chord_tone_pcs = {(chord_root_pc + iv) % 12 for iv in chord_quality}
        self._matrix = apply_chord_boost(base_mat, self._notes, chord_tone_pcs)
        # フレーズ終端スナップ用: コードトーンの index リスト
        self._chord_tone_idxs  = [i for i, n in enumerate(self._notes)
                                   if n % 12 in chord_tone_pcs]
        self._deg              = min(self._deg, max(0, len(self._notes) - 1))
        self._cur_scale        = scale_name
        self._cur_var          = variation
        self._cur_root         = root
        self._cur_oct          = base_oct
        self._cur_range        = n_range
        self._cur_chord_degree = chord_degree
        self._cur_chord_qual   = list(chord_quality)
        # コード/スケール変化でモチーフ・フレーズをリセット
        self._motif         = []
        self._motif_pos     = 0
        self._phrase_target = None
        self._phrase_pos    = 0

    def _get_rhythm_dur(self, style, density):
        """リズムスタイルから次のデュレーション（beats）を返す"""
        patterns = MELODY_RHYTHM_PATTERNS.get(style)
        if not patterns:
            return wchoice(self.DENSITY_DUR[density])
        if not self._rhythm_pattern or self._rhythm_pos >= len(self._rhythm_pattern):
            self._rhythm_pattern = random.choice(patterns)
            self._rhythm_pos = 0
        dur = self._rhythm_pattern[self._rhythm_pos]
        self._rhythm_pos += 1
        return dur

    def _choose_next_deg(self, characters, dur_b):
        """キャラクターに基づいて次の音度インデックスを返す"""
        n = len(self._notes)
        if n == 0: return 0

        # self._deg の安全クランプ
        self._deg = max(0, min(self._deg, n - 1))

        # ---- キャラクター未選択: 既存ロジック ----
        if not characters:
            if dur_b >= 4.0 and self._chord_tone_idxs:
                cur = self._notes[self._deg]
                return min(self._chord_tone_idxs, key=lambda i: abs(self._notes[i] - cur))
            deg = next_deg(self._deg, self._matrix)
            return max(0, min(deg, n - 1))

        # ---- ベース確率行 ----
        row = list(self._matrix[self._deg]) if self._deg < len(self._matrix) \
              else [1.0 / n] * n

        # ---- Character B: Phrase Builder ----
        if 'phrase' in characters:
            if self._phrase_target is None and self._chord_tone_idxs:
                self._phrase_target = random.choice(self._chord_tone_idxs)
                self._phrase_len    = random.randint(4, 8)
                self._phrase_pos    = 0
            # フレーズ終端: ターゲットへスナップ
            if self._phrase_pos >= self._phrase_len - 1:
                result = self._phrase_target if self._phrase_target is not None else self._deg
                self._phrase_pos    = 0
                self._phrase_target = random.choice(self._chord_tone_idxs) \
                                      if self._chord_tone_idxs else random.randint(0, n - 1)
                self._phrase_len    = random.randint(4, 8)
                if 'contour' in characters:
                    if result > self._deg: self._contour_bias = min(1.0, self._contour_bias + 0.12)
                    elif result < self._deg: self._contour_bias = max(-1.0, self._contour_bias - 0.12)
                return result
            # フレーズ中: ターゲット方向を強化
            target    = self._phrase_target or self._deg
            direction = 1 if target > self._deg else (-1 if target < self._deg else 0)
            for j in range(n):
                if direction > 0 and j > self._deg: row[j] *= 1.7
                elif direction < 0 and j < self._deg: row[j] *= 1.7
            self._phrase_pos += 1

        # ---- Character A: Contour Gravity ----
        if 'contour' in characters and abs(self._contour_bias) > 0.15:
            strength = abs(self._contour_bias) * 2.5
            for j in range(n):
                if self._contour_bias > 0 and j < self._deg:
                    row[j] *= (1.0 + strength)
                elif self._contour_bias < 0 and j > self._deg:
                    row[j] *= (1.0 + strength)

        # ---- Character C: Motif ----
        if 'motif' in characters:
            if not self._motif:
                cur = self._deg
                self._motif = []
                for _ in range(random.randint(3, 5)):
                    nd = max(0, min(next_deg(cur, self._matrix), n - 1))
                    self._motif.append(nd - cur)
                    cur = nd
                self._motif_pos   = 0
                self._motif_count = 0
                self._motif_max   = random.randint(2, 4)
            if self._motif_pos < len(self._motif):
                step = self._motif[self._motif_pos]
                if self._motif_count > 0:
                    step += random.choices([0, 0, 0, 1, -1], weights=[7, 7, 7, 1, 1])[0]
                target_deg = max(0, min(n - 1, self._deg + step))
                row[target_deg] *= 4.0
                self._motif_pos += 1
                if self._motif_pos >= len(self._motif):
                    self._motif_pos = 0
                    self._motif_count += 1
                    if self._motif_count >= self._motif_max:
                        self._motif = []

        # ---- Character D: ChordOnly ----
        if 'chord' in characters and self._chord_tone_idxs:
            chord_set = set(self._chord_tone_idxs)
            row = [w if j in chord_set else 0.0 for j, w in enumerate(row)]

        # ---- 正規化してサンプリング ----
        s = sum(row)
        row = [w / s for w in row] if s > 0 else [1.0 / n] * n
        r, c = random.random(), 0.0
        result = n - 1
        for i, w in enumerate(row):
            c += w
            if r < c:
                result = i
                break

        # コンターバイアス更新
        if 'contour' in characters:
            if result > self._deg:   self._contour_bias = min(1.0,  self._contour_bias + 0.12)
            elif result < self._deg: self._contour_bias = max(-1.0, self._contour_bias - 0.12)
            else:                    self._contour_bias *= 0.85

        return result

    def _loop(self):
        while self._running:
            s   = STATE.get()
            key = self.layer_key

            if not s['layers'][key]:
                midi_all_off(self.ch)
                time.sleep(0.5)
                continue

            var       = s['variation'][key]
            rest_prob = s['rest_prob'][key]

            # melody / sparkle は STATE からオクターブ・レンジを取得、他は固定
            if self.layer_key == 'melody':
                base_oct = s['melody_octave']
                n_range  = s['melody_range']
            elif self.layer_key == 'sparkle':
                base_oct = s['sparkle_octave']
                n_range  = s['sparkle_range']
            else:
                base_oct = self.octave
                n_range  = 1

            chord_degree = s['chord_degree']
            chord_qual   = s['chord_quality']
            if s['scale_name'] != self._cur_scale \
                    or abs(var - (self._cur_var or -1)) > 0.05 \
                    or s['root'] != self._cur_root \
                    or base_oct != self._cur_oct \
                    or n_range != self._cur_range \
                    or chord_degree != self._cur_chord_degree \
                    or chord_qual   != self._cur_chord_qual \
                    or not self._notes:
                self._rebuild(s['root'], s['scale_name'], var, base_oct, n_range,
                              chord_degree, chord_qual)

            characters    = s.get('melody_character', [])
            melody_rhythm = s.get('melody_rhythm', 'free')
            if self.layer_key == 'melody' and melody_rhythm != 'free':
                dur_b = self._get_rhythm_dur(melody_rhythm, s['density'])
            else:
                dur_b = wchoice(self.DENSITY_DUR[s['density']])
            self._deg  = self._choose_next_deg(characters, dur_b)
            if self._deg >= len(self._notes):
                self._deg = 0

            note  = self._notes[self._deg]
            beat  = 60.0 / STATE.bpm   # ノートごとに BPM 直読み → SLAVE追従
            # melody レイヤーのみ speed 倍率を適用
            speed = s['melody_speed'] if self.layer_key == 'melody' else 1.0
            dur_s = dur_b * beat * speed
            vel   = int((s['vel'][key] + random.randint(-15, 15)) * s['dynamic'])

            # ---- Simple character: 小節頭に1音、残りは休符 ----
            if 'simple' in characters and self.layer_key == 'melody':
                one_beat = beat * speed
                if random.random() < rest_prob:
                    self._interruptible_sleep(4.0 * one_beat)
                else:
                    name = NOTE_NAMES[note % 12]
                    self.log(f"{self.label}  {name}{note//12-1}  vel={vel}  [simple]")
                    midi_on(self.ch, note, vel)
                    self._interruptible_sleep(3.0 * one_beat)
                    midi_off(self.ch, note)
                    self._interruptible_sleep(one_beat)
                continue

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
        def _next(base, lo=0.6, hi=1.8):
            return time.time() + random.uniform(base * lo, base * hi)

        # 各変化のタイマーを分散して初期化
        t_dynamic  = time.time()
        t_mod      = _next(60)
        t_scale    = _next(80)
        t_dens     = _next(40)
        t_chord    = _next(50)
        t_arp      = _next(70)
        t_rhythm   = _next(90)
        t_bpm      = _next(120)
        t_layer    = _next(100)

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

        while self._running:
            s   = STATE.get()
            now = time.time()

            if s['auto_evolve']:
                depth = s['evolve_depth']   # 0.0〜1.0
                spd   = s['evolve_speed']   # 0.0〜1.0

                # インターバル基準: speed=0→90s、speed=1→5s
                base = max(5, 90 - spd * 85)

                # ① ダイナミクス波（毎ループ更新）
                if now >= t_dynamic:
                    sin_speed = 0.005 + spd * 0.03
                    self._phase += sin_speed
                    swing = 0.2 + depth * 0.65
                    STATE.dynamic = max(0.1, min(1.0, 0.55 + swing * math.sin(self._phase)))
                    t_dynamic = now + 0.1

                # ② 転調: depth低=近音程、depth高=全セミトーン
                if now >= t_mod:
                    if depth < 0.35:
                        iv_pool = [-2, 2, -5, 5]
                    elif depth < 0.65:
                        iv_pool = [-7, -5, -2, 2, 5, 7]
                    else:
                        iv_pool = list(range(-11, 12))
                    iv  = random.choice(iv_pool)
                    new = max(36, min(72, s['root'] + iv))
                    with STATE._lock: STATE.root = new
                    self.log(f"[EVOLVE] 転調 → {NOTE_NAMES[new % 12]}")
                    t_mod = _next(base * 1.2)

                # ③ スケール: depth低=関連のみ、depth高=全スケール
                if now >= t_scale:
                    cur  = s['scale_name']
                    opts = RELATED.get(cur, list(SCALES.keys())) if depth < 0.5 \
                           else [k for k in SCALES if k != cur]
                    new  = random.choice(opts)
                    with STATE._lock: STATE.scale_name = new
                    self.log(f"[EVOLVE] スケール → {new}")
                    t_scale = _next(base * 1.5)

                # ④ 密度
                if now >= t_dens:
                    if depth < 0.4:
                        opts = ['normal']  # 穏やか
                    else:
                        opts = [d for d in ['sparse', 'normal', 'dense'] if d != s['density']]
                    with STATE._lock: STATE.density = random.choice(opts)
                    self.log(f"[EVOLVE] 密度 → {STATE.density}")
                    t_dens = _next(base * 0.7)

                # ⑤ コード度数（depth > 0.3）
                if depth > 0.3 and now >= t_chord:
                    deg = random.choice(CHORD_DEGREES)
                    with STATE._lock: STATE.chord_degree = deg[1]
                    self.log(f"[EVOLVE] コード度数 → {deg[0]}")
                    t_chord = _next(base)

                # ⑥ アルペジオ モード + レート（depth > 0.4）
                if depth > 0.4 and now >= t_arp:
                    new_mode = random.choice(['up', 'down', 'zigzag', 'random'])
                    if depth < 0.6:
                        rate_pool = [0.25, 0.5, 1.0]
                    else:
                        rate_pool = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
                    new_rate = random.choice(rate_pool)
                    with STATE._lock:
                        STATE.arp_mode = new_mode
                        STATE.arp_rate = new_rate
                    self.log(f"[EVOLVE] アルペジオ {new_mode} rate={new_rate}")
                    t_arp = _next(base * 1.2)

                # ⑦ メロディ リズムスタイル（depth > 0.45）
                if depth > 0.45 and now >= t_rhythm:
                    styles = list(MELODY_RHYTHM_PATTERNS.keys())
                    new_r  = random.choice([r for r in styles if r != s['melody_rhythm']])
                    with STATE._lock: STATE.melody_rhythm = new_r
                    self.log(f"[EVOLVE] メロディリズム → {new_r}")
                    t_rhythm = _next(base * 1.4)

                # ⑧ BPM シフト（depth > 0.55）
                if depth > 0.55 and now >= t_bpm:
                    max_shift = int(depth * 50)
                    shift = random.randint(-max_shift, max_shift)
                    new_bpm = max(20, min(280, s['bpm'] + shift))
                    with STATE._lock: STATE.bpm = new_bpm
                    self.log(f"[EVOLVE] BPM → {new_bpm}")
                    t_bpm = _next(base * 2.5)

                # ⑨ レイヤー ON/OFF（depth > 0.65）
                if depth > 0.65 and now >= t_layer:
                    all_keys = ['drone', 'melody', 'sparkle', 'chord']
                    k = random.choice(all_keys)
                    with STATE._lock:
                        cur_on = STATE.layers[k]
                        # 最低2レイヤーは常時ON
                        if cur_on and sum(STATE.layers.values()) > 2:
                            STATE.layers[k] = False
                            self.log(f"[EVOLVE] レイヤー {k.upper()} OFF")
                        elif not cur_on:
                            STATE.layers[k] = True
                            self.log(f"[EVOLVE] レイヤー {k.upper()} ON")
                    t_layer = _next(base * 2.0)

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
        # 連続タイムライン: サイクル終了時刻を次のサイクル開始時刻として引き継ぐ
        # → STATE読み込みや音符構築の処理時間に引きずられない
        next_cycle_t = time.perf_counter()

        while self._running:
            s = STATE.get()
            if not s['layers'].get('chord', True):
                midi_all_off(self.ch)
                next_cycle_t = time.perf_counter()
                time.sleep(0.2)
                continue

            beat      = 60.0 / STATE.bpm
            root      = s['root']
            arp_on    = s['arp_on']
            arp_mode  = s['arp_mode']
            if s['arp_rate_random']:
                _all_rates = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
                lo, hi = s['arp_rate_rand_min'], s['arp_rate_rand_max']
                pool = [v for v in _all_rates if lo - 0.001 <= v <= hi + 0.001]
                arp_rate = random.choice(pool if pool else _all_rates)
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
                next_cycle_t = time.perf_counter()
                time.sleep(0.2)
                continue

            # rest_bars == 0 はレストなし
            rest_bars = s['chord_rest_bars']
            if rest_bars > 0 and random.random() < rest_prob:
                if s['chord_rest_bars_random']:
                    rest_bars = random.choice([1, 2, 4, 8, 16])
                rest_dur = beat * 4 * rest_bars
                next_cycle_t += rest_dur
                self._sleep_until(next_cycle_t)
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

                # サイクルのステップ長・スイングを確定（BPM変化は次サイクルから反映）
                step      = arp_rate * beat
                swing     = s['arp_swing']   # 0.5=straight, 0.75=heavy swing
                cycle_dur = len(seq) * step

                # 遅れすぎた場合はタイムラインをリセット（最大 1ステップ分まで許容）
                now = time.perf_counter()
                if next_cycle_t < now - step:
                    next_cycle_t = now

                names = [NOTE_NAMES[n % 12] for n in notes]
                self.log(f"Chord   {names}  [{arp_mode}]  {arp_rate:.2f}beat  swing={int((swing-0.5)*200)}%")

                # サイクル開始まで待機してから t0 を確定
                self._sleep_until(next_cycle_t)
                t0 = time.perf_counter()

                gate = step * 0.82
                for i, note in enumerate(seq):
                    if not self._running:
                        break
                    # スイング: 偶数ノートはそのまま、奇数ノートは遅らせる
                    # pair * 2*step + pos * 2*step*swing で三連符感を出す
                    pair  = i // 2
                    pos   = i % 2
                    on_t  = t0 + pair * 2 * step + pos * 2 * step * swing
                    off_t = on_t + gate

                    self._sleep_until(on_t)
                    if not self._running:
                        break
                    midi_on(self.ch, note, vel)

                    self._sleep_until(off_t)
                    if not self._running:
                        break
                    midi_off(self.ch, note)

                # タイムラインを前進（サイクル長ぴったり）
                next_cycle_t += cycle_dur

            else:
                names = [NOTE_NAMES[n % 12] for n in notes]
                dur   = wchoice({4.0: 2, 8.0: 3, 16.0: 1})
                self.log(f"Chord   {names}  [block]  {dur}拍")
                self._sleep_until(next_cycle_t)
                t0 = time.perf_counter()
                for note in notes:
                    midi_on(self.ch, note, vel)
                self._sleep_until(t0 + beat * dur * 0.88)
                for note in notes:
                    midi_off(self.ch, note)
                next_cycle_t += beat * dur

    def _sleep_until(self, target_t):
        """高精度絶対時刻待機
        遠い(>5ms)  : 1ms スリープ  → GIL を解放しつつ CPU 使用を抑える
        近い(>1ms)  : 0.2ms スリープ → オーバーシュートを最小化
        最後 1ms    : スピン         → サブミリ秒精度
        """
        while self._running:
            remaining = target_t - time.perf_counter()
            if remaining <= 0:
                break
            elif remaining > 0.005:
                time.sleep(0.001)
            elif remaining > 0.001:
                time.sleep(0.0002)
            # else: spin（最後の1ms、CPU使用するが高精度）

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
# KaossPad ウィジェット（XY パッド）
# ================================================================
class KaossPad(tk.Canvas):
    """
    X 軸 = Speed (0.0〜1.0)、Y 軸 = Depth (0.0〜1.0, 上が高い)
    ドラッグで値を変更し、command(x, y) を呼ぶ。
    auto_mod_start() / auto_mod_stop() でドット自動移動。
    """
    W = 200
    H = 160

    def __init__(self, parent, bg=C_PANEL, command=None, **kw):
        super().__init__(parent, width=self.W, height=self.H,
                         bg='#0c0c1e', highlightthickness=1,
                         highlightbackground='#2a2a4a', cursor='crosshair', **kw)
        self._x    = 0.5   # 現在位置 Speed
        self._y    = 0.5   # 現在位置 Depth
        self._cmd  = command

        # Auto Mod 用
        self._am_active = False
        self._am_tx     = random.random()
        self._am_ty     = random.random()
        self._am_speed  = 0.3
        self._am_mode   = 'random'
        self._am_phase  = 0.0
        self._am_after  = None

        # 衛星の向き・軌跡
        self._sat_angle  = 0.0          # 進行方向角度（ラジアン）
        self._sat_prev_x = self._x      # 前フレームの位置（angle 計算用）
        self._sat_prev_y = self._y
        self._sat_trail  = []           # [(cx, cy), ...] 最近の軌跡

        # 衛星タイプ
        self._sat_type      = 'sputnik1'
        self._claude_frame  = 0         # 8bitアニメフレーム 0-3
        self._claude_tick   = 0         # フレーム進行カウンタ

        # 円運動用ランダムパラメータ
        self._am_circle_r      = 0.25
        self._am_circle_dir    = 1.0
        self._am_circle_cx     = 0.5
        self._am_circle_cy     = 0.5
        self._am_circle_phase_r = 0.0  # 半径の緩やかな変動位相

        # 八の字運動用ランダムパラメータ
        self._am_f8_sx  = 0.40
        self._am_f8_sy  = 0.35
        self._am_f8_dir = 1.0
        self._am_f8_cx  = 0.5
        self._am_f8_cy  = 0.5

        self._draw()
        self.bind('<Button-1>',   self._on_click)
        self.bind('<B1-Motion>',  self._on_drag)

    # ── 描画 ──────────────────────────────────────────
    def _draw(self):
        self.delete('all')
        W, H = self.W, self.H
        cx = int(self._x * W)
        cy = int((1.0 - self._y) * H)

        # グリッド
        for i in range(1, 4):
            x = int(W * i / 4)
            self.create_line(x, 0, x, H, fill='#1e1e38', width=1)
        for i in range(1, 4):
            y = int(H * i / 4)
            self.create_line(0, y, W, y, fill='#1e1e38', width=1)

        # カーソル位置から広がるグロー
        r_outer = int(30 + self._y * 30)
        for r, alpha in [(r_outer, '#111128'), (r_outer//2, '#1a2a4a'), (12, '#1e3a6a')]:
            self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=alpha, outline='')

        # Auto Mod 目標点（薄く表示）
        if self._am_active and self._am_mode == 'random':
            tx = int(self._am_tx * W)
            ty = int((1.0 - self._am_ty) * H)
            self.create_oval(tx-4, ty-4, tx+4, ty+4,
                             outline='#3a5a8a', fill='', width=1, dash=(2, 3))
            self.create_line(cx, cy, tx, ty, fill='#1e2e4a', width=1, dash=(2, 4))

        # 十字線
        self.create_line(cx, 0, cx, H, fill='#2a3a6a', width=1, dash=(3, 4))
        self.create_line(0, cy, W, cy, fill='#2a3a6a', width=1, dash=(3, 4))

        # 軌跡
        trail = self._sat_trail
        for i, (tx, ty) in enumerate(trail):
            t = (i + 1) / max(len(trail), 1)
            r = max(1, int(t * 3))
            c = int(20 + t * 60)
            col = f'#{c:02x}{c:02x}{min(255, c+50):02x}'
            self.create_oval(tx-r, ty-r, tx+r, ty+r, fill=col, outline='')

        # 人工衛星
        self._draw_satellite(cx, cy, self._sat_angle)

        # 軸ラベル（四隅）
        dim = '#3a3a6a'
        self.create_text(4,     H-4,  text='CALM',    anchor='sw', fill=dim, font=('Helvetica', 7))
        self.create_text(W-4,   H-4,  text='FAST',    anchor='se', fill=dim, font=('Helvetica', 7))
        self.create_text(4,     4,    text='CHAOS',   anchor='nw', fill=C_EVO, font=('Helvetica', 7, 'bold'))
        self.create_text(W-4,   4,    text='SPEED →', anchor='ne', fill=dim, font=('Helvetica', 7))
        self.create_text(4,     H//2, text='↑ DEPTH', anchor='w',  fill=dim, font=('Helvetica', 7))

        # 現在値（緑色で視認性アップ）
        self.create_text(W//2, H-4,
                         text=f'D:{int(self._y*100)}  S:{int(self._x*100)}',
                         fill='#00c896', font=('Helvetica', 8, 'bold'))

    # ── 操作 ──────────────────────────────────────────
    def _on_click(self, e):
        self._update(e.x, e.y)

    def _on_drag(self, e):
        self._update(e.x, e.y)

    def _update_angle_and_trail(self):
        """移動量から進行角度を更新し、軌跡を追記"""
        W, H = self.W, self.H
        dx = (self._x - self._sat_prev_x) * W
        dy = -(self._y - self._sat_prev_y) * H  # 画面 y は反転
        if abs(dx) > 0.3 or abs(dy) > 0.3:
            self._sat_angle = math.atan2(dy, dx)
        self._sat_prev_x = self._x
        self._sat_prev_y = self._y
        cx = int(self._x * W)
        cy = int((1.0 - self._y) * H)
        self._sat_trail.append((cx, cy))
        if len(self._sat_trail) > 20:
            self._sat_trail.pop(0)

    def _update(self, px, py):
        self._x = max(0.0, min(1.0, px / self.W))
        self._y = max(0.0, min(1.0, 1.0 - py / self.H))
        self._update_angle_and_trail()
        self._draw()
        if self._cmd:
            self._cmd(self._x, self._y)

    def _draw_satellite(self, cx, cy, angle):
        """タイプに応じてポインタを描き分け"""
        if self._sat_type == 'sputnik3':
            self._draw_sputnik3(cx, cy, angle)
        elif self._sat_type == 'hawk':
            self._draw_hawk(cx, cy, angle)
        elif self._sat_type == 'claude':
            self._draw_claude(cx, cy, angle)
        else:
            self._draw_sputnik1(cx, cy, angle)

    def set_sat_type(self, mode):
        self._sat_type = mode
        self._draw()

    # ── ポインタ: スプートニク1号 ──────────────────────
    def _draw_sputnik1(self, cx, cy, angle):
        """スプートニク: 磨かれた金属球 + 前方付け根から後方へ流れる4本アンテナ"""
        R     = 7
        front = angle                # 進行方向（前）
        back  = angle + math.pi      # 後方

        # ── 球体ドロップシャドウ ────────────────────
        self.create_oval(cx-R+1, cy-R+2, cx+R+1, cy+R+2,
                         fill='#06060f', outline='')

        # ── 球体本体（3層で立体感）──────────────────
        self.create_oval(cx-R,   cy-R,   cx+R,   cy+R,
                         fill='#8888a8', outline='#b0b0c8', width=1)
        m = int(R * 0.72)
        self.create_oval(cx-m,   cy-m,   cx+m,   cy+m,
                         fill='#b8b8d0', outline='')
        s = int(R * 0.42)
        self.create_oval(cx-s,   cy-s,   cx+s,   cy+s,
                         fill='#d4d4e8', outline='')

        # ── 赤道縫い目（後方半円のみ）──────────────
        perp = angle + math.pi / 2
        pts  = []
        for i in range(9):
            t = perp + i * (math.pi / 8)
            pts.append(cx + R * math.cos(t))
            pts.append(cy + R * math.sin(t))
        self.create_line(*pts, fill='#686888', width=1, smooth=False)

        # ── スペキュラハイライト ─────────────────────
        hx = cx - R * 0.38
        hy = cy - R * 0.38
        hr = max(2, int(R * 0.28))
        self.create_oval(hx-hr, hy-hr, hx+hr, hy+hr,
                         fill='#eeeeff', outline='')

        # ── アンテナ（球体より後に描いて浮き出させる）──
        antennas = [
            (-0.62, -0.50, 15),
            (-0.22, -0.17, 12),
            ( 0.22,  0.17, 12),
            ( 0.62,  0.50, 15),
        ]
        for da_r, da_t, length in antennas:
            sx = cx + R * math.cos(front + da_r)
            sy = cy + R * math.sin(front + da_r)
            ex = cx + (R + length) * math.cos(back + da_t)
            ey = cy + (R + length) * math.sin(back + da_t)
            self.create_line(sx, sy, ex, ey, fill='#707090', width=2)
            self.create_line(sx, sy, ex, ey, fill='#a8a8c8', width=1)
            self.create_oval(ex-1.5, ey-1.5, ex+1.5, ey+1.5,
                             fill='#c0c0d8', outline='')

    # ── ポインタ: スプートニク3号 ─────────────────────
    def _draw_sputnik3(self, cx, cy, angle):
        """スプートニク3号: 長い円錐形ボディ + 後方に2本アンテナ"""
        def r(px, py):
            a = angle
            return (cx + px*math.cos(a) - py*math.sin(a),
                    cy + px*math.sin(a) + py*math.cos(a))

        def poly(*pts_local):
            return [c for pt in pts_local for c in r(*pt)]

        # ── シャドウ ──────────────────────────────
        sh = poly((13, 1), (-9, -10), (-13, -10), (-13, 10), (-9, 10))
        self.create_polygon(sh, fill='#06060f', outline='')

        # ── 本体（円錐形）──────────────────────────
        body = poly((13, 0), (-9, -9), (-13, -9), (-13, 9), (-9, 9))
        self.create_polygon(body, fill='#9898b8', outline='#b8b8d0', width=1)

        # ハイライト帯（中央）
        hi = poly((11, -1), (-7, -3), (-11, -3), (-11, 3), (-7, 3), (11, 1))
        self.create_polygon(hi, fill='#c4c4d8', outline='')

        # 内側ブライト
        br = poly((9, -0.5), (-4, -1.8), (-7, -1.8), (-7, 1.8), (-4, 1.8), (9, 0.5))
        self.create_polygon(br, fill='#dcdcec', outline='')

        # ── ベースプレート ─────────────────────────
        bp = poly((-9, -9), (-13, -9), (-13, 9), (-9, 9))
        self.create_polygon(bp, fill='#6868a0', outline='#8888b8', width=1)

        # ── アンテナ（後方コーナーから伸びる）──────
        for ay in [-8, 8]:
            ast = r(-12, ay * 0.9)
            aen = r(-22, ay * 1.8)
            self.create_line(ast[0], ast[1], aen[0], aen[1], fill='#6868a0', width=2)
            self.create_line(ast[0], ast[1], aen[0], aen[1], fill='#a8a8c8', width=1)
            self.create_oval(aen[0]-2, aen[1]-2, aen[0]+2, aen[1]+2,
                             fill='#c0c0d8', outline='')

        # ── 先端ハイライト ──────────────────────────
        tip_h = r(9, -0.5)
        self.create_oval(tip_h[0]-1.5, tip_h[1]-1.5, tip_h[0]+1.5, tip_h[1]+1.5,
                         fill='#eeeeff', outline='')

    # ── ポインタ: 鷹 ───────────────────────────────────
    # ── ピクセルアート描画ヘルパー ─────────────────────
    def _draw_pixel_art(self, cx, cy, angle, grid, colors, psize=2.0):
        """グリッド定義のピクセルアートを回転して描画する"""
        rows = len(grid)
        cols = len(grid[0])
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        ox = cols * psize / 2.0   # グリッド中心のローカルx
        oy = rows * psize / 2.0   # グリッド中心のローカルy

        def rot(lx, ly):
            return (cx + lx * cos_a - ly * sin_a,
                    cy + lx * sin_a + ly * cos_a)

        for ri, row in enumerate(grid):
            for ci, ck in enumerate(row):
                if not ck:
                    continue
                fill = colors.get(ck)
                if not fill:
                    continue
                lx = ci * psize - ox
                ly = ri * psize - oy
                pts = [rot(lx, ly), rot(lx+psize, ly),
                       rot(lx+psize, ly+psize), rot(lx, ly+psize)]
                self.create_polygon([c for pt in pts for c in pt],
                                    fill=fill, outline='')

    # ── ポインタ: 鷹（8bitスタイル+羽ばたきアニメ）──
    def _draw_hawk(self, cx, cy, angle):
        """鷹 8bit: 上空俯瞰、ブロック状の形状、羽ばたき4フレーム"""
        frame = self._claude_frame  # 0-3 で羽ばたき

        def r(px, py):
            a = angle
            return (cx + px*math.cos(a) - py*math.sin(a),
                    cy + px*math.sin(a) + py*math.cos(a))

        def poly(*pts):
            return [c for pt in pts for c in r(*pt)]

        # 8bit 限定パレット
        c_out  = '#080400'
        c_dark = '#3a1e08'
        c_wing = '#6a3810'
        c_med  = '#8a5020'
        c_lite = '#c07840'
        c_belly= '#e8a858'
        c_beak = '#e8a000'
        c_eye  = '#f0e000'

        # フレームごとの翼の開き具合: [全開, 中, 畳む, 中]
        wspan = [18, 12, 5, 12][frame]       # 翼先端までのy幅
        wback = [ 2,  6, 10,  6][frame]      # 翼先端のx後退量

        # ── シャドウ ────────────────────────────
        sh = poly((12,1),(4,-2),(-4,-3),(-10,-2),(-12,1),(-10,3),(-4,4),(4,3))
        self.create_polygon(sh, fill='#06060f', outline='')

        # ── 翼（左・右、8bitブロック形状）───────
        for side in (-1, 1):   # -1=左, 1=右
            ws = wspan * side
            wb = wback
            # 翼アウター
            wo = poly(
                ( 4,  3*side),
                ( 4 - wb*0.3,  ws*0.55),
                (-2 - wb,      ws),
                (-6 - wb,      ws - 2*side),
                (-5,           4*side),
                ( 2,           3*side),
            )
            self.create_polygon(wo, fill=c_wing, outline=c_out, width=1)
            # 翼インナー（明るめ帯）
            wi = poly(
                ( 3,  3*side),
                ( 3 - wb*0.2,  ws*0.38),
                (-1 - wb*0.65, ws*0.72),
                (-3,           4*side),
            )
            self.create_polygon(wi, fill=c_med, outline='')
            # 羽根ライン（3本、ドット状）
            for t in [0.32, 0.60, 0.84]:
                fx = 3 - (wb + 2) * t
                fy = ws * t
                fs = r(fx + 1.5, fy - 2.5*side)
                fe = r(fx - 2.5, fy + 2.0*side)
                self.create_line(fs[0],fs[1],fe[0],fe[1], fill=c_out, width=1)

        # ── 尾羽（3枚ブロック）──────────────────
        tc = poly((-9,-1),(-14,-2),(-15,0),(-14,2),(-9,1))
        self.create_polygon(tc, fill=c_dark, outline=c_out, width=1)
        tl = poly((-9,-2),(-12,-5),(-14,-3),(-11,-1))
        self.create_polygon(tl, fill=c_med, outline=c_out, width=1)
        tr = poly((-9, 2),(-12, 5),(-14, 3),(-11, 1))
        self.create_polygon(tr, fill=c_med, outline=c_out, width=1)

        # ── 胴体（8bitブロック矩形）─────────────
        body = poly((11,0),(8,-3),(2,-4),(-7,-3),(-10,0),
                    (-7,3),(2,4),(8,3))
        self.create_polygon(body, fill=c_dark, outline=c_out, width=1)
        belly = poly((7,0),(3,-2),(-2,-2),(-5,0),(-2,2),(3,2))
        self.create_polygon(belly, fill=c_belly, outline='')
        # ピクセルドット斑点
        for dx, dy in [(3,1.5),(0,-1.5),(-3,1)]:
            pt = r(dx, dy)
            self.create_rectangle(pt[0]-1,pt[1]-1,pt[0]+1,pt[1]+1,
                                  fill=c_dark, outline='')

        # ── 頭部（四角ベース）───────────────────
        h1=r(11,-3); h2=r(15,-3); h3=r(15,3); h4=r(11,3)
        self.create_polygon([h1[0],h1[1],h2[0],h2[1],h3[0],h3[1],h4[0],h4[1]],
                            fill=c_dark, outline=c_out, width=1)
        # 目（四角ピクセル）
        ey = r(13, -1.5)
        self.create_rectangle(ey[0]-2, ey[1]-2, ey[0]+2, ey[1]+2, fill=c_eye, outline='')
        pu = r(13.5, -1.5)
        self.create_rectangle(pu[0]-1, pu[1]-1, pu[0]+1, pu[1]+1, fill=c_out, outline='')

        # ── くちばし（8bitゴールド三角）─────────
        bk = poly((15,-0.5),(20,0),(15,0.5))
        self.create_polygon(bk, fill=c_beak, outline=c_out, width=1)

    # ── ポインタ: Clawd（Claude公式ロゴ近似: 5枚ブレードピンホイール）──
    def _draw_claude(self, cx, cy, angle):
        """8-bitレトロロボット（進行方向に頭を向け、4フレームアニメ）
        上空俯瞰: 前方(+x)=頭部, 後方(-x)=キャタピラ, ±y=左右"""

        frame = self._claude_frame  # 0-3

        def r(px, py):
            a = angle
            return (cx + px*math.cos(a) - py*math.sin(a),
                    cy + px*math.sin(a) + py*math.cos(a))

        def poly(*pts):
            return [c for pt in pts for c in r(*pt)]

        def px_rect(x0, y0, x1, y1):
            """ピクセル風矩形ポリゴン"""
            return poly((x0,y0),(x1,y0),(x1,y1),(x0,y1))

        def px_dot(px_x, px_y, half=1.5, fill='#ffffff'):
            """ピクセルドット（正方形）"""
            pt = r(px_x, px_y)
            self.create_rectangle(
                pt[0]-half, pt[1]-half, pt[0]+half, pt[1]+half,
                fill=fill, outline='')

        # ── 8-bit レトロパレット ──────────────
        C_STEEL  = '#8090A8'   # ロボット鋼鉄
        C_LITE   = '#B8C8D8'   # ハイライト（明るい上面）
        C_DARK   = '#181C28'   # アウトライン（ほぼ黒）
        C_MED    = '#506070'   # 中間シャドウ
        C_PANEL  = '#0A1E36'   # CRTパネル黒
        C_VISOR  = '#102840'   # バイザー
        C_GREEN  = '#00FF88'   # CRTグリーン目 (ON)
        C_GREEND = '#005530'   # 目 暗(blink)
        C_TRACK  = '#404858'   # キャタピラ
        C_TGROOV = '#282E3A'   # キャタピラ溝
        C_JOINT  = '#C8A840'   # 関節ボルト（ゴールド）
        C_ANT_N  = '#FF6600'   # アンテナ（通常・橙）
        C_ANT_B  = '#FFCC00'   # アンテナ（点灯・黄）
        C_WARN   = '#FF2200'   # 警告ランプ
        C_WARN_D = '#660800'   # 警告ランプ暗

        # ── アニメーション変数 ────────────────
        # キャタピラの溝を1フレームずつずらして回転感を出す
        grv_off  = [0, 2, 4, 6][frame]          # 溝のx位置オフセット
        eye_col  = C_GREEN  if frame != 2 else C_GREEND   # frame2=瞬き
        ant_col  = C_ANT_B  if frame % 2 == 1  else C_ANT_N
        warn_col = C_WARN   if frame in (1, 3)  else C_WARN_D

        # ── シャドウ ─────────────────────────
        sh = poly((11,1),(6,-5),(-8,-6),(-12,-3),(-13,0),
                  (-12,3),(-8,6),(6,5))
        self.create_polygon(sh, fill='#06060f', outline='')

        # ══ キャタピラ（左右、後方）══════════
        for side in (-1, 1):
            # キャタピラ本体（長方形ブロック）
            tr = px_rect(-12, side*4, 2, side*7)
            self.create_polygon(tr, fill=C_TRACK, outline=C_DARK, width=1)
            # 前輪・後輪（丸みのある四角）
            for wx in (-11, 1):
                wh = r(wx, side*5.5)
                self.create_oval(wh[0]-2.5, wh[1]-2.5, wh[0]+2.5, wh[1]+2.5,
                                 fill=C_MED, outline=C_DARK, width=1)
            # 溝（アニメ: grv_off でずれる）
            for gx_base in range(-10, 2, 4):
                gx = gx_base + (grv_off % 4) - 2
                if -12 <= gx <= 1:
                    px_dot(gx, side*5.5, half=1.0, fill=C_TGROOV)

        # ══ 胴体 ══════════════════════════════
        # 胴体外殻
        body = px_rect(-7, -4, 6, 4)
        self.create_polygon(body, fill=C_STEEL, outline=C_DARK, width=1)
        # 上面ハイライト
        hi = px_rect(-6, -3, 5, 3)
        self.create_polygon(hi, fill=C_LITE, outline='')

        # チェストパネル（CRTスクリーン）
        pan = px_rect(-4, -2.5, 2, 2.5)
        self.create_polygon(pan, fill=C_PANEL, outline=C_DARK, width=1)
        # パネル内のピクセルドット3×2
        for dx, dy, col in [
            (-3, -1.5, C_GREEN), (-1, -1.5, C_GREEN), (1, -1.5, C_GREEND),
            (-3,  1.5, C_GREEND),(-1,  1.5, C_GREEN), (1,  1.5, C_GREEN ),
        ]:
            px_dot(dx, dy, half=0.9, fill=col if frame != 2 else C_GREEND)

        # 警告ランプ（点滅）
        px_dot(3.5, 0, half=1.5, fill=warn_col)

        # ボルト（胴体四隅）
        for bx, by in [(-6,-3.5),(-6,3.5),(5,-3.5),(5,3.5)]:
            px_dot(bx, by, half=1.0, fill=C_JOINT)

        # ── ショルダー（腕の付け根・張り出し）──
        for side in (-1, 1):
            sh_p = px_rect(-2, side*4, 4, side*6)
            self.create_polygon(sh_p, fill=C_STEEL, outline=C_DARK, width=1)
            px_dot(1, side*5, half=1.2, fill=C_JOINT)

        # ══ 頭部 ══════════════════════════════
        # 頭部外殻（角丸っぽく見せる3枚重ね）
        head = px_rect(6, -4.5, 12, 4.5)
        self.create_polygon(head, fill=C_STEEL, outline=C_DARK, width=1)
        head_hi = px_rect(7, -3.5, 11, 3.5)
        self.create_polygon(head_hi, fill=C_LITE, outline='')

        # バイザー（目の部分の暗いスクリーン）
        visor = px_rect(8, -2.8, 11.5, 2.8)
        self.create_polygon(visor, fill=C_VISOR, outline=C_DARK, width=1)

        # 目（2つのピクセル、縦並び）
        for ey_y in (-1.5, 1.5):
            px_dot(9.8, ey_y, half=1.8, fill=eye_col)
            # 目の中央白点（瞳ハイライト）
            if frame != 2:
                px_dot(10.3, ey_y - 0.4, half=0.7, fill='#ffffff')

        # 頭部ボルト
        for bx, by in [(6.5,-4),(6.5,4),(11.5,-4),(11.5,4)]:
            px_dot(bx, by, half=1.0, fill=C_JOINT)

        # ── アンテナ ─────────────────────────
        # 根本: 頭頂部
        ant_b = r(9.5, -4.5)
        ant_m = r(10.0, -7.5)
        ant_t = r(10.5, -9.5)
        self.create_line(ant_b[0],ant_b[1], ant_m[0],ant_m[1],
                         fill=C_DARK, width=2)
        self.create_line(ant_m[0],ant_m[1], ant_t[0],ant_t[1],
                         fill=C_MED, width=1)
        # 先端ビード（点滅）
        self.create_oval(ant_t[0]-2.5, ant_t[1]-2.5, ant_t[0]+2.5, ant_t[1]+2.5,
                         fill=ant_col, outline=C_DARK, width=1)
        # 小ハイライト
        self.create_oval(ant_t[0]-1.2, ant_t[1]-1.5, ant_t[0]+0.5, ant_t[1]-0.2,
                         fill='#ffe8c0', outline='')

    def set_pos(self, x, y):
        self._x = max(0.0, min(1.0, float(x)))
        self._y = max(0.0, min(1.0, float(y)))
        self._draw()

    # ── Auto Mod ──────────────────────────────────────
    def auto_mod_start(self):
        self._am_active = True
        self._am_phase  = 0.0
        self._am_tx = random.random()
        self._am_ty = random.random()
        self._tick()

    def auto_mod_stop(self):
        self._am_active = False
        if self._am_after:
            try:
                self.after_cancel(self._am_after)
            except Exception:
                pass
            self._am_after = None
        self._draw()

    def set_am_speed(self, v):
        """v: 0.0〜1.0"""
        self._am_speed = max(0.01, float(v))

    def set_am_mode(self, mode):
        """mode: 'random' / 'circle' / 'figure8' / 'spiral'"""
        self._am_mode  = mode
        self._am_phase = 0.0

    def _tick(self):
        if not self._am_active:
            return

        spd = self._am_speed
        # 各モードの時間ステップ
        dt = 0.015 + spd * 0.08

        mode = self._am_mode

        if mode == 'random':
            # ランダム目標へのスムーズ補間
            lerp = 0.02 + spd * 0.12
            self._x += (self._am_tx - self._x) * lerp
            self._y += (self._am_ty - self._y) * lerp
            if math.hypot(self._am_tx - self._x, self._am_ty - self._y) < 0.03:
                self._am_tx = random.random()
                self._am_ty = random.random()

        elif mode == 'circle':
            # 方向・半径・中心をランダムに変化させる円運動
            self._am_phase += dt * self._am_circle_dir
            # 半径を緩やかに変動（0.08〜0.44 の間を正弦波でゆっくり変化）
            self._am_circle_phase_r += dt * 0.25
            r = 0.08 + 0.36 * (0.5 + 0.5 * math.sin(self._am_circle_phase_r))
            self._am_circle_r = r
            # ごく稀に中心をランダム移動
            if random.random() < 0.003:
                self._am_circle_cx = random.uniform(0.15, 0.85)
                self._am_circle_cy = random.uniform(0.15, 0.85)
            # ごく稀に回転方向を反転
            if random.random() < 0.0015:
                self._am_circle_dir *= -1
            self._x = max(0.0, min(1.0, self._am_circle_cx + r * math.cos(self._am_phase)))
            self._y = max(0.0, min(1.0, self._am_circle_cy + r * math.sin(self._am_phase)))

        elif mode == 'figure8':
            # 方向・スケール・中心をランダムに変化させる八の字（リサージュ曲線）
            self._am_phase += dt * 0.8 * self._am_f8_dir
            t = self._am_phase
            # スケールをゆっくり変動
            self._am_f8_sx = 0.20 + 0.22 * (0.5 + 0.5 * math.sin(t * 0.11))
            self._am_f8_sy = 0.16 + 0.20 * (0.5 + 0.5 * math.cos(t * 0.09))
            # ごく稀に中心をランダム移動
            if random.random() < 0.003:
                self._am_f8_cx = random.uniform(0.2, 0.8)
                self._am_f8_cy = random.uniform(0.2, 0.8)
            # ごく稀に方向反転
            if random.random() < 0.0015:
                self._am_f8_dir *= -1
            self._x = max(0.0, min(1.0, self._am_f8_cx + self._am_f8_sx * math.sin(t)))
            self._y = max(0.0, min(1.0, self._am_f8_cy + self._am_f8_sy * math.sin(2 * t)))

        elif mode == 'spiral':
            # 外向き螺旋 → リセット
            self._am_phase += dt * 0.7
            t = self._am_phase
            # 8回転で外周まで広がり、リセット
            period = 2 * math.pi * 6
            frac   = (t % period) / period      # 0→1 で一周期
            r      = frac * 0.47
            self._x = max(0.0, min(1.0, 0.5 + r * math.cos(t * 5)))
            self._y = max(0.0, min(1.0, 0.5 + r * math.sin(t * 5)))

        # Claude アニメーションフレームを4tickごとに進める
        self._claude_tick = (self._claude_tick + 1) % 4
        if self._claude_tick == 0:
            self._claude_frame = (self._claude_frame + 1) % 4

        self._update_angle_and_trail()
        self._draw()
        if self._cmd:
            self._cmd(self._x, self._y)

        interval = max(16, int(50 - spd * 34))
        self._am_after = self.after(interval, self._tick)


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
        return 'break'  # ページスクロールに伝播させない

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
        self.root.resizable(True, True)

        self._playing = False
        self._drone = self._melody = self._sparkle = self._evo = self._chord = None
        self._current_root_lbl  = None
        self._current_scale_lbl = None
        self._current_chord_lbl = None
        self._clock_receiver    = None   # MidiClockReceiver (slave)
        self._tap_times         = []     # タップテンポ用タイムスタンプ
        self._clock_sender      = None   # MidiClockSender   (master)
        self._sync_mode         = 'off'  # 'off' / 'slave' / 'master'
        self._build_ui()
        global _lamp_root
        _lamp_root = self.root   # シグナルランプ用 after() ターゲット
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ---- UI構築 ----------------------------------------
    def _build_ui(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        win_w = min(1400, sw - 20)
        win_h = min(900, sh - 40)
        self.root.geometry(f'{win_w}x{win_h}')
        self.root.minsize(1100, 720)

        # ── タイトルバー ──────────────────────────────────────────────
        title_bar = tk.Frame(self.root, bg=C_BG, pady=7)
        title_bar.pack(fill='x', padx=16)
        tk.Label(title_bar, text='✦  AMBIENT GENERATOR  ✦',
                 bg=C_BG, fg=C_TEXT,
                 font=('Helvetica', 13, 'bold')).pack(side='left')
        self._status_lbl = tk.Label(title_bar, text='● STOPPED',
                                    bg=C_BG, fg=C_OFF,
                                    font=('Helvetica', 9, 'bold'))
        self._status_lbl.pack(side='right')

        # ── Place de l'Étoile メインキャンバス ────────────────────────
        mc = tk.Canvas(self.root, bg=C_BG, highlightthickness=0)
        mc.pack(fill='both', expand=True)
        self._radial_canvas = mc

        CX, CY = 700, 440   # 凱旋門（中央ハブ）座標

        def pw(frame, x, y, anchor='center'):
            mc.create_window(x, y, window=frame, anchor=anchor)

        # コントロール辞書を初期化
        self._layer_vars    = {}
        self._var_rand_btns = {}
        self._var_knobs     = {}

        # ── 中央ハブ（KaossPad + AUTO EVOLVE + AUTO MOD）────────────
        hub = tk.Frame(mc, bg=C_BG)
        self._build_kaoss_hub(hub)
        pw(hub, CX, CY)

        # ── N: Transport ─────────────────────────────────────────────
        f_tr = tk.Frame(mc, bg=C_BG)
        self._build_transport(f_tr)
        pw(f_tr, CX, 92)

        # ── NW: Key + Scale ──────────────────────────────────────────
        f_ks = tk.Frame(mc, bg=C_BG)
        self._build_key(f_ks)
        self._build_scale(f_ks)
        pw(f_ks, 400, 195)

        # ── W: Chord Type + Density ──────────────────────────────────
        f_cd = tk.Frame(mc, bg=C_BG)
        self._build_chord_type(f_cd)
        self._build_density(f_cd)
        pw(f_cd, 228, CY)

        # ── SW: Drone Layer ──────────────────────────────────────────
        f_dn = tk.Frame(mc, bg=C_BG)
        self._build_drone_panel(f_dn)
        pw(f_dn, 390, 710)

        # ── S: Log ───────────────────────────────────────────────────
        f_lg = tk.Frame(mc, bg=C_BG)
        self._build_log(f_lg)
        pw(f_lg, CX, 808)

        # ── SE: Chord ARP ────────────────────────────────────────────
        f_ca = tk.Frame(mc, bg=C_BG)
        self._build_chord_panel(f_ca)
        pw(f_ca, 1010, 710)

        # ── E: Melody Layer ──────────────────────────────────────────
        f_ml = tk.Frame(mc, bg=C_BG)
        self._build_melody_panel(f_ml)
        pw(f_ml, 1172, CY)

        # ── NE: Sparkle Layer ────────────────────────────────────────
        f_sp = tk.Frame(mc, bg=C_BG)
        self._build_sparkle_panel(f_sp)
        pw(f_sp, 1000, 195)

        # ── 放射状デコレーションを描画 ───────────────────────────────
        self.root.after(150, lambda: self._draw_radial_bg(mc, CX, CY))

        # BPM ブリンク開始
        self.root.after(100, self._bpm_blink_tick)


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
            row, 'BPM', 30, 300, 52, C_TEXT, C_PANEL,
            command=self._on_bpm)
        self._bpm_knob.master.pack(side='right', padx=(12, 0))

        # TAP テンポボタン（正方形・赤く点滅でテンポ表示）
        self._tap_frame = tk.Frame(
            row, width=28, height=28, bg='#1e1e38', cursor='hand2')
        self._tap_frame.pack_propagate(False)
        self._tap_frame.pack(side='right', padx=(0, 4))
        self._tap_label = tk.Label(
            self._tap_frame, text='TAP', bg='#1e1e38', fg='#aaaacc',
            font=('Helvetica', 7, 'bold'), cursor='hand2')
        self._tap_label.place(relx=0.5, rely=0.5, anchor='center')
        self._tap_frame.bind('<Button-1>', lambda e: self._on_tap())
        self._tap_label.bind('<Button-1>', lambda e: self._on_tap())

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

        self._rdn_btn = tk.Button(rand_row, text='RDN', command=self._on_random_root,
                  bg='#2a2a4a', fg='#666688', relief='flat',
                  font=('Helvetica', 7, 'bold'), padx=5, pady=2,
                  activebackground='#5a0000', cursor='hand2')
        self._rdn_btn.pack(side='left')

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
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Scale.TCombobox',
                        fieldbackground=C_SLIDER, background=C_SLIDER,
                        foreground=C_TEXT, selectbackground=C_ACCENT,
                        arrowcolor=C_TEXT, font=('Helvetica', 13, 'bold'))
        style.map('Scale.TCombobox',
                  fieldbackground=[('readonly', C_SLIDER)],
                  foreground=[('readonly', C_TEXT)])
        menu = ttk.Combobox(f, textvariable=self._scale_var,
                            values=list(SCALES.keys()),
                            style='Scale.TCombobox',
                            state='readonly', width=20,
                            font=('Helvetica', 13, 'bold'))
        menu.pack(anchor='w', pady=(0, 4))
        menu.bind('<<ComboboxSelected>>', self._on_scale)

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

    def _build_kaoss_hub(self, parent):
        """中央ハブ: KaossPad + AUTO EVOLVE + AUTO MOD + POINTER"""
        f = tk.Frame(parent, bg=C_BG)

        # AUTO EVOLVE ボタン
        self._evolve_var = tk.BooleanVar(value=False)
        self._evolve_btn = tk.Label(
            f, text='⚡  AUTO EVOLVE',
            bg='#111128', fg='#334466',
            font=('Helvetica', 14, 'bold'),
            padx=12, pady=10, cursor='hand2', anchor='center')
        self._evolve_btn.pack(fill='x', pady=(0, 6))
        self._evolve_btn.bind('<Button-1>', lambda e: self._on_evolve_toggle())

        # XY パッド + Mod Wheel（横並び）
        pad_outer = tk.Frame(f, bg=C_BG)
        pad_outer.pack()

        # ── Mod Wheel（左） ──────────────────────────────────────
        mod_col = tk.Frame(pad_outer, bg=C_BG)
        mod_col.pack(side='left', padx=(0, 6))
        tk.Label(mod_col, text='MOD', bg=C_BG, fg='#6677aa',
                 font=('Helvetica', 7, 'bold')).pack(pady=(0, 2))
        self._mod_wheel_var = tk.IntVar(value=0)
        self._mod_wheel = tk.Scale(
            mod_col,
            from_=127, to=0,
            variable=self._mod_wheel_var,
            orient='vertical',
            length=KaossPad.H,
            width=22,
            showvalue=False,
            bg='#111128', fg='#6677aa',
            troughcolor='#0a0a1e',
            activebackground='#7c8fdd',
            highlightthickness=1,
            highlightbackground='#2a2a4a',
            command=self._on_mod_wheel)
        self._mod_wheel.pack()
        self._mod_val_lbl = tk.Label(mod_col, text='0', bg=C_BG, fg='#445566',
                                     font=('Helvetica', 7))
        self._mod_val_lbl.pack(pady=(2, 0))

        # ── KaossPad（右） ───────────────────────────────────────
        self._kaoss_pad = KaossPad(pad_outer, command=self._on_kaoss)
        self._kaoss_pad.pack(side='left')

        # Auto Mod モードボタン行
        mode_row = tk.Frame(f, bg=C_BG)
        mode_row.pack(fill='x', pady=(5, 2))
        tk.Label(mode_row, text='MOD MODE', bg=C_BG, fg='#445566',
                 font=('Helvetica', 7)).pack(side='left', padx=(0, 4))
        self._am_mode_btns = {}
        for key, label in [('random', 'RAND'), ('circle', '○'),
                            ('figure8', '∞'), ('spiral', '◌')]:
            btn = tk.Label(mode_row, text=label,
                           bg='#1e1e38', fg='#445566',
                           font=('Helvetica', 9, 'bold'),
                           padx=7, pady=3, cursor='hand2')
            btn.bind('<Button-1>', lambda e, k=key: self._on_am_mode(k))
            btn.pack(side='left', padx=1)
            self._am_mode_btns[key] = btn
        self._update_am_mode_buttons('random')

        # AUTO MOD スイッチ + 移動速度ノブ
        am_row = tk.Frame(f, bg=C_BG)
        am_row.pack(fill='x', pady=(2, 0))
        self._auto_mod_var = tk.BooleanVar(value=False)
        self._auto_mod_btn = tk.Label(
            am_row, text='◎  AUTO MOD',
            bg='#111128', fg='#445566',
            font=('Helvetica', 10, 'bold'),
            padx=10, pady=6, cursor='hand2')
        self._auto_mod_btn.pack(side='left')
        self._auto_mod_btn.bind('<Button-1>', lambda e: self._on_auto_mod_toggle())
        _, self._am_speed_knob = labeled_knob(
            am_row, 'Move Speed', 1, 100, 30,
            '#ff9966', C_BG, self._on_am_speed)
        self._am_speed_knob.master.pack(side='right', padx=(0, 4))

        # POINTER デザイン選択行
        tk.Frame(f, bg='#2a2a4a', height=1).pack(fill='x', pady=(8, 5))
        sat_row = tk.Frame(f, bg=C_BG)
        sat_row.pack(fill='x', pady=(0, 4))
        tk.Label(sat_row, text='POINTER', bg=C_BG, fg='#445566',
                 font=('Helvetica', 7)).pack(side='left', padx=(0, 4))
        self._sat_type_btns = {}
        for key, label in [('sputnik1', 'SP-1'), ('sputnik3', 'SP-3'),
                            ('hawk', '鷹'), ('claude', 'CLaUDE')]:
            btn = tk.Label(sat_row, text=label,
                           bg='#1e1e38', fg='#445566',
                           font=('Helvetica', 9, 'bold'),
                           padx=8, pady=3, cursor='hand2')
            btn.bind('<Button-1>', lambda e, k=key: self._on_sat_type(k))
            btn.pack(side='left', padx=1)
            self._sat_type_btns[key] = btn
        self._update_sat_type_buttons('sputnik1')

        f.pack()

    def _build_drone_panel(self, parent):
        BG = '#141428'
        f = section(parent, 'Drone')
        f.pack(fill='x', pady=(0, 6))
        block = tk.Frame(f, bg=BG, padx=10, pady=8)
        block.pack(fill='x', pady=3)

        header = tk.Frame(block, bg=BG)
        header.pack(fill='x', pady=(0, 6))
        lvar, _pb = pwr_btn(header, 'DRONE', BG, initial=True,
                            fg_on=C_TEXT, fg_off='#555577',
                            command=lambda: self._on_layer('drone'))
        self._layer_vars['drone'] = lvar
        _pb.pack(side='left')
        tk.Label(header, text='Ch.1', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(6, 0))
        lamp = tk.Label(header, text='●', bg=BG, fg='#2a2a4a',
                        font=('Helvetica', 10))
        lamp.pack(side='left', padx=(5, 0))
        _lamp_fns[0] = lambda on, w=lamp: w.config(fg='#00c896' if on else '#2a2a4a')

        knob_row = tk.Frame(block, bg=BG)
        knob_row.pack()
        _, kv = labeled_knob(knob_row, 'Vel', 1, 127, 45,
                              C_TEXT, BG, lambda v: self._on_vel('drone', v))
        kv.master.pack(side='left', padx=10)
        var_f, kvar = labeled_knob(knob_row, 'Variation', 0, 100, 20,
                                    C_VAR, BG, lambda v: self._on_variation('drone', v))
        rnd_var_btn = tk.Label(var_f, text='RND', bg=BG, fg='#4a9eff', relief='flat',
                               font=('Helvetica', 6, 'bold'), padx=3, pady=1, cursor='hand2')
        rnd_var_btn.bind('<Button-1>', lambda e: self._on_variation_random('drone'))
        rnd_var_btn.pack()
        self._var_rand_btns['drone'] = rnd_var_btn
        self._var_knobs['drone'] = kvar
        var_f.pack(side='left', padx=10)
        _, krest = labeled_knob(knob_row, 'Rest', 0, 100, 0,
                                 C_REST, BG, lambda v: self._on_rest('drone', v))
        krest.master.pack(side='left', padx=10)

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

        follow_row = tk.Frame(block, bg=BG)
        follow_row.pack(fill='x', pady=(4, 0))
        tk.Label(follow_row, text='Follow', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._drone_follow_btns = {}
        for fkey, flabel in [('root', 'ROOT'), ('chord', 'CHORD')]:
            b = tk.Label(follow_row, text=flabel, width=6,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, k=fkey: self._on_drone_follow(k))
            b.pack(side='left', padx=1)
            self._drone_follow_btns[fkey] = b
        self._update_drone_follow_buttons('root')

    def _build_melody_panel(self, parent):
        BG = '#141428'
        f = section(parent, 'Melody')
        f.pack(fill='x', pady=(0, 6))
        block = tk.Frame(f, bg=BG, padx=10, pady=8)
        block.pack(fill='x', pady=3)

        header = tk.Frame(block, bg=BG)
        header.pack(fill='x', pady=(0, 6))
        lvar, _pb = pwr_btn(header, 'MELODY', BG, initial=True,
                            fg_on=C_TEXT, fg_off='#555577',
                            command=lambda: self._on_layer('melody'))
        self._layer_vars['melody'] = lvar
        _pb.pack(side='left')
        tk.Label(header, text='Ch.2', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(6, 0))
        lamp = tk.Label(header, text='●', bg=BG, fg='#2a2a4a',
                        font=('Helvetica', 10))
        lamp.pack(side='left', padx=(5, 0))
        _lamp_fns[1] = lambda on, w=lamp: w.config(fg='#00c896' if on else '#2a2a4a')

        knob_row = tk.Frame(block, bg=BG)
        knob_row.pack()
        _, kv = labeled_knob(knob_row, 'Vel', 1, 127, 38,
                              C_TEXT, BG, lambda v: self._on_vel('melody', v))
        kv.master.pack(side='left', padx=10)
        var_f, kvar = labeled_knob(knob_row, 'Variation', 0, 100, 30,
                                    C_VAR, BG, lambda v: self._on_variation('melody', v))
        rnd_var_btn = tk.Label(var_f, text='RND', bg=BG, fg='#4a9eff', relief='flat',
                               font=('Helvetica', 6, 'bold'), padx=3, pady=1, cursor='hand2')
        rnd_var_btn.bind('<Button-1>', lambda e: self._on_variation_random('melody'))
        rnd_var_btn.pack()
        self._var_rand_btns['melody'] = rnd_var_btn
        self._var_knobs['melody'] = kvar
        var_f.pack(side='left', padx=10)
        _, krest = labeled_knob(knob_row, 'Rest', 0, 100, 35,
                                 C_REST, BG, lambda v: self._on_rest('melody', v))
        krest.master.pack(side='left', padx=10)

        oct_row = tk.Frame(block, bg=BG)
        oct_row.pack(fill='x', pady=(6, 0))
        tk.Label(oct_row, text='Oct', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._melody_oct_btns = {}
        for ov in [1, 2, 3, 4, 5]:
            b = tk.Label(oct_row, text=str(ov), width=3,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 9), pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=ov: self._on_melody_octave(v))
            b.pack(side='left', padx=1)
            self._melody_oct_btns[ov] = b
        self._update_melody_oct_buttons(1)

        rng_row = tk.Frame(block, bg=BG)
        rng_row.pack(fill='x', pady=(4, 0))
        tk.Label(rng_row, text='Range', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._melody_range_btns = {}
        _rng_labels = {1: '1oct', 2: '2oct', 3: '3oct'}
        for rv in [1, 2, 3]:
            b = tk.Label(rng_row, text=_rng_labels[rv],
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), padx=6, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=rv: self._on_melody_range(v))
            b.pack(side='left', padx=1)
            self._melody_range_btns[rv] = b
        self._update_melody_range_buttons(1)

        char_row = tk.Frame(block, bg=BG)
        char_row.pack(fill='x', pady=(4, 0))
        tk.Label(char_row, text='Char', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._melody_char_btns = {}
        for ckey, clabel, ccol in [
            ('contour', 'Contour',  '#69db7c'),
            ('phrase',  'Phrase',   '#4dabf7'),
            ('motif',   'Motif',    '#ffa94d'),
            ('chord',   'ChordOnly','#f783ac'),
            ('simple',  'Simple',   '#a9e34b'),
        ]:
            b = tk.Label(char_row, text=clabel,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), padx=6, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, k=ckey: self._on_melody_character(k))
            b.pack(side='left', padx=1)
            self._melody_char_btns[ckey] = (b, ccol)

        rhy_row = tk.Frame(block, bg=BG)
        rhy_row.pack(fill='x', pady=(4, 0))
        tk.Label(rhy_row, text='Rhythm', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._melody_rhythm_btns = {}
        for rkey, rlabel, rcol in [
            ('free',    'Free',    '#555577'),
            ('flowing', 'Flowing', '#69db7c'),
            ('dotted',  'Dotted',  '#4dabf7'),
            ('synco',   'Synco',   '#ffa94d'),
            ('staccato','Staccato','#ff6b6b'),
            ('breath',  'Breath',  '#da77f2'),
        ]:
            b = tk.Label(rhy_row, text=rlabel,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 7), padx=4, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, k=rkey: self._on_melody_rhythm(k))
            b.pack(side='left', padx=1)
            self._melody_rhythm_btns[rkey] = (b, rcol)
        self._update_melody_rhythm_buttons('free')

        spd_row = tk.Frame(block, bg=BG)
        spd_row.pack(fill='x', pady=(4, 0))
        tk.Label(spd_row, text='Speed', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._melody_speed_btns = {}
        for lbl_text, val in [('/16', 0.0625), ('/8', 0.125), ('/4', 0.25),
                               ('/2', 0.5), ('×1', 1.0), ('×2', 2.0), ('×4', 4.0)]:
            b = tk.Label(spd_row, text=lbl_text,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=val: self._on_melody_speed(v))
            b.pack(side='left', padx=1)
            self._melody_speed_btns[val] = b
        self._melody_speed_rand_btn = tk.Label(
            spd_row, text='RAND', bg='#1e1e38', fg='#4a9eff', relief='flat',
            font=('Helvetica', 8, 'bold'), padx=6, pady=3, cursor='hand2')
        self._melody_speed_rand_btn.bind('<Button-1>', lambda e: self._on_melody_speed_random())
        self._melody_speed_rand_btn.pack(side='left', padx=(6, 0))
        self._update_melody_speed_buttons(1.0)

    def _build_sparkle_panel(self, parent):
        BG = '#141428'
        f = section(parent, 'Sparkle')
        f.pack(fill='x', pady=(0, 6))
        block = tk.Frame(f, bg=BG, padx=10, pady=8)
        block.pack(fill='x', pady=3)

        header = tk.Frame(block, bg=BG)
        header.pack(fill='x', pady=(0, 6))
        lvar, _pb = pwr_btn(header, 'SPARKLE', BG, initial=True,
                            fg_on=C_TEXT, fg_off='#555577',
                            command=lambda: self._on_layer('sparkle'))
        self._layer_vars['sparkle'] = lvar
        _pb.pack(side='left')
        tk.Label(header, text='Ch.3', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(6, 0))
        lamp = tk.Label(header, text='●', bg=BG, fg='#2a2a4a',
                        font=('Helvetica', 10))
        lamp.pack(side='left', padx=(5, 0))
        _lamp_fns[2] = lambda on, w=lamp: w.config(fg='#00c896' if on else '#2a2a4a')

        knob_row = tk.Frame(block, bg=BG)
        knob_row.pack()
        _, kv = labeled_knob(knob_row, 'Vel', 1, 127, 28,
                              C_TEXT, BG, lambda v: self._on_vel('sparkle', v))
        kv.master.pack(side='left', padx=10)
        var_f, kvar = labeled_knob(knob_row, 'Variation', 0, 100, 60,
                                    C_VAR, BG, lambda v: self._on_variation('sparkle', v))
        rnd_var_btn = tk.Label(var_f, text='RND', bg=BG, fg='#4a9eff', relief='flat',
                               font=('Helvetica', 6, 'bold'), padx=3, pady=1, cursor='hand2')
        rnd_var_btn.bind('<Button-1>', lambda e: self._on_variation_random('sparkle'))
        rnd_var_btn.pack()
        self._var_rand_btns['sparkle'] = rnd_var_btn
        self._var_knobs['sparkle'] = kvar
        var_f.pack(side='left', padx=10)
        _, krest = labeled_knob(knob_row, 'Rest', 0, 100, 60,
                                 C_REST, BG, lambda v: self._on_rest('sparkle', v))
        krest.master.pack(side='left', padx=10)

        sp_oct_row = tk.Frame(block, bg=BG)
        sp_oct_row.pack(fill='x', pady=(6, 0))
        tk.Label(sp_oct_row, text='Oct', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._sparkle_oct_btns = {}
        for ov in [1, 2, 3, 4, 5]:
            b = tk.Label(sp_oct_row, text=str(ov), width=3,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 9), pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=ov: self._on_sparkle_octave(v))
            b.pack(side='left', padx=1)
            self._sparkle_oct_btns[ov] = b
        self._update_sparkle_oct_buttons(3)

        sp_rng_row = tk.Frame(block, bg=BG)
        sp_rng_row.pack(fill='x', pady=(4, 0))
        tk.Label(sp_rng_row, text='Range', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._sparkle_range_btns = {}
        for rv, rl in [(1, '1oct'), (2, '2oct'), (3, '3oct')]:
            b = tk.Label(sp_rng_row, text=rl,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), padx=6, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=rv: self._on_sparkle_range(v))
            b.pack(side='left', padx=1)
            self._sparkle_range_btns[rv] = b
        self._update_sparkle_range_buttons(1)

    def _build_chord_panel(self, parent):
        C_CHORD = '#7ecfe0'
        BG = '#141428'
        f = section(parent, 'Chord / Arp')
        f.pack(fill='x', pady=(0, 6))
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
        chord_lamp = tk.Label(header, text='●', bg=BG, fg='#2a2a4a',
                              font=('Helvetica', 10))
        chord_lamp.pack(side='left', padx=(5, 0))
        _lamp_fns[3] = lambda on, w=chord_lamp: w.config(fg='#00c896' if on else '#2a2a4a')

        chord_knob_row = tk.Frame(block, bg=BG)
        chord_knob_row.pack(fill='x', pady=(0, 6))
        _, self._chord_vel_knob = labeled_knob(
            chord_knob_row, 'Vel', 1, 127, 55,
            C_CHORD, BG, lambda v: self._on_vel('chord', v))
        self._chord_vel_knob.master.pack(side='left', padx=6)
        _, self._chord_rest_knob = labeled_knob(
            chord_knob_row, 'Rest %', 0, 100, 20,
            C_REST, BG, lambda v: self._on_rest('chord', v))
        self._chord_rest_knob.master.pack(side='left', padx=6)

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

        rate_row = tk.Frame(block, bg=BG)
        rate_row.pack(fill='x', pady=(0, 2))
        tk.Label(rate_row, text='Rate', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 4))
        self._arp_rate_btns = {}
        for label, val in ARP_RATES:
            lbl = tk.Label(rate_row, text=label,
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=val: self._on_arp_rate_btn(v))
            lbl.pack(side='left', padx=1)
            self._arp_rate_btns[val] = lbl
        self._arp_rand_var = tk.BooleanVar(value=False)
        self._arp_rand_btn = tk.Label(rate_row, text='RAND',
                                      bg='#1e1e38', fg='#4a9eff', relief='flat',
                                      font=('Helvetica', 8, 'bold'), padx=6, pady=3,
                                      cursor='hand2')
        self._arp_rand_btn.bind('<Button-1>', lambda e: self._on_arp_rate_random())
        self._arp_rand_btn.pack(side='left', padx=(6, 0))
        self._update_arp_rate_buttons(0.25)

        swing_row = tk.Frame(block, bg=BG)
        swing_row.pack(fill='x', pady=(2, 2))
        tk.Label(swing_row, text='Swing', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._swing_btns = {}
        for lbl_text, val in [('Str', 0.50), ('Soft', 0.58), ('Trip', 0.67), ('Hard', 0.75)]:
            b = tk.Label(swing_row, text=lbl_text,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=val: self._on_arp_swing(v))
            b.pack(side='left', padx=1)
            self._swing_btns[val] = b
        self._update_swing_buttons(0.50)

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
                           font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
            lbl.bind('<Button-1>', lambda e, v=b: self._on_arp_auto_bars(v))
            lbl.pack(side='left', padx=1)
            self._arp_auto_bar_btns[b] = lbl
        tk.Label(auto_row, text='小節', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(2, 0))
        self._update_bar_buttons(self._arp_auto_bar_btns, 4)

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

        restbar_row = tk.Frame(block, bg=BG)
        restbar_row.pack(fill='x', pady=(4, 0))
        tk.Label(restbar_row, text='Rest len', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 4))
        self._chord_rest_bar_btns = {}
        for b in [0, 1, 2, 4, 8, 16]:
            lbl = tk.Label(restbar_row, text='なし' if b == 0 else str(b),
                           bg='#1e1e38', fg='#4a9eff', relief='flat',
                           font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
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

    def _draw_radial_bg(self, mc, cx, cy):
        """凱旋門広場の放射状デコレーションを描画"""
        import math
        W = mc.winfo_width()
        H = mc.winfo_height()
        if W < 10:
            self.root.after(100, lambda: self._draw_radial_bg(mc, cx, cy))
            return
        R = max(W, H)
        # 8本のアベニュー線
        for i in range(8):
            angle = i * math.pi / 4
            ex = cx + math.cos(angle) * R
            ey = cy + math.sin(angle) * R
            mc.create_line(cx, cy, ex, ey,
                           fill='#181830', width=2, tags='bg_deco')
        # 外側の環状道路
        for r, col in [(175, '#212140'), (140, '#1c1c38'), (108, '#191934')]:
            mc.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline=col, width=1, tags='bg_deco')
        # デコレーションを最背面へ
        mc.tag_lower('bg_deco')

    def _build_layers(self, parent):
        f = section(parent, 'Layers')
        f.pack(fill='x', pady=(0, 6))

        layers_cfg = [
            ('drone',   'DRONE',   'Ch.1', 0, 45, 0.20, 0.00),
            ('melody',  'MELODY',  'Ch.2', 1, 38, 0.30, 0.35),
            ('sparkle', 'SPARKLE', 'Ch.3', 2, 28, 0.60, 0.60),
        ]
        self._layer_vars   = {}
        self._var_rand_btns = {}
        self._var_knobs     = {}

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

            var_f, kvar = labeled_knob(knob_row, 'Variation', 0, 100, int(def_var*100),
                                        C_VAR, BG, lambda v, k=key: self._on_variation(k, v))
            rnd_var_btn = tk.Label(var_f, text='RND', bg=BG, fg='#4a9eff', relief='flat',
                                   font=('Helvetica', 6, 'bold'), padx=3, pady=1, cursor='hand2')
            rnd_var_btn.bind('<Button-1>', lambda e, k=key: self._on_variation_random(k))
            rnd_var_btn.pack()
            self._var_rand_btns[key] = rnd_var_btn
            self._var_knobs[key] = kvar
            var_f.pack(side='left', padx=10)

            _, krest = labeled_knob(knob_row, 'Rest', 0, 100, int(def_rest*100),
                                     C_REST, BG, lambda v, k=key: self._on_rest(k, v))
            krest.master.pack(side='left', padx=10)

            # Sparkle: Octave + Range セレクター
            if key == 'sparkle':
                sp_oct_row = tk.Frame(block, bg=BG)
                sp_oct_row.pack(fill='x', pady=(6, 0))
                tk.Label(sp_oct_row, text='Oct', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._sparkle_oct_btns = {}
                _sp_oct_colors = {1:'#a9e4ff', 2:'#4dabf7', 3:'#69db7c', 4:'#ffa94d', 5:'#ff6b6b'}
                for ov in [1, 2, 3, 4, 5]:
                    b = tk.Label(sp_oct_row, text=str(ov), width=3,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 9), pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, v=ov: self._on_sparkle_octave(v))
                    b.pack(side='left', padx=1)
                    self._sparkle_oct_btns[ov] = b
                self._update_sparkle_oct_buttons(3)

                sp_rng_row = tk.Frame(block, bg=BG)
                sp_rng_row.pack(fill='x', pady=(4, 0))
                tk.Label(sp_rng_row, text='Range', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._sparkle_range_btns = {}
                for rv, rl in [(1,'1oct'), (2,'2oct'), (3,'3oct')]:
                    b = tk.Label(sp_rng_row, text=rl,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 8), padx=6, pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, v=rv: self._on_sparkle_range(v))
                    b.pack(side='left', padx=1)
                    self._sparkle_range_btns[rv] = b
                self._update_sparkle_range_buttons(1)

            # Melody のみ Octave / Range / Speed ボタンを追加
            if key == 'melody':
                # Oct ボタン
                oct_row = tk.Frame(block, bg=BG)
                oct_row.pack(fill='x', pady=(6, 0))
                tk.Label(oct_row, text='Oct', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._melody_oct_btns = {}
                _oct_colors = {1: '#a9e4ff', 2: '#4dabf7', 3: '#69db7c', 4: '#ffa94d', 5: '#ff6b6b'}
                for ov in [1, 2, 3, 4, 5]:
                    b = tk.Label(oct_row, text=str(ov), width=3,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 9), pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, v=ov: self._on_melody_octave(v))
                    b.pack(side='left', padx=1)
                    self._melody_oct_btns[ov] = b
                self._update_melody_oct_buttons(1)

                # Range ボタン（音域オクターブ数）
                rng_row = tk.Frame(block, bg=BG)
                rng_row.pack(fill='x', pady=(4, 0))
                tk.Label(rng_row, text='Range', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._melody_range_btns = {}
                _rng_labels = {1: '1oct', 2: '2oct', 3: '3oct'}
                _rng_colors = {1: '#69db7c', 2: '#ffa94d', 3: '#ff6b6b'}
                for rv in [1, 2, 3]:
                    b = tk.Label(rng_row, text=_rng_labels[rv],
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 8), padx=6, pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, v=rv: self._on_melody_range(v))
                    b.pack(side='left', padx=1)
                    self._melody_range_btns[rv] = b
                self._update_melody_range_buttons(1)

                # Character ボタン
                char_row = tk.Frame(block, bg=BG)
                char_row.pack(fill='x', pady=(4, 0))
                tk.Label(char_row, text='Char', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._melody_char_btns = {}
                _char_opts = [
                    ('contour', 'Contour',  '#69db7c'),
                    ('phrase',  'Phrase',   '#4dabf7'),
                    ('motif',   'Motif',    '#ffa94d'),
                    ('chord',   'ChordOnly','#f783ac'),
                    ('simple',  'Simple',   '#a9e34b'),
                ]
                for ckey, clabel, ccol in _char_opts:
                    b = tk.Label(char_row, text=clabel,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 8), padx=6, pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, k=ckey: self._on_melody_character(k))
                    b.pack(side='left', padx=1)
                    self._melody_char_btns[ckey] = (b, ccol)

                # Rhythm ボタン
                rhy_row = tk.Frame(block, bg=BG)
                rhy_row.pack(fill='x', pady=(4, 0))
                tk.Label(rhy_row, text='Rhythm', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._melody_rhythm_btns = {}
                _rhy_opts = [
                    ('free',    'Free',    '#555577'),
                    ('flowing', 'Flowing', '#69db7c'),
                    ('dotted',  'Dotted',  '#4dabf7'),
                    ('synco',   'Synco',   '#ffa94d'),
                    ('staccato','Staccato','#ff6b6b'),
                    ('breath',  'Breath',  '#da77f2'),
                ]
                for rkey, rlabel, rcol in _rhy_opts:
                    b = tk.Label(rhy_row, text=rlabel,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 7), padx=4, pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, k=rkey: self._on_melody_rhythm(k))
                    b.pack(side='left', padx=1)
                    self._melody_rhythm_btns[rkey] = (b, rcol)
                self._update_melody_rhythm_buttons('free')

                # Speed ボタン
                spd_row = tk.Frame(block, bg=BG)
                spd_row.pack(fill='x', pady=(4, 0))
                tk.Label(spd_row, text='Speed', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._melody_speed_btns = {}
                _spd_opts = [('/16', 0.0625), ('/8', 0.125), ('/4', 0.25), ('/2', 0.5), ('×1', 1.0), ('×2', 2.0), ('×4', 4.0)]
                for lbl_text, val in _spd_opts:
                    b = tk.Label(spd_row, text=lbl_text,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, v=val: self._on_melody_speed(v))
                    b.pack(side='left', padx=1)
                    self._melody_speed_btns[val] = b
                self._melody_speed_rand_btn = tk.Label(
                    spd_row, text='RAND', bg='#1e1e38', fg='#4a9eff', relief='flat',
                    font=('Helvetica', 8, 'bold'), padx=6, pady=3, cursor='hand2')
                self._melody_speed_rand_btn.bind('<Button-1>', lambda e: self._on_melody_speed_random())
                self._melody_speed_rand_btn.pack(side='left', padx=(6, 0))
                self._update_melody_speed_buttons(1.0)

            # Drone のみオクターブ選択 + ROOT/CHORD トグルを追加
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

                # ROOT / CHORD 追従トグル
                follow_row = tk.Frame(block, bg=BG)
                follow_row.pack(fill='x', pady=(4, 0))
                tk.Label(follow_row, text='Follow', bg=BG, fg=C_MUTED,
                         font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
                self._drone_follow_btns = {}
                for fkey, flabel in [('root', 'ROOT'), ('chord', 'CHORD')]:
                    b = tk.Label(follow_row, text=flabel, width=6,
                                 bg='#1e1e38', fg='#4a9eff', relief='flat',
                                 font=('Helvetica', 8), pady=3, cursor='hand2')
                    b.bind('<Button-1>', lambda e, k=fkey: self._on_drone_follow(k))
                    b.pack(side='left', padx=1)
                    self._drone_follow_btns[fkey] = b
                self._update_drone_follow_buttons('root')

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

        # Vel + Rest ノブ行
        chord_knob_row = tk.Frame(block, bg=BG)
        chord_knob_row.pack(fill='x', pady=(0, 6))
        _, self._chord_vel_knob = labeled_knob(
            chord_knob_row, 'Vel', 1, 127, 55,
            C_CHORD, BG, lambda v: self._on_vel('chord', v))
        self._chord_vel_knob.master.pack(side='left', padx=6)
        _, self._chord_rest_knob = labeled_knob(
            chord_knob_row, 'Rest %', 0, 100, 20,
            C_REST, BG, lambda v: self._on_rest('chord', v))
        self._chord_rest_knob.master.pack(side='left', padx=6)

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

        # Swing 行
        swing_row = tk.Frame(block, bg=BG)
        swing_row.pack(fill='x', pady=(2, 2))
        tk.Label(swing_row, text='Swing', bg=BG, fg=C_MUTED,
                 font=('Helvetica', 8)).pack(side='left', padx=(0, 6))
        self._swing_btns = {}
        _swing_opts = [('Str', 0.50), ('Soft', 0.58), ('Trip', 0.67), ('Hard', 0.75)]
        for lbl_text, val in _swing_opts:
            b = tk.Label(swing_row, text=lbl_text,
                         bg='#1e1e38', fg='#4a9eff', relief='flat',
                         font=('Helvetica', 8), padx=5, pady=3, cursor='hand2')
            b.bind('<Button-1>', lambda e, v=val: self._on_arp_swing(v))
            b.pack(side='left', padx=1)
            self._swing_btns[val] = b
        self._update_swing_buttons(0.50)

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
            if receiver.start(log_fn=self._log):
                self._clock_receiver = receiver
                self._sync_mode = 'slave'
                self._sync_btn.config(bg='#00b894', fg='#0f0f1e', text='◀ SLAVE')
                self._bpm_knob.color = '#444466'
                self._bpm_knob._draw()
                self._log('--- SYNC: SLAVE (Logic Pro → AMG) ---')
                self._log('※ Logic Pro を再生するとクロックが届きます')
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
        """MIDI クロック受信スレッドから呼ばれる"""
        # STATE はスレッドセーフ → 即時更新（UIスレッド待ちにしない）
        with STATE._lock:
            STATE.bpm = bpm
        # ノブ表示だけ UIスレッド経由
        self.root.after(0, lambda: self._bpm_knob.set(bpm))

    def _on_bpm(self, val):
        if self._clock_receiver is not None:
            return  # SYNC中はノブ操作を無視
        with STATE._lock: STATE.bpm = int(val)

    def _on_tap(self):
        """タップテンポ: 連続タップからBPMを算出してセット"""
        now = time.time()
        # 2秒以上空いたらリセット
        if self._tap_times and (now - self._tap_times[-1]) > 2.0:
            self._tap_times.clear()
        self._tap_times.append(now)
        if len(self._tap_times) > 8:
            self._tap_times.pop(0)
        if len(self._tap_times) >= 2:
            intervals = [self._tap_times[i+1] - self._tap_times[i]
                         for i in range(len(self._tap_times) - 1)]
            avg = sum(intervals) / len(intervals)
            bpm = int(round(60.0 / avg))
            bpm = max(30, min(300, bpm))
            with STATE._lock: STATE.bpm = bpm
            self._bpm_knob.set(bpm)

    def _bpm_blink_tick(self):
        """TAPボタンを現在BPMで赤く点滅させる（常時動作）"""
        bpm = STATE.bpm
        beat_ms = max(100, int(60000 / bpm))
        # 点灯（やわらかい赤で塗りつぶし）
        self._tap_frame.config(bg='#7a2a2a')
        self._tap_label.config(bg='#7a2a2a', fg='#cc8888')
        # 80ms後に消灯
        self.root.after(80, lambda: (
            self._tap_frame.config(bg='#1e1e38'),
            self._tap_label.config(bg='#1e1e38', fg='#aaaacc')
        ))
        # 次の拍でまた点灯
        self.root.after(beat_ms, self._bpm_blink_tick)

    def _on_root(self, semitone):
        if STATE.auto_root:
            # AUTO ON: ピッチクラスをプールにトグル（最低1つ残す）
            pool = list(STATE.auto_root_pool)
            if semitone in pool:
                if len(pool) > 1:
                    pool.remove(semitone)
            else:
                pool.append(semitone)
            with STATE._lock:
                STATE.auto_root_pool = pool
            self._update_root_buttons()
        else:
            new_root = semitone + self._oct_var.get() * 12
            self._root_var.set(new_root)
            with STATE._lock: STATE.root = new_root
            self._update_root_buttons()

    def _on_octave(self):
        new_root = STATE.root % 12 + self._oct_var.get() * 12
        with STATE._lock: STATE.root = new_root

    def _on_random_root(self):
        pool = STATE.auto_root_pool
        if pool:
            pc = random.choice(pool)
            base_oct = STATE.root // 12
            new_root = pc + base_oct * 12
            if new_root < 36: new_root += 12
            if new_root > 60: new_root -= 12
        else:
            new_root = random.choice(list(range(36, 61)))
        with STATE._lock: STATE.root = new_root
        self._update_root_buttons()
        self._log(f"[Root] → {NOTE_NAMES[new_root % 12]}{new_root//12-1}")

    def _on_auto_root(self):
        on = self._auto_root_var.get()
        with STATE._lock: STATE.auto_root = on
        # RDN ボタンをアクティブ時に赤く光らせる
        if on:
            self._rdn_btn.config(bg='#5a0000', fg='#ff4444')
        else:
            self._rdn_btn.config(bg='#2a2a4a', fg='#666688')
        # ボタン表示をプール/範囲モードに切り替え
        self._update_root_buttons()
        if on:
            self._update_bar_range_buttons(
                self._root_bar_btns, BAR_OPTIONS,
                STATE.auto_root_bars_min, STATE.auto_root_bars_max)
        else:
            self._update_bar_buttons(self._root_bar_btns, STATE.auto_root_bars)

    def _on_root_bars(self, val):
        if STATE.auto_root:
            # AUTO ON: 範囲の下限/上限をインデックス距離で振り分け
            all_v = BAR_OPTIONS
            idx_v  = all_v.index(val)
            idx_lo = all_v.index(STATE.auto_root_bars_min) if STATE.auto_root_bars_min in all_v else 0
            idx_hi = all_v.index(STATE.auto_root_bars_max) if STATE.auto_root_bars_max in all_v else len(all_v)-1
            with STATE._lock:
                if abs(idx_v - idx_lo) <= abs(idx_v - idx_hi):
                    STATE.auto_root_bars_min = val
                else:
                    STATE.auto_root_bars_max = val
                if STATE.auto_root_bars_min > STATE.auto_root_bars_max:
                    STATE.auto_root_bars_min, STATE.auto_root_bars_max = \
                        STATE.auto_root_bars_max, STATE.auto_root_bars_min
            self._update_bar_range_buttons(
                self._root_bar_btns, BAR_OPTIONS,
                STATE.auto_root_bars_min, STATE.auto_root_bars_max)
        else:
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

    def _update_bar_range_buttons(self, btns, all_opts, lo, hi):
        """AUTO ON時: 範囲内は色付き、範囲外はくすんだ表示"""
        colors = {0: '#aaaaaa', 1: '#ff6b6b', 2: '#ffa94d', 4: '#ffe066',
                  8: '#69db7c', 16: '#4dabf7', 32: '#cc5de8', 64: '#f783ac'}
        for b, btn in btns.items():
            in_range = (lo <= b <= hi)
            is_edge  = (b == lo or b == hi)
            if is_edge:
                btn.config(bg=colors.get(b, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 9, 'bold'))
            elif in_range:
                btn.config(bg='#2a2a3a', fg=colors.get(b, '#aaaacc'),
                           font=('Helvetica', 8))
            else:
                btn.config(bg='#1e1e38', fg='#333355',
                           font=('Helvetica', 8))

    def _on_scale(self, _=None):
        with STATE._lock: STATE.scale_name = self._scale_var.get()

    def _on_auto_scale(self):
        with STATE._lock: STATE.auto_scale = self._auto_scale_var.get()

    def _on_density(self):
        with STATE._lock: STATE.density = self._density_var.get()

    def _on_evolve_toggle(self):
        v = not self._evolve_var.get()
        self._evolve_var.set(v)
        with STATE._lock: STATE.auto_evolve = v
        if v:
            self._evolve_btn.config(bg='#0f1f3a', fg=C_EVO)
        else:
            self._evolve_btn.config(bg='#111128', fg='#334466')

    def _on_kaoss(self, x, y):
        # x = Speed (0-1), y = Depth (0-1)
        with STATE._lock:
            STATE.evolve_speed = x
            STATE.evolve_depth = y

    def _on_mod_wheel(self, val):
        v = int(val)
        # 表示を更新
        if hasattr(self, '_mod_val_lbl'):
            self._mod_val_lbl.config(text=str(v))
        # CC#1 を全チャンネル（0-3）へ送信
        try:
            midi = get_midi()
            for ch in range(4):
                midi.send_message([0xB0 | ch, 1, v])
        except Exception:
            pass

    def _on_auto_mod_toggle(self):
        v = not self._auto_mod_var.get()
        self._auto_mod_var.set(v)
        if v:
            self._auto_mod_btn.config(bg='#1a1a2e', fg='#ff9966')
            speed = self._am_speed_knob.get() / 100.0
            self._kaoss_pad.set_am_speed(speed)
            self._kaoss_pad.auto_mod_start()
        else:
            self._auto_mod_btn.config(bg='#111128', fg='#445566')
            self._kaoss_pad.auto_mod_stop()

    def _on_am_speed(self, val):
        self._kaoss_pad.set_am_speed(float(val) / 100.0)

    def _on_am_mode(self, key):
        self._kaoss_pad.set_am_mode(key)
        self._update_am_mode_buttons(key)

    def _update_am_mode_buttons(self, selected):
        for k, btn in self._am_mode_btns.items():
            if k == selected:
                btn.config(bg='#2a2a5a', fg='#ff9966')
            else:
                btn.config(bg='#1e1e38', fg='#445566')

    def _on_sat_type(self, key):
        self._kaoss_pad.set_sat_type(key)
        self._update_sat_type_buttons(key)

    def _update_sat_type_buttons(self, selected):
        for k, btn in self._sat_type_btns.items():
            if k == selected:
                btn.config(bg='#2a2a5a', fg='#9b8cf0')
            else:
                btn.config(bg='#1e1e38', fg='#445566')

    def _on_layer(self, key):
        with STATE._lock: STATE.layers[key] = self._layer_vars[key].get()

    def _on_vel(self, key, val):
        with STATE._lock: STATE.vel[key] = int(val)

    def _on_variation(self, key, val):
        with STATE._lock: STATE.variation[key] = int(val) / 100.0

    def _on_variation_random(self, key):
        new_val = not STATE.variation_random[key]
        with STATE._lock: STATE.variation_random[key] = new_val
        btn = self._var_rand_btns.get(key)
        if btn:
            if new_val:
                btn.config(bg='#da77f2', fg='#0f0f1e')
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff')

    def _auto_variation_tick(self):
        if not self._playing:
            return
        s = STATE.get()
        beat_ms = max(200, int(60000 / s['bpm']))
        # 4〜8拍ごとにランダム更新
        interval_ms = random.randint(4, 8) * beat_ms
        for key in ['drone', 'melody', 'sparkle', 'chord']:
            if s['variation_random'].get(key):
                new_var = round(random.random(), 2)
                with STATE._lock: STATE.variation[key] = new_var
                knob = self._var_knobs.get(key)
                if knob:
                    self.root.after(0, lambda k=knob, v=new_var: k.set(int(v * 100)))
        self.root.after(interval_ms, self._auto_variation_tick)

    def _on_rest(self, key, val):
        with STATE._lock: STATE.rest_prob[key] = int(val) / 100.0

    def _on_arp_on(self):
        with STATE._lock: STATE.arp_on = self._arp_var.get()

    def _on_arp_mode(self, _=None):
        with STATE._lock: STATE.arp_mode = self._arp_mode_var.get()

    _ARP_RATE_VALS = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0]

    def _on_arp_rate_btn(self, val):
        if STATE.arp_rate_random:
            # RAND ON: インデックス距離で近い方の境界を更新
            with STATE._lock:
                lo, hi    = STATE.arp_rate_rand_min, STATE.arp_rate_rand_max
                all_v     = self._ARP_RATE_VALS
                idx_v     = all_v.index(val)
                idx_lo    = all_v.index(lo) if lo in all_v else 0
                idx_hi    = all_v.index(hi) if hi in all_v else len(all_v) - 1
                if abs(idx_v - idx_lo) < abs(idx_v - idx_hi):
                    STATE.arp_rate_rand_min = val
                else:
                    STATE.arp_rate_rand_max = val
                if STATE.arp_rate_rand_min > STATE.arp_rate_rand_max:
                    STATE.arp_rate_rand_min, STATE.arp_rate_rand_max = \
                        STATE.arp_rate_rand_max, STATE.arp_rate_rand_min
        else:
            with STATE._lock:
                STATE.arp_rate        = val
                STATE.arp_rate_random = False
            self._arp_rand_var.set(False)
        self._update_arp_rate_buttons(STATE.arp_rate)

    def _on_arp_rate_random(self):
        new_state = not self._arp_rand_var.get()
        self._arp_rand_var.set(new_state)
        with STATE._lock: STATE.arp_rate_random = new_state
        self._update_arp_rate_buttons(STATE.arp_rate)

    def _update_arp_rate_buttons(self, selected):
        rand_on = self._arp_rand_var.get() if hasattr(self, '_arp_rand_var') else False
        lo = STATE.arp_rate_rand_min
        hi = STATE.arp_rate_rand_max
        for val, btn in self._arp_rate_btns.items():
            col = ARP_RATE_COLORS.get(val, '#69db7c')
            if rand_on:
                in_range = lo - 0.001 <= val <= hi + 0.001
                is_edge  = abs(val - lo) < 0.001 or abs(val - hi) < 0.001
                if in_range and is_edge:
                    btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
                elif in_range:
                    btn.config(bg='#2a2a3a', fg=col,  font=('Helvetica', 8))
                else:
                    btn.config(bg='#1e1e38', fg='#333355', font=('Helvetica', 8))
            else:
                if val == selected:
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

    def _on_arp_swing(self, val):
        with STATE._lock: STATE.arp_swing = val
        self._update_swing_buttons(val)

    def _update_swing_buttons(self, selected):
        colors = {0.50: '#a9e4ff', 0.58: '#69db7c', 0.67: '#ffd166', 0.75: '#ff6b6b'}
        for val, btn in self._swing_btns.items():
            if abs(val - selected) < 0.01:
                btn.config(bg=colors.get(val, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 8, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))

    _SPEED_VALS = [0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]

    def _on_melody_speed(self, val):
        if STATE.melody_speed_random:
            # RAND ON のとき: インデックス距離で近い方の境界を更新
            with STATE._lock:
                lo, hi = STATE.melody_speed_rand_min, STATE.melody_speed_rand_max
                all_v  = self._SPEED_VALS
                idx_v  = all_v.index(val)
                idx_lo = all_v.index(lo) if lo in all_v else 0
                idx_hi = all_v.index(hi) if hi in all_v else len(all_v) - 1
                # インデックス距離が等しい場合は上限（hi）側を優先
                if abs(idx_v - idx_lo) < abs(idx_v - idx_hi):
                    STATE.melody_speed_rand_min = val
                else:
                    STATE.melody_speed_rand_max = val
                # 逆転を防ぐ
                if STATE.melody_speed_rand_min > STATE.melody_speed_rand_max:
                    STATE.melody_speed_rand_min, STATE.melody_speed_rand_max = \
                        STATE.melody_speed_rand_max, STATE.melody_speed_rand_min
        else:
            with STATE._lock:
                STATE.melody_speed = val
        self._update_melody_speed_buttons(STATE.melody_speed)

    def _on_melody_speed_random(self):
        new_state = not STATE.melody_speed_random
        with STATE._lock: STATE.melody_speed_random = new_state
        self._update_melody_speed_buttons(STATE.melody_speed)
        if new_state:
            self._auto_melody_speed_tick()

    def _auto_melody_speed_tick(self):
        """Speed を範囲内でランダムに自動切り替え（2〜8小節ごと）"""
        if not self._playing:
            return
        if not STATE.melody_speed_random:
            return
        _all = [0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
        lo, hi = STATE.melody_speed_rand_min, STATE.melody_speed_rand_max
        pool = [v for v in _all if lo - 0.001 <= v <= hi + 0.001]
        if pool:
            new_speed = random.choice(pool)
            with STATE._lock: STATE.melody_speed = new_speed
            self._update_melody_speed_buttons(new_speed)
        bars = random.choice([2, 2, 4, 4, 4, 8])
        self.root.after(bars_to_ms(bars, STATE.bpm), self._auto_melody_speed_tick)

    def _update_melody_speed_buttons(self, selected):
        colors = {0.0625: '#ff4444', 0.125: '#ff6b6b', 0.25: '#ffa94d',
                  0.5: '#ffd166', 1.0: '#69db7c', 2.0: '#4dabf7', 4.0: '#748ffc'}
        rand_on = STATE.melody_speed_random
        lo = STATE.melody_speed_rand_min
        hi = STATE.melody_speed_rand_max
        for val, btn in self._melody_speed_btns.items():
            in_range = rand_on and (lo - 0.001 <= val <= hi + 0.001)
            is_sel   = abs(val - selected) < 0.001
            if rand_on:
                if in_range:
                    # 範囲内: 端点は濃く、中間は薄く
                    is_edge = abs(val - lo) < 0.001 or abs(val - hi) < 0.001
                    if is_edge:
                        btn.config(bg=colors.get(val, C_ON), fg='#0f0f1e',
                                   font=('Helvetica', 8, 'bold'))
                    else:
                        # 中間ノード: 少し暗い色で範囲を示す
                        btn.config(bg='#2a3a2a', fg='#88cc88',
                                   font=('Helvetica', 8))
                else:
                    btn.config(bg='#1e1e38', fg='#333355', font=('Helvetica', 8))
            else:
                if is_sel:
                    btn.config(bg=colors.get(val, C_ON), fg='#0f0f1e',
                               font=('Helvetica', 8, 'bold'))
                else:
                    btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))
        # RAND ボタン
        if hasattr(self, '_melody_speed_rand_btn'):
            if rand_on:
                self._melody_speed_rand_btn.config(bg='#da77f2', fg='#0f0f1e',
                                                   font=('Helvetica', 8, 'bold'))
            else:
                self._melody_speed_rand_btn.config(bg='#1e1e38', fg='#4a9eff',
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

    def _on_melody_octave(self, val):
        with STATE._lock: STATE.melody_octave = val
        self._update_melody_oct_buttons(val)

    def _update_melody_oct_buttons(self, selected):
        colors = {1: '#a9e4ff', 2: '#4dabf7', 3: '#69db7c', 4: '#ffa94d', 5: '#ff6b6b'}
        for ov, btn in self._melody_oct_btns.items():
            if ov == selected:
                btn.config(bg=colors.get(ov, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 9, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff',
                           font=('Helvetica', 9))

    def _on_melody_range(self, val):
        with STATE._lock: STATE.melody_range = val
        self._update_melody_range_buttons(val)

    def _update_melody_range_buttons(self, selected):
        colors = {1: '#69db7c', 2: '#ffa94d', 3: '#ff6b6b'}
        for rv, btn in self._melody_range_btns.items():
            if rv == selected:
                btn.config(bg=colors.get(rv, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 8, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff',
                           font=('Helvetica', 8))

    def _on_sparkle_octave(self, val):
        with STATE._lock: STATE.sparkle_octave = val
        self._update_sparkle_oct_buttons(val)

    def _update_sparkle_oct_buttons(self, selected):
        colors = {1:'#a9e4ff', 2:'#4dabf7', 3:'#69db7c', 4:'#ffa94d', 5:'#ff6b6b'}
        for ov, btn in self._sparkle_oct_btns.items():
            if ov == selected:
                btn.config(bg=colors.get(ov, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 9, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff',
                           font=('Helvetica', 9))

    def _on_sparkle_range(self, val):
        with STATE._lock: STATE.sparkle_range = val
        self._update_sparkle_range_buttons(val)

    def _update_sparkle_range_buttons(self, selected):
        colors = {1:'#69db7c', 2:'#ffa94d', 3:'#ff6b6b'}
        for rv, btn in self._sparkle_range_btns.items():
            if rv == selected:
                btn.config(bg=colors.get(rv, C_ON), fg='#0f0f1e',
                           font=('Helvetica', 8, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff',
                           font=('Helvetica', 8))

    def _on_melody_rhythm(self, key):
        with STATE._lock: STATE.melody_rhythm = key
        self._update_melody_rhythm_buttons(key)

    def _update_melody_rhythm_buttons(self, selected):
        for key, (btn, col) in self._melody_rhythm_btns.items():
            if key == selected:
                btn.config(bg=col if col != '#555577' else '#3a3a5a',
                           fg='#0f0f1e' if col != '#555577' else '#aaaacc',
                           font=('Helvetica', 7, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 7))

    def _on_melody_character(self, key):
        chars = list(STATE.melody_character)
        if key in chars:
            chars.remove(key)
        else:
            chars.append(key)
        with STATE._lock: STATE.melody_character = chars
        self._update_melody_char_buttons(chars)

    def _update_melody_char_buttons(self, chars):
        for key, (btn, col) in self._melody_char_btns.items():
            if key in chars:
                btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 8, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))

    def _on_drone_follow(self, key):
        with STATE._lock: STATE.drone_follow = key
        self._update_drone_follow_buttons(key)

    def _update_drone_follow_buttons(self, selected):
        colors = {'root': '#69db7c', 'chord': '#4dabf7'}
        for key, btn in self._drone_follow_btns.items():
            if key == selected:
                btn.config(bg=colors[key], fg='#0f0f1e', font=('Helvetica', 8, 'bold'))
            else:
                btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 8))

    def _on_chord_octave(self):
        with STATE._lock: STATE.chord_octave = self._chord_oct_var.get()

    def _on_chord_oct_range(self):
        with STATE._lock: STATE.chord_oct_range = self._chord_oct_range_var.get()

    def _on_chord_degree(self, semitone):
        if STATE.chord_auto:
            # AUTO ON: プールをトグル（最低1つは残す）
            pool = list(STATE.chord_auto_degrees_pool)
            if semitone in pool:
                if len(pool) > 1:
                    pool.remove(semitone)
            else:
                pool.append(semitone)
            with STATE._lock:
                STATE.chord_auto_degrees_pool = pool
            self._update_chord_degree_buttons(STATE.chord_degree)
        else:
            with STATE._lock: STATE.chord_degree = semitone
            self._update_chord_degree_buttons(semitone)
            deg_lbl  = next((l for l, s in CHORD_DEGREES if s == semitone), str(semitone))
            qual_lbl = next((l for l, ivs in CHORD_QUALITIES if ivs == STATE.chord_quality), '')
            self._log(f"[Chord] → {deg_lbl}{qual_lbl}")

    def _on_chord_quality(self, ivs, key):
        if STATE.chord_auto:
            # AUTO ON: プールをトグル（最低1つは残す）
            pool = list(STATE.chord_auto_qualities_pool)
            if key in pool:
                if len(pool) > 1:
                    pool.remove(key)
            else:
                pool.append(key)
            with STATE._lock:
                STATE.chord_auto_qualities_pool = pool
            qual_key = next((k for k, _, _ in self._chord_quality_btns.values()
                             if False), 'maj')  # dummy; use current
            self._update_chord_quality_buttons(
                next((l for l, q in CHORD_QUALITIES if q == STATE.chord_quality), 'maj'))
        else:
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
        # ボタン表示をモード切替に合わせて更新
        cur_deg_lbl = next((l for l, s in CHORD_DEGREES if s == STATE.chord_degree), 'Ⅰ')
        cur_qual_lbl = next((l for l, ivs in CHORD_QUALITIES if ivs == STATE.chord_quality), 'maj')
        self._update_chord_degree_buttons(STATE.chord_degree)
        self._update_chord_quality_buttons(cur_qual_lbl)
        _CHORD_BAR_OPTS = [2, 4, 8, 16]
        if new:
            self._update_bar_range_buttons(
                self._chord_auto_bar_btns, _CHORD_BAR_OPTS,
                STATE.chord_auto_bars_min, STATE.chord_auto_bars_max)
        else:
            self._update_bar_buttons(self._chord_auto_bar_btns, STATE.chord_auto_bars)

    def _on_chord_auto_bars(self, val):
        _CHORD_BAR_OPTS = [2, 4, 8, 16]
        if STATE.chord_auto:
            idx_v  = _CHORD_BAR_OPTS.index(val)
            idx_lo = _CHORD_BAR_OPTS.index(STATE.chord_auto_bars_min) \
                     if STATE.chord_auto_bars_min in _CHORD_BAR_OPTS else 0
            idx_hi = _CHORD_BAR_OPTS.index(STATE.chord_auto_bars_max) \
                     if STATE.chord_auto_bars_max in _CHORD_BAR_OPTS else len(_CHORD_BAR_OPTS)-1
            with STATE._lock:
                if abs(idx_v - idx_lo) <= abs(idx_v - idx_hi):
                    STATE.chord_auto_bars_min = val
                else:
                    STATE.chord_auto_bars_max = val
                if STATE.chord_auto_bars_min > STATE.chord_auto_bars_max:
                    STATE.chord_auto_bars_min, STATE.chord_auto_bars_max = \
                        STATE.chord_auto_bars_max, STATE.chord_auto_bars_min
            self._update_bar_range_buttons(
                self._chord_auto_bar_btns, _CHORD_BAR_OPTS,
                STATE.chord_auto_bars_min, STATE.chord_auto_bars_max)
        else:
            with STATE._lock: STATE.chord_auto_bars = val
            self._update_bar_buttons(self._chord_auto_bar_btns, val)

    def _update_chord_degree_buttons(self, selected):
        auto_on  = STATE.chord_auto
        pool     = STATE.chord_auto_degrees_pool
        for semitone, (btn, col) in self._chord_degree_btns.items():
            if auto_on:
                in_pool = semitone in pool
                is_cur  = semitone == selected
                if in_pool and is_cur:
                    btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
                elif in_pool:
                    btn.config(bg='#2a2a3a', fg=col, font=('Helvetica', 9))
                else:
                    btn.config(bg='#1e1e38', fg='#333355', font=('Helvetica', 9))
            else:
                if semitone == selected:
                    btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
                else:
                    btn.config(bg='#1e1e38', fg='#4a9eff', font=('Helvetica', 9))

    def _update_chord_quality_buttons(self, selected_key):
        auto_on = STATE.chord_auto
        pool    = STATE.chord_auto_qualities_pool
        for key, (btn, col, ivs) in self._chord_quality_btns.items():
            if auto_on:
                in_pool = key in pool
                is_cur  = key == selected_key
                if in_pool and is_cur:
                    btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 8, 'bold'))
                elif in_pool:
                    btn.config(bg='#2a2a3a', fg=col, font=('Helvetica', 8))
                else:
                    btn.config(bg='#1e1e38', fg='#333355', font=('Helvetica', 8))
            else:
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
            new_oct   = random.choice([1, 2, 3])
            new_range = random.choice([1, 2, 3])
            # レートは RAND が OFF の時だけ変更（ON の時は RAND 設定を維持）
            lo, hi    = s['arp_rate_rand_min'], s['arp_rate_rand_max']
            rate_pool = [v for _, v in ARP_RATES if lo - 0.001 <= v <= hi + 0.001]
            new_rate  = random.choice(rate_pool if rate_pool else [v for _, v in ARP_RATES])
            with STATE._lock:
                STATE.arp_mode        = new_mode
                STATE.chord_octave    = new_oct
                STATE.chord_oct_range = new_range
                if not STATE.arp_rate_random:
                    # RAND OFF の時だけ固定レートを変更
                    STATE.arp_rate = new_rate
            # UI 同期（RAND ボタンの状態は変えない）
            self._arp_mode_var.set(new_mode)
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
        root         = STATE.root
        auto_on      = STATE.auto_root
        pool         = STATE.auto_root_pool
        current_name = NOTE_NAMES[root % 12]
        octave       = root // 12 - 1
        for name, btn in self._note_btns.items():
            is_sharp = '#' in name
            idx = NOTE_NAMES.index(name)
            col = self.NOTE_COLORS.get(name, C_ACCENT)
            if auto_on:
                in_pool = idx in pool
                is_cur  = name == current_name
                if in_pool and is_cur:
                    btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
                elif in_pool:
                    btn.config(bg='#2a2a3a', fg=col, font=('Helvetica', 8, 'normal'))
                else:
                    btn.config(bg='#1e1e38' if is_sharp else '#1e2030',
                               fg='#333355', font=('Helvetica', 8, 'normal'))
            else:
                if name == current_name:
                    btn.config(bg=col, fg='#0f0f1e', font=('Helvetica', 9, 'bold'))
                else:
                    btn.config(bg='#1e1e38' if is_sharp else '#1e2030',
                               fg='#4a9eff', font=('Helvetica', 8, 'normal'))
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
        """コード度数+クオリティをプール内からランダムに自動切り替え"""
        if not self._playing:
            return
        s = STATE.get()
        if s['chord_auto']:
            # プール内の候補に絞ってランダム選択
            deg_pool  = [(l, st) for l, st in CHORD_DEGREES
                         if st in s['chord_auto_degrees_pool']]
            qual_pool = [(l, ivs) for l, ivs in CHORD_QUALITIES
                         if l in s['chord_auto_qualities_pool']]
            if not deg_pool:  deg_pool  = list(CHORD_DEGREES)
            if not qual_pool: qual_pool = list(CHORD_QUALITIES)
            new_deg_lbl,  new_deg  = random.choice(deg_pool)
            new_qual_lbl, new_qual = random.choice(qual_pool)
            with STATE._lock:
                STATE.chord_degree  = new_deg
                STATE.chord_quality = new_qual
            self._update_chord_degree_buttons(new_deg)
            self._update_chord_quality_buttons(new_qual_lbl)
            _CHORD_BAR_OPTS = [2, 4, 8, 16]
            lo, hi = s['chord_auto_bars_min'], s['chord_auto_bars_max']
            bar_pool = [b for b in _CHORD_BAR_OPTS if lo <= b <= hi] or _CHORD_BAR_OPTS
            next_bars = random.choice(bar_pool)
            with STATE._lock: STATE.chord_auto_bars = next_bars
            self._update_bar_range_buttons(self._chord_auto_bar_btns, _CHORD_BAR_OPTS, lo, hi)
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
        self.root.after(500, self._auto_melody_speed_tick)
        self.root.after(500, self._auto_variation_tick)

    def _auto_root_tick(self):
        if not self._playing:
            return
        s = STATE.get()
        if s['auto_root']:
            pool = s['auto_root_pool']
            # プールから音名を選び、現在のオクターブ帯（36〜60）に収める
            pc = random.choice(pool)
            base_oct = (STATE.root // 12)   # 現在のオクターブを維持
            new_root = pc + base_oct * 12
            # 36〜60 の範囲に収まるよう調整
            if new_root < 36: new_root += 12
            if new_root > 60: new_root -= 12
            with STATE._lock: STATE.root = new_root
            name = NOTE_NAMES[new_root % 12]
            # 次の小節数を範囲内からランダム選択
            lo, hi = s['auto_root_bars_min'], s['auto_root_bars_max']
            bar_pool = [b for b in BAR_OPTIONS if lo <= b <= hi] or BAR_OPTIONS
            next_bars = random.choice(bar_pool)
            with STATE._lock: STATE.auto_root_bars = next_bars
            self._update_bar_range_buttons(self._root_bar_btns, BAR_OPTIONS, lo, hi)
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
