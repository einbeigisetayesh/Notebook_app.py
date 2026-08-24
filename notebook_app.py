import tkinter as tk
from tkinter import colorchooser, ttk, filedialog
import tkinter.font as tkFont
from PIL import Image, ImageDraw, ImageTk
import math
import random
import datetime
import json
import base64
import io
import threading

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

# ===================== Page / Canvas Size Constants =====================
# The whole page (background art, buttons, everything) is a fixed size that
# matches the window — nothing about the page itself scrolls anymore.
# Only the Text widget where you actually write gets its own scrollbar,
# like a normal text editor.
W = 600
H = 500

WINDOW_W = W  # window matches the page width exactly, no leftover white strip on the side
WINDOW_H = H

# The writing box (title + ruled text area) always stays exactly this many
# pixels, no matter what font size/family is chosen in "Features". Only the
# spacing between the ruled lines and the size of the writing itself change
# with font size — the box, and everything around it on the page, never
# grows or shrinks.
TEXTBOX_W = 480
TEXTBOX_H = 230

root = tk.Tk()
root.geometry(f"{WINDOW_W}x{WINDOW_H}")
root.title("notebook")

selected_color = "light pink"
selected_size = 15
bg_image_tk = None  # keep a reference so the image isn't garbage-collected

# Give scrollbars a clearly visible pink thumb instead of relying on
# whatever (sometimes near-invisible) default the OS theme provides.
_scrollbar_style = ttk.Style()
try:
    _scrollbar_style.theme_use("default")
except tk.TclError:
    pass
_scrollbar_style.configure(
    "Notebook.Vertical.TScrollbar",
    background="#FF9FBB",
    troughcolor="#FFE4EC",
    bordercolor="#FF69B4",
    arrowcolor="#FFFFFF",
    relief="flat",
)

# ===================== Cute Pastel Popups (replaces tkinter.messagebox) =====================
# All info / warning / error popups in the app go through this instead of
# the plain OS messagebox, so they always look like part of the notebook
# (pastel colors, rounded card, cute icon) and always read in English.
_DIALOG_PALETTE = {
    "info": {"bg": "#E0F7FA", "accent": "#4FC3F7", "icon": "💌"},
    "warning": {"bg": "#FFE4EC", "accent": "#FF9FBB", "icon": "🐰"},
    "error": {"bg": "#FFD6E8", "accent": "#FF6FA5", "icon": "🐰"},
}

def show_cute_dialog(kind, title, message):
    style = _DIALOG_PALETTE.get(kind, _DIALOG_PALETTE["info"])

    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=style["bg"])
    win.resizable(False, False)
    try:
        win.transient(root)
        win.grab_set()
    except tk.TclError:
        pass

    card = tk.Frame(
        win, bg=style["bg"], highlightbackground=style["accent"],
        highlightthickness=3, bd=0
    )
    card.pack(padx=16, pady=16)

    tk.Label(card, text=style["icon"], font=("Arial", 30), bg=style["bg"]).pack(pady=(16, 4))
    tk.Label(
        card, text=title, font=("Arial", 14, "bold"), bg=style["bg"], fg="#7A5C68"
    ).pack(pady=(0, 6), padx=20)
    tk.Label(
        card, text=message, font=("Arial", 11), bg=style["bg"], fg="#7A5C68",
        wraplength=260, justify="center"
    ).pack(padx=20, pady=(0, 14))

    make_button(
        card, "OK 🌸", win.destroy, bg=style["accent"], fg="white", font=("Arial", 12)
    ).pack(pady=(0, 16))

    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"+{max(x,0)}+{max(y,0)}")
    win.focus_set()

def cute_info(title, message):
    show_cute_dialog("info", title, message)

def cute_warning(title, message):
    show_cute_dialog("warning", title, message)

def cute_error(title, message):
    show_cute_dialog("error", title, message)

def show_cute_confirm(title, message, on_confirm):
    """A pastel-pink Yes/No confirmation popup (with a little bunny 🐰),
    used before anything gets deleted so nothing is removed by accident."""
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg="#FFE4EC")
    win.resizable(False, False)
    try:
        win.transient(root)
        win.grab_set()
    except tk.TclError:
        pass

    card = tk.Frame(
        win, bg="#FFE4EC", highlightbackground="#FF9FBB",
        highlightthickness=3, bd=0
    )
    card.pack(padx=16, pady=16)

    tk.Label(card, text="🐰", font=("Arial", 30), bg="#FFE4EC").pack(pady=(16, 4))
    tk.Label(
        card, text=title, font=("Arial", 14, "bold"), bg="#FFE4EC", fg="#7A5C68"
    ).pack(pady=(0, 6), padx=20)
    tk.Label(
        card, text=message, font=("Arial", 11), bg="#FFE4EC", fg="#7A5C68",
        wraplength=260, justify="center"
    ).pack(padx=20, pady=(0, 14))

    btn_row = tk.Frame(card, bg="#FFE4EC")
    btn_row.pack(pady=(0, 16))

    def _confirm():
        win.destroy()
        on_confirm()

    make_button(
        btn_row, "Yes, delete 🐰", _confirm, bg="#FF6FA5", fg="white", font=("Arial", 11)
    ).pack(side="left", padx=6)
    make_button(
        btn_row, "Cancel", win.destroy, bg="#FFC1DC", fg="white", font=("Arial", 11)
    ).pack(side="left", padx=6)

    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"+{max(x,0)}+{max(y,0)}")
    win.focus_set()

def delete_note_and_refresh(note, refresh_func):
    """Deletes one specific saved note (by its id) after the person
    confirms, then rebuilds whichever list (Notes or Favorites) it was
    removed from so it disappears right away."""
    def _do_delete():
        notes = load_notes()
        notes = [n for n in notes if n.get("id") != note.get("id")]
        save_notes(notes)
        refresh_func()

    show_cute_confirm(
        "Delete this note?", "This can't be undone. Are you sure?", _do_delete
    )

# ===================== Page Container =====================
# All pages live on top of each other inside this container.
# Switching pages just raises one to the front (no blank flashes).
container = tk.Frame(root)
container.pack(fill="both", expand=True)

def show_page(page):
    page.tkraise()

def _lighten_hex(hex_color, amount=0.18):
    """Nudges a hex color a bit lighter, used for the cute hover glow on
    buttons. Falls back to the original color for named tk colors it
    can't parse (like 'white')."""
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return hex_color
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color

def make_button(parent, text, command, bg="#FF9FBB", fg="white", font=("Arial", 17)):
    """A clickable Label styled as a soft, pastel, rounded-feeling button
    with a gentle 'puff up' glow on hover, so the whole notebook feels a
    little more alive and huggable. 🎀
    Works around a macOS Tkinter bug where tk.Button ignores bg/fg colors
    until it is pressed."""
    hover_bg = _lighten_hex(bg, 0.22)
    btn = tk.Label(
        parent, text=text, bg=bg, fg=fg, font=font,
        padx=14, pady=7, relief="flat", borderwidth=0, cursor="hand2",
        highlightthickness=2, highlightbackground=_lighten_hex(bg, 0.35),
        highlightcolor=_lighten_hex(bg, 0.35),
    )
    btn._base_bg = bg
    btn._hover_bg = hover_bg

    def _on_enter(e):
        btn.configure(bg=hover_bg, highlightbackground="#FFFFFF")

    def _on_leave(e):
        btn.configure(bg=bg, highlightbackground=_lighten_hex(bg, 0.35))

    btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)
    return btn

def make_text_box(parent, width=60, height=15, **text_kwargs):
    """Creates a Text widget together with its own vertical scrollbar,
    wired together with grid() inside a small dedicated frame — this is the
    reliable way to get a working scrollbar in Tkinter (placing a separate
    scrollbar next to the widget with place() can end up not actually
    tracking/scrolling it).

    Returns (frame, text_widget). Place *frame* on the page wherever the
    text box should sit — do not place text_widget directly.

    Only this text box scrolls: the scrollbar, the mouse wheel (while
    hovering over the box), and the built-in Tk "keep cursor visible while
    typing" behavior are all scoped only to this widget/frame — never to
    the rest of the page.
    """
    frame = tk.Frame(parent, bg="white", highlightthickness=0, bd=0)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    text_kwargs.setdefault("wrap", "word")
    text_widget = tk.Text(frame, width=width, height=height, **text_kwargs)
    scrollbar = ttk.Scrollbar(
        frame, orient="vertical",
        style="Notebook.Vertical.TScrollbar", command=text_widget.yview
    )
    text_widget.configure(yscrollcommand=scrollbar.set)

    text_widget.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    def _on_wheel(event):
        num = getattr(event, "num", None)
        if num == 4:
            text_widget.yview_scroll(-2, "units")
        elif num == 5:
            text_widget.yview_scroll(2, "units")
        else:
            delta = getattr(event, "delta", 0)
            if delta:
                steps = int(-1 * (delta / 120))
                if steps == 0:
                    steps = -1 if delta > 0 else 1
                text_widget.yview_scroll(steps, "units")
        return "break"

    # Bind/unbind the wheel only while the mouse is actually over this box
    # (same reliable pattern used for the notes list further down). This is
    # what lets you freely scroll up and down at ANY point in what you've
    # written — not only once you've typed all the way down to the last
    # visible line.
    def _bind_wheel(_e=None):
        text_widget.bind_all("<MouseWheel>", _on_wheel)
        text_widget.bind_all("<Button-4>", _on_wheel)
        text_widget.bind_all("<Button-5>", _on_wheel)

    def _unbind_wheel(_e=None):
        text_widget.unbind_all("<MouseWheel>")
        text_widget.unbind_all("<Button-4>")
        text_widget.unbind_all("<Button-5>")

    text_widget.bind("<Enter>", _bind_wheel)
    text_widget.bind("<Leave>", _unbind_wheel)

    # Note: we deliberately do NOT add a custom "see(insert) on every
    # keystroke" handler here anymore. Tk's Text widget already keeps the
    # cursor visible as you type on its own, and that extra handler was
    # forcing the view back down to the cursor right after every key press
    # — which is exactly what made manual scrolling feel like it only
    # "worked" once you reached the last line.

    return frame, text_widget

