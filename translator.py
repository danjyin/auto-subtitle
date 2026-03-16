#!/usr/bin/env python3
"""
Auto Screen Subtitle — OCR Translation
Reads text in a chosen language visible on screen, translates it, shows the
translation in a transparent overlay below.

No API key needed. Uses local EasyOCR model + free Google Translate.

Install:
    pip install mss easyocr deep-translator Pillow
"""

import sys
import time
import queue
import warnings
import threading
import tkinter as tk
from tkinter import ttk

warnings.filterwarnings("ignore", message="'pin_memory'")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

try:
    import mss
except ImportError:
    sys.exit("Missing dependency.  Run:  pip install mss")

try:
    import easyocr
except ImportError:
    sys.exit("Missing dependency.  Run:  pip install easyocr")

try:
    from PIL import Image
    import numpy as np
except ImportError:
    sys.exit("Missing dependency.  Run:  pip install Pillow")

try:
    from deep_translator import GoogleTranslator
except ImportError:
    sys.exit("Missing dependency.  Run:  pip install deep-translator")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUBTITLE_LINGER  = 5000  # ms subtitle stays visible before dimming
OCR_SCALE        = 0.4   # downscale factor for OCR speed (smaller = faster)
OCR_CONF         = 0.4   # minimum EasyOCR confidence to accept a word
_TRANSPARENT_KEY = "#010101"


# ---------------------------------------------------------------------------
# Language / region data
# ---------------------------------------------------------------------------
def _has_cjk(t):
    return any('\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' for c in t)

def _has_kana(t):
    return any('\u3040' <= c <= '\u30ff' for c in t)

def _has_hangul(t):
    return any('\uac00' <= c <= '\ud7af' for c in t)

def _has_arabic(t):
    return any('\u0600' <= c <= '\u06ff' for c in t)

def _has_cyrillic(t):
    return any('\u0400' <= c <= '\u04ff' for c in t)

# (display_name, easyocr_langs, google_src_code, char_filter_fn_or_None)
SOURCE_LANGUAGES = [
    ("Chinese (Simplified)",  ["ch_sim", "en"], "zh-CN", _has_cjk),
    ("Chinese (Traditional)", ["ch_tra", "en"], "zh-TW", _has_cjk),
    ("Japanese",  ["ja",  "en"], "ja", lambda t: _has_cjk(t) or _has_kana(t)),
    ("Korean",    ["ko",  "en"], "ko", _has_hangul),
    ("Arabic",    ["ar",  "en"], "ar", _has_arabic),
    ("Russian",   ["ru",  "en"], "ru", _has_cyrillic),
    ("French",    ["fr",  "en"], "fr", None),
    ("German",    ["de",  "en"], "de", None),
    ("Spanish",   ["es",  "en"], "es", None),
    ("Portuguese",["pt",  "en"], "pt", None),
    ("Italian",   ["it",  "en"], "it", None),
    ("Dutch",     ["nl",  "en"], "nl", None),
]

TARGET_LANGUAGES = [
    ("English",              "en"),
    ("Chinese (Simplified)", "zh-CN"),
    ("Japanese",             "ja"),
    ("Korean",               "ko"),
    ("French",               "fr"),
    ("Spanish",              "es"),
    ("German",               "de"),
    ("Portuguese",           "pt"),
]

# (display_name, region_key)
SCREEN_REGIONS = [
    ("Bottom third  (subtitle area)", "bottom_third"),
    ("Bottom half",                   "bottom_half"),
    ("Full screen",                   "full"),
    ("Top half",                      "top_half"),
]


