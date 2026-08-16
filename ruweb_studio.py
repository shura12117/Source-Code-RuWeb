# ruweb_studio.py - v5.0
import tkinter as tk
from tkinter import filedialog, messagebox
import os, sys, re, json, time, threading, subprocess, tempfile, webbrowser, http.server, hashlib, shutil
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from ruweb_engine import RuwebEngine
from ruweb_ai import RuWebAI, RuWebAIWindow

try:
    from tkinterweb import HtmlFrame
    HAS_TKW = True
except ImportError:
    HAS_TKW = False

FIREBASE_API_KEY = "AIzaSyAoXa7nPYtmHB-k-C938nW2nnnJ8ayEzZ4"
FIREBASE_PROJECT_ID = "ruweb-studio"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
AUTH_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"

VERSION = "5.0"

DEBUG_LOG = os.path.join(tempfile.gettempdir(), 'ruweb_debug.log')
def _dbg(msg):
    try: print(msg)
    except Exception: pass
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
    except Exception: pass


# ==================== LINTER ====================
class RuwebLinter:
    def lint(self, code, engine):
        issues = []
        if not code.strip():
            return issues
        lines = code.split('\n')
        defined_ids = set(); used_ids = {}
        defined_funcs = set(); used_funcs = {}
        in_style = in_script = False
        style_indent = script_indent = 0
        has_body = False

        for i, raw in enumerate(lines, 1):
            s = raw.strip()
            if not s: continue
            ind = len(raw) - len(raw.lstrip())

            if s.startswith('стили') and not in_style and not in_script:
                in_style = True; style_indent = ind; continue
            if in_style:
                if ind <= style_indent and s: in_style = False
                else: continue

            if s.startswith('сценарий') and not in_script and not in_style:
                in_script = True; script_indent = ind; continue
            if in_script:
                if ind <= script_indent and s: in_script = False
                else:
                    m = re.search(r'\bфункция\s+([\wа-яА-Я_]+)', s)
                    if m: defined_funcs.add(m.group(1))
                    for fm in re.finditer(r'\bслушать\s*\([^,]+,\s*([\wа-яА-Я_]+)\s*\)', s):
                        used_funcs.setdefault(fm.group(1), []).append(i)
                    continue

            if s.startswith('#') or s.startswith('//') or s.startswith('|') or s.startswith('/'):
                continue
            if s == 'документ_html': continue

            parts = s.split(maxsplit=1)
            tag = parts[0].rstrip('/')
            if tag == 'тело': has_body = True
            if tag and tag not in engine.tag_map and tag not in engine.self_closing:
                issues.append((i, 'error', f'Неизвестный тег «{tag}»'))

            # лишние символы после атрибутов/текста
            if len(parts) > 1:
                rest = parts[1]
                cleaned = re.sub(r'[a-zA-Zа-яА-Я_][\w-]*\s*=\s*"[^"]*"', '', rest)
                cleaned = cleaned.strip()
                if cleaned.endswith('/'): cleaned = cleaned[:-1].strip()
                cleaned = re.sub(r'"[^"]*"', '', cleaned, count=1).strip()
                if cleaned:
                    issues.append((i, 'error', f'Лишние символы: «{cleaned}»'))

            for idm in re.finditer(r'\bид\s*=\s*"([^"]+)"', s):
                v = idm.group(1)
                if v in defined_ids: issues.append((i, 'warning', f'ид «{v}» объявлен повторно'))
                defined_ids.add(v)
            for idm in re.finditer(r'\bполучить_по_ид\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', s):
                used_ids.setdefault(idm.group(1), []).append(i)

        for v, lns in used_ids.items():
            if v not in defined_ids:
                for ln in lns: issues.append((ln, 'error', f'получить_по_ид ищет «{v}», но такого ид нет'))
        for fn, lns in used_funcs.items():
            if fn not in defined_funcs:
                for ln in lns: issues.append((ln, 'error', f'Функция «{fn}» в слушать, но не определена'))
        if not has_body:
            issues.append((1, 'warning', 'Нет блока «тело» — страница будет пустой'))

        issues.sort(key=lambda x: (0 if x[1]=='error' else 1, x[0]))
        return issues