def make_titled_text_box(parent, width=60, height=14, **text_kwargs):
    """Same idea as make_text_box, but with a small title field sitting
    right above the writing area so each page/note can be given its own
    name. Returns (wrapper_frame, title_entry, text_widget) — place
    *wrapper_frame* wherever the whole titled box should sit.

    Use text_widget._get_title() to read back the title the person typed
    (empty string if they left the placeholder alone)."""
    wrapper = tk.Frame(parent, bg="white", highlightthickness=0, bd=0)

    placeholder ="name..."
    title_entry = tk.Entry(
        wrapper, font=("Arial", 13, "bold"), fg="#bbbbbb", bg="white",
        relief="flat", justify="center", highlightthickness=1,
        highlightbackground="#39272F", highlightcolor="#FF9FBB"
    )
    title_entry.insert(0, placeholder)
    title_entry._placeholder = placeholder

    def _clear_placeholder(event=None):
        if title_entry.get() == title_entry._placeholder:
            title_entry.delete(0, tk.END)
            title_entry.configure(fg="#FF69B4")

    def _restore_placeholder(event=None):
        if not title_entry.get().strip():
            title_entry.insert(0, title_entry._placeholder)
            title_entry.configure(fg="#bbbbbb")

    title_entry.bind("<FocusIn>", _clear_placeholder)
    title_entry.bind("<FocusOut>", _restore_placeholder)
    title_entry.pack(fill="x", padx=4, pady=(0, 6))

    text_frame, text_widget = make_text_box(wrapper, width=width, height=height, **text_kwargs)
    text_frame.pack(fill="both", expand=True)

    def get_title():
        val = title_entry.get().strip()
        return "" if val == title_entry._placeholder else val

    text_widget._title_entry = title_entry
    text_widget._get_title = get_title

    return wrapper, title_entry, text_widget

# ===================== Voice-to-Text (Speech Recognition) =====================
# Lets the person tap a microphone button and dictate straight into
# whichever writing box they're using — the recognized words are inserted
# right at the cursor position. Needs two extra packages the app doesn't
# ship with by default:
#
#     pip install SpeechRecognition pyaudio
#
# (On Windows pyaudio installs normally with pip. On macOS you may need
# `brew install portaudio` first. On Linux, `sudo apt-get install
# python3-pyaudio` or `portaudio19-dev` before the pip install.)
#
# It also needs an internet connection, since it uses Google's free
# speech-to-text web service under the hood (the same one used by
# `recognizer.recognize_google`). Default dictation language is Persian
# ("fa-IR") since that's what most notes here will be written in — change
# VOICE_LANGUAGE below to "en-US" (or any other Google-supported language
# code) if you'd rather dictate in English.
VOICE_LANGUAGE = "fa-IR"

def _set_voice_button_state(btn, state):
    """Flips a mic button between its idle / listening / processing looks.
    state is one of: "idle", "listening", "processing"."""
    if state == "listening":
        btn.configure(text="🎙️ Listening…", bg="#FF3B7A", fg="white")
    elif state == "processing":
        btn.configure(text="⏳ Processing…", bg="#B983FF", fg="white")
    else:
        btn.configure(text="🎙️ Voice", bg="#7FC7FF", fg="white")
        btn._base_bg = "#7FC7FF"
        btn._hover_bg = _lighten_hex("#7FC7FF", 0.22)

def _run_speech_recognition(text_widget, btn):
    """Runs on a background thread so recording/recognizing never freezes
    the notebook window. Only touches Tkinter widgets back on the main
    thread via root.after(), which is the safe way to do it."""
    recognizer = sr.Recognizer()
    # Stop recording sooner once you go quiet, instead of waiting a long
    # fixed time — this is what was making it feel stuck on "Listening…".
    recognizer.pause_threshold = 0.6
    recognizer.non_speaking_duration = 0.4
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            # timeout: how long to wait for you to START speaking.
            # phrase_time_limit: the longest a single recording can run —
            # kept short so it can't get "stuck" listening for too long.
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)
    except sr.WaitTimeoutError:
        root.after(0, lambda: cute_warning(
            "No speech detected", "We didn't hear anything. Try again and start talking right away."
        ))
        root.after(0, lambda: _set_voice_button_state(btn, "idle"))
        return
    except Exception:
        root.after(0, lambda: cute_error(
            "Microphone error", "Couldn't access your microphone. Check your mic permissions and try again."
        ))
        root.after(0, lambda: _set_voice_button_state(btn, "idle"))
        return

    # Recording is done — now it's off to Google's servers to be
    # transcribed. Switch the button so it's clear it's not stuck.
    root.after(0, lambda: _set_voice_button_state(btn, "processing"))

    try:
        recognized_text = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
    except sr.UnknownValueError:
        root.after(0, lambda: cute_warning(
            "Didn't catch that", "Couldn't understand the audio. Please try again, speaking clearly."
        ))
        root.after(0, lambda: _set_voice_button_state(btn, "idle"))
        return
    except sr.RequestError:
        root.after(0, lambda: cute_error(
            "No internet", "Voice-to-text needs an internet connection to work."
        ))
        root.after(0, lambda: _set_voice_button_state(btn, "idle"))
        return

    def _apply():
        text_widget.insert(tk.INSERT, recognized_text + " ")
        text_widget.focus_set()
        _set_voice_button_state(btn, "idle")
        btn._listening = False

    root.after(0, _apply)