# ---------------------------------------------------------------------------
# Language picker dialog
# ---------------------------------------------------------------------------
class LanguageDialog:
    def __init__(self):
        self.result = None

        self.root = tk.Tk()
        self.root.title("Auto Subtitle — Settings")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        pad = {"padx": 12, "pady": 5}

        tk.Label(self.root, text="Text language on screen:", anchor="w").grid(
            row=0, column=0, sticky="w", **pad)
        self._src_var = tk.StringVar()
        src_names = [e[0] for e in SOURCE_LANGUAGES]
        ttk.Combobox(self.root, textvariable=self._src_var,
                     values=src_names, state="readonly", width=30).grid(
            row=0, column=1, **pad)
        self._src_var.set(src_names[0])

        tk.Label(self.root, text="Translate to:", anchor="w").grid(
            row=1, column=0, sticky="w", **pad)
        self._tgt_var = tk.StringVar()
        tgt_names = [e[0] for e in TARGET_LANGUAGES]
        ttk.Combobox(self.root, textvariable=self._tgt_var,
                     values=tgt_names, state="readonly", width=30).grid(
            row=1, column=1, **pad)
        self._tgt_var.set("English")

        tk.Label(self.root, text="Scan area:", anchor="w").grid(
            row=2, column=0, sticky="w", **pad)
        self._region_var = tk.StringVar()
        region_names = [e[0] for e in SCREEN_REGIONS]
        ttk.Combobox(self.root, textvariable=self._region_var,
                     values=region_names, state="readonly", width=30).grid(
            row=2, column=1, **pad)
        self._region_var.set(region_names[0])

        btn = tk.Frame(self.root)
        btn.grid(row=3, column=0, columnspan=2, pady=10)
        tk.Button(btn, text="Start", width=10, command=self._ok).pack(side="left", padx=6)
        tk.Button(btn, text="Cancel", width=10,
                  command=self.root.destroy).pack(side="left", padx=6)

        self.root.bind("<Return>", lambda _: self._ok())
        self.root.bind("<Escape>", lambda _: self.root.destroy())

        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _ok(self):
        src = next(e for e in SOURCE_LANGUAGES if e[0] == self._src_var.get())
        tgt = next(e for e in TARGET_LANGUAGES if e[0] == self._tgt_var.get())
        rgn = next(e for e in SCREEN_REGIONS   if e[0] == self._region_var.get())
        self.result = (src, tgt[1], rgn[1])
        self.root.destroy()

    def ask(self):
        self.root.mainloop()
        return self.result


# ---------------------------------------------------------------------------
# Subtitle overlay window
# ---------------------------------------------------------------------------
class SubtitleWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto Subtitle")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 1.0)   # fully opaque (text only visible)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h, x, y = sw - 200, 80, 100, sh - 80 - 40

        self.root.geometry(f"{w}x{h}+{x}+{y}")
        # Make the entire window background transparent
        self.root.configure(bg=_TRANSPARENT_KEY)
        self.root.attributes("-transparentcolor", _TRANSPARENT_KEY)

        # Labels sit directly on the transparent window — no panel/frame
        # Line 1: original text (light blue, small)
        self.orig_label = tk.Label(
            self.root, text="", font=("Arial", 12),
            fg="#AAAADD", bg=_TRANSPARENT_KEY,
            wraplength=w - 20, justify="center")
        self.orig_label.pack(fill="x", pady=(4, 0))

        # Line 2: translated text (bright blue, bold)
        self.trans_label = tk.Label(
            self.root, text="Auto Subtitle  •  Loading OCR model…",
            font=("Arial", 17, "bold"),
            fg="#AAAAAA", bg=_TRANSPARENT_KEY,
            wraplength=w - 20, justify="center")
        self.trans_label.pack(fill="x", pady=(0, 4))

        self._dx = self._dy = 0
        for widget in (self.root, self.orig_label, self.trans_label):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<Button-3>", self._context_menu)
        self.root.bind("<Escape>", lambda _: self.root.destroy())

        self._linger_job = None

    def _drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _context_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Close (Esc)", command=self.root.destroy)
        m.post(e.x_root, e.y_root)

    def set_subtitle(self, original: str, translated: str):
        self.orig_label.config(text=original, fg="#AAAADD")
        self.trans_label.config(text=translated, fg="#00CFFF")
        if self._linger_job:
            self.root.after_cancel(self._linger_job)
        self._linger_job = self.root.after(SUBTITLE_LINGER, self._dim)

    def set_status(self, text: str, color: str = "#55AAFF"):
        self.orig_label.config(text="", fg="#000000")
        self.trans_label.config(text=text, fg=color)
        if self._linger_job:
            self.root.after_cancel(self._linger_job)

    def _dim(self):
        self.orig_label.config(text="")
        self.trans_label.config(text="", fg=_TRANSPARENT_KEY)

    def _poll(self, q: queue.Queue):
        try:
            while True:
                msg = q.get_nowait()
                if isinstance(msg, tuple):
                    self.set_subtitle(msg[0], msg[1])
                elif msg.startswith("[ERROR]"):
                    self.set_status(msg, "#FF5555")
                else:
                    self.set_status(msg, "#55AAFF")
        except queue.Empty:
            pass
        try:
            self.root.after(200, self._poll, q)
        except tk.TclError:
            pass

    def run(self, q: queue.Queue):
        self.root.after(200, self._poll, q)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Screen OCR translator
