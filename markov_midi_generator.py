#!/usr/bin/env python3
"""
Markov Chain MIDI Generator for Logic Pro
IAC Driver経由でLogic Proにリアルタイム送信

使い方:
    pip install python-rtmidi
    python3 markov_midi_generator.py
"""

import rtmidi
import time
import random
import threading
import sys

# ==================== 設定 ====================
CONFIG = {
    'bpm': 90,
    'root_note': 60,          # ルート音 (60 = C4)
    'scale': 'pentatonic_minor',
    'octave_range': 2,         # 使用オクターブ数
    'channel': 0,              # MIDIチャンネル (0-15)
    'velocity_base': 75,       # 基本ベロシティ
    'velocity_variation': 25,  # ベロシティのゆらぎ幅
    'rest_probability': 0.08,  # 休符の確率 (0.0〜1.0)
    'octave_change_prob': 0.12,# オクターブ変化の確率
    'gate_time': 0.82,         # ゲートタイム (音の長さの割合)
    # 音符の長さ（拍単位）とその出現重み
    'durations': {
        0.25: 2,   # 16分音符
        0.5:  5,   # 8分音符
        1.0:  4,   # 4分音符
        2.0:  1,   # 2分音符
    },
}

# ==================== スケール定義 ====================
SCALES = {
    'major':            [0, 2, 4, 5, 7, 9, 11],
    'minor':            [0, 2, 3, 5, 7, 8, 10],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'blues':            [0, 3, 5, 6, 7, 10],
    'phrygian':         [0, 1, 3, 5, 7, 8, 10],
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def note_name(midi_note):
    return f"{NOTE_NAMES[midi_note % 12]}{midi_note // 12 - 1}"

# ==================== Markov遷移行列 ====================
def build_transition_matrix(scale_len):
    """
    音楽的な重み付きMarkov遷移行列を生成
    - 隣接音への移動を優先（stepwise motion）
    - 大きな跳躍は稀に
    """
    matrix = []
    for i in range(scale_len):
        row = []
        for j in range(scale_len):
            dist = abs(i - j)
            if dist == 0:
                w = 0.3    # 同音反復（少し）
            elif dist == 1:
                w = 5.0    # 隣接音（最も自然）
            elif dist == 2:
                w = 3.0    # 2度飛び
            elif dist == 3:
                w = 1.5    # 3度
            elif dist == 4:
                w = 0.7    # 4度
            else:
                w = 0.2    # 大きな跳躍（稀）
            row.append(w)
        total = sum(row)
        matrix.append([w / total for w in row])
    return matrix

def next_degree(current, matrix):
    """Markov連鎖で次の音階度数を選択"""
    weights = matrix[current]
    r = random.random()
    cumulative = 0.0
    for i, w in enumerate(weights):
        cumulative += w
        if r < cumulative:
            return i
    return len(matrix) - 1

def weighted_choice(choices_dict):
    """重み付きランダム選択 {value: weight}"""
    values = list(choices_dict.keys())
    weights = list(choices_dict.values())
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0.0
    for v, w in zip(values, weights):
        cumulative += w
        if r < cumulative:
            return v
    return values[-1]

# ==================== MIDI ジェネレーター ====================
class MarkovMidiGenerator:
    def __init__(self, config):
        self.config = config
        self.running = False
        self._thread = None

        self.midiout = rtmidi.MidiOut()
        self._connect_midi()
        self._build_scale()

    def _connect_midi(self):
        ports = self.midiout.get_ports()
        if not ports:
            print("エラー: MIDIポートが見つかりません。IAC Driverを有効化してください。")
            sys.exit(1)

        print("利用可能なMIDIポート:")
        for i, name in enumerate(ports):
            print(f"  [{i}] {name}")

        # IAC Driverを自動検出
        iac_index = next((i for i, n in enumerate(ports) if 'IAC' in n), None)
        if iac_index is not None:
            self.midiout.open_port(iac_index)
            print(f"\n[接続] IAC Driver: {ports[iac_index]}")
        else:
            self.midiout.open_port(0)
            print(f"\n[接続] {ports[0]}  ※ IAC Driverが見つからなかったためポート0を使用")

    def _build_scale(self):
        scale_name = self.config['scale']
        intervals = SCALES.get(scale_name, SCALES['pentatonic_minor'])
        root = self.config['root_note']
        octave_range = self.config['octave_range']

        self.scale_intervals = intervals
        self.scale_len = len(intervals)
        self.octave_range = octave_range
        self.root = root
        self.matrix = build_transition_matrix(self.scale_len)

        print(f"\nスケール: {scale_name}  ルート: {note_name(root)}  "
              f"オクターブ: {octave_range}  BPM: {self.config['bpm']}")

    # ---- MIDI メッセージ送信 ----
    def _note_on(self, note, velocity):
        ch = self.config['channel']
        self.midiout.send_message([0x90 | ch, note, velocity])

    def _note_off(self, note):
        ch = self.config['channel']
        self.midiout.send_message([0x80 | ch, note, 0])

    def _all_notes_off(self):
        ch = self.config['channel']
        self.midiout.send_message([0xB0 | ch, 123, 0])

    # ---- 演奏ループ ----
    def _play_loop(self):
        beat = 60.0 / self.config['bpm']
        degree = random.randint(0, self.scale_len - 1)
        octave = random.randint(0, self.octave_range - 1)
        last_note = None

        while self.running:
            # Markov連鎖で次の度数を選択
            degree = next_degree(degree, self.matrix)

            # オクターブ変化
            if random.random() < self.config['octave_change_prob']:
                octave = random.randint(0, self.octave_range - 1)

            note = self.root + octave * 12 + self.scale_intervals[degree]
            if not (0 <= note <= 127):
                continue

            # 音符の長さ
            dur_beats = weighted_choice(self.config['durations'])
            dur_sec = dur_beats * beat
            gate = self.config['gate_time']

            # ベロシティ（人間らしいゆらぎ）
            velocity = self.config['velocity_base'] + random.randint(
                -self.config['velocity_variation'],
                self.config['velocity_variation']
            )
            velocity = max(1, min(127, velocity))

            # 休符
            if random.random() < self.config['rest_probability']:
                print(f"  休符  ({dur_beats}拍)")
                time.sleep(dur_sec)
                continue

            # 発音
            print(f"  {note_name(note):4s} vel={velocity:3d}  ({dur_beats}拍)")
            if last_note is not None:
                self._note_off(last_note)
            self._note_on(note, velocity)
            last_note = note

            time.sleep(dur_sec * gate)
            self._note_off(note)
            last_note = None
            time.sleep(dur_sec * (1.0 - gate))

    # ---- 開始 / 停止 ----
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()
        print("\n[演奏開始]  Ctrl+C で停止\n")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._all_notes_off()
        print("\n[演奏停止]")


# ==================== メイン ====================
def main():
    print("=" * 50)
    print("  Markov Chain MIDI Generator")
    print("=" * 50)

    gen = MarkovMidiGenerator(CONFIG)
    gen.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        gen.stop()


if __name__ == '__main__':
    main()