def insert_voice_text(text_widget, btn):
    """Click handler for the 🎙️ Voice button: starts listening on the
    microphone and, once recognized, drops the spoken words straight into
    text_widget at the current cursor position."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        cute_error(
            "Missing package",
            "Voice-to-text needs two extra packages.\nInstall them with:\n"
            "pip install SpeechRecognition pyaudio"
        )
        return
    if getattr(btn, "_listening", False):
        return  # already listening — ignore extra clicks

    btn._listening = True
    _set_voice_button_state(btn, "listening")
    threading.Thread(target=_run_speech_recognition, args=(text_widget, btn), daemon=True).start()

# ===================== Welcome Page =====================
welcome_page = tk.Frame(container, bg="#FFF3F7")
welcome_page.place(x=0, y=0, relwidth=1, relheight=1)

# A soft pastel-gradient picture sits behind everything on the welcome
# page (filled in for real once the background generators are defined
# further down — see _apply_welcome_background()).
welcome_bg_label = tk.Label(welcome_page, bd=0)
welcome_bg_label.place(x=0, y=0, width=W, height=H)
welcome_bg_label.lower()

welcome_card = tk.Frame(
    welcome_page, bg="#FFFFFF", highlightbackground="#FF9FBB",
    highlightthickness=3, bd=0
)
welcome_card.place(x=W // 2, y=205, anchor="center")

tk.Label(
    welcome_card, text="⋆⁺₊⋆ ☁️ ⋆⁺₊⋆", font=("Arial", 12),
    bg="#FFFFFF", fg="#FF9FBB"
).pack(pady=(14, 0))

welcome_label = tk.Label(
    welcome_card,
    text="ᘉᓍᖶᘿᗷᓍᓍᖽᐸ",
    font=("Arial", 38),
    bg="#FFFFFF",
    fg="#FF6FA5"
)
welcome_label.pack(padx=40, pady=(4, 4))

tk.Label(
    welcome_card, text="my cute notebook 🎀", font=("Arial", 13, "italic"),
    bg="#FFFFFF", fg="pink"
).pack(pady=(0, 14))

enter_btn = make_button(
    welcome_page, "Enter", lambda: go_home(),
    bg="#FF9FBB", fg="white", font=("Arial", 18, "bold")
)
enter_btn.place(x=W // 2, y=420, anchor="center")

# Cute corner stickers
cutelabel = tk.Label(
    welcome_page,
    text="♡ ∩_∩  \n.  („• ֊ •„)♡\n |￣U U￣|",
    font=("Arial", 18),
    bg="#FFF3F7", fg="#FF9FBB", justify="left"
)
cutelabel.place(x=14, y=10)

cutelabel2 = tk.Label(
    welcome_page,
    text="╱|、\n(˚ˎ 。7\n |、˜〵\nじしˍ,)ノ",
    font=("Arial", 16),
    fg="white",bg="#FF9FBB", justify="left"
)
cutelabel2.place(x=520, y=390)

'''for _txt, _x, _y, _sz in [
    ("✨", 60, 60, 20), ("🌸", 540, 40, 22), ("💗", 40, 430, 20),
    ("⭐", 560, 220, 18), ("🎀", 500, 130, 20), ("☁️", 30, 250, 20),
]:
    tk.Label(welcome_page, text=_txt, font=("Arial", _sz), bg="#FFF3F7").place(x=_x, y=_y)'''

# ===================== Main Page =====================
main_page = tk.Frame(container, bg="#FFF9FC")
main_page.place(x=0, y=0, relwidth=1, relheight=1)

# Soft pastel background image (filled in once the background generators
# are defined further down — see the "main_bg_label.configure" call near
# the write page's default background).
main_bg_label = tk.Label(main_page, bd=0)
main_bg_label.place(x=0, y=0, width=W, height=H)
main_bg_label.lower()

'''main_header = tk.Label(
    main_page, text="📔 My Cute Notebook", font=("Arial", 18, "bold"),
    bg="#FFD6E8", fg="#B24A72", padx=16, pady=6
)
main_header.place(x=W // 2, y=30, anchor="center")'''

# Widgets are placed straight onto main_page (no extra opaque wrapper
# frame) so the pastel background image shows through around them.
main_buttons = main_page

# ===================== Write Page =====================
# write_page is a plain, fixed-size frame now — no Canvas wrapper, so the
# page itself never scrolls. Only text_area (below) gets its own scrollbar.
write_page = tk.Frame(container, bg="white", width=W, height=H)
write_page.place(x=0, y=0, relwidth=1, relheight=1)
write_inner = write_page

# Background image label — sits behind everything else on the write page.
bg_label = tk.Label(write_inner, bd=0)
bg_label.place(x=0, y=0, width=W, height=H)
bg_label.lower()

# The text box keeps its original size and position — it does NOT stretch,
# and its pixel size is fixed (TEXTBOX_W x TEXTBOX_H) so picking a bigger or
# smaller font/size never changes the box itself — only the writing inside it.
text_area_frame, text_area_title, text_area = make_titled_text_box(write_inner, width=60, height=14, bg="white")
text_area_frame.place(x=W // 2, y=int(H * 0.55), anchor="center", width=TEXTBOX_W, height=TEXTBOX_H)

text_area_frame.lift()
# ===================== Built-in Cute Background Patterns =====================
# These are drawn entirely with code (no external images needed), so the
# app works out of the box for anyone who runs it.

def _heart_points(cx, cy, scale):
    pts = []
    for i in range(0, 360, 8):
        t = math.radians(i)
        x = 16 * (math.sin(t) ** 3)
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * scale, cy - y * scale))
    return pts

def _star_points(cx, cy, outer_r, inner_r, rotation=90):
    pts = []
    for i in range(10):
        angle = math.radians(rotation + i * 36)
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    return pts

def generate_sky_clouds_bg():
    """Soft pastel-blue sky filled with fluffy white clouds of different sizes."""
    top = _hex_to_rgb("#BFE6FF")
    bottom = _hex_to_rgb("#EAF7FF")
    img = Image.new("RGB", (W, H), "#BFE6FF")
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=_lerp_color(top, bottom, t))

    def cloud(x, y, s=1.0):
        parts = [(0, 0, 55, 38), (32, -16, 58, 46), (66, 0, 55, 38), (18, 12, 90, 32)]
        for dx, dy, w, h in parts:
            draw.ellipse([x + dx * s, y + dy * s, x + dx * s + w * s, y + dy * s + h * s], fill="white")

    cloud_spots = [
        (20, 40, 0.8), (300, 20, 1.1), (150, 130, 0.7), (430, 110, 0.9),
        (60, 220, 0.6), (350, 230, 1.0), (500, 300, 0.75), (10, 340, 0.9),
        (230, 330, 0.65), (400, 400, 0.85), (120, 400, 0.7), (480, 60, 0.6),
    ]
    for x, y, s in cloud_spots:
        cloud(x, y, s)
    return img

def generate_pink_hearts_bg():
    """Cute, soft-white background scattered with lots of tiny pink hearts."""
    img = Image.new("RGB", (W, H), "#FFF3F7")
    draw = ImageDraw.Draw(img)
    random.seed(1)
    colors = ["#FFB6C1", "#FF9FBB", "#FFD6E4", "#FF7FA8", "#FFC7DA"]
    for _ in range(55):
        cx = random.randint(0, W)
        cy = random.randint(0, H)
        scale = random.uniform(0.25, 0.6)
        color = random.choice(colors)
        draw.polygon(_heart_points(cx, cy, scale * 6), fill=color)
    return img

def generate_pastel_candies_bg():
    """Cute pastel-colored candies (lollipops) scattered on a soft cream background."""
    img = Image.new("RGB", (W, H), "#FFF9F0")
    draw = ImageDraw.Draw(img)
    candy_colors = [
        ("#FFB6D9", "#FF7FB8"), ("#B6E3FF", "#7FC7FF"), ("#D9B6FF", "#B37FFF"),
        ("#FFF3B0", "#FFE066"), ("#B6FFD9", "#7FE0B0"),
    ]
    random.seed(7)
    for _ in range(16):
        cx = random.randint(30, W - 30)
        cy = random.randint(30, H - 30)
        r = random.randint(16, 26)
        base, stripe = random.choice(candy_colors)
        draw.line([cx, cy + r - 2, cx, cy + r + 26], fill="#E8D9C8", width=4)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=base)
        for k in range(3):
            ang0 = k * 120
            draw.arc(
                [cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4],
                start=ang0, end=ang0 + 70, fill=stripe, width=4
            )
        draw.ellipse([cx - r // 2, cy - r // 2, cx - r // 2 + 6, cy - r // 2 + 6], fill="white")
    return img

def generate_bubbles_bg():
    """Soft bubbles in many different sizes floating over a pastel gradient."""
    img = Image.new("RGB", (W, H), "#F3E8FF")
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(243 + (230 - 243) * t)
        g = int(232 + (245 - 232) * t)
        b = int(255 + (255 - 255) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    random.seed(3)
    colors = ["#FFD6E8", "#D6F0FF", "#E8D6FF", "#FFFDD6", "#D6FFE8"]
    for _ in range(40):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(6, 55)
        color = random.choice(colors)
        draw.ellipse([x - r, y - r, x + r, y + r], outline=color, width=3)
        draw.ellipse([x - r + 6, y - r + 6, x + r - 6, y + r - 6], fill=color)
        hr = max(2, r // 5)
        draw.ellipse(
            [x - r // 2, y - r // 2, x - r // 2 + hr, y - r // 2 + hr], fill="white"
        )
    return img

def generate_flowers_bg():
    """Colorful, cute little flowers scattered over a soft mint-white background."""
    img = Image.new("RGB", (W, H), "#F3FFF6")
    draw = ImageDraw.Draw(img)
    petal_colors = ["#FF9FBB", "#FFD166", "#B983FF", "#7FC7FF", "#FF8C69", "#F76E9E"]
    center_color = "#FFF3B0"
    random.seed(5)
    for _ in range(22):
        cx = random.randint(20, W - 20)
        cy = random.randint(20, H - 20)
        pr = random.randint(7, 12)
        color = random.choice(petal_colors)
        for i in range(6):
            angle = math.radians(i * 60)
            px = cx + pr * 1.1 * math.cos(angle)
            py = cy + pr * 1.1 * math.sin(angle)
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=color)
        draw.ellipse([cx - pr * 0.6, cy - pr * 0.6, cx + pr * 0.6, cy + pr * 0.6], fill=center_color)
        if random.random() < 0.4:
            draw.line([cx, cy + pr, cx, cy + pr + 18], fill="#8FD9A0", width=2)
            draw.ellipse([cx + 2, cy + pr + 8, cx + 14, cy + pr + 16], fill="#8FD9A0")
    return img

def generate_starry_bg():
    """Extra theme: a cute starry night sky with a crescent moon."""
    img = Image.new("RGB", (W, H), "#1B1140")
    draw = ImageDraw.Draw(img)
    for y in range(H):
        shade = int(20 + (y / H) * 25)
        draw.line([(0, y), (W, y)], fill=(27, 17, max(0, 64 - shade)))
    random.seed(2)
    for _ in range(90):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.choice([1, 1, 2])
        draw.ellipse([x - r, y - r, x + r, y + r], fill="white")
    draw.ellipse([460, 50, 540, 130], fill="#FFF7CC")
    draw.ellipse([480, 45, 555, 125], fill="#1B1140")
    return img

def generate_rainbow_stripes_bg():
    """Extra theme: soft pastel rainbow stripes."""
    stripe_colors = ["#FFD6D6", "#FFE6C7", "#FFF6C7", "#D9F7D6", "#D6ECFF", "#E3D6FF"]
    img = Image.new("RGB", (W, H), stripe_colors[0])
    draw = ImageDraw.Draw(img)
    band_h = H / len(stripe_colors)
    for i, c in enumerate(stripe_colors):
        draw.rectangle([0, i * band_h, W, (i + 1) * band_h + 1], fill=c)
    random.seed(9)
    for _ in range(14):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(3, 6)
        draw.ellipse([x - r, y - r, x + r, y + r], fill="white")
    return img

def add_notebook_lines(img, spacing=32, color=(120, 120, 150, 70), margin=40):
    """Overlays faint horizontal ruled lines on top of any background image."""
    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    y = margin
    while y < H - 10:
        draw.line([(margin, y), (W - margin, y)], fill=color, width=1)
        y += spacing
    combined = Image.alpha_composite(img, overlay)
    return combined.convert("RGB")

def add_ruled_lines(text_widget, color="black"):
    """Draws thin horizontal rule lines directly on top of a Text widget,
    spaced to match its font's line height, so it looks like ruled
    notebook paper and typed text sits right on the lines.
    Safe to call again (e.g. after a resize or font change) — old lines
    are removed first."""
    text_widget.update_idletasks()

    # remove any lines drawn previously
    for ln in getattr(text_widget, "_ruled_lines", []):
        ln.destroy()
    text_widget._ruled_lines = []

    try:
        f = tkFont.Font(font=text_widget.cget("font"))
        line_height = f.metrics("linespace")
    except Exception:
        line_height = 20

    height = text_widget.winfo_height()
    if height <= 1 or line_height <= 0:
        return  # widget not laid out yet

    y = line_height
    while y < height:
        ln = tk.Frame(text_widget.master, bg=color, height=1,
                       bd=0, highlightthickness=0)
        # place it positioned relative to the text widget itself, on top of it
        ln.place(in_=text_widget, x=0, y=y, relwidth=1.0, height=1)
        text_widget._ruled_lines.append(ln)
        y += line_height

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def generate_pastel_bg(top_hex, bottom_hex, dot_hexes, seed):
    """Generic soft pastel background: a vertical gradient with a
    scattering of translucent-looking pastel circles on top."""
    top = _hex_to_rgb(top_hex)
    bottom = _hex_to_rgb(bottom_hex)
    img = Image.new("RGB", (W, H), top_hex)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=_lerp_color(top, bottom, t))
    random.seed(seed)
    for _ in range(24):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(12, 40)
        color = random.choice(dot_hexes)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return img

def generate_lavender_bg():
    return generate_pastel_bg("#E9DFFF", "#D8C6FF",
                               ["#F3E8FF", "#FFFFFF", "#E0CFFF", "#F9F0FF"], 11)

def generate_mint_bg():
    return generate_pastel_bg("#DFFFEA", "#C6FFE0",
                               ["#E8FFF0", "#FFFFFF", "#CFFFE4", "#F0FFF6"], 12)

def generate_peach_bg():
    return generate_pastel_bg("#FFE8D6", "#FFD3B0",
                               ["#FFF0E0", "#FFFFFF", "#FFDCC0", "#FFF5EC"], 13)

def generate_skyblue_bg():
    return generate_pastel_bg("#DDF3FF", "#C2E9FF",
                               ["#EAF8FF", "#FFFFFF", "#D0EEFF", "#F2FBFF"], 14)

def generate_lemon_bg():
    return generate_pastel_bg("#FFFBD6", "#FFF5B0",
                               ["#FFFDE8", "#FFFFFF", "#FFF6C0", "#FFFCEF"], 15)

def generate_sunset_bg():
    return generate_pastel_bg("#FFE3EC", "#FFC9E0",
                               ["#FFEFF5", "#FFFFFF", "#FFD6E8", "#FFF5FA"], 16)

SOFT_PINK_PAGE_COLOR = "#FFDCEA"

def generate_main_page_soft_pink_bg():
    """A calm, flat soft-pink background for the writing pages — a single
    solid color (no gradient, no dots), so any label with a matching
    background (like the cat art) blends in perfectly with no visible box
    behind it."""
    return Image.new("RGB", (W, H), SOFT_PINK_PAGE_COLOR)

BACKGROUND_THEMES = {
    "Blue sky☁️": generate_sky_clouds_bg,
    "Pink haerts💗": generate_pink_hearts_bg,
    " Colorful sweets 🍭": generate_pastel_candies_bg,
    " Cute bubles 🫧": generate_bubbles_bg,
    " Flowers 🌸": generate_flowers_bg,
    " Night sky 🌙": generate_starry_bg,
    " Colorful rainbow 🌈": generate_rainbow_stripes_bg,
    " Light Purple 💜": generate_lavender_bg,
    " Light green 🌿": generate_mint_bg,
    "Light orenge  🍑": generate_peach_bg,
    "Light blue  💙": generate_skyblue_bg,
    "Light yellow  🍋": generate_lemon_bg,
    " Afternoon mood  🌇": generate_sunset_bg,
}

def apply_background(generator_func):
    global bg_image_tk
    img = generator_func()
    #img = add_notebook_lines(img)
    bg_image_tk = ImageTk.PhotoImage(img)
    bg_label.configure(image=bg_image_tk)
    bg_label.lower()

def apply_background_image(img):
    """Same as apply_background, but takes an already-built PIL image
    directly (used for a picture picked from the user's own device)."""
    global bg_image_tk
    bg_image_tk = ImageTk.PhotoImage(img)
    bg_label.configure(image=bg_image_tk)
    bg_label.lower()

def choose_custom_background_from_device(parent_window=None):
    """Lets the person pick any picture from their computer and use it as
    the notebook's background, resized/cropped so it fills the page
    (W x H) exactly without stretching out of proportion."""
    path = filedialog.askopenfilename(
        title="Choose a picture for background",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("All files", "*.*"),
        ],
    )
    if not path:
        return
    try:
        img = Image.open(path).convert("RGB")
        img_ratio = img.width / img.height
        target_ratio = W / H
        if img_ratio > target_ratio:
            new_h = H
            new_w = int(H * img_ratio)
        else:
            new_w = W
            new_h = int(W / img_ratio)
        img = img.resize((new_w, new_h))
        left = (new_w - W) // 2
        top = (new_h - H) // 2
        img = img.crop((left, top, left + W, top + H))
    except Exception:
        cute_error("Oops!", "Picture has not uploaded.Try again.")
        return

    apply_background_image(img)
    if parent_window is not None:
        parent_window.destroy()

