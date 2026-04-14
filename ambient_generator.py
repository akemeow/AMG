#!/usr/bin/env python3
"""
Ambient MIDI Generator — Evolving Version
3レイヤー + ランダム展開

Layer 1 (Ch.1) : ドローン    — 持続する低音
Layer 2 (Ch.2) : メロディ    — ゆっくり浮遊する音
Layer 3 (Ch.3) : スパークル  — 高音域の散発的アクセント

展開要素:
  - ルート音の転調 (30〜90秒ごと)
  - スケール切り替え
  - 密度フェーズ (sparse / normal / dense)
  - ダイナミクス波 (全体の音量が緩やかに変化)
"""

import rtmidi
import time
import random
import threading
import math

# ==================== スケール ====================
SCALES = {
    'lydian':           [0, 2, 4, 6, 7, 9, 11],
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'phrygian':         [0, 1, 3, 5, 7, 8, 10],
    'major':            [0, 2, 4, 5, 7, 9, 11],
}

# 転調で移動しやすい音程（5度圏など）
MODULATION_INTERVALS = [-5, -2, 2, 5, 7]

# ==================== グローバルステート ====================
class GlobalState:
    def __init__(self):
        self.lock = threading.Lock()
        self.root = 48              # C3
        self.scale_name = 'lydian'
        self.bpm = 52
        self.density = 'normal'     # sparse / normal / dense
        self.dynamic = 1.0          # 0.3 〜 1.0 (全体音量係数)
        self.running = True

    def get(self):
        with self.lock:
            return (self.root, self.scale_name, self.bpm,
                    self.density, self.dynamic)

    def set_root(self, v):
        with self.lock: self.root = v

    def set_scale(self, v):
        with self.lock: self.scale_name = v

    def set_density(self, v):
        with self.lock: self.density = v

    def set_dynamic(self, v):
        with self.lock: self.dynamic = max(0.2, min(1.0, v))

STATE = GlobalState()

# ==================== 展開コントローラー ====================
class EvolutionController:
    """バックグラウンドでパラメータをランダムに変化させる"""

    DENSITY_REST = {
        'sparse': 0.55,
        'normal': 0.30,
        'dense':  0.10,
    }

    def __init__(self):
        self.dynamic_phase = 0.0   # sin波の位相

    def _loop(self):
        next_modulation = time.time() + random.uniform(30, 60)
        next_scale_change = time.time() + random.uniform(45, 90)
        next_density_change = time.time() + random.uniform(20, 50)
        dynamic_speed = random.uniform(0.003, 0.008)

        while STATE.running:
            now = time.time()

            # ダイナミクス波（sin波でゆっくり変化）
            self.dynamic_phase += dynamic_speed
            dyn = 0.6 + 0.35 * math.sin(self.dynamic_phase)
            STATE.set_dynamic(dyn)

            # 転調
            if now >= next_modulation:
                root, scale, *_ = STATE.get()
                interval = random.choice(MODULATION_INTERVALS)
                new_root = root + interval
                new_root = max(36, min(60, new_root))  # C2〜C4の範囲
                STATE.set_root(new_root)
                print(f"\n  [展開] 転調: {root} → {new_root} (+{interval})")
                next_modulation = now + random.uniform(30, 90)

            # スケール切り替え
            if now >= next_scale_change:
                _, current_scale, *_ = STATE.get()
                candidates = [s for s in SCALES if s != current_scale]
                new_scale = random.choice(candidates)
                STATE.set_scale(new_scale)
                print(f"\n  [展開] スケール: {current_scale} → {new_scale}")
                next_scale_change = now + random.uniform(45, 120)

            # 密度フェーズ
            if now >= next_density_change:
                _, _, _, current_density, _ = STATE.get()
                candidates = [d for d in ['sparse', 'normal', 'dense']
                              if d != current_density]
                new_density = random.choice(candidates)
                STATE.set_density(new_density)
                print(f"\n  [展開] 密度: {current_density} → {new_density}")
                next_density_change = now + random.uniform(20, 60)

            time.sleep(0.1)

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

# ==================== Markov ====================
def build_matrix(scale_len):
    matrix = []
    for i in range(scale_len):
        row = []
        for j in range(scale_len):
            dist = abs(i - j)
            if dist == 0:   w = 0.5
            elif dist == 1: w = 5.0
            elif dist == 2: w = 3.0
            elif dist == 3: w = 1.5
            elif dist == 4: w = 0.7
            else:           w = 0.2
            row.append(w)
        total = sum(row)
        matrix.append([w / total for w in row])
    return matrix

def next_degree(current, matrix):
    r = random.random()
    c = 0.0
    for i, w in enumerate(matrix[current]):
        c += w
        if r < c:
            return i
    return len(matrix) - 1

def weighted_choice(d):
    keys, weights = list(d.keys()), list(d.values())
    total = sum(weights)
    r = random.uniform(0, total)
    c = 0.0
    for k, w in zip(keys, weights):
        c += w
        if r < c:
            return k
    return keys[-1]

