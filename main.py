import tkinter as tk
import os, json, random, threading, sys

SPLASH_W, SPLASH_H = 560, 400

WISDOMS = [
    "Весна - не лето. Салат - не котлета.",
    "Умный в гору не пойдёт, умный метнётся за пивом.",
    "Сделай в банке перевод - ты пчела я пчеловод.",
    "Душ не баня, помыл яйца, до свидание.",
]

THEMES = {
    'dark': {
        'bg_dark': '#181a1f', 'bg_panel': '#21252b', 'accent': '#667eea',
        'accent2': '#764ba2', 'text_primary': '#d7dae0', 'text_secondary': '#8b93a3',
        'track': '#2a2f3a',
    },
    'light': {
        'bg_dark': '#f2f3f5', 'bg_panel': '#ffffff', 'accent': '#667eea',
        'accent2': '#764ba2', 'text_primary': '#1e1e1e', 'text_secondary': '#555555',
        'track': '#dcdde1',
    },
}

def load_theme():
    name = 'dark'
    try:
        path = os.path.join(os.path.expanduser('~'), '.ruweb_settings.json')
        with open(path, 'r', encoding='utf-8') as f:
            name = json.load(f).get('theme', 'dark')
    except Exception:
        pass
    return THEMES.get(name, THEMES['dark'])


class Splash:
    def __init__(self, theme):
        self.tr = theme
        self.result = None
        self.error = None
        self.holder = {}
        self.progress = 0.0
        self.angle = 0

        self.root = tk.Tk()
        self.root.title("RuWeb Studio 2026")
        self.root.overrideredirect(True)          # без рамок и кнопок
        self.root.resizable(False, False)          # нельзя растянуть
        self.root.configure(bg=self.tr['bg_dark'])
        self.root.attributes('-topmost', True)

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - SPLASH_W) // 2
        y = (self.root.winfo_screenheight() - SPLASH_H) // 2
        self.root.geometry(f"{SPLASH_W}x{SPLASH_H}+{x}+{y}")

        self._build()

    def _build(self):
        tr = self.tr
        # логотип + название
        tk.Label(self.root, text="⚡", font=('Segoe UI', 34, 'bold'),
                 bg=tr['bg_dark'], fg=tr['accent']).pack(pady=(26, 0))
        tk.Label(self.root, text="RuWeb Studio 2026", font=('Segoe UI', 20, 'bold'),
                 bg=tr['bg_dark'], fg=tr['text_primary']).pack(pady=(2, 0))
        tk.Label(self.root, text="движок веб-разработки на русском", font=('Segoe UI', 10),
                 bg=tr['bg_dark'], fg=tr['text_secondary']).pack()

        # спиннер
        self.canvas = tk.Canvas(self.root, width=120, height=120,
                                bg=tr['bg_dark'], highlightthickness=0)
        self.canvas.pack(pady=(14, 0))

        # мудрость дня
        tk.Label(self.root, text="МУДРОСТЬ ДНЯ", font=('Segoe UI', 11, 'bold'),
                 bg=tr['bg_dark'], fg=tr['accent']).pack(pady=(12, 2))
        wisdom = random.choice(WISDOMS)
        self.wisdom_lbl = tk.Label(self.root, text=f"«{wisdom}»", font=('Segoe UI', 10, 'italic'),
                                   bg=tr['bg_dark'], fg=tr['text_secondary'],
                                   wraplength=SPLASH_W - 80, justify='center')
        self.wisdom_lbl.pack()

        # прогресс-бар
        self.bar = tk.Canvas(self.root, height=8, bg=tr['track'], highlightthickness=0)
        self.bar.pack(fill=tk.X, padx=50, pady=(16, 0))
        self.pct = tk.Label(self.root, text="0%", font=('Segoe UI', 9, 'bold'),
                            bg=tr['bg_dark'], fg=tr['text_secondary'])
        self.pct.pack(pady=(6, 0))
        self.status = tk.Label(self.root, text="Загрузка…", font=('Segoe UI', 9),
                               bg=tr['bg_dark'], fg=tr['text_secondary'])
        self.status.pack()

    # ---------- фоновый импорт ----------
    def start_import(self):
        def _import():
            try:
                import ruweb_studio
                self.holder['mod'] = ruweb_studio
            except Exception as e:
                self.holder['err'] = e
            self.holder['done'] = True
        threading.Thread(target=_import, daemon=True).start()

    # ---------- анимация ----------
    def _draw_spinner(self):
        c = self.canvas
        c.delete('all')
        p = 10; s = 120
        c.create_arc(p, p, s-p, s-p, start=0, extent=360,
                     outline=self.tr['track'], width=6, style='arc')
        c.create_arc(p, p, s-p, s-p, start=self.angle, extent=110,
                     outline=self.tr['accent'], width=6, style='arc')
        c.create_arc(p, p, s-p, s-p, start=self.angle+180, extent=50,
                     outline=self.tr['accent2'], width=6, style='arc')

    def _draw_progress(self):
        self.bar.delete('all')
        w = self.bar.winfo_width()
        h = self.bar.winfo_height()
        if w > 1:
            fw = max(2, int(w * self.progress / 100.0))
            self.bar.create_rectangle(0, 0, fw, h, fill=self.tr['accent'], outline=self.tr['accent'])
        self.pct.config(text=f"{int(self.progress)}%")

    def _tick(self):
        self.angle = (self.angle + 14) % 360
        self._draw_spinner()

        done = self.holder.get('done', False)
        if not done:
            self.progress = min(self.progress + random.uniform(0.5, 1.6), 90)
            self.status.config(text="Загрузка модулей…")
        else:
            self.progress = min(self.progress + 5, 100)
            self.status.config(text="Запуск интерфейса…")
        self._draw_progress()

        if self.holder.get('err'):
            self.error = self.holder['err']
            self._finish()
            return
        if done and self.progress >= 100:
            self.result = self.holder.get('mod')
            self._finish()
            return
        self.root.after(30, self._tick)

    def _finish(self):
        try:
            self.root.quit()
        except Exception:
            pass

    def run(self):
        self.root.after(60, self._tick)
        self.root.mainloop()
        try:
            self.root.destroy()
        except Exception:
            pass


def main():
    theme = load_theme()
    splash = Splash(theme)
    splash.start_import()
    splash.run()

    if splash.error is not None:
        import tkinter.messagebox as mb
        mb.showerror("Ошибка запуска", f"Не удалось загрузить RuWeb Studio:\n{splash.error}")
        sys.exit(1)
    if splash.result is None:
        sys.exit(1)

    app = splash.result.RuwebStudio()
    app.run()


if __name__ == '__main__':
    main()