# ==================== FIREBASE AUTH ====================
class FirebaseAuth:
    def __init__(self, settings):
        self.settings = settings
        self.api_key = FIREBASE_API_KEY
        self.user_email = None; self.id_token = None; self.refresh_token = None
        self.local_id = None; self.display_name = None; self.email_verified = False
        self._load_session()
    def _load_session(self):
        try:
            data = self.settings.get('firebase_session', {})
            if data and data.get('id_token') and data.get('refresh_token'):
                self.id_token = data['id_token']; self.refresh_token = data['refresh_token']
                self.user_email = data.get('email'); self.local_id = data.get('local_id')
                self.display_name = data.get('display_name', '')
                self.email_verified = data.get('email_verified', False)
                if self._refresh_token():
                    if not self.email_verified:
                        threading.Thread(target=self._silent_verify, daemon=True).start()
                else: self.logout()
        except Exception as e:
            _dbg(f"[AUTH] load error: {e}"); self.logout()
    def _silent_verify(self):
        try: self.check_verification()
        except Exception: pass
    def _save_session(self):
        self.settings.set('firebase_session', {
            'email': self.user_email, 'id_token': self.id_token,
            'refresh_token': self.refresh_token, 'local_id': self.local_id,
            'display_name': self.display_name, 'email_verified': self.email_verified})
    def is_logged_in(self): return bool(self.id_token and self.email_verified)
    def get_display_name(self):
        if self.display_name: return self.display_name
        if self.user_email: return self.user_email.split('@')[0]
        return ''
    def _refresh_token(self):
        if not self.refresh_token: return False
        try:
            r = requests.post(f"https://securetoken.googleapis.com/v1/token?key={self.api_key}",
                              json={'grant_type':'refresh_token','refresh_token':self.refresh_token}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                self.id_token = d.get('id_token', self.id_token)
                self.refresh_token = d.get('refresh_token', self.refresh_token)
                return True
            return False
        except Exception: return False
    def _generate_password(self, email):
        return hashlib.sha256(f"{email}:ruweb-studio-2026-secret-salt".encode()).hexdigest()[:24]
    def send_verification_email(self, email):
        if not HAS_REQUESTS: return False, "Не установлен requests: pip install requests"
        email = email.strip().lower(); password = self._generate_password(email)
        try:
            r = requests.post(f"{AUTH_BASE}:signUp?key={self.api_key}",
                              json={'email':email,'password':password,'returnSecureToken':True}, timeout=15)
            if r.status_code == 200:
                d = r.json()
                self.id_token=d['idToken']; self.refresh_token=d['refreshToken']
                self.local_id=d['localId']; self.user_email=email
                self.email_verified=False; self._save_session()
            else:
                err = r.json().get('error', {}).get('message','')
                if err == 'EMAIL_EXISTS':
                    r2 = requests.post(f"{AUTH_BASE}:signInWithPassword?key={self.api_key}",
                                       json={'email':email,'password':password,'returnSecureToken':True}, timeout=15)
                    if r2.status_code != 200:
                        return False, f"Ошибка входа: {r2.json().get('error',{}).get('message','')}"
                    d = r2.json()
                    self.id_token=d['idToken']; self.refresh_token=d['refreshToken']
                    self.local_id=d['localId']; self.user_email=email
                    self.email_verified=d.get('emailVerified', False); self._save_session()
                else: return False, f"Ошибка регистрации: {err}"
            if self.email_verified:
                self._save_session(); return True, ''
            r3 = requests.post(f"{AUTH_BASE}:sendOobCode?key={self.api_key}",
                               json={'requestType':'VERIFY_EMAIL','idToken':self.id_token}, timeout=15)
            if r3.status_code != 200:
                return False, f"Не удалось отправить письмо: {r3.json().get('error',{}).get('message','')}"
            return True, ''
        except requests.exceptions.ConnectionError:
            return False, "Нет подключения к интернету"
        except Exception as e:
            return False, f"Ошибка: {e}"
    def check_verification(self):
        if not self.id_token: return False
        try:
            self._refresh_token()
            r = requests.post(f"{AUTH_BASE}:lookup?key={self.api_key}",
                              json={'idToken':self.id_token}, timeout=10)
            if r.status_code == 200:
                users = r.json().get('users', [])
                if users:
                    u = users[0]
                    self.email_verified = u.get('emailVerified', False)
                    self.display_name = u.get('displayName','')
                    self.user_email = u.get('email', self.user_email)
                    self._save_session(); return self.email_verified
            return False
        except Exception: return False
    def logout(self):
        self.id_token=None; self.refresh_token=None; self.user_email=None
        self.local_id=None; self.display_name=None; self.email_verified=False
        self.settings.set('firebase_session', {})


class CloudProjects:
    def __init__(self, auth): self.auth = auth
    def _auth_header(self): return {'Authorization': f'Bearer {self.auth.id_token}'}
    def list_projects(self):
        if not self.auth.is_logged_in(): return []
        try:
            r = requests.get(f"{FIRESTORE_BASE}/users/{self.auth.local_id}/projects",
                             headers=self._auth_header(), timeout=15)
            if r.status_code != 200: return []
            return [{'name':d['name'].split('/')[-1],
                     'content':d.get('fields',{}).get('content',{}).get('stringValue',''),
                     'updated':d.get('updateTime','')} for d in r.json().get('documents',[])]
        except Exception as e:
            _dbg(f"[CLOUD] list error: {e}"); return []
    def save_project(self, name, content):
        if not self.auth.is_logged_in(): return False, "Не авторизован"
        try:
            name = name.replace('.ruweb','')
            url = f"{FIRESTORE_BASE}/users/{self.auth.local_id}/projects/{name}?updateMask.fieldPaths=content&updateMask.fieldPaths=updated_at"
            body = {'fields': {'content':{'stringValue':content},
                               'updated_at':{'timestampValue':datetime.utcnow().isoformat()+'Z'}}}
            r = requests.patch(url, json=body, headers=self._auth_header(), timeout=20)
            if r.status_code in (200,201): return True, ''
            return False, f"Ошибка сохранения: {r.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Нет подключения к интернету"
        except Exception as e:
            return False, f"Таймаут/сеть: {e}"
    def delete_project(self, name):
        if not self.auth.is_logged_in(): return False
        try:
            r = requests.delete(f"{FIRESTORE_BASE}/users/{self.auth.local_id}/projects/{name.replace('.ruweb','')}",
                                headers=self._auth_header(), timeout=10)
            return r.status_code == 200
        except Exception: return False


# ==================== WINDOWS API ====================
IS_WIN = (sys.platform == 'win32')
if IS_WIN:
    import ctypes
    from ctypes import wintypes
    _u32 = ctypes.windll.user32; _k32 = ctypes.windll.kernel32
    HWND = ctypes.c_void_p; UINT = ctypes.c_uint; WPARAM = ctypes.c_uint64
    LPARAM = ctypes.c_int64; LRESULT = ctypes.c_int64
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)
    GWL_STYLE=-16; GWL_EXSTYLE=-20; GWLP_WNDPROC=-4; GA_ROOT=2
    WS_OVERLAPPEDWINDOW=0x00CF0000; WS_POPUP=0x80000000; WS_CAPTION=0x00C00000
    WS_THICKFRAME=0x00040000; WS_SYSMENU=0x00080000; WS_MINIMIZEBOX=0x00020000
    WS_MAXIMIZEBOX=0x00010000; WS_CHILD=0x40000000; WS_VISIBLE=0x10000000
    WS_EX_APPWINDOW=0x00040000; WS_EX_TOOLWINDOW=0x00000080
    SW_SHOW=5; SW_HIDE=0; SW_RESTORE=9; SW_MINIMIZE=6
    SWP_NOZORDER=0x0004; SWP_FRAMECHANGED=0x0020
    WM_KEYDOWN=0x0100; WM_KEYUP=0x0101; VK_F5=0x74; WM_CLOSE=0x0010
    WM_NCLBUTTONDOWN=0x00A1; WM_NCHITTEST=0x0084; WM_SYSCOMMAND=0x0112
    HTCLIENT=1; SC_MOVE=0xF010; SC_CLOSE=0xF060; SC_MINIMIZE=0xF020
    SC_MAXIMIZE=0xF030; SC_KEYMENU=0xF100; PROCESS_TERMINATE=0x0001
    _u32.GetWindowLongW.restype=ctypes.c_long; _u32.GetWindowLongW.argtypes=[HWND, ctypes.c_int]
    _u32.SetWindowLongW.restype=ctypes.c_long; _u32.SetWindowLongW.argtypes=[HWND, ctypes.c_int, ctypes.c_long]
    _u32.SetWindowLongPtrW.restype=ctypes.c_void_p; _u32.SetWindowLongPtrW.argtypes=[HWND, ctypes.c_int, ctypes.c_void_p]
    _u32.CallWindowProcW.restype=LRESULT; _u32.CallWindowProcW.argtypes=[ctypes.c_void_p, HWND, UINT, WPARAM, LPARAM]
    _u32.SetParent.restype=HWND; _u32.SetParent.argtypes=[HWND, HWND]
    _u32.ShowWindow.restype=wintypes.BOOL; _u32.ShowWindow.argtypes=[HWND, ctypes.c_int]
    _u32.IsWindowVisible.restype=wintypes.BOOL; _u32.IsWindowVisible.argtypes=[HWND]
    _u32.IsWindow.restype=wintypes.BOOL; _u32.IsWindow.argtypes=[HWND]
    _u32.IsIconic.restype=wintypes.BOOL; _u32.IsIconic.argtypes=[HWND]
    _u32.GetAncestor.restype=HWND; _u32.GetAncestor.argtypes=[HWND, UINT]
    _u32.SetWindowPos.restype=wintypes.BOOL
    _u32.SetWindowPos.argtypes=[HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, UINT]
    _u32.PostMessageW.restype=wintypes.BOOL; _u32.PostMessageW.argtypes=[HWND, UINT, WPARAM, LPARAM]
    _u32.GetClassNameW.restype=ctypes.c_int; _u32.GetClassNameW.argtypes=[HWND, ctypes.c_wchar_p, ctypes.c_int]
    _u32.EnumWindows.restype=wintypes.BOOL; _u32.EnumWindows.argtypes=[WNDENUMPROC, LPARAM]
    _u32.GetWindowThreadProcessId.restype=wintypes.DWORD
    _u32.GetWindowThreadProcessId.argtypes=[HWND, ctypes.POINTER(wintypes.DWORD)]
    _k32.OpenProcess.restype=ctypes.c_void_p; _k32.OpenProcess.argtypes=[wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.TerminateProcess.restype=wintypes.BOOL; _k32.TerminateProcess.argtypes=[ctypes.c_void_p, UINT]
    _k32.CloseHandle.restype=wintypes.BOOL; _k32.CloseHandle.argtypes=[ctypes.c_void_p]
    def _get_style(h): return _u32.GetWindowLongW(h, GWL_STYLE) & 0xFFFFFFFF
    def _set_style(h, s):
        if s > 0x7FFFFFFF: s -= 0x100000000
        _u32.SetWindowLongW(h, GWL_STYLE, s)
    def _get_exstyle(h): return _u32.GetWindowLongW(h, GWL_EXSTYLE) & 0xFFFFFFFF
    def _set_exstyle(h, s):
        if s > 0x7FFFFFFF: s -= 0x100000000
        _u32.SetWindowLongW(h, GWL_EXSTYLE, s)
    def _enum_chrome_windows():
        found=[]
        def cb(h,l):
            buf=ctypes.create_unicode_buffer(64)
            _u32.GetClassNameW(h,buf,64)
            if buf.value=='Chrome_WidgetWin_1': found.append(h)
            return True
        c=WNDENUMPROC(cb); _u32.EnumWindows(c,0); return set(found)
    def _kill_window_owner(h):
        try:
            pid=wintypes.DWORD(0)
            _u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value:
                hh=_k32.OpenProcess(PROCESS_TERMINATE, False, pid.value)
                if hh: _k32.TerminateProcess(hh,1); _k32.CloseHandle(hh)
        except Exception as e: _dbg(f"[BROWSER] kill error: {e}")
else:
    def _enum_chrome_windows(): return set()

UI_FONT='Segoe UI'; CODE_FONT='Cascadia Code'; INDENT='  '

THEMES = {
    'dark': {'bg_dark':'#181a1f','bg_panel':'#21252b','bg_card':'#282c34','bg_input':'#3a3f4b',
             'bg_hover':'#333842','text_primary':'#d7dae0','text_secondary':'#8b93a3',
             'accent':'#667eea','accent2':'#764ba2','white':'#ffffff','green':'#43e97b',
             'editor_bg':'#181a1f','editor_fg':'#d7dae0','linenum_bg':'#21252b',
             'linenum_fg':'#4f5869','console_bg':'#0c0c0c','console_fg':'#00ff00',
             'sel_bg':'#3a4a6b','insert':'white','dot_fg':'#8b93a3',
             'titlebar_bg':'#1b1e24','titlebar_fg':'#9aa0ab','close_hover':'#e81123'},
    'light': {'bg_dark':'#f2f3f5','bg_panel':'#ffffff','bg_card':'#ffffff','bg_input':'#e8e9ec',
              'bg_hover':'#dcdde1','text_primary':'#1e1e1e','text_secondary':'#555555',
              'accent':'#667eea','accent2':'#764ba2','white':'#ffffff','green':'#0a8a3a',
              'editor_bg':'#ffffff','editor_fg':'#1e1e1e','linenum_bg':'#f2f3f5',
              'linenum_fg':'#8b93a3','console_bg':'#ffffff','console_fg':'#0a8a3a',
              'sel_bg':'#b4d5ff','insert':'#1e1e1e','dot_fg':'#a0a8b8',
              'titlebar_bg':'#e9eaee','titlebar_fg':'#555555','close_hover':'#e81123'},
}

class Settings:
    def __init__(self):
        self.path = os.path.join(os.path.expanduser('~'), '.ruweb_settings.json')
        self.data = self._load()
    def _load(self):
        try:
            with open(self.path,'r',encoding='utf-8') as f: return json.load(f)
        except Exception: return {'theme':'dark'}
    def save(self):
        try:
            with open(self.path,'w',encoding='utf-8') as f: json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception: pass
    def get(self,k,d=None): return self.data.get(k,d)
    def set(self,k,v): self.data[k]=v; self.save()

class _PreviewHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data = self.server.ruweb_html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        if self.path=='/log':
            try:
                length=int(self.headers.get('Content-Length',0))
                data=self.rfile.read(length).decode('utf-8', errors='replace')
                cb=getattr(self.server,'log_callback',None)
                if cb: cb(data)
            except Exception: pass
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers(); return
        self.send_response(404); self.end_headers()
    def log_message(self,*a): pass

class RealBrowserPanel:
    def __init__(self, root, holder, url, on_fail, on_ready):
        self.root=root; self.holder=holder; self.url=url
        self.on_fail=on_fail; self.on_ready=on_ready
        self.proc=None; self.hwnd=None; self._before=set()
        self._old_proc=None; self._c_proc=None; self._watch_id=None
        self._watching=False; self._alive=True
    @staticmethod
    def find_browser_exe():
        cands=[]
        for env in ('LOCALAPPDATA','PROGRAMFILES','PROGRAMFILES(X86)'):
            base=os.environ.get(env)
            if base:
                cands.append(os.path.join(base,'Microsoft\\Edge\\Application\\msedge.exe'))
                cands.append(os.path.join(base,'Google\\Chrome\\Application\\chrome.exe'))
        for c in cands:
            if os.path.exists(c): return c
        return None
    def _chrome_windows(self): return _enum_chrome_windows()
    def _spawn_args(self):
        exe=self.find_browser_exe()
        profile=os.path.join(tempfile.gettempdir(),'ruweb_embed_profile')
        return [exe, f'--app={self.url}', f'--user-data-dir={profile}',
                '--no-first-run','--no-default-browser-check','--disable-extensions',
                '--window-position=-32000,-32000']
    def start(self):
        exe=self.find_browser_exe()
        if not exe: return False
        try:
            self._before=self._chrome_windows()
            self.proc=subprocess.Popen(self._spawn_args())
            threading.Thread(target=self._wait_window, daemon=True).start()
            return True
        except Exception as e:
            _dbg(f"[BROWSER] start error: {e}"); return False
    def _wait_window(self):
        for i in range(120):
            time.sleep(0.25)
            if not self._alive: return
            new=self._chrome_windows()-self._before
            if new:
                vis=[h for h in new if _u32.IsWindowVisible(h)]
                if vis:
                    h=vis[0]; self.root.after(0, lambda: self._attach(h)); return
        self.root.after(0, self.on_fail)
    def _attach(self, hwnd):
        try:
            self.holder.update_idletasks(); self.hwnd=hwnd
            _u32.SetParent(hwnd, self.holder.winfo_id())
            self._apply_style(); self._subclass()
            _u32.ShowWindow(hwnd, SW_SHOW); self._resize()
            self.holder.bind('<Configure>', lambda e: self._resize())
            self._start_watchdog(); self.on_ready()
        except Exception as e:
            _dbg(f"[BROWSER] attach error: {e}"); self.on_fail()
    def _apply_style(self):
        if not self.hwnd: return
        s=_get_style(self.hwnd)
        s &= ~(WS_OVERLAPPEDWINDOW|WS_POPUP|WS_CAPTION|WS_THICKFRAME|WS_SYSMENU|WS_MINIMIZEBOX|WS_MAXIMIZEBOX)
        s |= WS_CHILD|WS_VISIBLE
        _set_style(self.hwnd, s)
        try:
            ex=_get_exstyle(self.hwnd); ex &= ~WS_EX_APPWINDOW; _set_exstyle(self.hwnd, ex)
        except Exception: pass
    def _subclass(self):
        def proc(hwnd, msg, wparam, lparam):
            try:
                if msg==WM_NCHITTEST: return HTCLIENT
                if msg==WM_CLOSE: return 0
                if msg==WM_NCLBUTTONDOWN: return 0
                if msg==WM_SYSCOMMAND:
                    cmd=wparam & 0xFFF0
                    if cmd in (SC_MOVE,SC_CLOSE,SC_MINIMIZE,SC_MAXIMIZE,SC_KEYMENU): return 0
            except Exception: pass
            return _u32.CallWindowProcW(self._old_proc, hwnd, msg, wparam, lparam)
        self._c_proc=WNDPROC(proc)
        self._old_proc=_u32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC, ctypes.cast(self._c_proc, ctypes.c_void_p))
    def _start_watchdog(self):
        if self._watching: return
        self._watching=True; self._alive=True; self._watch()
    def _watch(self):
        if not self._alive or not self._watching: return
        try:
            if self.hwnd is not None and not _u32.IsWindow(self.hwnd):
                self.hwnd=None; self._old_proc=None; self._before=self._chrome_windows()
                try:
                    self.proc=subprocess.Popen(self._spawn_args())
                    threading.Thread(target=self._wait_window, daemon=True).start()
                except Exception: pass
            elif self.hwnd:
                if _u32.IsIconic(self.hwnd): _u32.ShowWindow(self.hwnd, SW_RESTORE)
                if not _u32.IsWindowVisible(self.hwnd): _u32.ShowWindow(self.hwnd, SW_SHOW)
                self._apply_style(); self._resize()
        except Exception: pass
        self._watch_id=self.root.after(1500, self._watch)
    def _resize(self):
        if not self.hwnd: return
        try:
            w=max(self.holder.winfo_width(),1); h=max(self.holder.winfo_height(),1)
            _u32.SetWindowPos(self.hwnd, None, 0,0,w,h, SWP_NOZORDER|SWP_FRAMECHANGED)
        except Exception: pass
    def reload(self):
        if not self.hwnd: return
        try:
            _u32.PostMessageW(self.hwnd, WM_KEYDOWN, VK_F5, 0)
            _u32.PostMessageW(self.hwnd, WM_KEYUP, VK_F5, 0)
        except Exception: pass
    def restart(self):
        self.shutdown(); self._alive=True; return self.start()
    def shutdown(self):
        self._alive=False; self._watching=False
        if self._watch_id:
            try: self.root.after_cancel(self._watch_id)
            except Exception: pass
            self._watch_id=None
        if self.hwnd and IS_WIN:
            if _u32.IsWindow(self.hwnd): _kill_window_owner(self.hwnd)
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.proc=None
        self.hwnd=None; self._old_proc=None


