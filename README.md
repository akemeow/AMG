# 🎵 Ambient MIDI Generator (AMG)

リアルタイムでアンビエント MIDI を生成する GUI アプリケーション。  
スケール・コード・密度・進化を直感的に操作し、変化し続けるアンビエントサウンドを作れます。

---

## スクリーンショット

> アプリ起動後にキャプチャを追加してください。

---

## 主な機能

### 🎹 MIDI 生成
- **3レイヤー構成** — Drone（持続音）、Melody（メロディ）、Sparkle（装飾音）
- 各レイヤーを独立してオン/オフ、ベロシティ・バリエーション・レストを調整
- MIDI チャンネル 1〜3 に個別出力（外部シンセ・DAW と接続）

### 🎼 スケール & キー
| カテゴリ | スケール例 |
|----------|-----------|
| 明るい系 | Major, Lydian, Lydian Dominant, Mixolydian, Pentatonic Major |
| 暗い系 | Minor, Dorian, Phrygian, Harmonic Minor, Blues |
| エキゾチック | Phrygian Dominant, Hungarian Minor, Double Harmonic, Hirajoshi |
| 浮遊系 | Whole Tone, Diminished |

- **Auto Root** — ルート音をランダム自動変更
- **Auto Scale** — スケールをランダム自動変更（変更速度ノブ付き）

### 🎵 コード & アルペジオ
- コードディグリー選択（Ⅰ〜Ⅶ♭）
- コードタイプ：Major / Minor / Dominant7 / Major7 / Minor7 / Diminished / Sus4 など
- アルペジオモード：Up / Down / UpDown / Random / Block / ChordOnly
- **スイング** 4段階：Straight / Soft (58%) / Triplet (67%) / Hard (75%)
- ノートレート（BPM 同期）：1/1 〜 1/16 から選択

### ⚡ AUTO EVOLVE
曲の展開を自動で変化させる「アイデアの種」。デフォルトOFF。

- XY **Kaoss Pad** で Depth（Y軸）と Speed（X軸）を同時コントロール
- 進化ターゲット：Dynamic / Root / Scale / Density / Chord Degree /
  Arp Mode / Arp Rate / Melody Rhythm / Layer ON|OFF

### 🔄 AUTO MOD
パッド上のポインタが自動で動き、パラメータを連続変調。

| モード | 動き |
|--------|------|
| RAND | ランダムな目標点へのスムーズ補間 |
| ○ 円 | 中心・半径がゆっくり変動する円運動 |
| ∞ 八の字 | 中心・スケールが変動するリサージュ曲線 |
| ◌ 渦巻 | 外向き螺旋でリセット |

### 🛸 ポインタデザイン（4種）
| ボタン | デザイン |
|--------|---------|
| SP-1 | スプートニク1号（金属球 + 4本アンテナ） |
| SP-3 | スプートニク3号（円錐ボディ + 後方アンテナ） |
| 鷹 | 8-bit 鷹シルエット（羽ばたきアニメ） |
| CLaUDE | 8-bit レトロロボット（瞬き・キャタピラ・アンテナ点滅アニメ） |

### ⏱ BPM & クロック同期
- 手動 BPM（30〜300）
- **Logic Pro 等の DAW から MIDI Clock を受信して BPM 自動同期**（Slave モード）
- 内部 MIDI Clock 送信も可能

---

## 必要環境

| 項目 | バージョン |
|------|-----------|
| Python | 3.11 |
| Tkinter | 8.6（macOS は `python-tk@3.11` を使用） |
| python-rtmidi | 1.5.8 |
| OS | macOS（Apple Silicon / Intel 確認済み） |

> **macOS + Tk 9.0 の注意**  
> Tk 9.0 では `<MouseWheel>` イベントが届かないバグがあります。  
> 必ず Tk 8.6 ベースの Python 3.11 を使用してください。

---

## インストール

```bash
# 1. リポジトリをクローン
git clone https://github.com/akemeow/AMG.git
cd AMG

# 2. Homebrew で Tk 8.6 + Python 3.11 を用意（macOS）
brew install tcl-tk@8 python-tk@3.11

# 3. venv を作成（python3.11 を明示）
python3.11 -m venv venv
source venv/bin/activate

# 4. 依存パッケージをインストール
pip install python-rtmidi
```

---

## 起動方法

```bash
source venv/bin/activate
python ambient_app.py
```

---

## 使い方

### 基本フロー

1. **MIDI ポートを選択** — Transport セクション右上のドロップダウンで出力先を選ぶ
2. **Key / Scale を設定** — ルート音とスケールを選択
3. **Chord Type を選択** — コードの種類・ディグリーを設定
4. **Density を調整** — Sparse / Normal / Dense からノート密度を選ぶ
5. **▶ START** を押して生成開始

### AUTO EVOLVE を使う

1. `⚡ AUTO EVOLVE` ボタンをクリックして有効化（オレンジ色に点灯）
2. Kaoss Pad をドラッグして Depth（Y 軸）と Speed（X 軸）を調整
3. より激しい変化にするには Depth を高く、変化を遅くするには Speed を低く

### AUTO MOD を使う

1. `MOD MODE` ボタンで動きのパターンを選択
2. `◎ AUTO MOD` をクリックして有効化
3. `Move Speed` ノブで移動速度を調整
4. ポインタを `POINTER` ボタンで好みのデザインに変更

### DAW 同期（MIDI Clock Slave）

1. Logic Pro 等で MIDI Clock 送信を有効にする
2. アプリ上部 Transport の `SLAVE` ボタンをオン
3. DAW を再生すると BPM が自動追従

---

## ファイル構成

```
AMG/
├── ambient_app.py          # メイン GUI アプリ（本体）
├── ambient_generator.py    # コア MIDI 生成ロジック
├── markov_midi_generator.py# マルコフ連鎖ベースのジェネレータ（旧版）
├── run.sh                  # 起動スクリプト
├── venv/                   # Python 仮想環境（git 管理外）
└── README.md
```

---

## アーキテクチャ

```
AmbientApp (Tkinter GUI)
    │
    ├─ STATE (AppState)          共有状態（スレッドセーフ）
    │
    ├─ MidiClockReceiver         MIDI Clock 受信スレッド
    ├─ MidiClockSender           MIDI Clock 送信スレッド
    │
    ├─ DroneLayer                持続音生成スレッド
    ├─ MelodyLayer               メロディ生成スレッド（リズムパターン対応）
    ├─ SparkleLayer              装飾音生成スレッド
    ├─ ChordLayer                コード/アルペジオ生成スレッド
    │
    ├─ EvolutionController       AUTO EVOLVE ロジック
    │
    └─ KaossPad (tk.Canvas)      XY パッド + AUTO MOD アニメーション
            └─ ポインタ描画
                 ├─ _draw_sputnik1()   スプートニク1号
                 ├─ _draw_sputnik3()   スプートニク3号
                 ├─ _draw_hawk()       鷹（8-bit アニメ）
                 └─ _draw_claude()     レトロロボット（8-bit アニメ）
```

---

## ライセンス

MIT License

---

## クレジット

- Built with [Python](https://www.python.org/) + [Tkinter](https://docs.python.org/3/library/tkinter.html) + [python-rtmidi](https://github.com/SpotlightKid/python-rtmidi)
- Developed with [Claude Code](https://claude.ai/claude-code) (Anthropic)