# ==================== MIDI接続 ====================
def connect_midi():
    midiout = rtmidi.MidiOut()
    ports = midiout.get_ports()
    if not ports:
        print("エラー: MIDIポートが見つかりません")
        raise SystemExit(1)
    iac = next((i for i, p in enumerate(ports) if 'IAC' in p), 0)
    midiout.open_port(iac)
    print(f"[接続] {ports[iac]}")
    return midiout

# ==================== ドローンレイヤー ====================
class DroneLayer:
    def __init__(self, midiout):
        self.out = midiout
        self.ch = 0
        self.running = False
        self.active = []

    def _on(self, note, vel):
        self.out.send_message([0x90 | self.ch, note, max(1, min(127, vel))])

    def _off(self, note):
        self.out.send_message([0x80 | self.ch, note, 0])

    def _all_off(self):
        for n in self.active: self._off(n)
        self.active.clear()

    def _loop(self):
        last_root = None
        while self.running:
            root, _, bpm, _, dynamic = STATE.get()
            beat = 60.0 / bpm

            if root != last_root:
                self._all_off()
                last_root = root

            self._all_off()
            notes = [root, root + 7]   # ルート + 5度
            vel = int(45 * dynamic)
            self.active = notes[:]
            for n in notes:
                if 0 <= n <= 127:
                    self._on(n, vel)
            print(f"  [Drone ] {notes}  vel={vel}")
            time.sleep(16 * beat)

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        self._all_off()

# ==================== メロディ / スパークルレイヤー ====================
class MelodyLayer:
    DENSITY_REST = {
        'sparse': 0.55,
        'normal': 0.30,
        'dense':  0.10,
    }
    DENSITY_DUR = {
        'sparse': {4.0: 2, 6.0: 3, 8.0: 2},
        'normal': {2.0: 2, 4.0: 4, 6.0: 2},
        'dense':  {1.0: 2, 2.0: 4, 4.0: 2},
    }

    def __init__(self, midiout, channel, octave, vel_base, gate, label):
        self.out = midiout
        self.ch = channel
        self.octave = octave
        self.vel_base = vel_base
        self.gate = gate
        self.label = label
        self.running = False
        self._degree = 0
        self._cur_scale = None
        self._matrix = None
        self._notes = []

    def _rebuild(self, root, scale_name):
        intervals = SCALES[scale_name]
        self._notes = [root + self.octave * 12 + iv for iv in intervals
                       if 0 <= root + self.octave * 12 + iv <= 127]
        self._matrix = build_matrix(len(intervals))
        self._degree = min(self._degree, len(intervals) - 1)
        self._cur_scale = scale_name

    def _on(self, note, vel):
        self.out.send_message([0x90 | self.ch, note, max(1, min(127, vel))])

    def _off(self, note):
        self.out.send_message([0x80 | self.ch, note, 0])

    def _all_off(self):
        self.out.send_message([0xB0 | self.ch, 123, 0])

    def _loop(self):
        while self.running:
            root, scale_name, bpm, density, dynamic = STATE.get()
            beat = 60.0 / bpm

            if scale_name != self._cur_scale or not self._notes:
                self._rebuild(root, scale_name)

            self._degree = next_degree(self._degree, self._matrix)
            if self._degree >= len(self._notes):
                self._degree = 0
            note = self._notes[self._degree]

            dur_beats = weighted_choice(self.DENSITY_DUR[density])
            dur_sec = dur_beats * beat

            vel = int((self.vel_base + random.randint(-15, 15)) * dynamic)

            rest_prob = self.DENSITY_REST[density]
            if random.random() < rest_prob:
                time.sleep(dur_sec)
                continue

            print(f"  [{self.label}] note={note} vel={vel} ({dur_beats}拍)")
            self._on(note, vel)
            time.sleep(dur_sec * self.gate)
            self._off(note)
            time.sleep(dur_sec * (1.0 - self.gate))

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        self._all_off()

# ==================== メイン ====================
def main():
    print("=" * 50)
    print("  Ambient MIDI Generator  [Evolving]")
    print("=" * 50)
    print(f"  BPM: {STATE.bpm}  Root: {STATE.root}  Scale: {STATE.scale_name}")
    print()
    print("  Ch.1 → ドローン   (パッド・低音)")
    print("  Ch.2 → メロディ   (パッド・中音)")
    print("  Ch.3 → スパークル (ベル・高音)")
    print()

    midiout = connect_midi()

    drone   = DroneLayer  (midiout)
    melody  = MelodyLayer (midiout, channel=1, octave=1, vel_base=38, gate=0.75, label="Melody ")
    sparkle = MelodyLayer (midiout, channel=2, octave=3, vel_base=28, gate=0.55, label="Sparkle")
    evo     = EvolutionController()

    drone.start()
    time.sleep(2.0)
    melody.start()
    time.sleep(3.5)
    sparkle.start()
    time.sleep(2.0)
    evo.start()

    print("\n[演奏中]  Ctrl+C で停止\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n停止中...")
        STATE.running = False
        drone.stop()
        melody.stop()
        sparkle.stop()
        print("[停止完了]")

if __name__ == '__main__':
    main()