def choose_background():
    """Opens a small menu of built-in cute background themes to choose from,
    plus a button to pick any picture straight from the user's device."""
    theme_win = tk.Toplevel(root)
    theme_win.title(" Choose Background")
    theme_win.geometry("320x700")
    theme_win.configure(bg="#FFF6FA")

    tk.Label(
        theme_win, text="🎀 Choose Background :)", font=("Arial", 13, "bold"),
        bg="#FFF6FA", fg="#B24A72"
    ).pack(pady=10)

    make_button(
        theme_win, "  Choose Picture From System  ",
        lambda w=theme_win: choose_custom_background_from_device(w),
        bg="#7FC7FF", fg="white", font=("Arial", 13)
    ).pack(pady=(0, 10), padx=20, fill="x")

    _theme_palette = ["#FF9FBB", "#B983FF", "#FFD166", "#8FE0B0", "#7FC7FF", "#FF8C69"]
    for i, (name, func) in enumerate(BACKGROUND_THEMES.items()):
        make_button(
            theme_win, name,
            lambda f=func, w=theme_win: (apply_background(f), w.destroy()),
            bg=_theme_palette[i % len(_theme_palette)], fg="white", font=("Arial", 13)
        ).pack(pady=6, padx=20, fill="x")

# Give the writing page the same soft pink background as the main page by default
_default_bg = generate_main_page_soft_pink_bg()
bg_image_tk = ImageTk.PhotoImage(_default_bg)
bg_label.configure(image=bg_image_tk)
bg_label.lower()

# Give the welcome page a soft, pastel, cute-sticker vibe right from the start
_welcome_bg_img = ImageTk.PhotoImage(generate_pink_hearts_bg())
welcome_bg_label.configure(image=_welcome_bg_img)
welcome_bg_label.lower()

# Give the main (home) page a soft, calm pink background
_main_bg_img = ImageTk.PhotoImage(generate_main_page_soft_pink_bg())
main_bg_label.configure(image=_main_bg_img)
main_bg_label.lower()