class LoginWindow:
    def __init__(self, parent, auth, on_success):
        self.parent=parent; self.auth=auth; self.on_success=on_success
        self.window=None; self.email_entry=None; self.status_label=None
        self.send_btn=None; self._poll_id=None
    def show(self):
        c=THEMES['dark']
        self.window=tk.Toplevel(self.parent); self.window.title("Вход в RuWeb Studio")
        self.window.geometry("480x420"); self.window.configure(bg=c['bg_panel'])
        self.window.transient(self.parent); self.window.grab_set(); self.window.resizable(False,False)
        self.window.update_idletasks()
        self.window.geometry(f"+{self.parent.winfo_x()+(self.parent.winfo_width()-480)//2}+{self.parent.winfo_y()+(self.parent.winfo_height()-420)//2}")
        head=tk.Frame(self.window, bg=c['bg_panel'], pady=18); head.pack(fill=tk.X)
        tk.Label(head, text="⚡", font=(UI_FONT,22,'bold'), bg=c['bg_panel'], fg=c['accent']).pack()
        tk.Label(head, text="Вход в RuWeb Studio", font=(UI_FONT,16,'bold'), bg=c['bg_panel'], fg=c['text_primary']).pack(pady=(4,2))
        tk.Label(head, text="Войдите через Google-аккаунт", font=(UI_FONT,10), bg=c['bg_panel'], fg=c['text_secondary']).pack()
        form=tk.Frame(self.window, bg=c['bg_panel']); form.pack(fill=tk.X, padx=36)
        tk.Label(form, text="Email от Google:", bg=c['bg_panel'], fg=c['text_secondary'], font=(UI_FONT,10), anchor='w').pack(fill=tk.X, pady=(6,4))
        self.email_entry=tk.Entry(form, font=(UI_FONT,12), bg=c['bg_input'], fg=c['text_primary'], relief=tk.FLAT, insertbackground='white')
        self.email_entry.pack(fill=tk.X, ipady=8); self.email_entry.focus_set()
        self.email_entry.bind('<Return>', lambda e: self._on_send())
        self.status_label=tk.Label(self.window, text="", bg=c['bg_panel'], fg=c['text_secondary'], font=(UI_FONT,10), wraplength=400, justify='center')
        self.status_label.pack(pady=14)
        bf=tk.Frame(self.window, bg=c['bg_panel']); bf.pack(fill=tk.X, padx=36)
        self.send_btn=tk.Button(bf, text="Отправить письмо подтверждения", font=(UI_FONT,11,'bold'), bg=c['accent'], fg='white', relief=tk.FLAT, cursor='hand2', padx=20, pady=9, command=self._on_send)
        self.send_btn.pack(fill=tk.X, pady=(0,8))
        tk.Button(bf, text="Отмена", font=(UI_FONT,10), bg=c['bg_hover'], fg=c['text_primary'], relief=tk.FLAT, cursor='hand2', command=self._close).pack(fill=tk.X)
        self.window.protocol("WM_DELETE_WINDOW", self._close)
    def _set_status(self, text, color=None):
        if self.status_label and self.status_label.winfo_exists():
            self.status_label.config(text=text, fg=color or THEMES['dark']['text_secondary'])
    def _on_send(self):
        email=self.email_entry.get().strip()
        if not email or '@' not in email:
            self._set_status("Введите корректный email", '#f5576c'); return
        self.send_btn.config(state='disabled', text="Отправляем...")
        self._set_status("Отправляем письмо подтверждения...", color=THEMES['dark']['accent'])
        def worker():
            s,e = self.auth.send_verification_email(email)
            self.window.after(0, lambda: self._on_send_done(s,e))
        threading.Thread(target=worker, daemon=True).start()
    def _on_send_done(self, success, err):
        if not success:
            self.send_btn.config(state='normal', text="Отправить письмо подтверждения")
            self._set_status(err, '#f5576c'); return
        if self.auth.email_verified:
            self._set_status("Вход выполнен!", THEMES['dark']['green'])
            self.window.after(500, self._finish); return
        self._show_waiting_state()
    def _show_waiting_state(self):
        c=THEMES['dark']
        for w in self.window.winfo_children(): w.destroy()
        head=tk.Frame(self.window, bg=c['bg_panel'], pady=18); head.pack(fill=tk.X)
        self.spinner_label=tk.Label(head, text="⏳", font=(UI_FONT,28), bg=c['bg_panel'], fg=c['accent']); self.spinner_label.pack()
        self._animate_spinner()
        tk.Label(head, text="Ожидание подтверждения", font=(UI_FONT,16,'bold'), bg=c['bg_panel'], fg=c['text_primary']).pack(pady=(8,2))
        tk.Label(head, text=f"Письмо отправлено на {self.auth.user_email}", font=(UI_FONT,10), bg=c['bg_panel'], fg=c['text_secondary']).pack()
        hf=tk.Frame(self.window, bg=c['bg_card'], padx=20, pady=14); hf.pack(fill=tk.X, padx=36, pady=10)
        tk.Label(hf, text="📧 Перейдите по ссылке в письме,\nкоторое пришло на вашу почту", font=(UI_FONT,11), bg=c['bg_card'], fg=c['text_primary'], justify='center').pack()
        tk.Label(hf, text="💡 Загляните в папку «Спам» —\nписьмо могло попасть туда", font=(UI_FONT,10,'italic'), bg=c['bg_card'], fg='#ffcc00', justify='center').pack(pady=(10,0))
        self.status_label=tk.Label(self.window, text="Ожидаем перехода по ссылке...", bg=c['bg_panel'], fg=c['text_secondary'], font=(UI_FONT,10))
        self.status_label.pack(pady=10)
        tk.Button(self.window, text="Отмена", font=(UI_FONT,10), bg=c['bg_hover'], fg=c['text_primary'], relief=tk.FLAT, cursor='hand2', command=self._cancel_waiting).pack(pady=10)
        self._start_polling()
    def _animate_spinner(self):
        if not self.window or not self.window.winfo_exists(): return
        if not hasattr(self,'spinner_label') or not self.spinner_label.winfo_exists(): return
        icons=['⏳','📧','🔄','✨']
        self.spinner_label.config(text=icons[(getattr(self,'_spin_phase',0)+1)%len(icons)])
        self._spin_phase=(getattr(self,'_spin_phase',0)+1)%len(icons)
        self.window.after(600, self._animate_spinner)
    def _start_polling(self):
        def poll():
            if not self.window or not self.window.winfo_exists(): return
            if self.auth.check_verification():
                self._set_status("✅ Email подтверждён! Входим...", THEMES['dark']['green'])
                self.window.after(800, self._finish)
            else:
                self._poll_id=self.window.after(2000, poll)
        self._poll_id=self.window.after(2000, poll)
    def _cancel_waiting(self):
        if self._poll_id:
            try: self.window.after_cancel(self._poll_id)
            except Exception: pass
            self._poll_id=None
        self._close()
    def _finish(self):
        if self._poll_id:
            try: self.window.after_cancel(self._poll_id)
            except Exception: pass
        if self.window and self.window.winfo_exists(): self.window.destroy()
        self.on_success()
    def _close(self):
        if self._poll_id:
            try: self.window.after_cancel(self._poll_id)
            except Exception: pass
        if self.window and self.window.winfo_exists(): self.window.destroy()

class SyntaxHighlighter:
    def __init__(self, t):
        self.t=t
        for tag, fg in [('tag','#4ec9b0'),('attr','#9cdcfe'),('string','#ce9178'),
                        ('comment','#6a9955'),('keyword','#569cd6'),('func','#dcdcaa'),
                        ('num','#b5cea8'),('doc','#808080')]:
            self.t.tag_configure(tag, foreground=fg)
    def highlight(self, event=None):
        for tag in ['tag','attr','string','comment','keyword','func','num','doc']:
            self.t.tag_remove(tag, '1.0', tk.END)
        content=self.t.get('1.0','end-1c')
        if not content.strip(): return
        for m in re.finditer(r'#[^\n]*', content): self._add(m.start(), m.end(), 'comment')
        for m in re.finditer(r'"[^"]*"', content): self._add(m.start(), m.end(), 'string')
        for m in re.finditer(r'\b\d+\b', content): self._add(m.start(), m.end(), 'num')
        for m in re.finditer(r'документ_html', content): self._add(m.start(), m.end(), 'doc')
        for m in re.finditer(r'\b(перем|конст|функция|возврат|если|иначе|для|пока|истина|ложь)\b', content): self._add(m.start(), m.end(), 'keyword')
        for m in re.finditer(r'\b(вывести|предупредить|получить_по_ид|слушать)\b', content): self._add(m.start(), m.end(), 'func')
        for m in re.finditer(r'\b(страница|голова|тело|заголовок|мета|стили|сценарий|секция|заголовок_блок|подвал|основной|заголовок[12]|абзац|блок|кнопка|список|элемент)\b', content): self._add(m.start(), m.end(), 'tag')
        for m in re.finditer(r'\b(класс|ид|стиль|язык|кодировка|тип|имя|значение|подсказка|при_клике)\b', content): self._add(m.start(), m.end(), 'attr')
    def _add(self, s, e, tag):
        content=self.t.get('1.0','end-1c')
        line=content[:s].count('\n')+1
        last=content[:s].rfind('\n')
        col=s if last==-1 else s-last-1
        try: self.t.tag_add(tag, f'{line}.{col}', f'{line}.{col+(e-s)}')
        except Exception: pass

class ModernButton(tk.Button):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.dbg=kw.get('bg','#3e3e42'); self.hbg=kw.get('activebackground','#505050')
        self.bind('<Enter>', lambda e: self.configure(bg=self.hbg))
        self.bind('<Leave>', lambda e: self.configure(bg=self.dbg))