# ---------------------------------------------------------------------------
class ScreenTranslator:
    def __init__(self, src_entry, tgt_code: str, region_code: str):
        # src_entry = (display_name, ocr_langs, google_src, char_filter)
        self._ocr_langs    = src_entry[1]
        self._google_src   = src_entry[2]
        self._char_filter  = src_entry[3]   # fn(text)->bool or None
        self._tgt_code     = tgt_code
        self._region_code  = region_code

        self.text_q: queue.Queue  = queue.Queue()
        self._frame_q: queue.Queue = queue.Queue(maxsize=1)
        self.running  = False
        self._reader  = None
        self._xlator  = None
        self._last    = ""          # last translated text (dedup)

    # --- model loading -------------------------------------------------------
    def _load(self):
        self.text_q.put("[INFO] Loading OCR model — first run downloads ~200 MB…")
        try:
            self._reader = easyocr.Reader(self._ocr_langs, gpu=False, verbose=False)
            self._xlator = GoogleTranslator(source=self._google_src,
                                            target=self._tgt_code)
            self.text_q.put("[INFO] Ready — scanning screen for text…")
        except Exception as exc:
            self.text_q.put(f"[ERROR] Load failed: {exc}")
            self.running = False

    # --- capture region helper -----------------------------------------------
    def _region(self, monitor: dict) -> dict:
        L, T, W, H = monitor['left'], monitor['top'], monitor['width'], monitor['height']
        if self._region_code == "bottom_third":
            return {'left': L, 'top': T + H * 2 // 3, 'width': W, 'height': H // 3}
        if self._region_code == "bottom_half":
            return {'left': L, 'top': T + H // 2,     'width': W, 'height': H // 2}
        if self._region_code == "top_half":
            return {'left': L, 'top': T,               'width': W, 'height': H // 2}
        return monitor   # full

    # --- frame capture thread (fast) ----------------------------------------
    def _capture(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while self.running:
                region = self._region(monitor)
                shot   = sct.grab(region)
                img    = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
                nw = int(img.width  * OCR_SCALE)
                nh = int(img.height * OCR_SCALE)
                arr = np.array(img.resize((nw, nh), Image.LANCZOS))
                # Always keep only the latest frame
                try:
                    self._frame_q.get_nowait()
                except queue.Empty:
                    pass
                self._frame_q.put(arr)
                time.sleep(0.4)   # capture every 0.4 s

    # --- OCR + translate thread (runs as fast as model allows) ---------------
    def _scan(self):
        while self.running and self._reader is None:
            time.sleep(0.2)

        while self.running:
            try:
                arr = self._frame_q.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                results = self._reader.readtext(arr, detail=1, paragraph=False,
                                               decoder='greedy', beamWidth=1)
            except Exception as exc:
                print(f"[ocr error] {exc}")
                continue

            texts = []
            for (_, text, conf) in results:
                text = text.strip()
                if not text or conf < OCR_CONF:
                    continue
                if self._char_filter is None or self._char_filter(text):
                    texts.append(text)

            combined = "  ".join(texts)
            if combined:
                print(f"[ocr] {combined!r}")

            if combined and combined != self._last:
                self._last = combined
                try:
                    translated = self._xlator.translate(combined)
                    print(f"[translate] {translated!r}")
                    if translated and translated.strip():
                        self.text_q.put((combined, translated.strip()))
                except Exception as exc:
                    print(f"[translate error] {exc}")

    # --- thread management ---------------------------------------------------
    def start(self, text_q: queue.Queue):
        self.text_q  = text_q
        self.running = True
        threading.Thread(target=self._load,    daemon=True).start()
        threading.Thread(target=self._capture, daemon=True).start()
        threading.Thread(target=self._scan,    daemon=True).start()

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    dialog = LanguageDialog()
    result = dialog.ask()
    if result is None:
        return

    src_entry, tgt_code, region_code = result
    print(f"Auto Screen Subtitle  |  source={src_entry[0]}  "
          f"target={tgt_code}  region={region_code}")
    print("Right-click the subtitle bar → Close, or press Escape to quit.\n")

    text_q     = queue.Queue()
    translator = ScreenTranslator(src_entry, tgt_code, region_code)
    translator.start(text_q)

    window = SubtitleWindow()
    window.run(text_q)

    translator.stop()
    print("Goodbye.")


if __name__ == "__main__":
    main()