# ===================== Create New Page =====================
def create_page(current_page=None):
    # a plain, fixed-size frame — no Canvas wrapper, so the page itself
    # never scrolls. Only its Text widget (below) gets a scrollbar.
    page = tk.Frame(container, bg="white", width=W, height=H)
    page.place(x=0, y=0, relwidth=1, relheight=1)
    page_inner = page

    # each new page also gets its own background image, matching the current one
    page_bg_label = tk.Label(page_inner, bd=0)
    page_bg_label.place(x=0, y=0, width=W, height=H)
    if bg_image_tk is not None:
        page_bg_label.configure(image=bg_image_tk)
    page_bg_label.lower()

    # The text box keeps its original position, and — like the main writing
    # page — its pixel size is fixed (TEXTBOX_W x TEXTBOX_H), so changing
    # font size in "Features" only changes the ruled-line spacing and the
    # size of the pencil/writing itself, never the box or the page around it.
    txt_frame, txt_title_entry, txt = make_titled_text_box(
        page_inner,
        width=60,
        height=14,
        font=build_current_font(),
        fg=selected_color,
        bg="white"
    )
    txt_frame.place(x=W // 2, y=int(H * 0.55), anchor="center", width=TEXTBOX_W, height=TEXTBOX_H)
    txt.bind("<Configure>", lambda e, w=txt: add_ruled_lines(w))
    add_ruled_lines(txt)

    # ---------- Top bar: Home · cute page title sticker · Favorites ----------
    make_button(
        page_inner, " Home", go_home, bg="#FFD1E3", fg="white", font=("Arial", 13)
    ).place(x=10, y=10)

    title_sticker = tk.Label(
        page_inner, text="🌷  New Page 🌷", font=("Arial", 13, "bold"),
        bg="#FFD6E8", fg="#B24A72", padx=12, pady=4
    )
    title_sticker.place(x=W // 2, y=22, anchor="center")

    fav_badge = make_favorite_badge(page_inner, bg=SOFT_PINK_PAGE_COLOR)
    fav_badge.place(x=440, y=48, anchor="w")
    make_button(
        page_inner, "Add To Favorites", lambda: add_to_favorites(txt, fav_badge), bg="#FF7FA8",
        fg="white", font=("Arial", 10)
    ).place(x=460, y=8)

    # ---------- Toolbar: one colorful icon per feature, evenly spaced ----------
    make_button(
        page_inner, "Image", lambda: insert_image_into_text(txt),
        bg="#FF9FBB", fg="white", font=("Arial", 12)
    ).place(x=12, y=95)
    voice_btn_new = make_button(
        page_inner, "🎙️ Voice", lambda: None,
        bg="pink", fg="white", font=("Arial", 12)
    )
    voice_btn_new.bind("<Button-1>", lambda e, b=voice_btn_new: insert_voice_text(txt, b))
    voice_btn_new.place(x=118, y=95)
    make_button(
        page_inner, "Highlight", lambda: open_highlight_picker(txt),
        bg="#FF7FA8", fg="white", font=("Arial", 12)
    ).place(x=232, y=95)
    make_button(
        page_inner, " Emoji", lambda: open_emoji_picker(txt),
        bg="#FF5C94", fg="white", font=("Arial", 12)
    ).place(x=350, y=95)
    make_button(
        page_inner, " Night", lambda: toggle_night_mode(txt, page_bg_label),
        bg="#E0417A", fg="white", font=("Arial", 12)
    ).place(x=465, y=95)

    # a tiny sparkly divider sitting just above the ruled paper, purely decorative
    tk.Label(
        page_inner, text="⋆⁺₊⋆ ☁️ ⋆⁺₊⋆", font=("Arial", 9),
        bg=SOFT_PINK_PAGE_COLOR, fg="#FFB6D9"
    ).place(x=W // 2, y=148, anchor="center")

    # ---------- Bottom bar: Save · Next Page ----------
    make_button(
        page_inner, "Save", lambda: save_text(txt), bg="#C2185B", fg="white", font=("Arial", 14)
    ).place(x=25, y=420)
    make_button(
        page_inner, "Next Page ➜", lambda: create_page(page), bg="#A01050", fg="white", font=("Arial", 14)
    ).place(x=420, y=450)

    show_page(page)

# ===================== Emoji Picker =====================
EMOJI_LIST = [
    "😀", "😂", "🥰", "😍", "😊", "😉", "😎", "🥳", "😴", "😭",
    "❤️", "💕", "💗", "💖", "⭐", "✨", "🔥", "🌸", "🌈", "🍀",
    "🐱", "🐶", "🦋", "🌙", "☀️", "🍓", "🍩", "🎀", "📌", "✅",
]

def insert_emoji(text_widget, emoji, window):
    text_widget.insert(tk.INSERT, emoji)
    text_widget.focus_set()
    window.destroy()

def open_emoji_picker(text_widget):
    win = tk.Toplevel(root)
    win.title("😊 Choose Emoji")
    win.geometry("280x320")
    win.configure(bg="#FFF6FA")

    tk.Label(
        win, text="😊 Choose Emoji", font=("Arial", 13, "bold"),
        bg="#FFF6FA", fg="#B24A72"
    ).pack(pady=8)

    grid = tk.Frame(win, bg="#FFF6FA")
    grid.pack(padx=10, pady=5)

    cols = 6
    for i, emo in enumerate(EMOJI_LIST):
        lbl = tk.Label(
            grid, text=emo, font=("Arial", 18), bg="#FFE4EC", cursor="hand2",
            padx=4, pady=4, highlightthickness=1, highlightbackground="#FFD6E8"
        )
        lbl.grid(row=i // cols, column=i % cols, padx=3, pady=3)
        lbl.bind("<Button-1>", lambda e, em=emo: insert_emoji(text_widget, em, win))
        lbl.bind("<Enter>", lambda e, w=lbl: w.configure(bg="#FFB6D9"))
        lbl.bind("<Leave>", lambda e, w=lbl: w.configure(bg="#FFE4EC"))

# ===================== Insert Image into Text =====================
def insert_image_into_text(text_widget):
    """Lets the person pick an image from their computer and drops it
    right into the writing area at the cursor's position. The raw image
    bytes are also kept (base64-encoded) alongside the widget so that, if
    this page gets saved, the picture is written into notes.json together
    with the text — not lost."""
    path = filedialog.askopenfilename(
        title="Choose a picture",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("All files", "*.*"),
        ],
    )
    if not path:
        return
    try:
        img = Image.open(path)
        img = img.convert("RGBA") if img.mode not in ("RGB", "RGBA") else img
        # keep it a reasonable size so it fits nicely inside the notebook page
        img.thumbnail((220, 220))
        photo = ImageTk.PhotoImage(img)
    except Exception:
        cute_error("Oops!", "We couldn't open this picture.")
        return

    # Tk garbage-collects PhotoImages with no live reference, so keep one
    # per text widget for as long as that widget exists.
    if not hasattr(text_widget, "_inserted_images"):
        text_widget._inserted_images = []
    text_widget._inserted_images.append(photo)

    # Keep the exact bytes of the (already resized) picture, keyed by the
    # internal image name Tk assigns it, so save_text() can bundle it into
    # the same note record as the surrounding text.
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode("ascii")
    if not hasattr(text_widget, "_image_data"):
        text_widget._image_data = {}

    img_name = text_widget.image_create(tk.INSERT, image=photo)
    text_widget._image_data[img_name] = b64_data

    text_widget.insert(tk.INSERT, "\n")
    text_widget.focus_set()

# ===================== Highlight (5 pastel colors) =====================
HIGHLIGHT_COLORS = ["#FFF3B0", "#FFD6E8", "#C9F2C7", "#C7E8FF", "#E5D4FF"]

def highlight_selected(text_widget, color, window=None):
    try:
        start = text_widget.index("sel.first")
        end = text_widget.index("sel.last")
    except tk.TclError:
        cute_warning("Nothing selected", "Please select some text first.")
        if window is not None:
            window.destroy()
        return
    tag_name = f"highlight_{color}"
    text_widget.tag_configure(tag_name, background=color)
    text_widget.tag_add(tag_name, start, end)
    if window is not None:
        window.destroy()

def open_highlight_picker(text_widget):
    win = tk.Toplevel(root)
    win.title("Highlight")
    win.geometry("300x130")
    win.configure(bg="#FFF6FA")

    tk.Label(
        win, text="🖍 Choose a highlighter     ", font=("Arial", 12, "bold"),
        bg="#FFF6FA", fg="#B24A72"
    ).pack(pady=10)

    swatch_row = tk.Frame(win, bg="#FFF6FA")
    swatch_row.pack(pady=5)

    for color in HIGHLIGHT_COLORS:
        sw = tk.Label(swatch_row, bg=color, width=4, height=2,
                       relief="flat", highlightthickness=2,
                       highlightbackground="#FFB6D9", cursor="hand2")
        sw.pack(side="left", padx=6)
        sw.bind("<Button-1>", lambda e, c=color: highlight_selected(text_widget, c, win))

# ===================== Timestamp Helper =====================
WEEKDAYS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}
# kept for backwards compatibility with older code paths / saved notes
PERSIAN_WEEKDAYS = WEEKDAYS

def get_timestamp_line():
    now = datetime.datetime.now()
    weekday = WEEKDAYS[now.weekday()]
    date_str = now.strftime("%Y/%m/%d")
    time_str = now.strftime("%H:%M")
    return f"🕐 {weekday}, {date_str} - {time_str}"

NOTES_FILE = "notes.json"

def load_notes():
    """Returns the list of saved notes, each a separate record:
    {id, date, weekday, time, content, color, size, segments}. Newest last."""
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

# ===================== Favorites Badge (cute pastel sticker) =====================
def make_favorite_badge(parent, bg="white"):
    """A small label that sits above the 'Add to Favorites' button and
    stays invisible (no text, no border, matches the page background)
    until something is actually added — then it turns into a cute pastel
    sticker for a couple of seconds to confirm it worked."""
    badge = tk.Label(
        parent, text="", font=("Arial", 11, "bold"),
        bg=bg, fg="#B24A72", padx=10, pady=4,
        highlightthickness=0, bd=0
    )
    badge._idle_bg = bg
    badge._hide_job = None
    return badge

def _flash_favorite_badge(badge):
    if badge is None:
        return
    badge.configure(
        text="💖 Added to Favorites!", bg="#FFD6E8",
        highlightbackground="#FF9FBB", highlightthickness=2
    )
    if getattr(badge, "_hide_job", None):
        try:
            badge.after_cancel(badge._hide_job)
        except Exception:
            pass

    def _hide():
        badge.configure(text="", bg=badge._idle_bg, highlightthickness=0)
        badge._hide_job = None

    badge._hide_job = badge.after(2500, _hide)

# ===================== Save Function =====================
def _serialize_text_widget(text_widget):
    """Walks the text widget from start to end and returns an ordered list
    of segments — {"type": "text", "content": ...} or
    {"type": "image", "data": <base64 png>} — in the exact order they
    appear. This is what lets a saved note be rebuilt later with any
    pictures sitting in exactly the same spot among the words."""
    segments = []
    image_map = getattr(text_widget, "_image_data", {})
    for key, value, _index in text_widget.dump("1.0", tk.END, text=True, image=True):
        if key == "text" and value:
            segments.append({"type": "text", "content": value})
        elif key == "image":
            b64_data = image_map.get(value)
            if b64_data:
                segments.append({"type": "image", "data": b64_data})
    return segments

def save_text(text_widget):
    try:
        content = text_widget.get("1.0", tk.END).strip()
        segments = _serialize_text_widget(text_widget)
        has_image = any(s["type"] == "image" for s in segments)

        if content or has_image:
            now = datetime.datetime.now()

            try:
                font_obj = tkFont.Font(font=text_widget.cget("font"))
                size = font_obj.actual("size")
                font_family = font_obj.actual("family")
                is_bold = font_obj.actual("weight") == "bold"
                is_italic = font_obj.actual("slant") == "italic"
                is_underline = bool(font_obj.actual("underline"))
            except Exception:
                size = selected_size
                font_family = selected_font_family
                is_bold = selected_bold
                is_italic = selected_italic
                is_underline = selected_underline

            title = ""
            get_title = getattr(text_widget, "_get_title", None)
            if callable(get_title):
                title = get_title()

            entry = {
                "id": now.strftime("%Y%m%d%H%M%S%f"),
                "date": now.strftime("%Y/%m/%d"),
                "weekday": WEEKDAYS[now.weekday()],
                "time": now.strftime("%H:%M"),
                "content": content,
                "color": text_widget.cget("fg"),
                "size": size,
                "font_family": font_family,
                "bold": is_bold,
                "italic": is_italic,
                "underline": is_underline,
                "segments": segments,
                "title": title,
            }
            notes = load_notes()
            notes.append(entry)
            save_notes(notes)
            cute_info("Saved!", "Your note has been saved.")
        else:
            cute_warning("Nothing to save", "Write something first, then try saving again.")
    except Exception:
        cute_error("Oops!", "Your note could not be saved.")

def add_to_favorites(text_widget, badge=None):
    """Saves whatever is currently written in text_widget as a note,
    marked as a favorite, and flashes the little pastel sticker above the
    button to confirm it."""
    try:
        content = text_widget.get("1.0", tk.END).strip()
        segments = _serialize_text_widget(text_widget)
        has_image = any(s["type"] == "image" for s in segments)

        if not content and not has_image:
            cute_warning("Nothing to add", "Write something first, then add it to your favorites.")
            return

        now = datetime.datetime.now()

        try:
            font_obj = tkFont.Font(font=text_widget.cget("font"))
            size = font_obj.actual("size")
            font_family = font_obj.actual("family")
            is_bold = font_obj.actual("weight") == "bold"
            is_italic = font_obj.actual("slant") == "italic"
            is_underline = bool(font_obj.actual("underline"))
        except Exception:
            size = selected_size
            font_family = selected_font_family
            is_bold = selected_bold
            is_italic = selected_italic
            is_underline = selected_underline

        title = ""
        get_title = getattr(text_widget, "_get_title", None)
        if callable(get_title):
            title = get_title()

        entry = {
            "id": now.strftime("%Y%m%d%H%M%S%f"),
            "date": now.strftime("%Y/%m/%d"),
            "weekday": WEEKDAYS[now.weekday()],
            "time": now.strftime("%H:%M"),
            "content": content,
            "color": text_widget.cget("fg"),
            "size": size,
            "font_family": font_family,
            "bold": is_bold,
            "italic": is_italic,
            "underline": is_underline,
            "segments": segments,
            "title": title,
            "favorite": True,
        }
        notes = load_notes()
        notes.append(entry)
        save_notes(notes)
        _flash_favorite_badge(badge)
    except Exception:
        cute_error("Oops!", "This could not be added to your favorites.")

# ===================== Night Mode =====================
def apply_night_mode(text_widget, page_bg_label, enable):
    if enable:
        dark_img = Image.new("RGB", (W, H), "#14141f")
        photo = ImageTk.PhotoImage(dark_img)
        page_bg_label._dark_photo = photo  # keep a reference alive
        page_bg_label.configure(image=photo)
        text_widget.configure(bg="#1e1e2e", fg="#f5f5f5", insertbackground="white")
        add_ruled_lines(text_widget, color="#5a5a6e")
    else:
        if bg_image_tk is not None:
            page_bg_label.configure(image=bg_image_tk)
        text_widget.configure(bg="white", fg=selected_color, insertbackground="black")
        add_ruled_lines(text_widget, color="black")

def toggle_night_mode(text_widget, page_bg_label):
    current = getattr(text_widget, "_night_mode", False)
    new_state = not current
    text_widget._night_mode = new_state
    apply_night_mode(text_widget, page_bg_label, new_state)

# ===================== Color & Size =====================
# A curated palette (not just a single "click for the OS color dialog"
# button), with a live preview and a "Custom Color..." escape hatch for
# anyone who wants a color outside the palette.
PRESET_COLORS = [
    ("Blush Pink", "#FF6FA5"), ("Hot Pink", "#FF1493"), ("Rose", "#E75480"),
    ("Coral", "#FF7F50"), ("Sunset Orange", "#FF6B35"), ("Golden", "#FFB700"),
    ("Lemon", "#FFD93D"), ("Lime", "#B4E600"), ("Mint", "#00D9A6"),
    ("Teal", "#00B4B4"), ("Sky Blue", "#4CC9F0"), ("Ocean Blue", "#0077B6"),
    ("Periwinkle", "#7B7FFF"), ("Lavender", "#B983FF"), ("Grape", "#8E44AD"),
    ("Berry", "#C2185B"), ("Chocolate", "#8B5E3C"), ("Charcoal", "#3A3A3A"),
    ("Slate", "#5B6B7C"), ("Forest", "#2E7D32"),
]

def choose_color():
    global selected_color

    picker = tk.Toplevel(root)
    picker.title("🎨 Choose Your Pen Color")
    picker.geometry("340x520")
    picker.configure(bg="#FFF6FA")
    picker.resizable(False, False)

    tk.Label(
        picker, text="Pick a pen color", font=("Arial", 15, "bold"),
        bg="#FFF6FA", fg="#FF69B4"
    ).pack(pady=(14, 4))

    preview_frame = tk.Frame(picker, bg="#FFF0F5", highlightbackground="#FFD6E8",
                              highlightthickness=1)
    preview_frame.pack(fill="x", padx=20, pady=10)
    preview_label = tk.Label(
        preview_frame, text="Aa Bb Cc  —  example text✒️",
        font=("Arial", 16), bg="#FFF0F5", fg=selected_color
    )
    preview_label.pack(pady=14)

    grid = tk.Frame(picker, bg="#FFF6FA")
    grid.pack(padx=16, pady=6)

    current_choice = {"value": selected_color}
    swatch_widgets = []

    def pick(hex_color):
        current_choice["value"] = hex_color
        preview_label.configure(fg=hex_color)
        for sw, c in swatch_widgets:
            sw.configure(
                highlightthickness=3 if c == hex_color else 1,
                highlightbackground="#FF69B4" if c == hex_color else "#ddd",
            )

    cols = 5
    for i, (name, hex_color) in enumerate(PRESET_COLORS):
        sw = tk.Label(
            grid, bg=hex_color, width=4, height=2, relief="flat",
            highlightthickness=1, highlightbackground="#ddd", cursor="hand2"
        )
        sw.grid(row=i // cols, column=i % cols, padx=6, pady=6)
        sw.bind("<Button-1>", lambda e, c=hex_color: pick(c))
        swatch_widgets.append((sw, hex_color))

    def open_custom():
        c = colorchooser.askcolor(color=current_choice["value"], title="Custom Color")[1]
        if c:
            pick(c)

    make_button(
        picker, "🌈 Custom Color…", open_custom, bg="#E5D4FF", fg="#5B4B8A",
        font=("Arial", 12)
    ).pack(pady=(10, 4), padx=20, fill="x")

    def apply_and_close():
        global selected_color
        selected_color = current_choice["value"]
        picker.destroy()

    make_button(
        picker, "✓ Use This Color", apply_and_close, font=("Arial", 13)
    ).pack(pady=12, padx=20, fill="x")

# ===================== Features (font size, pen/font family, style) =====================
# Font "pen" choices — each one gives the writing a different feel.
FONT_CHOICES = [
    ("✒️ Classic", "Arial"),
    ("✏️ Handwritten", "Comic Sans MS"),
    ("⌨️ Typewriter", "Courier New"),
    ("🖋 Formal", "Times New Roman"),
    ("📖 Storybook", "Georgia"),
    ("🧊 Modern", "Verdana"),
]

selected_font_family = "Arial"
selected_bold = False
selected_italic = False
selected_underline = False

def build_current_font():
    """Builds the tkinter font tuple for whatever pen/size/style is
    currently selected, ready to hand straight to a widget's font=..."""
    style_parts = []
    if selected_bold:
        style_parts.append("bold")
    if selected_italic:
        style_parts.append("italic")
    if selected_underline:
        style_parts.append("underline")
    if style_parts:
        return (selected_font_family, selected_size, " ".join(style_parts))
    return (selected_font_family, selected_size)

def open_size_window():
    """The 'features' panel: font size, pen/font style, and
    bold/italic/underline toggles, all with a live preview."""
    global selected_size, selected_font_family, selected_bold, selected_italic, selected_underline

    win = tk.Toplevel(root)
    win.title("✨ Features")
    win.geometry("360x640")
    win.configure(bg="#FFF6FA")
    win.resizable(False, False)

    tk.Label(
        win, text="✨ Features", font=("Arial", 15, "bold"),
        bg="#FFF6FA", fg="#FF69B4"
    ).pack(pady=(14, 4))

    preview_frame = tk.Frame(win, bg="#FFF0F5", highlightbackground="#FFD6E8", highlightthickness=1)
    preview_frame.pack(fill="x", padx=20, pady=8)
    preview_label = tk.Label(preview_frame, text="Aa Bb Cc — example text", bg="#FFF0F5", fg=selected_color)
    preview_label.pack(pady=16)

    # local working copy — only committed to the real globals when
    # "OK" is pressed
    state = {
        "size": selected_size,
        "family": selected_font_family,
        "bold": selected_bold,
        "italic": selected_italic,
        "underline": selected_underline,
    }

    def _font_tuple():
        parts = []
        if state["bold"]:
            parts.append("bold")
        if state["italic"]:
            parts.append("italic")
        if state["underline"]:
            parts.append("underline")
        return (state["family"], state["size"], " ".join(parts)) if parts else (state["family"], state["size"])

    def refresh_preview():
        try:
            preview_label.configure(font=_font_tuple())
        except Exception:
            preview_label.configure(font=(state["family"], state["size"]))

    # ---- Font size ----
    tk.Label(win, text="Size", font=("Arial", 12, "bold"), bg="#FFF6FA", fg="#B98CA6").pack(anchor="w", padx=20, pady=(6, 2))
    size_row = tk.Frame(win, bg="#FFF6FA")
    size_row.pack(padx=16, pady=2)
    sizes = [12, 14, 16, 18, 20, 22, 24, 28]
    size_buttons = []

    def pick_size(s):
        state["size"] = s
        for b, sz in size_buttons:
            b.configure(bg="#FF69B4" if sz == s else "#FFE4EC", fg="white" if sz == s else "#333333")
        refresh_preview()

    for i, s in enumerate(sizes):
        b = make_button(size_row, f"{s}", lambda x=s: pick_size(x), bg="#FFE4EC", fg="#333333", font=("Arial", 11))
        b.grid(row=i // 4, column=i % 4, padx=4, pady=4)
        size_buttons.append((b, s))
    pick_size(state["size"])

    # ---- Pen / font family ----
    tk.Label(win, text="🖊 Font", font=("Arial", 12, "bold"), bg="#FFF6FA", fg="#B98CA6").pack(anchor="w", padx=20, pady=(12, 2))
    family_row = tk.Frame(win, bg="#FFF6FA")
    family_row.pack(padx=16, pady=2, fill="x")
    family_row.grid_columnconfigure(0, weight=1)
    family_row.grid_columnconfigure(1, weight=1)
    family_buttons = []

    def pick_family(fam):
        state["family"] = fam
        for b, f in family_buttons:
            b.configure(bg="#FF69B4" if f == fam else "#FFE4EC", fg="white" if f == fam else "#333333")
        refresh_preview()

    for i, (label, fam) in enumerate(FONT_CHOICES):
        b = make_button(family_row, label, lambda x=fam: pick_family(x), bg="#FFE4EC", fg="#333333", font=(fam, 11))
        b.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="ew")
        family_buttons.append((b, fam))
    pick_family(state["family"])

    # ---- Style toggles ----
    tk.Label(win, text="Style", font=("Arial", 12, "bold"), bg="#FFF6FA", fg="#B98CA6").pack(anchor="w", padx=20, pady=(12, 2))
    style_row = tk.Frame(win, bg="#FFF6FA")
    style_row.pack(padx=16, pady=2)

    def make_toggle(parent, text, key):
        def toggle():
            state[key] = not state[key]
            btn.configure(bg="#FF69B4" if state[key] else "#FFE4EC", fg="white" if state[key] else "#333333")
            refresh_preview()
        btn = make_button(
            parent, text, toggle,
            bg="#FF69B4" if state[key] else "#FFE4EC",
            fg="white" if state[key] else "#333333",
            font=("Arial", 12)
        )
        return btn

    make_toggle(style_row, "B  Bold", "bold").pack(side="left", padx=4)
    make_toggle(style_row, "I  Italic", "italic").pack(side="left", padx=4)
    make_toggle(style_row, "U  Underline", "underline").pack(side="left", padx=4)

    refresh_preview()

    def apply_and_close():
        global selected_size, selected_font_family, selected_bold, selected_italic, selected_underline
        selected_size = state["size"]
        selected_font_family = state["family"]
        selected_bold = state["bold"]
        selected_italic = state["italic"]
        selected_underline = state["underline"]
        win.destroy()

    make_button(win, "✓ OK", apply_and_close, font=("Arial", 13)).pack(pady=16, padx=20, fill="x")

# ===================== Start Writing =====================
def start_writing():
    text_area.configure(fg=selected_color, font=build_current_font())
    show_page(write_page)
    add_ruled_lines(text_area)

text_area.bind("<Configure>", lambda e: add_ruled_lines(text_area))

# ===================== Notes Page (view saved notes, grouped by date) =====================
def _note_preview(content, limit=40):
    """A short one-line preview of a note's content for its list row."""
    snippet = content.replace("\n", " ").strip()
    if len(snippet) > limit:
        snippet = snippet[:limit] + "…"
    return snippet

def _readable_note_color(color_value):
    """The note viewer window always has a plain white background, so a
    very pale saved pen color (like the default 'light pink') can end up
    almost invisible there even though it looked fine on a colored/
    patterned page background. If the stored color is too close to white
    to read comfortably, fall back to a soft, readable dark color instead
    — this is what makes sure your writing always actually shows up when
    you open a note."""
    try:
        r, g, b = root.winfo_rgb(color_value)
        r, g, b = r / 65535, g / 65535, b / 65535
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        if luminance > 0.75:
            return "#7A5C68"
    except Exception:
        pass
    return color_value

def open_note_detail(note):
    """Opens ONE note, on its own, in a small window — never mixed with
    other notes. It's rebuilt using the exact pen color and font size the
    note was written with, and any pictures that were saved with it are
    dropped back in at the same spot."""
    note_title = note.get("title") or "Untitled"

    win = tk.Toplevel(root)
    win.title(f"{note_title} — {note.get('date','')} {note.get('time','')}")
    win.geometry("420x470")
    win.configure(bg="#FFF6FA")

    tk.Label(
        win, text=f"📝 {note_title}",
        font=("Arial", 15, "bold"), bg="#FFF6FA", fg="#FF69B4"
    ).pack(pady=(14, 2))
    tk.Label(
        win, text=f"🕐 {note.get('weekday','')}, {note.get('date','')} - {note.get('time','')}",
        font=("Arial", 11), bg="#FFF6FA", fg="#B98CA6"
    ).pack(pady=(0, 8))

    note_color = _readable_note_color(note.get("color") or "black")
    note_size = note.get("size") or 14
    note_family = note.get("font_family") or "Arial"
    style_parts = []
    if note.get("bold"):
        style_parts.append("bold")
    if note.get("italic"):
        style_parts.append("italic")
    if note.get("underline"):
        style_parts.append("underline")
    note_font = (note_family, note_size, " ".join(style_parts)) if style_parts else (note_family, note_size)

    body_frame, body_text = make_text_box(
        win, width=44, height=16,
        fg=note_color, font=note_font, bg="white"
    )
    body_frame.pack(padx=15, pady=8, fill="both", expand=True)

    segments = note.get("segments")
    if segments:
        body_text._detail_images = []  # keep PhotoImage references alive
        for seg in segments:
            if seg["type"] == "text":
                body_text.insert(tk.END, seg["content"])
            elif seg["type"] == "image":
                try:
                    raw = base64.b64decode(seg["data"])
                    img = Image.open(io.BytesIO(raw))
                    photo = ImageTk.PhotoImage(img)
                    body_text._detail_images.append(photo)
                    body_text.image_create(tk.END, image=photo)
                except Exception:
                    pass
    else:
        # notes saved before this feature existed only have plain content
        body_text.insert("1.0", note.get("content", ""))

    body_text.configure(state="disabled")  # read-only viewer for this one note

    make_button(
        win, "❌ Close", win.destroy, bg="#FF9FBB", fg="white", font=("Arial", 12)
    ).pack(pady=10)

notes_page = tk.Frame(container, bg="#FFF9FC")
notes_page.place(x=0, y=0, relwidth=1, relheight=1)

notes_top_bar = tk.Frame(notes_page, bg="#FFD6E8")
notes_top_bar.pack(fill="x")

make_button(
    notes_top_bar, "🏠 Home", lambda: show_page(main_page),
    bg="pink", fg="white", font=("Arial", 13)
).pack(side="left", padx=20, pady=14)
tk.Label(
    notes_top_bar, text="📚 My Notes", font=("Arial", 18, "bold"), bg="#FFD6E8", fg="#B24A72"
).pack(side="left", padx=20)

# The list of notes can grow long, so it gets its own ordinary scrollable
# area — this is just a browsing list, not the writing box, so scrolling
# the whole list here is expected and fine.
notes_canvas = tk.Canvas(notes_page, bg="#FFF9FC", highlightthickness=0)
notes_list_scrollbar = ttk.Scrollbar(
    notes_page, orient="vertical",
    style="Notebook.Vertical.TScrollbar", command=notes_canvas.yview
)
notes_canvas.configure(yscrollcommand=notes_list_scrollbar.set)
notes_list_scrollbar.pack(side="right", fill="y")
notes_canvas.pack(side="left", fill="both", expand=True, padx=20, pady=10)

notes_list_inner = tk.Frame(notes_canvas, bg="#FFF9FC")
notes_canvas_window = notes_canvas.create_window((0, 0), window=notes_list_inner, anchor="nw")

def _update_notes_scrollregion(event=None):
    notes_canvas.configure(scrollregion=notes_canvas.bbox("all"))
notes_list_inner.bind("<Configure>", _update_notes_scrollregion)

def _notes_canvas_width(event):
    notes_canvas.itemconfig(notes_canvas_window, width=event.width)
notes_canvas.bind("<Configure>", _notes_canvas_width)

def _notes_wheel(event):
    num = getattr(event, "num", None)
    if num == 4:
        notes_canvas.yview_scroll(-2, "units")
    elif num == 5:
        notes_canvas.yview_scroll(2, "units")
    else:
        delta = getattr(event, "delta", 0)
        if delta:
            notes_canvas.yview_scroll(int(-1 * (delta / 40)), "units")

def _bind_notes_wheel(_e=None):
    notes_canvas.bind_all("<MouseWheel>", _notes_wheel)
    notes_canvas.bind_all("<Button-4>", _notes_wheel)
    notes_canvas.bind_all("<Button-5>", _notes_wheel)

def _unbind_notes_wheel(_e=None):
    notes_canvas.unbind_all("<MouseWheel>")
    notes_canvas.unbind_all("<Button-4>")
    notes_canvas.unbind_all("<Button-5>")

notes_canvas.bind("<Enter>", _bind_notes_wheel)
notes_canvas.bind("<Leave>", _unbind_notes_wheel)

def show_notes_page():
    # rebuild the list every time the page is opened, so it's always current
    for child in notes_list_inner.winfo_children():
        child.destroy()

    notes = load_notes()

    if not notes:
        tk.Label(
            notes_list_inner, text="🌸 No notes yet — start writing to fill this page!",
            font=("Arial", 13), bg="#FFF9FC", fg="#B98CA6"
        ).pack(pady=20)
    else:
        # group notes by their title now, instead of by date — each named
        # note gets its own section, newest section (by its most recent
        # entry) first, newest entry first inside each section
        groups = {}
        for note in notes:
            key = note.get("title") or "No title"
            groups.setdefault(key, []).append(note)

        def _group_sort_key(group_key):
            return max(f"{n['date']} {n['time']}" for n in groups[group_key])

        for group_title in sorted(groups.keys(), key=_group_sort_key, reverse=True):
            group_notes = sorted(
                groups[group_title], key=lambda n: f"{n['date']} {n['time']}", reverse=True
            )

            tk.Label(
                notes_list_inner, text=f"📝 {group_title}",
                font=("Arial", 14, "bold"), bg="#FFF9FC", fg="#FF69B4"
            ).pack(anchor="w", pady=(14, 4), padx=6)

            for note in group_notes:
                row = tk.Frame(
                    notes_list_inner, bg="#FFE8F0", highlightthickness=2,
                    highlightbackground="#FFB6D9", cursor="hand2"
                )
                row.pack(fill="x", padx=6, pady=4)

                has_pic = any(s.get("type") == "image" for s in note.get("segments", []))

                has_fav = bool(note.get("favorite"))
                row_label = tk.Label(
                    row,
                    text=f"📅 {note['weekday']}, {note['date']} - {note['time']}"
                         + ("  🖼" if has_pic else "")
                         + ("  💖" if has_fav else ""),
                    font=("Arial", 12), bg="#FFE8F0", fg="#7A5C68", anchor="w", justify="left"
                )
                row_label.pack(side="left", fill="x", expand=True, padx=10, pady=8)

                make_button(
                    row, "🗑 Delete",
                    lambda n=note: delete_note_and_refresh(n, show_notes_page),
                    bg="#FF6FA5", fg="white", font=("Arial", 10)
                ).pack(side="right", padx=8, pady=6)

                # clicking a row opens ONLY that note, never all of them together
                row.bind("<Button-1>", lambda e, n=note: open_note_detail(n))
                row_label.bind("<Button-1>", lambda e, n=note: open_note_detail(n))

    notes_canvas.yview_moveto(0)
    show_page(notes_page)

# ===================== Favorites Page (only notes marked 💖) =====================
favorites_page = tk.Frame(container, bg="#FFF6FA")
favorites_page.place(x=0, y=0, relwidth=1, relheight=1)

favorites_top_bar = tk.Frame(favorites_page, bg="#FFC7DA")
favorites_top_bar.pack(fill="x")

make_button(
    favorites_top_bar, "🏠 Home", lambda: show_page(main_page),
    bg="pink", fg="white", font=("Arial", 13)
).pack(side="left", padx=20, pady=14)
tk.Label(
    favorites_top_bar, text=" My Favorites", font=("Arial", 18, "bold"), bg="#FFC7DA", fg="#B2295E"
).pack(side="left", padx=20)

favorites_canvas = tk.Canvas(favorites_page, bg="#FFF6FA", highlightthickness=0)
favorites_list_scrollbar = ttk.Scrollbar(
    favorites_page, orient="vertical",
    style="Notebook.Vertical.TScrollbar", command=favorites_canvas.yview
)
favorites_canvas.configure(yscrollcommand=favorites_list_scrollbar.set)
favorites_list_scrollbar.pack(side="right", fill="y")
favorites_canvas.pack(side="left", fill="both", expand=True, padx=20, pady=10)

favorites_list_inner = tk.Frame(favorites_canvas, bg="#FFF6FA")
favorites_canvas_window = favorites_canvas.create_window((0, 0), window=favorites_list_inner, anchor="nw")

def _update_favorites_scrollregion(event=None):
    favorites_canvas.configure(scrollregion=favorites_canvas.bbox("all"))
favorites_list_inner.bind("<Configure>", _update_favorites_scrollregion)

def _favorites_canvas_width(event):
    favorites_canvas.itemconfig(favorites_canvas_window, width=event.width)
favorites_canvas.bind("<Configure>", _favorites_canvas_width)

def _favorites_wheel(event):
    num = getattr(event, "num", None)
    if num == 4:
        favorites_canvas.yview_scroll(-2, "units")
    elif num == 5:
        favorites_canvas.yview_scroll(2, "units")
    else:
        delta = getattr(event, "delta", 0)
        if delta:
            favorites_canvas.yview_scroll(int(-1 * (delta / 40)), "units")

def _bind_favorites_wheel(_e=None):
    favorites_canvas.bind_all("<MouseWheel>", _favorites_wheel)
    favorites_canvas.bind_all("<Button-4>", _favorites_wheel)
    favorites_canvas.bind_all("<Button-5>", _favorites_wheel)

def _unbind_favorites_wheel(_e=None):
    favorites_canvas.unbind_all("<MouseWheel>")
    favorites_canvas.unbind_all("<Button-4>")
    favorites_canvas.unbind_all("<Button-5>")

favorites_canvas.bind("<Enter>", _bind_favorites_wheel)
favorites_canvas.bind("<Leave>", _unbind_favorites_wheel)

def show_favorites_page():
    # rebuild the list every time the page is opened, so it's always current
    for child in favorites_list_inner.winfo_children():
        child.destroy()

    notes = [n for n in load_notes() if n.get("favorite")]

    if not notes:
        tk.Label(
            favorites_list_inner, text="💗 No favorites yet — tap 💖 while writing to add one!",
            font=("Arial", 13), bg="#FFF6FA", fg="#B98CA6", wraplength=380, justify="center"
        ).pack(pady=20)
    else:
        notes_sorted = sorted(notes, key=lambda n: f"{n['date']} {n['time']}", reverse=True)

        for note in notes_sorted:
            row = tk.Frame(
                favorites_list_inner, bg="#FFE0EC", highlightthickness=2,
                highlightbackground="#FF9FBB", cursor="hand2"
            )
            row.pack(fill="x", padx=6, pady=4)

            has_pic = any(s.get("type") == "image" for s in note.get("segments", []))
            note_title = note.get("title") or "No title"

            row_label = tk.Label(
                row,
                text=f"💖 {note_title} — {note['weekday']}, {note['date']} - {note['time']}"
                     + ("  🖼" if has_pic else ""),
                font=("Arial", 12), bg="#FFE0EC", fg="#7A5C68", anchor="w", justify="left"
            )
            row_label.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            make_button(
                row, "🗑 Delete",
                lambda n=note: delete_note_and_refresh(n, show_favorites_page),
                bg="#FF6FA5", fg="white", font=("Arial", 10)
            ).pack(side="right", padx=8, pady=6)

            row.bind("<Button-1>", lambda e, n=note: open_note_detail(n))
            row_label.bind("<Button-1>", lambda e, n=note: open_note_detail(n))

    favorites_canvas.yview_moveto(0)
    show_page(favorites_page)

# ===================== Home =====================
home_date_label = tk.Label(
    main_buttons, text="", font=("Arial", 12, "bold"),
    bg="#FFD6E8", fg="#B24A72", padx=12, pady=4
)
home_date_label.place(x=W // 2, y=25, anchor="center")

home_stats_card = tk.Frame(
    main_buttons, bg="#FFFFFF", highlightbackground="#FF9FBB", highlightthickness=2, bd=0
)
home_stats_card.place(x=430, y=150, anchor="center")

home_stats_label = tk.Label(
    home_stats_card, text="", font=("Arial", 13, "bold"),
    bg="#FFFFFF", fg="#B24A72", justify="center"
)
home_stats_label.pack(padx=18, pady=12)

def update_home_widgets():
    """Refreshes the little date sticker and the notes/favorites stats
    card on the home page — called every time the home page is opened so
    the counts and the date are always current."""
    now = datetime.datetime.now()
    home_date_label.configure(
        text=f"🗓 {WEEKDAYS[now.weekday()]}, {now.strftime('%Y/%m/%d')}"
    )

    notes = load_notes()
    total = len(notes)
    favs = sum(1 for n in notes if n.get("favorite"))
    home_stats_label.configure(text=f"📝 {total} notes\n💖 {favs} favorites")

def go_home():
    update_home_widgets()
    show_page(main_page)

# ===================== Main Buttons =====================
make_button(
    main_buttons, " Choose the color", choose_color,
    bg="#FFC1DC", fg="white", font=("Arial", 18)
).place(x=20, y=65)
make_button(
    main_buttons, " Features", open_size_window,
    bg="#FF9FBB", fg="white", font=("Arial", 18)
).place(x=20, y=115)
make_button(
    main_buttons, "Background", choose_background,
    bg="#FF7FA8", fg="white", font=("Arial", 18)
).place(x=20, y=165)
make_button(
    main_buttons, " My Notes", show_notes_page,
    bg="#FF5C94", fg="white", font=("Arial", 18)
).place(x=20, y=215)
make_button(
    main_buttons, " Favorites", show_favorites_page,
    bg="#E0417A", fg="white", font=("Arial", 18)
).place(x=20, y=265)
make_button(
    main_buttons, " Start writing", start_writing,
    bg="#C2185B", fg="white", font=("Arial", 22, "bold")
).place(x=50, y=420)

'''for _txt, _x, _y, _sz in [
    ("🌸", 560, 60, 20), ("⭐", 30, 380, 18), ("🎀", 300, 200, 22),
    ("☁️", 560, 400, 18),
]:
    tk.Label(main_page, text=_txt, font=("Arial", _sz), bg="#FFF9FC").place(x=_x, y=_y)'''

cutelabel3 = tk.Label(
    main_buttons,
    text="⠀⠀\n⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀"
         "⠀\n⠀⠀⠀⢀⡴⣆⠀⠀⠀⠀⠀⣠⡀⠀⠀⠀⠀⠀⠀⣼⣿⡗⠀⠀⠀"
         "⠀\n⠀⣠⠟⠀⠘⠷⠶⠶⠶⠾⠉⢳⡄⠀⠀⠀⠀⠀⣧⣿⠀⠀⠀⠀⠀"
         "⠀\n⠀⣰⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣤⣤⣤⣤⣤⣿⢿⣄⠀⠀⠀⠀"
         "\n⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣧⠀⠀⠀⠀⠀⠀⠙⣷⡴⠶⣦"
         "⠀\n⠀⢱⡀⠀⠉⠉⠀⠀⠀⠀⠛⠃⠀⢠⡟⠀⠀⠀⢀⣀⣠⣤⠿⠞⠛⠋"
         "\n⣠⠾⠋⠙⣶⣤⣤⣤⣤⣤⣀⣠⣤⣾⣿⠴⠶⠚⠋⠉⠁⠀⠀⠀⠀⠀"
         "\n⠛⠒⠛⠉⠉⠀⠀⠀⣴⠟⢃⡴⠛⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
         "⠀\n⠀⠛⠛⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    font=("Arial", 14),
    bg=SOFT_PINK_PAGE_COLOR,
    fg="deep pink")
cutelabel3.place(x=300, y=310)

# ===================== Write Page Buttons =====================
tk.Label(
    write_inner, text="🌷  My notebook 🌷", font=("Arial", 13, "bold"),
    bg="#FFD6E8", fg="#B24A72", padx=12, pady=4
).place(x=W // 2, y=22, anchor="center")

make_button(write_inner, " Home", go_home, bg="#FFD1E3", fg="white", font=("Arial", 13)).place(x=10, y=10)
make_button(
    write_inner, "Next Page ➜", lambda: create_page(write_page),
    bg="#A01050", fg="white", font=("Arial", 13)
).place(x=420, y=450)
make_button(
    write_inner, " Save", lambda: save_text(text_area),
    bg="#FF5C94", fg="white", font=("Arial", 13)
).place(x=25, y=420)
make_button(
    write_inner, " Emoji", lambda: open_emoji_picker(text_area),
    bg="#FFB6D5", fg="white", font=("Arial", 12)
).place(x=350, y=95)
make_button(
    write_inner, " Highlight", lambda: open_highlight_picker(text_area),
    bg="#FF9FBB", fg="white", font=("Arial", 12)
).place(x=232, y=95)
make_button(
    write_inner, " Night", lambda: toggle_night_mode(text_area, bg_label),
    bg="#E0417A", fg="white", font=("Arial", 12)
).place(x=465, y=95)
make_button(
    write_inner, " Image", lambda: insert_image_into_text(text_area),
    bg="#FF7FA8", fg="white", font=("Arial", 12)
).place(x=12, y=95)
voice_btn_write = make_button(
    write_inner, "🎙️ Voice", lambda: None,
    bg="pink", fg="white", font=("Arial", 12)
)
voice_btn_write.bind("<Button-1>", lambda e, b=voice_btn_write: insert_voice_text(text_area, b))
voice_btn_write.place(x=118, y=95)

tk.Label(
    write_inner, text="⋆⁺₊⋆ ☁️ ⋆⁺₊⋆", font=("Arial", 9),
    bg=SOFT_PINK_PAGE_COLOR, fg="#FFB6D9"
).place(x=W // 2, y=148, anchor="center")

write_fav_badge = make_favorite_badge(write_inner, bg=SOFT_PINK_PAGE_COLOR)
write_fav_badge.place(x=350, y=25)
make_button(
    write_inner, " Add to Favorites", lambda: add_to_favorites(text_area, write_fav_badge),
    bg="#C2185B", fg="white", font=("Arial", 10)
).place(x=460, y=8)

# ===================== Start on Welcome Page =====================
show_page(welcome_page)

root.mainloop()