class RuwebStudio:
    CARD_COLORS=['#667eea','#764ba2','#f093fb','#4facfe','#43e97b','#fa709a','#30cfd0','#f5576c']
    BANNER_COLORS=[(102,126,234),(118,75,162),(240,147,251),(79,172,254),(67,233,123)]
    JS_OPENERS=('функция','если','иначе_если','иначе','для','пока','цикл','когда','попробовать','поймать_ошибку')
    HTML_OPENERS=('страница','голова','тело','секция','статья','навигация','боковая',
                  'заголовок_блок','подвал','основной','список','список_нум','таблица',
                  'форма','цитата','детали','диалог','стили','сценарий')

    def __init__(self):
        _dbg(f"[APP] Start v{VERSION}")
        self.root=tk.Tk(); self.root.title(f"RuWeb Studio 2026  v{VERSION}")
        self.root.geometry("1280x760"); self.root.minsize(1000,600)
        self.settings=Settings()
        self.c=THEMES[self.settings.get('theme','dark')].copy()
        self.root.overrideredirect(True); self.root.configure(bg=self.c['bg_dark'])
        self.engine=RuwebEngine()
        self.linter=RuwebLinter()
        self.auth=FirebaseAuth(self.settings)
        self.cloud=CloudProjects(self.auth)
        self.ruweb_ai=RuWebAI(self.auth, self.settings)
        self.ai_window=None
        self.projects_dir=os.path.join(os.path.expanduser('~'),'RuwebProjects')
        os.makedirs(self.projects_dir, exist_ok=True)
        self.preview_server=http.server.ThreadingHTTPServer(('127.0.0.1',0), _PreviewHandler)
        self.preview_server.ruweb_html='<html><body></body></html>'
        self.preview_server.log_callback=self._on_js_log
        threading.Thread(target=self.preview_server.serve_forever, daemon=True).start()
        self.preview_url=f'http://127.0.0.1:{self.preview_server.server_address[1]}/'
        self.current_file=None; self.current_is_cloud=False
        self.editor=None; self.line_numbers=None; self.file_label=None
        self.status_label=None; self.cursor_label=None
        self.preview_mode='none'; self.browser_frame=None; self.real_panel=None
        self.preview_holder=None; self.preview_title=None
        self.hub_canvas=None; self.hub_banner=None
        self.modified=False; self._saving=False; self._current_view='hub'
        self._highlight_after=None; self._lint_after=None
        self._banner_after=None; self._banner_phase=0.0
        self._font_size=12; self._drag_data=None; self._resize_data=None
        self._is_maximized=False; self._prev_geometry=None
        self._console_visible=False
        self.editor_console_pane=None; self.console_frame=None; self.console_text=None
        self._console_log_counter=0
        self._has_errors=False
        self._last_lint_sig=None
        self.cloud_projects_cache={}
        self._build_titlebar()
        self.content=tk.Frame(self.root, bg=self.c['bg_dark']); self.content.pack(fill=tk.BOTH, expand=True)
        self._build_grip()
        self.root.after(100, self._fix_taskbar_icon)
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.show_project_hub()
        self.root.after(500, self._refresh_session_async)

    def _refresh_session_async(self):
        if not self.auth.id_token: return
        def worker():
            self.auth.check_verification()
            try: self.root.after(0, self._refresh_hub_auth_ui)
            except Exception: pass
        threading.Thread(target=worker, daemon=True).start()

    def _minimize_win(self):
        try:
            if IS_WIN:
                h=_u32.GetAncestor(self.root.winfo_id(), GA_ROOT)
                if not h: h=self.root.winfo_id()
                _u32.ShowWindow(h, SW_MINIMIZE); return
        except Exception: pass
        try: self.root.iconify()
        except Exception: pass

    def _open_login(self):
        def on_success():
            self._refresh_hub_auth_ui(); self._load_cloud_projects_async()
            self.console_log(f"Вход выполнен: {self.auth.user_email}")
        LoginWindow(self.root, self.auth, on_success).show()

    def _logout(self):
        if messagebox.askyesno("Выход", "Выйти из аккаунта RuWeb?"):
            self.auth.logout(); self.cloud_projects_cache={}; self._refresh_hub_auth_ui()

    def _refresh_hub_auth_ui(self):
        if not hasattr(self,'_auth_btn') or not self._auth_btn.winfo_exists(): return
        if self.auth.is_logged_in():
            name=self.auth.get_display_name()
            if len(name)>18: name=name[:16]+'…'
            self._auth_btn.config(text=f"👤 {name}", bg='#2f5a4f', command=self._show_user_menu)
        else:
            self._auth_btn.config(text="🔑 Войти", bg='#3a4a6b', command=self._open_login)

    def _show_user_menu(self):
        menu=tk.Menu(self.root, tearoff=0, bg=self.c['bg_card'], fg=self.c['text_primary'])
        menu.add_command(label=f"📧 {self.auth.user_email}", state='disabled')
        menu.add_separator()
        menu.add_command(label="🌐 Мои облачные проекты",
                         command=lambda: messagebox.showinfo("Облако", f"Синхронизация: {self.auth.user_email}"))
        menu.add_separator()
        menu.add_command(label="🚪 Выйти", command=self._logout)
        try: menu.tk_popup(self._auth_btn.winfo_rootx()-150, self._auth_btn.winfo_rooty()+self._auth_btn.winfo_height())
        except Exception: pass

    def _load_cloud_projects_async(self):
        if not self.auth.is_logged_in(): return
        def worker():
            p=self.cloud.list_projects()
            self.root.after(0, lambda: self._on_cloud_loaded(p))
        threading.Thread(target=worker, daemon=True).start()

    def _on_cloud_loaded(self, projects):
        self.cloud_projects_cache={p['name']: p for p in projects}
        if self._current_view=='hub': self._load_projects()

    def _fix_taskbar_icon(self):
        if not IS_WIN: return
        try:
            self.root.update_idletasks()
            ch=self.root.winfo_id(); ph=_u32.GetParent(ch)
            if not ph: ph=ch
            s=_get_exstyle(ph); s|=WS_EX_APPWINDOW; s&=~WS_EX_TOOLWINDOW; _set_exstyle(ph,s)
            _u32.ShowWindow(ph, SW_HIDE); _u32.ShowWindow(ph, SW_SHOW)
            if ph!=ch:
                s2=_get_exstyle(ch); s2&=~WS_EX_TOOLWINDOW; _set_exstyle(ch,s2)
            self.root.focus_force()
        except Exception: pass

    def _build_titlebar(self):
        self.titlebar=tk.Frame(self.root, bg=self.c['titlebar_bg'], height=40)
        self.titlebar.pack(fill=tk.X, side=tk.TOP); self.titlebar.pack_propagate(False)
        self.tb_icon=tk.Label(self.titlebar, text='⚡', bg=self.c['titlebar_bg'], fg=self.c['accent'], font=(UI_FONT,13,'bold'))
        self.tb_icon.pack(side=tk.LEFT, padx=(14,8))
        self.tb_title=tk.Label(self.titlebar, text=f'RuWeb Studio 2026  v{VERSION}', bg=self.c['titlebar_bg'], fg=self.c['titlebar_fg'], font=(UI_FONT,10))
        self.tb_title.pack(side=tk.LEFT)
        self.tb_btns=tk.Frame(self.titlebar, bg=self.c['titlebar_bg']); self.tb_btns.pack(side=tk.RIGHT)
        self.tb_min=tk.Label(self.tb_btns, text='—', bg=self.c['titlebar_bg'], fg=self.c['titlebar_fg'], font=(UI_FONT,10), width=4, height=1, cursor='hand2'); self.tb_min.pack(side=tk.LEFT)
        self.tb_max=tk.Label(self.tb_btns, text='▢', bg=self.c['titlebar_bg'], fg=self.c['titlebar_fg'], font=(UI_FONT,10), width=4, height=1, cursor='hand2'); self.tb_max.pack(side=tk.LEFT)
        self.tb_close=tk.Label(self.tb_btns, text='✕', bg=self.c['titlebar_bg'], fg=self.c['titlebar_fg'], font=(UI_FONT,10), width=4, height=1, cursor='hand2'); self.tb_close.pack(side=tk.LEFT)
        self.tb_min.bind('<Button-1>', lambda e: self._minimize_win())
        self.tb_max.bind('<Button-1>', lambda e: self._toggle_max())
        self.tb_close.bind('<Button-1>', lambda e: self.on_exit())
        def hover(lbl, bg, fg):
            lbl.bind('<Enter>', lambda e: lbl.config(bg=bg, fg=fg))
            lbl.bind('<Leave>', lambda e: lbl.config(bg=self.c['titlebar_bg'], fg=self.c['titlebar_fg']))
        hover(self.tb_min, self.c['bg_hover'], self.c['text_primary'])
        hover(self.tb_max, self.c['bg_hover'], self.c['text_primary'])
        self.tb_close.bind('<Enter>', lambda e: self.tb_close.config(bg=self.c['close_hover'], fg='white'))
        self.tb_close.bind('<Leave>', lambda e: self.tb_close.config(bg=self.c['titlebar_bg'], fg=self.c['titlebar_fg']))
        for w in (self.titlebar, self.tb_icon, self.tb_title):
            w.bind('<Button-1>', self._start_move); w.bind('<B1-Motion>', self._do_move)
            w.bind('<Double-Button-1>', lambda e: self._toggle_max())

    def _toggle_max(self):
        if self._is_maximized:
            self.root.overrideredirect(False)
            if self._prev_geometry: self.root.geometry(self._prev_geometry)
            self.root.overrideredirect(True); self.root.after(50, self._fix_taskbar_icon)
            self._is_maximized=False; self.tb_max.config(text='▢')
        else:
            self._prev_geometry=self.root.geometry(); self.root.update_idletasks()
            self.root.geometry(f'{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0')
            self._is_maximized=True; self.tb_max.config(text='❐')

    def _start_move(self, e): self._drag_data=(e.x_root-self.root.winfo_x(), e.y_root-self.root.winfo_y())
    def _do_move(self, e):
        if not self._drag_data: return
        self.root.geometry(f'+{e.x_root-self._drag_data[0]}+{e.y_root-self._drag_data[1]}')

    def _build_grip(self):
        self.grip=tk.Label(self.root, text='', bg=self.c['bg_dark'], fg=self.c['text_secondary'], cursor='bottom_right_corner', font=(UI_FONT,10))
        self.grip.place(relx=1.0, rely=1.0, anchor='se')
        self.grip.bind('<Button-1>', self._start_resize); self.grip.bind('<B1-Motion>', self._do_resize)
    def _start_resize(self, e): self._resize_data=(e.x_root, e.y_root, self.root.winfo_width(), self.root.winfo_height())
    def _do_resize(self, e):
        if not self._resize_data: return
        x0,y0,w0,h0=self._resize_data
        self.root.geometry(f'{max(1000,w0+(e.x_root-x0))}x{max(600,h0+(e.y_root-y0))}')

    def _style_titlebar(self):
        c=self.c
        self.titlebar.configure(bg=c['titlebar_bg']); self.tb_icon.configure(bg=c['titlebar_bg'])
        self.tb_title.configure(bg=c['titlebar_bg'], fg=c['titlebar_fg']); self.tb_btns.configure(bg=c['titlebar_bg'])
        for b in (self.tb_min,self.tb_max,self.tb_close): b.configure(bg=c['titlebar_bg'], fg=c['titlebar_fg'])
        self.grip.configure(bg=c['bg_dark'], fg=c['text_secondary'])

    def _get_colors(self): return self.c

    def _on_js_log(self, m):
        text=str(m); low=text.lower()
        if 'error' in low or 'ошибка' in low: self.console_log(text, 'error')
        elif 'warn' in low or 'предупреждение' in low: self.console_log(text, 'warning')
        else: self.console_log(text, 'info')

    # ==================== КОНСОЛЬ ====================
    def console_log(self, message, level='info'):
        if not self.console_text or not self.console_text.winfo_exists(): return
        try:
            ts=datetime.now().strftime('%H:%M:%S')
            if level=='error': prefix='❌ ОШИБКА'; color='#ff5555'
            elif level=='warning': prefix='⚠ ПРЕДУПРЕЖДЕНИЕ'; color='#ffcc00'
            else: prefix='ℹ'; color='#00ff00'
            self._console_log_counter+=1
            tag=f'log_{self._console_log_counter}'
            self.console_text.config(state=tk.NORMAL)
            self.console_text.tag_configure(tag, foreground=color)
            self.console_text.insert(tk.END, f"[{ts}] {prefix}: {message}\n", tag)
            self.console_text.see(tk.END)
            self.console_text.config(state=tk.DISABLED)
        except Exception as e: _dbg(f"[CONSOLE] log error: {e}")

    def console_clear(self):
        if self.console_text and self.console_text.winfo_exists():
            self.console_text.config(state=tk.NORMAL)
            self.console_text.delete('1.0', tk.END)
            self.console_text.config(state=tk.DISABLED)

    def _toggle_console(self):
        if not self.editor_console_pane or not self.console_frame: return
        if self._console_visible:
            try: self.editor_console_pane.forget(self.console_frame)
            except Exception: pass
            self._console_visible=False
        else:
            try: self.editor_console_pane.add(self.console_frame, height=180, minsize=80)
            except Exception: pass
            self._console_visible=True

    # ==================== LINTER / ДИАГНОСТИКА ====================
    def _run_lint(self):
        if not self.editor: return
        try:
            code=self.editor.get('1.0','end-1c')
            issues=self.linter.lint(code, self.engine)
            self._apply_diagnostics(issues)
        except Exception as e: _dbg(f"[LINT] error: {e}")

    def _apply_diagnostics(self, issues):
        if not self.editor: return
        try:
            self.editor.tag_remove('err_line','1.0',tk.END)
            self.editor.tag_remove('warn_line','1.0',tk.END)
            self.editor.tag_configure('err_line', background='#3a1f1f')
            self.editor.tag_configure('warn_line', background='#3a341f')
        except Exception: return

        self._has_errors = any(l=='error' for _,l,_ in issues)

        # не спамим: пишем в консоль только если список ошибок изменился
        sig = tuple(sorted((ln,l,m) for ln,l,m in issues))
        changed = (sig != self._last_lint_sig)
        self._last_lint_sig = sig

        seen=set()
        for line_num, level, msg in issues:
            key=(line_num, level, msg)
            if key in seen: continue
            seen.add(key)
            tag = 'err_line' if level=='error' else 'warn_line'
            try: self.editor.tag_add(tag, f'{line_num}.0', f'{line_num}.end+1c')
            except Exception: pass
            if changed:
                self.console_log(f"Строка {line_num}: {msg}", level)

    def _block_if_errors(self, action_name):
        if self._has_errors:
            messagebox.showwarning(f"{action_name} заблокирован",
                "В коде есть ошибки (красные строки).\nИсправьте их перед экспортом.")
            return True
        return False

    def _set_theme(self, t):
        if t not in THEMES: return
        self.c=THEMES[t].copy(); self.settings.set('theme', t)
        self.root.configure(bg=self.c['bg_dark']); self.content.configure(bg=self.c['bg_dark'])
        self._style_titlebar(); self._apply_theme_recursive(self.content)
        try: self.highlighter.highlight()
        except Exception: pass
        if self.editor: self._update_ln()

    def _apply_theme_recursive(self, w):
        try:
            cls=w.__class__.__name__
            if cls in ('Text','Canvas','Scrollbar'):
                if w is getattr(self,'editor',None):
                    w.configure(bg=self.c['editor_bg'], fg=self.c['editor_fg'], insertbackground=self.c['insert'], selectbackground=self.c['sel_bg'])
                elif w is getattr(self,'line_numbers',None):
                    w.configure(bg=self.c['linenum_bg'], fg=self.c['linenum_fg'])
                return
            if cls in ('Frame','LabelFrame'):
                if w is getattr(self,'preview_holder',None): return
                w.configure(bg=self.c['bg_dark'])
            elif cls=='Label':
                if hasattr(w,'_no_theme') and w._no_theme: return
                w.configure(bg=self.c['bg_dark'], fg=self.c['text_primary'])
            elif cls=='Button':
                w.configure(bg=self.c['bg_hover'], fg=self.c['text_primary'])
            elif cls=='Entry':
                w.configure(bg=self.c['bg_input'], fg=self.c['text_primary'], insertbackground=self.c['insert'])
        except Exception: pass
        for ch in w.winfo_children(): self._apply_theme_recursive(ch)

    def clear_window(self):
        self._shutdown_real_browser(); self._stop_banner_anim()
        for w in self.content.winfo_children(): w.destroy()
        self.editor=None; self.line_numbers=None
        self.console_text=None; self.console_frame=None
        self.editor_console_pane=None; self._console_visible=False
        self._has_errors=False; self._last_lint_sig=None
    def _shutdown_real_browser(self):
        if self.real_panel: self.real_panel.shutdown(); self.real_panel=None

    def on_exit(self):
        if self.current_file and self.modified:
            r=messagebox.askyesnocancel("Выход", "Сохранить изменения?")
            if r is None: return
            if r: self._do_save()
        self._shutdown_real_browser(); self._stop_banner_anim()
        try: self.preview_server.shutdown()
        except Exception: pass
        self.root.destroy()

    def _set_file_label(self):
        if self.current_file:
            if self.current_is_cloud:
                name=f"☁ {self.current_file}"
                name=('* '+name) if self.modified else name
            else:
                name=os.path.basename(self.current_file)
                name=('* '+name) if self.modified else name
        else: name='...'
        if self.file_label: self.file_label.config(text=name)
        self.tb_title.config(text=f"RuWeb Studio 2026  v{VERSION} — {name}")

    def _sample(self, t):
        n=len(self.BANNER_COLORS); x=(t%1.0)*n; i=int(x)%n; j=(i+1)%n; f=x-int(x)
        c1,c2=self.BANNER_COLORS[i], self.BANNER_COLORS[j]
        return '#%02x%02x%02x' % tuple(int(c1[k]+(c2[k]-c1[k])*f) for k in range(3))

    def _draw_banner(self):
        b=self.hub_banner
        if not b or not b.winfo_exists(): return
        w=max(b.winfo_width(),1); h=150; b.delete('all'); step=4; ph=self._banner_phase
        for y in range(0,h,step):
            b.create_line(0,y,w,y+step, fill=self._sample((y/h)*0.35+ph*0.15), width=step)
        bw=300; bx=((ph*1.6)%1.4-0.2)*(w+bw)-bw/2
        base=self._sample(0.5*0.35+ph*0.15)
        r0,g0,b0=int(base[1:3],16), int(base[3:5],16), int(base[5:7],16)
        for i in range(0,bw,12):
            x=bx+i
            if -20<x<w+20:
                f=1-abs(i-bw/2)/(bw/2); add=int(255*(f**2)*0.30)
                b.create_line(x,0,x+12,h, width=12, fill='#%02x%02x%02x'%(min(255,r0+add),min(255,g0+add),min(255,b0+add)))
        b.create_text(367,68,anchor='nw', text='2026', font=(UI_FONT,12,'bold'), fill='#e6e6fa')
        b.create_text(58,44,anchor='nw', text='RUWEB STUDIO', font=(UI_FONT,30,'bold'), fill='white')
        b.create_text(w-30,40,anchor='ne', text=f'v{VERSION}', font=(UI_FONT,12,'bold'), fill='#ffffff')

    def _start_banner_anim(self):
        self._stop_banner_anim()
        def tick():
            if not self.hub_banner or not self.hub_banner.winfo_exists(): return
            self._banner_phase=(self._banner_phase+0.008)%1.0
            self._draw_banner(); self._banner_after=self.root.after(50, tick)
        self._banner_after=self.root.after(50, tick)
    def _stop_banner_anim(self):
        if self._banner_after:
            try: self.root.after_cancel(self._banner_after)
            except Exception: pass
            self._banner_after=None

    def show_project_hub(self):
        if self.current_file and self.modified: self._do_save()
        self.clear_window()
        self.current_file=None; self.current_is_cloud=False; self.modified=False
        self._current_view='hub'
        self.hub_banner=tk.Canvas(self.content, height=150, highlightthickness=0, bg=self.c['bg_dark'])
        self.hub_banner.pack(fill=tk.X); self.hub_banner.bind('<Configure>', lambda e: self._draw_banner())
        self._draw_banner(); self._start_banner_anim()
        tools=tk.Frame(self.content, bg=self.c['bg_panel'], height=56); tools.pack(fill=tk.X); tools.pack_propagate(False)
        tk.Label(tools, text="Проекты", font=(UI_FONT,13,'bold'), bg=self.c['bg_panel'], fg=self.c['text_primary']).pack(side=tk.LEFT, padx=20)
        self.search_var=tk.StringVar(); self.search_var.trace_add('write', lambda *a: self._load_projects())
        tk.Entry(tools, textvariable=self.search_var, font=(UI_FONT,11), bg=self.c['bg_input'], fg=self.c['text_primary'], relief=tk.FLAT, insertbackground='white').pack(side=tk.LEFT, padx=10, ipady=6, fill=tk.X, expand=True)
        if self.auth.is_logged_in():
            name=self.auth.get_display_name()
            if len(name)>18: name=name[:16]+'…'
            bt,bb,bc=f"👤 {name}", '#2f5a4f', self._show_user_menu
        else:
            bt,bb,bc="🔑 Войти", '#3a4a6b', self._open_login
        self._auth_btn=ModernButton(tools, text=bt, font=(UI_FONT,11,'bold'), bg=bb, activebackground='#4a5a7b', fg='white', relief=tk.FLAT, cursor='hand2', padx=18, pady=8, command=bc)
        self._auth_btn.pack(side=tk.RIGHT, padx=6)
        ModernButton(tools, text="⚙ Настройки", font=(UI_FONT,11,'bold'), bg='#3a4a6b', activebackground='#4a5a7b', fg='white', relief=tk.FLAT, cursor='hand2', padx=18, pady=8, command=self.show_settings).pack(side=tk.RIGHT, padx=6)
        ModernButton(tools, text="📥 Импорт", font=(UI_FONT,11,'bold'), bg='#4a5a7b', activebackground='#5a6a8b', fg='white', relief=tk.FLAT, cursor='hand2', padx=18, pady=8, command=self._import_project).pack(side=tk.RIGHT, padx=6)
        ModernButton(tools, text="+ Новый проект", font=(UI_FONT,11,'bold'), bg=self.c['accent'], activebackground=self.c['accent2'], fg='white', relief=tk.FLAT, cursor='hand2', padx=22, pady=8, command=self.new_project_dialog).pack(side=tk.RIGHT, padx=8)
        pf=tk.Frame(self.content, bg=self.c['bg_dark']); pf.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        self.hub_canvas=tk.Canvas(pf, bg=self.c['bg_dark'], highlightthickness=0)
        sb=tk.Scrollbar(pf, orient=tk.VERTICAL, command=self.hub_canvas.yview)
        self.pc=tk.Frame(self.hub_canvas, bg=self.c['bg_dark'])
        self.pc.bind('<Configure>', lambda e: self.hub_canvas.configure(scrollregion=self.hub_canvas.bbox('all')))
        self.hub_canvas.create_window((0,0), window=self.pc, anchor='nw')
        self.hub_canvas.configure(yscrollcommand=sb.set)
        self.hub_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        def _mw(e):
            try:
                if self.hub_canvas and self.hub_canvas.winfo_exists():
                    self.hub_canvas.yview_scroll(int(-1*(e.delta/120)), 'units')
            except Exception: pass
        self.root.bind_all('<MouseWheel>', _mw)
        self._load_projects(); self._load_cloud_projects_async()

    def _import_project(self):
        fp=filedialog.askopenfilename(title="Импорт проекта RuWeb",
                                      filetypes=[("RuWeb проект","*.ruweb"),("Все файлы","*.*")])
        if not fp: return
        try:
            name=os.path.basename(fp)
            dest=os.path.join(self.projects_dir, name)
            shutil.copy(fp, dest)
            self._load_projects()
            self._open_editor(dest)
            self.console_log(f"Импортирован: {name}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать: {e}")

    def show_settings(self):
        self.clear_window(); self._current_view='settings'
        head=tk.Frame(self.content, bg=self.c['bg_panel'], height=56); head.pack(fill=tk.X); head.pack_propagate(False)
        ModernButton(head, text="← Назад к проектам", font=(UI_FONT,11,'bold'), bg=self.c['bg_hover'], fg=self.c['text_primary'], relief=tk.FLAT, cursor='hand2', padx=18, pady=8, command=self.show_project_hub).pack(side=tk.LEFT, padx=20, pady=10)
        tk.Label(head, text="⚙ Настройки движка", font=(UI_FONT,14,'bold'), bg=self.c['bg_panel'], fg=self.c['text_primary']).pack(side=tk.LEFT, padx=20)
        body=tk.Frame(self.content, bg=self.c['bg_dark']); body.pack(fill=tk.BOTH, expand=True, padx=40, pady=30)
        tk.Label(body, text="Оформление", font=(UI_FONT,16,'bold'), bg=self.c['bg_dark'], fg=self.c['text_primary']).pack(anchor='w', pady=(0,10))
        tf=tk.Frame(body, bg=self.c['bg_card'], padx=20, pady=16, highlightthickness=1, highlightbackground=self.c['bg_hover']); tf.pack(fill=tk.X, pady=(0,20))
        tk.Label(tf, text="Тема интерфейса", font=(UI_FONT,12,'bold'), bg=self.c['bg_card'], fg=self.c['text_primary']).pack(anchor='w')
        tk.Label(tf, text="Переключение между тёмной и светлой темой. Сохраняется автоматически.", font=(UI_FONT,9), bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(anchor='w', pady=(2,12))
        tr=tk.Frame(tf, bg=self.c['bg_card']); tr.pack(fill=tk.X)
        cur=self.settings.get('theme','dark')
        def mtb(name, label, desc):
            act=(cur==name); f=tk.Frame(tr, bg=self.c['bg_card']); f.pack(side=tk.LEFT, padx=(0,12))
            tk.Button(f, text=label, font=(UI_FONT,11,'bold'), bg=self.c['accent'] if act else self.c['bg_hover'], fg='white' if act else self.c['text_primary'], relief=tk.FLAT, cursor='hand2', padx=22, pady=10, command=lambda: self._on_theme_click(name)).pack()
            tk.Label(f, text=desc, font=(UI_FONT,8), bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(pady=(4,0))
        mtb('dark','🌙 Тёмная','По умолчанию'); mtb('light','☀ Светлая','Для яркого освещения')
        tk.Label(body, text="Аккаунт", font=(UI_FONT,16,'bold'), bg=self.c['bg_dark'], fg=self.c['text_primary']).pack(anchor='w', pady=(10,10))
        af=tk.Frame(body, bg=self.c['bg_card'], padx=20, pady=16, highlightthickness=1, highlightbackground=self.c['bg_hover']); af.pack(fill=tk.X, pady=(0,20))
        if self.auth.is_logged_in():
            tk.Label(af, text=f"Вы вошли как {self.auth.user_email}", font=(UI_FONT,12,'bold'), bg=self.c['bg_card'], fg=self.c['text_primary']).pack(anchor='w')
            tk.Label(af, text="Облачные проекты синхронизируются с вашим аккаунтом", font=(UI_FONT,9), bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(anchor='w', pady=(2,10))
            tk.Button(af, text="🚪 Выйти", font=(UI_FONT,10,'bold'), bg='#8b2f3f', fg='white', relief=tk.FLAT, cursor='hand2', padx=16, pady=6, command=self._logout).pack(anchor='w')
        else:
            tk.Label(af, text="Войдите для синхронизации проектов в облаке", font=(UI_FONT,11), bg=self.c['bg_card'], fg=self.c['text_primary']).pack(anchor='w', pady=(0,10))
            tk.Button(af, text="🔑 Войти через Google", font=(UI_FONT,11,'bold'), bg=self.c['accent'], fg='white', relief=tk.FLAT, cursor='hand2', padx=20, pady=8, command=self._open_login).pack(anchor='w')
        tk.Label(body, text="Наши соц. сети", font=(UI_FONT,16,'bold'), bg=self.c['bg_dark'], fg=self.c['text_primary']).pack(anchor='w', pady=(10,10))
        sf=tk.Frame(body, bg=self.c['bg_card'], padx=20, pady=16, highlightthickness=1, highlightbackground=self.c['bg_hover']); sf.pack(fill=tk.X)
        tk.Label(sf, text="Связь с командой и сообществом", font=(UI_FONT,9), bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(anchor='w', pady=(0,14))
        sr=tk.Frame(sf, bg=self.c['bg_card']); sr.pack(fill=tk.X)
        def msb(label, url, color):
            f=tk.Frame(sr, bg=self.c['bg_card']); f.pack(side=tk.LEFT, padx=(0,10))
            tk.Button(f, text=label, font=(UI_FONT,11,'bold'), bg=color, fg='white', relief=tk.FLAT, cursor='hand2', padx=22, pady=10, activebackground=color, command=lambda: webbrowser.open(url, new=2)).pack(fill=tk.X, expand=True)
        msb('✈ Telegram','https://t.me/BazukaHome_Creator','#27a7e7')
        msb('🎮 Lolka','https://lolka.gg/1rg8Lg1oI','#764ba2')
        msb('🌐 Наш сайт','https://ruweb-studio.ct.ws','#43e97b')
        tk.Label(body, text="О программе", font=(UI_FONT,16,'bold'), bg=self.c['bg_dark'], fg=self.c['text_primary']).pack(anchor='w', pady=(20,10))
        ab=tk.Frame(body, bg=self.c['bg_card'], padx=20, pady=16, highlightthickness=1, highlightbackground=self.c['bg_hover']); ab.pack(fill=tk.X)
        tk.Label(ab, text=f"RuWeb Studio 2026  -  версия {VERSION}", font=(UI_FONT,11,'bold'), bg=self.c['bg_card'], fg=self.c['text_primary']).pack(anchor='w')
        tk.Label(ab, text="Движок трансляции русского кода в HTML5 + CSS + JavaScript.\nСинтаксис на основе отступов, без закрывающих тегов и слова «конец».\nФайлы проектов: .ruweb  •  Проекты: ~/RuwebProjects\n\nПредпросмотр: ⟳ Перезапуск / F5 / Ctrl+S  •  Зум кода: Ctrl + колёсико\nОблачные проекты и RuWeb AI: синхронизация в Google-аккаунте", font=(UI_FONT,7), bg=self.c['bg_card'], fg=self.c['text_secondary'], justify='left').pack(anchor='w', pady=(6,0))

    def _on_theme_click(self, t): self._set_theme(t); self.show_settings()
    def _buy_ai_sub(self):
        if not self.auth.is_logged_in():
            messagebox.showwarning("Требуется вход", "Для покупки подписки нужно войти в аккаунт.")
            self._open_login(); return
        webbrowser.open(self.ruweb_ai.get_pay_url(), new=2)

    def _load_projects(self, *a):
        for w in self.pc.winfo_children(): w.destroy()
        q=self.search_var.get().strip().lower() if hasattr(self,'search_var') else ''
        local=[]
        try:
            local=sorted([f for f in os.listdir(self.projects_dir)
                          if f.endswith('.ruweb') and not f.startswith('__cloud_')],
                         key=lambda f: os.path.getmtime(os.path.join(self.projects_dir,f)), reverse=True)
        except Exception: pass
        cloud=[]
        if self.auth.is_logged_in() and self.cloud_projects_cache:
            for n,d in self.cloud_projects_cache.items():
                cloud.append({'name':n,'updated':d.get('updated',''),'content':d.get('content','')})
        if q:
            local=[p for p in local if q in p.lower()]
            cloud=[p for p in cloud if q in p['name'].lower()]
        if not local and not cloud:
            ef=tk.Frame(self.pc, bg=self.c['bg_dark']); ef.pack(pady=60)
            tk.Label(ef, text="Проектов не найдено", font=(UI_FONT,14,'bold'), bg=self.c['bg_dark'], fg=self.c['text_primary']).pack(pady=(10,4))
            tk.Label(ef, text="Нажмите «+ Новый проект» или «📥 Импорт»", font=(UI_FONT,10), bg=self.c['bg_dark'], fg=self.c['text_secondary']).pack()
            return
        r,c=0,0
        if cloud:
            tk.Label(self.pc, text="☁ Облачные проекты", font=(UI_FONT,12,'bold'), bg=self.c['bg_dark'], fg=self.c['accent']).grid(row=r, column=0, columnspan=3, sticky='w', padx=10, pady=(0,8)); r+=1
            for p in cloud:
                self._build_cloud_card(p, r, c); c+=1
                if c>=3: c=0; r+=1
            if local:
                r+=1
                tk.Label(self.pc, text="💾 Локальные проекты", font=(UI_FONT,12,'bold'), bg=self.c['bg_dark'], fg=self.c['text_secondary']).grid(row=r, column=0, columnspan=3, sticky='w', padx=10, pady=(0,8)); r+=1; c=0
        for pf_name in local:
            self._build_card(os.path.join(self.projects_dir, pf_name), pf_name, r, c); c+=1
            if c>=3: c=0; r+=1

    def _build_cloud_card(self, proj, r, c):
        name=proj['name']; color=self.CARD_COLORS[hash(name)%len(self.CARD_COLORS)]
        card=tk.Frame(self.pc, bg=self.c['bg_card'], cursor='hand2', highlightthickness=2, highlightbackground=self.c['bg_dark'])
        card.grid(row=r, column=c, padx=10, pady=10, sticky='nsew'); card.configure(width=280, height=190); card.pack_propagate(False)
        tk.Frame(card, bg=color, height=8).pack(fill=tk.X)
        body=tk.Frame(card, bg=self.c['bg_card']); body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        top=tk.Frame(body, bg=self.c['bg_card']); top.pack(fill=tk.X)
        icon=tk.Label(top, text="☁", font=(UI_FONT,16,'bold'), bg=color, fg='white', width=3, height=1); icon.pack(side=tk.LEFT); icon._no_theme=True
        tk.Label(top, text=name[:22], font=(UI_FONT,13,'bold'), anchor='w', bg=self.c['bg_card'], fg=self.c['text_primary']).pack(side=tk.LEFT, padx=10)
        db=tk.Label(top, text="X", font=(UI_FONT,11,'bold'), bg=self.c['bg_card'], fg=self.c['text_secondary'], cursor='hand2'); db.pack(side=tk.RIGHT)
        db.bind('<Button-1>', lambda e, n=name: self._delete_cloud_project(n))
        db.bind('<Enter>', lambda e: db.config(fg='#f5576c'))
        db.bind('<Leave>', lambda e: db.config(fg=self.c['text_secondary']))
        tk.Label(body, text="☁ Облачный проект", font=(UI_FONT,9,'bold'), anchor='w', bg=self.c['bg_card'], fg=color).pack(anchor='w', pady=(14,2))
        upd=proj.get('updated','')
        if upd:
            try: mt=datetime.fromisoformat(upd.replace('Z','+00:00')).strftime('%d.%m.%Y %H:%M')
            except Exception: mt=upd[:16]
        else: mt='—'
        tk.Label(body, text=f"Изменён: {mt}", font=(UI_FONT,9), anchor='w', bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(anchor='w')
        tk.Label(body, text="Синхронизирован ✓", font=(UI_FONT,9), anchor='w', bg=self.c['bg_card'], fg='#43e97b').pack(anchor='w', pady=(4,0))
        tk.Label(body, text="Открыть →", font=(UI_FONT,10,'bold'), bg=self.c['bg_card'], fg=color).pack(anchor='w', pady=(6,0))
        for w in [card, body, top, icon]+[x for x in body.winfo_children() if x != db]:
            w.bind('<Button-1>', lambda e, n=name: self._open_cloud_project(n))
            w.bind('<Enter>', lambda e: card.config(highlightbackground=color))
            w.bind('<Leave>', lambda e: card.config(highlightbackground=self.c['bg_dark']))

    def _delete_cloud_project(self, name):
        if messagebox.askyesno("Удаление", f"Удалить облачный проект «{name}»?"):
            ok=self.cloud.delete_project(name)
            if ok:
                self.cloud_projects_cache.pop(name, None)
                tmp=os.path.join(self.projects_dir, f"__cloud_{name}.ruweb")
                if os.path.exists(tmp):
                    try: os.remove(tmp)
                    except Exception: pass
                self._load_projects()
                self.console_log(f"Удалён облачный проект: {name}")
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить из облака")

    def _open_cloud_project(self, name):
        data=self.cloud_projects_cache.get(name)
        if not data:
            messagebox.showerror("Ошибка", "Проект не найден в облаке"); return
        temp_fp=os.path.join(self.projects_dir, f"__cloud_{name}.ruweb")
        try:
            with open(temp_fp, 'w', encoding='utf-8') as f: f.write(data['content'])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить: {e}"); return
        self.current_is_cloud=True; self._open_editor(temp_fp)
        self.current_file=name; self.current_is_cloud=True; self._cloud_temp_path=temp_fp
        self._set_file_label()

    def _build_card(self, pp, pf_name, r, c):
        pn=pf_name.replace('.ruweb',''); color=self.CARD_COLORS[hash(pn)%len(self.CARD_COLORS)]
        card=tk.Frame(self.pc, bg=self.c['bg_card'], cursor='hand2', highlightthickness=2, highlightbackground=self.c['bg_dark'])
        card.grid(row=r, column=c, padx=10, pady=10, sticky='nsew'); card.configure(width=280, height=190); card.pack_propagate(False)
        tk.Frame(card, bg=color, height=8).pack(fill=tk.X)
        body=tk.Frame(card, bg=self.c['bg_card']); body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        top=tk.Frame(body, bg=self.c['bg_card']); top.pack(fill=tk.X)
        icon=tk.Label(top, text=pn[0].upper(), font=(UI_FONT,18,'bold'), bg=color, fg='white', width=3, height=1); icon.pack(side=tk.LEFT); icon._no_theme=True
        tk.Label(top, text=pn[:22], font=(UI_FONT,13,'bold'), anchor='w', bg=self.c['bg_card'], fg=self.c['text_primary']).pack(side=tk.LEFT, padx=10)
        db=tk.Label(top, text="X", font=(UI_FONT,11,'bold'), bg=self.c['bg_card'], fg=self.c['text_secondary'], cursor='hand2'); db.pack(side=tk.RIGHT)
        db.bind('<Button-1>', lambda e, p=pp: self._delete_project(p))
        db.bind('<Enter>', lambda e: db.config(fg='#f5576c'))
        db.bind('<Leave>', lambda e: db.config(fg=self.c['text_secondary']))
        mt=datetime.fromtimestamp(os.path.getmtime(pp)).strftime('%d.%m.%Y %H:%M')
        tk.Label(body, text=f"Изменён: {mt}", font=(UI_FONT,9), anchor='w', bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(anchor='w', pady=(14,2))
        tk.Label(body, text=f"Размер: {os.path.getsize(pp)/1024:.1f} KB", font=(UI_FONT,9), anchor='w', bg=self.c['bg_card'], fg=self.c['text_secondary']).pack(anchor='w')
        tk.Label(body, text="Открыть →", font=(UI_FONT,10,'bold'), bg=self.c['bg_card'], fg=color).pack(anchor='w', pady=(8,0))
        for w in [card, body, top, icon]+[x for x in body.winfo_children() if x != db]:
            w.bind('<Button-1>', lambda e, p=pp: self._open_editor(p))
            w.bind('<Enter>', lambda e: card.config(highlightbackground=color))
            w.bind('<Leave>', lambda e: card.config(highlightbackground=self.c['bg_dark']))
        card.bind('<Button-3>', lambda e, p=pp: self._ctx_menu(e, p))

    def _ctx_menu(self, event, pp):
        menu=tk.Menu(self.root, tearoff=0, bg=self.c['bg_card'], fg=self.c['text_primary'])
        menu.add_command(label="Открыть", command=lambda: self._open_editor(pp))
        menu.add_command(label="Экспорт HTML", command=lambda: self._quick_export(pp))
        menu.add_separator()
        menu.add_command(label="Удалить", command=lambda: self._delete_project(pp))
        menu.tk_popup(event.x_root, event.y_root)

    def new_project_dialog(self):
        d=tk.Toplevel(self.root); d.title("Новый проект"); d.geometry("500x340")
        d.configure(bg=self.c['bg_panel']); d.transient(self.root); d.grab_set(); d.update_idletasks()
        d.geometry(f"+{self.root.winfo_x()+(self.root.winfo_width()-500)//2}+{self.root.winfo_y()+(self.root.winfo_height()-340)//2}")
        tk.Label(d, text="Создание проекта", font=(UI_FONT,14,'bold'), bg=self.c['bg_panel'], fg=self.c['text_primary']).pack(pady=14)
        tk.Label(d, text="Название:", bg=self.c['bg_panel'], fg=self.c['text_secondary'], font=(UI_FONT,10)).pack(anchor='w', padx=30)
        ne=tk.Entry(d, font=(UI_FONT,12), bg=self.c['bg_input'], fg=self.c['text_primary'], relief=tk.FLAT, insertbackground='white')
        ne.pack(fill=tk.X, padx=30, pady=(5,14), ipady=8); ne.insert(0, "мой_сайт")
        tk.Label(d, text="Место сохранения:", bg=self.c['bg_panel'], fg=self.c['text_secondary'], font=(UI_FONT,10)).pack(anchor='w', padx=30)
        lf=tk.Frame(d, bg=self.c['bg_panel']); lf.pack(fill=tk.X, padx=30, pady=(4,14))
        lv=tk.StringVar(value='local')
        lo=tk.Frame(lf, bg=self.c['bg_card'], padx=14, pady=10, highlightthickness=2, highlightbackground=self.c['accent']); lo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        tk.Radiobutton(lo, text="💾 На устройстве", variable=lv, value='local', bg=self.c['bg_card'], fg=self.c['text_primary'], selectcolor=self.c['bg_input'], font=(UI_FONT,10,'bold'), anchor='w').pack(anchor='w')
        tk.Label(lo, text="Файл в ~/RuwebProjects", font=(UI_FONT,8), bg=self.c['bg_card'], fg=self.c['text_secondary'], anchor='w').pack(anchor='w')
        co=tk.Frame(lf, bg=self.c['bg_card'], padx=14, pady=10, highlightthickness=2, highlightbackground=self.c['bg_hover']); co.pack(side=tk.LEFT, fill=tk.X, expand=True)
        crb=tk.Radiobutton(co, text="☁ В облаке", variable=lv, value='cloud', bg=self.c['bg_card'], fg=self.c['text_primary'], selectcolor=self.c['bg_input'], font=(UI_FONT,10,'bold'), anchor='w'); crb.pack(anchor='w')
        tk.Label(co, text="Синхронизация с аккаунтом", font=(UI_FONT,8), bg=self.c['bg_card'], fg=self.c['text_secondary'], anchor='w').pack(anchor='w')
        if not self.auth.is_logged_in():
            crb.config(state='disabled')
            tk.Label(co, text="⚠ Требуется вход", font=(UI_FONT,8,'bold'), bg=self.c['bg_card'], fg='#ffcc00', anchor='w').pack(anchor='w')
        def uh(*e):
            if lv.get()=='local':
                lo.config(highlightbackground=self.c['accent']); co.config(highlightbackground=self.c['bg_hover'])
            else:
                lo.config(highlightbackground=self.c['bg_hover']); co.config(highlightbackground=self.c['accent'])
        lv.trace_add('write', uh)
        bf=tk.Frame(d, bg=self.c['bg_panel']); bf.pack(fill=tk.X, padx=30)
        def create():
            name=ne.get().strip().replace('.ruweb','')
            if not name:
                messagebox.showwarning("Ошибка", "Введите название"); return
            if lv.get()=='cloud':
                if not self.auth.is_logged_in():
                    messagebox.showwarning("Ошибка", "Войдите в аккаунт"); return
                if not self._check_internet():
                    messagebox.showwarning("Ошибка", "Нет подключения к интернету."); return
                fp=os.path.join(self.projects_dir, f"{name}.ruweb")
                content=self.engine.get_base_template()
                with open(fp, 'w', encoding='utf-8') as f: f.write(content)
                s, err = self.cloud.save_project(name, content)
                if not s: messagebox.showwarning("Облако", f"Проект создан локально.\nОшибка облака: {err}")
                self.cloud_projects_cache[name]={'name':name,'content':content,'updated':''}
                d.destroy(); self._open_editor(fp)
            else:
                fp=os.path.join(self.projects_dir, f"{name}.ruweb")
                with open(fp, 'w', encoding='utf-8') as f: f.write(self.engine.get_base_template())
                d.destroy(); self._open_editor(fp)
        ModernButton(bf, text="Создать", font=(UI_FONT,11,'bold'), bg=self.c['accent'], activebackground=self.c['accent2'], fg='white', relief=tk.FLAT, cursor='hand2', padx=28, pady=9, command=create).pack(side=tk.RIGHT)
        ModernButton(bf, text="Отмена", font=(UI_FONT,11), bg=self.c['bg_hover'], fg=self.c['text_primary'], relief=tk.FLAT, command=d.destroy).pack(side=tk.RIGHT, padx=10)

    def _check_internet(self):
        try:
            requests.get('https://www.google.com', timeout=3); return True
        except Exception: return False

    def _open_editor(self, fp):
        self.clear_window(); self.current_file=fp; self.current_is_cloud=False
        self.modified=False; self._current_view='editor'
        self._build_editor()
        try:
            with open(fp, 'r', encoding='utf-8') as f: content=f.read()
            if not content.strip():
                content=self.engine.get_base_template()
                with open(fp, 'w', encoding='utf-8') as f: f.write(content)
            self.editor.delete('1.0', tk.END); self.editor.insert('1.0', content)
            self.modified=False
            self._update_ln(); self._do_highlight(); self._set_file_label()
            self.status_label.config(text=f"Открыт: {os.path.basename(fp)}")
            self.root.after(400, self._soft_refresh)
            self.root.after(500, self._run_lint)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _build_editor(self):
        tb=tk.Frame(self.content, bg=self.c['bg_panel'], height=48); tb.pack(fill=tk.X); tb.pack_propagate(False)
        ModernButton(tb, text="←", font=(UI_FONT,12,'bold'), bg=self.c['bg_hover'], fg=self.c['text_primary'], relief=tk.FLAT, cursor='hand2', padx=14, command=self.show_project_hub).pack(side=tk.LEFT, padx=(12,4))
        tab=tk.Frame(tb, bg=self.c['bg_card'], padx=4); tab.pack(side=tk.LEFT, padx=6, pady=8, fill=tk.Y)
        self.file_label=tk.Label(tab, text="...", font=(UI_FONT,11,'bold'), bg=self.c['bg_card'], fg=self.c['text_primary']); self.file_label.pack(side=tk.LEFT, padx=10)
        ModernButton(tb, text="🤖 RuWeb AI", font=(UI_FONT,10,'bold'), bg='#764ba2', activebackground='#8b5cf6', fg='white', relief=tk.FLAT, cursor='hand2', padx=12, command=self._open_ruweb_ai).pack(side=tk.RIGHT, padx=4, pady=9)
        self.console_btn=ModernButton(tb, text="Консоль", font=(UI_FONT,10,'bold'), bg=self.c['bg_hover'],
                                      fg=self.c['text_primary'], relief=tk.FLAT, cursor='hand2', padx=12,
                                      command=self._toggle_console)
        self.console_btn.pack(side=tk.RIGHT, padx=4, pady=9)
        for txt, cmd, bg in [("Экспорт", self.export_html, self.c['bg_hover']),
                             ("В браузере", self.open_in_browser, '#2f3a4f'),
                             ("Сохранить", self.save_file, '#2f4f3f')]:
            ModernButton(tb, text=txt, font=(UI_FONT,10,'bold'), bg=bg, fg=self.c['text_primary'], relief=tk.FLAT, cursor='hand2', padx=12, command=cmd).pack(side=tk.RIGHT, padx=4, pady=9)
        mp=tk.PanedWindow(self.content, orient=tk.HORIZONTAL, bg=self.c['bg_dark'], sashwidth=4); mp.pack(fill=tk.BOTH, expand=True)
        pp=tk.Frame(self.content, bg=self.c['bg_dark']); mp.add(pp, width=600)
        ph=tk.Frame(pp, bg=self.c['bg_card'], height=34); ph.pack(fill=tk.X)
        self.preview_title=tk.Label(ph, text="Предпросмотр (нажмите ⟳ или F5 для обновления)", bg=self.c['bg_card'], fg=self.c['text_secondary'], font=(UI_FONT,10,'bold')); self.preview_title.pack(side=tk.LEFT, padx=10)
        ModernButton(ph, text="⟳ Перезапуск", font=(UI_FONT,10,'bold'), bg='#2f4f3f', activebackground='#3a6050', fg='white', relief=tk.FLAT, command=self._restart_preview).pack(side=tk.RIGHT, padx=5)
        self.preview_holder=tk.Frame(pp, bg='#ffffff'); self.preview_holder.pack(fill=tk.BOTH, expand=True)
        ep=tk.Frame(self.content, bg=self.c['bg_dark']); mp.add(ep, width=700)

        self.editor_console_pane=tk.PanedWindow(ep, orient=tk.VERTICAL, bg=self.c['bg_dark'], sashwidth=4, sashrelief=tk.FLAT)
        self.editor_console_pane.pack(fill=tk.BOTH, expand=True)

        editor_area=tk.Frame(self.editor_console_pane, bg=self.c['bg_dark'])
        self.editor_console_pane.add(editor_area, minsize=200)
        ec=tk.Frame(editor_area, bg=self.c['bg_dark']); ec.pack(fill=tk.BOTH, expand=True)
        self.line_numbers=tk.Text(ec, width=7, padx=8, pady=12, bg=self.c['linenum_bg'], fg=self.c['linenum_fg'], font=(CODE_FONT, self._font_size), relief=tk.FLAT, state=tk.DISABLED)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        self.editor=tk.Text(ec, wrap=tk.NONE, bg=self.c['editor_bg'], fg=self.c['editor_fg'], insertbackground=self.c['insert'], font=(CODE_FONT, self._font_size), relief=tk.FLAT, padx=15, pady=12, undo=True, maxundo=100, selectbackground=self.c['sel_bg'], tabs=('2c',))
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        es=tk.Scrollbar(ec, command=self._scroll); es.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor.configure(yscrollcommand=es.set)

        self.console_frame=tk.Frame(self.editor_console_pane, bg=self.c['bg_panel'])
        console_head=tk.Frame(self.console_frame, bg=self.c['bg_panel'], height=32)
        console_head.pack(fill=tk.X); console_head.pack_propagate(False)
        tk.Label(console_head, text="📋 Консоль RuWeb", bg=self.c['bg_panel'], fg=self.c['text_primary'],
                 font=(UI_FONT,10,'bold')).pack(side=tk.LEFT, padx=12, pady=6)
        close_btn=tk.Label(console_head, text="✕", bg=self.c['bg_panel'], fg=self.c['text_secondary'],
                           font=(UI_FONT,10,'bold'), cursor='hand2', padx=8)
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind('<Button-1>', lambda e: self._toggle_console())
        close_btn.bind('<Enter>', lambda e: close_btn.config(fg='#f5576c'))
        close_btn.bind('<Leave>', lambda e: close_btn.config(fg=self.c['text_secondary']))
        clear_btn=tk.Label(console_head, text="Очистить", bg=self.c['bg_panel'], fg=self.c['text_secondary'],
                           font=(UI_FONT,9), cursor='hand2', padx=8)
        clear_btn.pack(side=tk.RIGHT)
        clear_btn.bind('<Button-1>', lambda e: self.console_clear())
        clear_btn.bind('<Enter>', lambda e: clear_btn.config(fg=self.c['text_primary']))
        clear_btn.bind('<Leave>', lambda e: clear_btn.config(fg=self.c['text_secondary']))
        self.console_text=tk.Text(self.console_frame, bg=self.c['console_bg'], fg=self.c['console_fg'],
                                  font=('Consolas',10), relief=tk.FLAT, padx=10, pady=5,
                                  state=tk.DISABLED, wrap=tk.WORD)
        self.console_text.pack(fill=tk.BOTH, expand=True)
        console_sc=tk.Scrollbar(self.console_text, command=self.console_text.yview)
        console_sc.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_text.config(yscrollcommand=console_sc.set)
        self._console_visible=False

        self.status_bar=tk.Frame(self.content, bg=self.c['bg_panel'], height=26); self.status_bar.pack(fill=tk.X); self.status_bar.pack_propagate(False)
        tk.Frame(self.status_bar, bg=self.c['accent'], width=4).pack(side=tk.LEFT, fill=tk.Y)
        self.status_label=tk.Label(self.status_bar, text="Готов", font=(UI_FONT,9), bg=self.c['bg_panel'], fg=self.c['text_secondary']); self.status_label.pack(side=tk.LEFT, padx=12)
        self.cursor_label=tk.Label(self.status_bar, text="Стр: 1, Стлб: 1", font=(UI_FONT,9), bg=self.c['bg_panel'], fg=self.c['text_secondary']); self.cursor_label.pack(side=tk.RIGHT, padx=15)
        self.highlighter=SyntaxHighlighter(self.editor)
        self.editor.bind('<KeyRelease>', self._on_change)
        self.editor.bind('<ButtonRelease-1>', self._cursor_pos)
        self.editor.bind('<Key>', self._cursor_pos)
        self.editor.bind('<Return>', self._on_enter)
        self.editor.bind('<Tab>', self._on_tab)
        self.editor.bind('<Shift-Tab>', self._on_shift_tab)
        self.editor.bind('<BackSpace>', self._on_backspace)
        self.editor.bind('<Control-MouseWheel>', self._on_zoom)
        self.line_numbers.bind('<Control-MouseWheel>', self._on_zoom)
        self._kc_map=self._build_keycode_map()
        self.editor.bind('<KeyPress>', self._on_editor_key)
        self.root.bind('<KeyPress>', self._on_root_key)
        self.root.bind('<F5>', lambda e: self._restart_preview())
        self._start_preview_engine()

    def _open_ruweb_ai(self):
        # Открываем окно БЕЗ блокирующих сетевых вызовов в главном потоке
        if self.ai_window is None:
            self.ai_window=RuWebAIWindow(self.root, self.ruweb_ai, self.editor, self._get_colors, self._open_login)
        self.ai_window.show()

    def _on_zoom(self, event):
        self._font_size=min(28, self._font_size+1) if event.delta>0 else max(8, self._font_size-1)
        f=(CODE_FONT, self._font_size)
        self.editor.configure(font=f); self.line_numbers.configure(font=f)
        self._update_ln(); self.status_label.config(text=f"Масштаб кода: {self._font_size}pt")
        return 'break'

    def _update_ln(self, event=None):
        try:
            lines=self.editor.get('1.0','end-1c').split('\n')
            self.line_numbers.config(state=tk.NORMAL); self.line_numbers.delete('1.0', tk.END)
            for i, line in enumerate(lines, start=1):
                dots=(len(line)-len(line.lstrip(' ')))//2
                self.line_numbers.insert(tk.END, (f"{i:>2} {'•'*dots}" if dots else f"{i:>2}")+'\n')
            self.line_numbers.delete('end-1c', tk.END); self.line_numbers.config(state=tk.DISABLED)
        except Exception: pass

    def _get_line_indent(self, ln):
        try:
            line=self.editor.get(f'{ln}.0', f'{ln}.end'); return len(line)-len(line.lstrip(' '))
        except Exception: return 0
    def _get_line_text(self, ln):
        try: return self.editor.get(f'{ln}.0', f'{ln}.end')
        except Exception: return ''

    def _on_enter(self, event):
        ln=int(self.editor.index(tk.INSERT).split('.')[0])
        cur=self._get_line_text(ln); stripped=cur.lstrip(' ')
        ind=' '*(len(cur)-len(stripped))
        if stripped.startswith('|'):
            self.editor.insert(tk.INSERT, '\n'+ind+'| '); self.root.after(10, self._update_ln); return 'break'
        if not stripped:
            self.editor.insert(tk.INSERT, '\n'+ind); self.root.after(10, self._update_ln); return 'break'
        if stripped.endswith('/') and not stripped.startswith('/'):
            self.editor.insert(tk.INSERT, '\n'+ind); self.root.after(10, self._update_ln); return 'break'
        has_text=bool(re.search(r'"[^"]*"\s*$', stripped))
        is_js=any(stripped.startswith(k) for k in self.JS_OPENERS)
        is_html=any(stripped.startswith(t) for t in self.HTML_OPENERS)
        if (is_js or is_html) and not has_text:
            self.editor.insert(tk.INSERT, '\n'+ind+INDENT); self.root.after(10, self._update_ln); return 'break'
        self.editor.insert(tk.INSERT, '\n'+ind); self.root.after(10, self._update_ln); return 'break'

    def _on_tab(self, event):
        try:
            fl=int(self.editor.index(tk.SEL_FIRST).split('.')[0]); ll=int(self.editor.index(tk.SEL_LAST).split('.')[0])
            for ln in range(fl, ll+1): self.editor.insert(f'{ln}.0', INDENT)
            self.editor.tag_add(tk.SEL, f'{fl}.0', f'{ll}.end'); self.root.after(10, self._update_ln); return 'break'
        except tk.TclError: pass
        self.editor.insert(tk.INSERT, INDENT); self.root.after(10, self._update_ln); return 'break'

    def _on_shift_tab(self, event):
        try:
            fl=int(self.editor.index(tk.SEL_FIRST).split('.')[0]); ll=int(self.editor.index(tk.SEL_LAST).split('.')[0])
            for ln in range(fl, ll+1):
                line=self._get_line_text(ln)
                if line.startswith(INDENT): self.editor.delete(f'{ln}.0', f'{ln}.2')
                elif line.startswith(' '): self.editor.delete(f'{ln}.0', f'{ln}.1')
            self.editor.tag_add(tk.SEL, f'{fl}.0', f'{ll}.end')
        except tk.TclError:
            ln=int(self.editor.index(tk.INSERT).split('.')[0]); line=self._get_line_text(ln)
            if line.startswith(INDENT): self.editor.delete(f'{ln}.0', f'{ln}.2')
            elif line.startswith(' '): self.editor.delete(f'{ln}.0', f'{ln}.1')
        self.root.after(10, self._update_ln); return 'break'

    def _on_backspace(self, event):
        ln, col = self.editor.index(tk.INSERT).split('.'); col=int(col)
        if col==0: return None
        line=self._get_line_text(ln)
        if line[:col].strip()=='':
            if line.startswith(INDENT) and col>=2 and col==len(line)-len(line.lstrip(' ')):
                nc=max(0, col-(2 if col%2==0 else 1))
                self.editor.delete(f'{ln}.{nc}', f'{ln}.{col}'); self.root.after(10, self._update_ln); return 'break'
        return None

    def _start_preview_engine(self):
        self.preview_mode='none'
        if IS_WIN and RealBrowserPanel.find_browser_exe():
            self.real_panel=RealBrowserPanel(self.root, self.preview_holder, self.preview_url, on_fail=self._fallback_preview, on_ready=self._on_real_ready)
            if self.real_panel.start():
                self.preview_mode='real_starting'; self.preview_title.config(text="Запуск браузерного движка…"); return
            self.real_panel=None
        self._fallback_preview()

    def _on_real_ready(self):
        self.preview_mode='real'
        self.preview_title.config(text="Предпросмотр: браузер RuWeb (⟳ / F5 для обновления)")
        try:
            self.preview_server.ruweb_html=self._render_html(self.editor.get('1.0','end-1c'))
            self.real_panel.reload()
        except Exception as e: _dbg(f"[PREVIEW] ready error: {e}")

    def _fallback_preview(self):
        self._shutdown_real_browser()
        for w in self.preview_holder.winfo_children(): w.destroy()
        if HAS_TKW:
            self.preview_mode='tkinterweb'
            try:
                self.browser_frame=HtmlFrame(self.preview_holder, messages_enabled=False)
                self.browser_frame.pack(fill=tk.BOTH, expand=True)
                self.preview_title.config(text="Предпросмотр: HTML+CSS (ограниченная поддержка)")
                if hasattr(self,'editor') and self.editor:
                    self.browser_frame.load_html(self._render_html(self.editor.get('1.0','end-1c')))
            except Exception as e:
                tk.Label(self.preview_holder, text=f"Ошибка tkinterweb:\n{e}", bg='white', fg='red', justify='center').pack(expand=True)
        else:
            self.preview_mode='none'
            tk.Label(self.preview_holder, text="Предпросмотр недоступен\n\npip install tkinterweb", bg='white', fg='red', justify='center').pack(expand=True)

    def _soft_refresh(self):
        try:
            html=self._render_html(self.editor.get('1.0','end-1c'))
            self.preview_server.ruweb_html=html
            if self.preview_mode=='real' and self.real_panel: self.real_panel.reload()
            elif self.preview_mode=='tkinterweb' and self.browser_frame: self.browser_frame.load_html(html)
        except Exception: pass

    def _restart_preview(self, event=None):
        try:
            html=self._render_html(self.editor.get('1.0','end-1c'))
            self.preview_server.ruweb_html=html
        except Exception: return 'break'
        if self.preview_mode=='real' and self.real_panel:
            self.preview_title.config(text="⟳ Перезапуск браузерного движка…")
            self.status_label.config(text="Перезапуск браузера…")
            self.preview_mode='real_starting'; self.real_panel.restart()
        elif self.preview_mode=='real_starting':
            self.status_label.config(text="Браузер ещё запускается…")
        elif self.preview_mode=='tkinterweb' and self.browser_frame:
            try:
                self.browser_frame.load_html(html); self.status_label.config(text="Предпросмотр обновлён")
            except Exception: pass
        self.root.after(300, self._run_lint)
        return 'break'

    def _build_keycode_map(self):
        if sys.platform=='win32': vk={'s':83,'c':67,'v':86,'x':88,'a':65,'z':90,'y':89,'e':69}
        elif sys.platform=='darwin': vk={'s':1,'c':8,'v':9,'x':7,'a':0,'z':6,'y':16,'e':14}
        else: vk={'s':39,'c':54,'v':55,'x':53,'a':38,'z':52,'y':29,'e':26}
        actions={'s':self.save_file,'e':self.export_html,'c':self.copy_text,'v':self.paste_text,
                 'x':self.cut_text,'a':self.select_all,'z':self.undo,'y':self.redo}
        return {vk[k]: actions[k] for k in actions}
    def _on_editor_key(self, event):
        if event.state & 0x4:
            a=self._kc_map.get(event.keycode)
            if a: return a()
        return None
    def _on_root_key(self, event):
        if event.state & 0x4:
            a=self._kc_map.get(event.keycode)
            if a: return a()
        return None

    def copy_text(self, event=None):
        try:
            self.root.clipboard_clear(); self.root.clipboard_append(self.editor.get(tk.SEL_FIRST, tk.SEL_LAST))
            self.status_label.config(text="Скопировано")
        except tk.TclError: pass
        return 'break'
    def paste_text(self, event=None):
        try:
            t=self.root.clipboard_get()
            if t:
                try: self.editor.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError: pass
                self.editor.insert(tk.INSERT, t); self.status_label.config(text="Вставлено")
        except tk.TclError: pass
        return 'break'
    def cut_text(self, event=None):
        try:
            self.root.clipboard_clear(); self.root.clipboard_append(self.editor.get(tk.SEL_FIRST, tk.SEL_LAST))
            self.editor.delete(tk.SEL_FIRST, tk.SEL_LAST); self.status_label.config(text="Вырезано")
        except tk.TclError: pass
        return 'break'
    def select_all(self, event=None):
        self.editor.tag_add(tk.SEL, '1.0', 'end-1c'); self.editor.mark_set(tk.INSERT, '1.0'); self.editor.see(tk.INSERT); return 'break'
    def undo(self, event=None):
        try: self.editor.edit_undo(); self.status_label.config(text="Отменено"); self.root.after(10, self._update_ln)
        except tk.TclError: pass
        return 'break'
    def redo(self, event=None):
        try: self.editor.edit_redo(); self.status_label.config(text="Повторено"); self.root.after(10, self._update_ln)
        except tk.TclError: pass
        return 'break'

    def _get_save_path(self):
        if self.current_is_cloud:
            return getattr(self, '_cloud_temp_path', os.path.join(self.projects_dir, f"{self.current_file}.ruweb"))
        return self.current_file

    def save_file(self, event=None):
        if not self.current_file: return 'break'
        self._saving=True
        try:
            content=self.editor.get('1.0','end-1c')
            lp=self._get_save_path()
            with open(lp, 'w', encoding='utf-8') as f: f.write(content)
            if self.current_is_cloud:
                name=self.current_file.replace('.ruweb','')
                self.status_label.config(text="Синхронизация с облаком...")
                threading.Thread(target=self._save_to_cloud_async, args=(name, content), daemon=True).start()
            else:
                self.modified=False; self._set_file_label()
                self.status_label.config(text=f"Сохранено в {datetime.now().strftime('%H:%M:%S')}")
                self.console_log(f"Сохранено: {os.path.basename(lp)}")
                self._restart_preview()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
        finally:
            self._saving=False
        return 'break'

    def _save_to_cloud_async(self, name, content):
        s, err = self.cloud.save_project(name, content)
        self.root.after(0, lambda: self._on_cloud_saved(s, err, name, content))
    def _on_cloud_saved(self, s, err, name, content):
        if s:
            self.modified=False; self._set_file_label()
            self.status_label.config(text=f"☁ Сохранено в облаке в {datetime.now().strftime('%H:%M:%S')}")
            self.console_log(f"☁ Сохранено в облаке: {name}")
            self.cloud_projects_cache[name]={'name':name,'content':content,'updated':''}
        else:
            # Понятное сообщение вместо "неизвестной ошибки"
            self.status_label.config(text="⚠ Облако недоступно (таймаут сети). Проект сохранён локально.")
            self.console_log(f"Облако недоступно (таймаут сети). Проект «{name}» сохранён локально.", 'warning')
        self._restart_preview()

    def _do_save(self):
        if self.current_file:
            try:
                content=self.editor.get('1.0','end-1c')
                with open(self._get_save_path(), 'w', encoding='utf-8') as f: f.write(content)
                self.modified=False
                if self.current_is_cloud:
                    self.cloud.save_project(self.current_file.replace('.ruweb',''), content)
            except Exception: pass

    def _render_html(self, rc):
        hc=self.engine.translate(rc)
        if '<html' not in hc.lower():
            hc=('<!DOCTYPE html>\n<html lang="ru">\n<head>\n<meta charset="UTF-8">\n'
                + self.engine.CONSOLE_BRIDGE + '\n</head>\n<body>\n' + hc + '\n</body>\n</html>')
        return hc

    def export_html(self, event=None):
        if not self.current_file:
            messagebox.showwarning("Ошибка", "Откройте проект"); return 'break'
        if self._block_if_errors("Экспорт"): return 'break'
        hp=filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML","*.html")])
        if hp:
            with open(hp, 'w', encoding='utf-8') as f: f.write(self._render_html(self.editor.get('1.0','end-1c')))
            self.status_label.config(text="Экспортировано"); messagebox.showinfo("Готово", f"Сохранено: {hp}")
            self.console_log(f"Экспортировано в HTML: {hp}")
        return 'break'

    def open_in_browser(self, event=None):
        if not self.current_file:
            messagebox.showwarning("Ошибка", "Откройте проект"); return 'break'
        if self._block_if_errors("Запуск в браузере"): return 'break'
        self.save_file()
        temp_html=os.path.join(tempfile.gettempdir(), 'ruweb_preview.html')
        with open(temp_html, 'w', encoding='utf-8') as f: f.write(self._render_html(self.editor.get('1.0','end-1c')))
        webbrowser.open(f'file://{temp_html}')
        self.status_label.config(text="Открыто в браузере (F12 — консоль)")
        self.console_log("Открыто во внешнем браузере")
        return 'break'

    def _quick_export(self, pp):
        hp=pp.replace('.ruweb', '.html')
        with open(pp, 'r', encoding='utf-8') as f: rc=f.read()
        with open(hp, 'w', encoding='utf-8') as f: f.write(self._render_html(rc))
        messagebox.showinfo("Готово", f"Сохранено: {hp}")

    def _delete_project(self, pp):
        if messagebox.askyesno("Удаление", f"Удалить {os.path.basename(pp)}?\nФайл будет удалён с компьютера."):
            try:
                os.remove(pp)
                self.console_log(f"Удалён локальный проект: {os.path.basename(pp)}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить файл: {e}")
            self._load_projects()

    def _on_change(self, event=None):
        if getattr(self, '_saving', False): return
        self.modified=True; self._set_file_label(); self._cursor_pos()
        if self._highlight_after:
            try: self.root.after_cancel(self._highlight_after)
            except Exception: pass
        self._highlight_after=self.root.after(250, self._do_highlight)
        if self._lint_after:
            try: self.root.after_cancel(self._lint_after)
            except Exception: pass
        self._lint_after=self.root.after(350, self._run_lint)

    def _do_highlight(self):
        try: self.highlighter.highlight()
        except Exception: pass

    def _cursor_pos(self, event=None):
        line, col = self.editor.index(tk.INSERT).split('.')
        self.cursor_label.config(text=f"Стр: {line}, Стлб: {int(col)+1}")

    def _scroll(self, *args):
        self.editor.yview(*args); self.line_numbers.yview(*args)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    if not HAS_REQUESTS:
        import tkinter.messagebox as mb
        mb.showerror("Ошибка зависимостей", "Не установлен модуль requests.\n\nУстановите: pip install requests")
        sys.exit(1)
    app = RuwebStudio()
    app.run()