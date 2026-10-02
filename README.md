# YouTube Cover Image Cropper

YouTube動画のカバー画像（サムネイル）を16:9比率で切り出し、1280x720のJPEGとして書き出すデスクトップアプリケーションです。

## 考え方

何が問題で、それをどう解いているかを PAD（問題分析図）で示します。各段の詳細は下の各節を参照してください。

<img src="docs/pad/concept.png" alt="考え方の PAD。手元の画像から動画のカバー画像を作るため、画像を読み込み、人が回転・16:9 の枠・JPEG 品質を実寸プレビューで見比べて決め、1280×720 の JPEG として書き出す" width="100%">

<sub>図の元は [`docs/pad/concept.spd`](docs/pad/concept.spd)。[padkit](https://github.com/mashi727/padkit) で検査・描画しています。</sub>

## Features

- **16:9アスペクト比でのクロップ**: ドラッグで移動、コーナーでリサイズ
- **回転調整**: 0-359度の回転に対応
- **品質調整**: JPEGの圧縮品質をリアルタイムで調整
- **ドットバイドットプレビュー**: 実寸（1280x720）での品質比較表示
- **クリップボード対応**: Ctrl+Vで画像を貼り付け
- **ファイルブラウザ**: 左パネルで画像ファイルを簡単に選択

## Screenshot

![App Screenshot](screenshot.png)

## Requirements

- Python 3.10+
- PySide6

## Installation

### pip (推奨)

```bash
pip install git+https://github.com/mashi727/youtube-cover-cropper.git
```

### From source

```bash
# Clone the repository
git clone https://github.com/mashi727/youtube-cover-cropper.git
cd youtube-cover-cropper

# Install as package
pip install .

# Or install in development mode
pip install -e .
```

## Usage

```bash
# Run the app
youtube-cover-cropper

# Start with a specific directory
youtube-cover-cropper /path/to/your/images
```

### As Python module

```bash
python -m youtube_cover_cropper [directory]
```

### Controls

| Operation | Action |
|-----------|--------|
| クリック | 画像を読み込み |
| ドラッグ | クロップ範囲を移動 |
| コーナードラッグ | クロップ範囲をリサイズ |
| Ctrl+V | クリップボードから貼り付け |
| 回転スライダー | 画像を回転 |
| 品質スライダー | JPEG品質を調整 |
| Preview (split) | 実寸プレビュー表示 |

## Output

- **サイズ**: 1280 x 720 pixels
- **フォーマット**: JPEG
- **品質**: 1-100（調整可能、デフォルト85）

## License

MIT License
