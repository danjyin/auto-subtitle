# Auto Screen Subtitle

Real-time screen OCR + translation overlay for Windows.
Detects text in a chosen language visible on your screen and shows the English translation in a transparent floating bar — no API key required.

## How it works

1. Captures a region of your screen (bottom third by default, where subtitles appear)
2. Runs local OCR via [EasyOCR](https://github.com/JaidedAI/EasyOCR) to extract text
3. Translates it using Google Translate (via [deep-translator](https://github.com/nidhaloff/deep-translator))
4. Shows original text + translation in a transparent, always-on-top overlay

## Requirements

- Windows 10 / 11
- Python 3.9+

## Install

```bat
setup.bat
```

Or manually:

```bat
pip install easyocr mss Pillow deep-translator torch
```

> EasyOCR downloads its language model (~500 MB) on first run.

## Usage

```bat
run.bat
```

A settings dialog will open. Choose:
- **Source language** — language of the text on screen (e.g. Chinese Simplified)
- **Translate to** — target language (default: English)
- **Scan area** — screen region to scan (default: Bottom third)

Press **Escape** or right-click the subtitle bar → **Close** to quit.

## Supported source languages

Chinese (Simplified/Traditional), Japanese, Korean, French, German, Spanish, Portuguese, Russian, Arabic, Italian, Dutch

## Notes

- The overlay is transparent and always on top — drag it to reposition
- First OCR scan takes a few seconds while the model initialises
- Scanning speed depends on your CPU; bottom-third mode is fastest

## Changelog

### v1.0.0
- Initial release: screen OCR + translation overlay
- Language selection dialog (source + target + scan region)
- Transparent always-on-top subtitle bar with original + translated lines
- Greedy decoder for faster OCR; auto-normalisation and silence filtering removed (audio approach replaced with OCR)
