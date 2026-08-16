# ruweb_ai.py - v5.7 - понимает БОЛЬШИЕ промты: разбивает на команды и выполняет по порядку
import tkinter as tk
from tkinter import messagebox
import os, re, json, random, threading, webbrowser, time
from datetime import datetime
import requests

try:
    from ruweb_engine import RuwebEngine
    _ENGINE = RuwebEngine()
except Exception:
    _ENGINE = None

FIREBASE_PROJECT_ID = "ruweb-studio"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
AI_PAY_URL = "https://ruweb-studio.ct.ws/pay_ai.php"


class RuWebAI:
    NAME = "RuWeb AI"
    CREATE_RE = r'(сделай|создай|собери|напиши|сгенерируй|добавь|допиши|хочу|нужен|нужна|нужно)'
    TOPIC_NAMES = {'game': 'игра 🎮', 'business': 'бизнес 📈', 'cafe': 'кафе ☕', 'shop': 'магазин 🛒',
                   'portfolio': 'портфолио 🎨', 'generic': 'универсальный ✨'}
    COLORS = {'красн': '#ff4757', 'син': '#3742fa', 'голуб': '#70a1ff', 'зелён': '#2ed573',
              'зелен': '#2ed573', 'бел': '#ffffff', 'чёрн': '#111111', 'черн': '#111111',
              'розов': '#ff6b81', 'фиолет': '#a55eea', 'оранж': '#ffa502', 'жёлт': '#ffd32a',
              'желт': '#ffd32a', 'сер': '#747d8c', 'золот': '#ffd700'}

    def __init__(self, auth, settings):
        self.auth = auth
        self.settings = settings
        self.engine = _ENGINE
        self.history_file = os.path.join(os.path.expanduser('~'), '.ruweb_ai_history.json')
        self.chat_history = self._load_history()
        self._last = None
        self.user_name = None

    def _load_history(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history[-40:], f, ensure_ascii=False)
        except Exception:
            pass

    def clear_history(self):
        self.chat_history = []
        self._save_history()

    def _pick(self, pool):
        opts = [p for p in pool if p != self._last] or pool
        r = random.choice(opts)
        self._last = r
        return r

    # ---------- подписка ----------
    def check_subscription(self):
        if not self.auth.is_logged_in():
            return {'active': False, 'reason': 'not_logged_in'}
        uid = self.auth.local_id
        for path in [f"users/{uid}", f"users/{uid}/subscription/subscription", f"users/{uid}/users/{uid}"]:
            try:
                r = requests.get(f"{FIRESTORE_BASE}/{path}",
                                 headers={'Authorization': f'Bearer {self.auth.id_token}'}, timeout=10)
                if r.status_code != 200:
                    continue
                sub = self._parse_sub(r.json().get('fields', {}))
                if not sub:
                    continue
                if not sub.get('active', {}).get('booleanValue', False):
                    continue
                expires = sub.get('expires_at', {}).get('timestampValue', '')
                if expires:
                    try:
                        exp = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                        now = datetime.now(exp.tzinfo)
                        if exp <= now:
                            return {'active': False, 'reason': 'expired', 'days_ago': (now - exp).days}
                        return {'active': True, 'days_left': (exp - now).days}
                    except Exception:
                        return {'active': True, 'days_left': 0}
                return {'active': True, 'days_left': 0}
            except Exception:
                pass
        return {'active': False, 'reason': 'no_subscription'}

    def _parse_sub(self, fields):
        if 'subscription' in fields and isinstance(fields['subscription'], dict) \
                and 'mapValue' in fields['subscription']:
            return fields['subscription']['mapValue'].get('fields', {})
        if 'active' in fields:
            return fields
        return None

    def get_pay_url(self):
        return (f"{AI_PAY_URL}?uid={self.auth.local_id}"
                f"&email={self.auth.user_email}&token={self.auth.id_token}")

    # ================= МОЗГ (конвейер команд) =================
    def chat(self, code, user_message):
        msg = user_message.strip()
        self.chat_history.append({"role": "user", "content": msg})
        reply, action = self._brain(code, msg)
        self.chat_history.append({"role": "assistant", "content": reply})
        self._save_history()
        return reply, action

    def _split_commands(self, msg):
        parts = re.split(r'[\n;]+|\bи\b|\bа также\b|\bещё\b|\bзатем\b|\bпотом\b|\bплюс\b|,\s*|\.\s+', msg)
        frags = [p.strip(' .,!?') for p in parts if p and p.strip(' .,!?')]
        return frags if frags else [msg]

    def _brain(self, code, msg):
        low = msg.lower()
        frags = self._split_commands(msg)
        multi = len(frags) > 1
        work = code
        descs, replies = [], []
        for frag in frags:
            res = self._run_fragment(work, frag.lower(), msg, multi)
            if res is None:
                continue
            if 'code' in res:
                work = res['code']
            if res.get('desc'):
                descs.append(res['desc'])
            if res.get('reply'):
                replies.append(res['reply'])
        if descs:
            reply = "✅ Готово! " + " • ".join(descs) + \
                    "\nИзменения уже в редакторе — нажми F5 или Ctrl+S."
            if replies:
                reply += "\n\n" + "\n\n".join(replies)
            return reply, {'mode': 'set_code', 'code': work}
        if replies:
            return "\n\n".join(replies), None
        if re.search(r'(вставь|в редактор|примени)', low):
            return "✅ Вставляю последний ответ в редактор.", {'mode': 'last'}
        if re.search(self.CREATE_RE, low):
            return ("Могу сделать сайт (игра/бизнес/кафе/магазин/портфолио) и ПРАВИТЬ его: "
                    "«добавь логотип Beam», «сделай кнопки красными», «переименуй сайт», "
                    "«добавь раздел о нас», «сделай шрифт больше».\n"
                    "Пиши большой запрос списком — выполню всё по порядку. "
                    "Ещё умею: кликер, кнопка, счётчик, форма, меню, галерея, таймер, таблица, градиент, анимация."), None
        return self._free_talk(msg), None

    def _run_fragment(self, work, flow, msg, multi):
        m = re.search(r'меня зовут\s+([\wа-яА-Я_]+)', flow)
        if m:
            self.user_name = m.group(1).capitalize()
            return {'reply': f"Приятно познакомиться, {self.user_name}! 😊 Запомнил."}
        st = self._smalltalk(flow)
        if st:
            return {'reply': st}
        h = self._studio_help(flow)
        if h:
            return {'reply': h}
        lh = self._lang_help(flow)
        if lh:
            return {'reply': lh}
        if self._other_lang(flow):
            return {'reply': "Я знаю только один язык — RuWeb 😊 Давай лучше сделаю что-то на нём?"}
        if re.search(r'(не работает|почему не|ничего не|не идёт|не запускается|сломал)', flow):
            return {'reply': self._diagnose(work)}
        if re.search(r'(объясни|что делает|разбор|поясни|что за код)', flow):
            return {'reply': self._explain(work)}
        if re.search(r'(ошибк|исправ|почини|баг)', flow):
            return {'reply': self._fix(work)}
        if self._clear_match(flow):
            return {'code': '', 'desc': 'Убрал весь код 🧹'}
        gen = self._generate(flow, msg)
        if gen:
            code_txt, labels = gen
            if re.search(r'(покажи|выведи|в чат)', flow):
                return {'reply': "Смотри, вот код 👇\n```ruweb\n" + code_txt + "\n```"}
            replace = (not work.strip()) \
                or re.search(r'(убери|удали|замени|перепиши|с нуля|начни заново|полностью)', flow) \
                or 'сайт' in labels or 'кликер' in labels
            if replace:
                return {'code': code_txt, 'desc': 'Собрал заново: ' + ', '.join(labels)}
            return {'code': work.rstrip('\n') + '\n\n' + code_txt,
                    'desc': 'Добавил: ' + ', '.join(labels)}
        e = self._edit(work, flow, msg)
        if e:
            return {'code': e[0], 'desc': e[1]}
        if self._style_match(flow):
            return {'code': self._set_styles(work, self._gen_styles()), 'desc': 'Прокачал стили 🎨'}
        if multi:
            return None
        return None

    # ---------- РЕДАКТИРОВАНИЕ ----------
    def _color_word(self, low):
        for k in self.COLORS:
            if k in low:
                return k
        return None

    def _color_edit(self, low):
        return bool(self._color_word(low) and
                    re.search(r'(фон|кнопк|текст|надпис|карточк|цвет|сделай|перекрас)', low))

    def _edit_probe(self, low):
        if re.search(r'(логотип|лого\b)', low):
            return True
        if re.search(r'(переименуй|назови|смени название|название на)', low):
            return True
        if re.search(r'(добавь|сделай|создай).{0,20}(раздел|секци|о нас|подвал|футер)', low):
            return True
        if self._color_edit(low):
            return True
        if re.search(r'шрифт.{0,12}(больше|крупнее|меньше)', low):
            return True
        return False

    def _site_title(self, code):
        m = re.search(r'заголовок\s+"([^"]+)"', code)
        return m.group(1) if m else None

    def _append_styles(self, code, css_lines):
        block = 'стили\n' + '\n'.join('  | ' + l for l in css_lines)
        return code.rstrip('\n') + '\n' + block + '\n'

    def _insert_after_body(self, code, lines):
        out = []
        done = False
        for ln in code.split('\n'):
            out.append(ln)
            if not done and ln.strip().startswith('тело'):
                out += ['  ' + l for l in lines]
                done = True
        if not done:
            out += lines
        return '\n'.join(out)

    def _rename_site(self, code, name):
        code = re.sub(r'(заголовок\s+)"[^"]*"', lambda m2: m2.group(1) + '"' + name + '"', code, count=1)
        code = re.sub(r'(заголовок1(?:\s+[^\n"]*)?)"[^"]*"', lambda m2: m2.group(1) + '"' + name + '"', code, count=1)
        return code

    def _add_section(self, code, title, text):
        lines = ['секция класс="секция"', '  заголовок2 "' + title + '"', '  абзац "' + text + '"']
        out = []
        done = False
        for ln in code.split('\n'):
            if not done and ln.strip().startswith('подвал'):
                out += ['  ' + l for l in lines]
                done = True
            out.append(ln)
        if not done:
            return self._insert_after_body(code, lines)
        return '\n'.join(out)

    def _set_styles(self, code, new_block):
        lines = code.split('\n')
        start = None
        base_ind = 0
        scen_ind = None
        for idx, ln in enumerate(lines):
            s = ln.strip()
            if not s:
                continue
            ind = len(ln) - len(ln.lstrip())
            if scen_ind is not None:
                if ind <= scen_ind:
                    scen_ind = None
                else:
                    continue
            if s == 'сценарий' or s.startswith('сценарий '):
                scen_ind = ind
                continue
            if s == 'стили' or s.startswith('стили '):
                start = idx
                base_ind = ind
                break
        pref = ' ' * base_ind
        block_lines = [(pref + ln) if ln.strip() else ln for ln in new_block.split('\n')]
        if start is None:
            return code.rstrip('\n') + '\n' + '\n'.join(block_lines) + '\n'
        end = len(lines)
        for j in range(start + 1, len(lines)):
            s = lines[j].strip()
            if not s:
                continue
            ind = len(lines[j]) - len(lines[j].lstrip())
            if s.startswith('/стили'):
                end = j + 1
                break
            if ind <= base_ind:
                end = j
                break
        return '\n'.join(lines[:start] + block_lines + lines[end:])

    def _edit(self, code, low, msg):
        if not code.strip():
            return None
        if re.search(r'(логотип|лого\b)', low):
            name = self._extract_name(msg)
            if not name:
                m = re.search(r'\b([A-Z][A-Za-z0-9\-]{1,20})\b', msg)
                name = m.group(1) if m else (self._site_title(code) or 'LOGO')
            new = self._insert_after_body(code, ['блок класс="лого" "' + name + '"'])
            new = self._append_styles(new, [
                '.лого { шрифт-размер: 30px; шрифт-вес: полужирный; текст-выравнивание: центр; поля: 18px; текст-тень: 0 4px 16px rgba(0,0,0,0.45); }'])
            return new, "Добавил логотип «" + name + "» 🏷"
        if re.search(r'(переименуй|назови|смени название|название на)', low):
            name = self._extract_name(msg)
            if not name:
                m = re.search(r'\b([A-Z][A-Za-z0-9\-]{1,20})\b', msg)
                name = m.group(1) if m else None
            if name:
                return self._rename_site(code, name), "Переименовал сайт в «" + name + "» ✏️"
        if re.search(r'(добавь|сделай|создай).{0,20}(раздел|секци|о нас|подвал|футер)', low):
            title = "О нас" if 'о нас' in low else "Новый раздел"
            return self._add_section(code, title, "Здесь расскажи о себе или о проекте."), \
                   "Добавил раздел «" + title + "» 📄"
        if self._color_edit(low):
            hexc = self.COLORS[self._color_word(low)]
            if 'кнопк' in low:
                css = ['.кнопка { фон: ' + hexc + '; тень: 0 8px 24px rgba(0,0,0,0.35); }']
                desc = "Перекрасил кнопки 🎨"
            elif 'карточк' in low:
                css = ['.карточка { фон: ' + hexc + '; }']
                desc = "Перекрасил карточки 🎨"
            elif 'текст' in low or 'надпис' in low:
                css = ['тело { цвет: ' + hexc + '; }']
                desc = "Поменял цвет текста 🎨"
            else:
                css = ['тело { фон: линейный-градиент(135град, ' + hexc + ', #0f0c29); }']
                desc = "Поменял фон сайта 🎨"
            return self._append_styles(code, css), desc
        m = re.search(r'шрифт.{0,12}(больше|крупнее|меньше)', low)
        if m:
            if m.group(1) == 'меньше':
                css = ['заголовок1 { шрифт-размер: 40px; }', 'тело { шрифт-размер: 14px; }']
            else:
                css = ['заголовок1 { шрифт-размер: 68px; }', 'тело { шрифт-размер: 18px; }']
            return self._append_styles(code, css), "Изменил размер шрифта 🔠"
        return None

    # ---------- интенты ----------
    def _other_lang(self, low):
        return bool(
            re.search(r'(питон|python|javascript|джаваскрипт|typescript|тайпскрипт|react|реакт|php|java\b|джава|c\+\+|c#|английск|html|css)', low)
            and re.search(r'(напиши|сделай|создай|код|скрипт|функци|сайт|страниц|на языке)', low))

    def _clear_match(self, low):
        return bool(re.search(r'(весь код|всё из редактора|очисти редактор|очисти код|удали всё|удали все|убери всё|убери весь|снеси всё|сотри всё|очисти всё)', low))

    def _style_match(self, low):
        return bool(re.search(r'(стил|оформлен|дизайн|улучш|красивее|круче|симпатич|лучше)', low))

    def _site_topic(self, low):
        if re.search(r'(игр|гейм|game|игров|аркад|шутер|квест)', low):
            return 'game'
        if re.search(r'(бизнес|компан|фирм|корпорат|стартап|услуг|агентств|маркетинг)', low):
            return 'business'
        if re.search(r'(кафе|ресторан|кофе|кофейн|еда|пицц|бар\b|пекарн)', low):
            return 'cafe'
        if re.search(r'(магазин|шоп|товар|техник|одежд|маркет|каталог)', low):
            return 'shop'
        if re.search(r'(портфолио|резюме|личн|блог|дизайнер|фотограф|разработчик)', low):
            return 'portfolio'
        return 'generic'

    def _extract_name(self, msg):
        m = re.search(r'(?:название|называется|под названием)\s*[:\-]?\s*["«]?([A-Za-zА-Яа-яЁё0-9_\-]+)', msg)
        if m:
            word = m.group(1)
            if word.lower() not in ('сайта', 'игры', 'кафе', 'магазина', 'портфолио', 'бизнеса'):
                return word
        m = re.search(r'["«]([^"»]{2,30})["»]', msg)
        if m:
            return m.group(1)
        return None

    def _intent(self, low):
        if re.search(r'меня зовут\s+[\wа-я]', low):
            return 'name'
        if self._smalltalk_key(low):
            return 'smalltalk'
        if self._studio_help(low) or self._lang_help(low):
            return 'help'
        if self._other_lang(low):
            return 'otherlang'
        if re.search(r'(не работает|почему не|ничего не|не идёт|не запускается|сломал)', low):
            return 'diagnose'
        if re.search(r'(объясни|что делает|разбор|поясни|что за код)', low):
            return 'explain'
        if re.search(r'(ошибк|исправ|почини|баг)', low):
            return 'fix'
        if self._edit_probe(low):
            return 'edit'
        if self._gen_items(low):
            return 'generate'
        if self._clear_match(low):
            return 'clear'
        if self._style_match(low):
            return 'style'
        if re.search(r'(вставь|в редактор|примени)', low):
            return 'insert'
        return 'free'

    def thinking_stages(self, msg, code):
        low = msg.lower()
        frags = self._split_commands(msg)
        intent = self._intent(low)
        lines = len([l for l in code.splitlines() if l.strip()])
        st = []
        if len(frags) > 1:
            st.append((f"🧠 Большой запрос: разбиваю на команды ({len(frags)})…", 0.8))
        if intent == 'edit':
            st += [("🧩 Смотрю текущий сайт…", 0.7),
                   (f"✂️ Вношу правки в код ({lines} строк)…", 0.8)]
            return st
        if intent == 'generate':
            st.append(("🤖 Читаю запрос…", 0.6))
            if lines:
                st.append((f"🔎 Смотрю твой код в редакторе: {lines} строк…", 0.9))
            if 'сайт' in low:
                nm = self._extract_name(msg)
                st.append(("🧭 Определяю тему сайта…" + (f" Название: «{nm}»" if nm else ""), 0.7))
            if re.search(r'(убери|удали|замени|перепиши|с нуля|новый|начни заново|создай)', low):
                st.append(("🧹 Понял: старое убираю, пишу новое с нуля…", 0.8))
            st.append(("✍️ Пишу код на RuWeb и вставляю в редактор…", 0.9))
            return st
        if intent == 'clear':
            st.append(("🧹 Понял, убираю весь код…", 0.6))
            return st
        if intent == 'style':
            st += [("🎨 Смотрю текущие стили…", 0.7),
                   ("🧩 Подбираю палитру, тени и hover-эффекты…", 0.8),
                   ("✍️ Пишу новые стили в редактор…", 0.7)]
            return st
        if intent in ('diagnose', 'fix'):
            st += [("🤖 Читаю запрос…", 0.5),
                   (f"🔎 Проверяю код: {lines} строк…", 0.9),
                   ("🧩 Сверяю ид, функции и css-свойства…", 0.7)]
            return st
        if intent == 'explain':
            st += [("🔎 Читаю твой код…", 0.8), ("🧩 Разбираю структуру…", 0.7)]
            return st
        if intent in ('smalltalk', 'help', 'name', 'otherlang'):
            st.append(("🤖 RuWeb AI думает…", 0.4))
            return st
        st += [("🤖 Думаю…", 0.5), ("💡 Подбираю ответ…", 0.6)]
        return st

    # ---------- живое общение ----------
    def _smalltalk_key(self, low):
        patterns = [
            (r'\b(привет|здравствуй|здарова|дарова|салют|хай|hello|hi|hey|ку|приветик|добрый)\b', 'hi'),
            (r'(как дела|как ты|как поживаешь|как настроение|как сам)', 'how'),
            (r'(кто ты|ты кто|расскажи о себе|что ты такое)', 'who'),
            (r'(как тебя зовут|твоё имя|твое имя)', 'name_ai'),
            (r'(спасибо|благодар|спс|сенкс)', 'thanks'),
            (r'(пока|до свидания|прощай|бб|до встречи)', 'bye'),
            (r'(шутк|анекдот|рассмеши|пошути)', 'joke'),
            (r'(что умеешь|помощь|help|команды|что ты можешь)', 'skills'),
        ]
        for pat, key in patterns:
            if re.search(pat, low):
                return key
        return None

    def _smalltalk(self, low):
        key = self._smalltalk_key(low)
        if not key:
            return None
        name = f", {self.user_name}" if self.user_name else ""
        if key == 'hi':
            return self._pick([
                f"Привет{name}! 👋 Рад тебя видеть. Что будем делать — код, идеи или поболтаем?",
                f"Здарова{name}! 😄 Я на связи. Рассказывай, что нужно.",
                f"Привет-привет{name}! ✨ Есть идеи или начнём с кода?",
                f"О, {self.user_name or 'друг'}! 👋 Давно не виделись. Чем помочь?"])
        if key == 'how':
            return self._pick([
                "Отлично! 😊 А у тебя? Кстати, могу подсказать по коду или студии.",
                "Бодро! Процессор холодный, настроение хорошее 😄 Что нужно?",
                "Хорошо! Лучше, когда есть интересный проект. Есть такой?"])
        if key == 'who':
            return ("Я — RuWeb AI, собственная ИИ студии. 🤖 Знаю язык RuWeb (теги, css, js), "
                    "вижу твой код и сам пишу в редактор. Могу и поболтать.")
        if key == 'name_ai':
            return "Меня зовут RuWeb AI. 😊 Можно просто «Ру»."
        if key == 'thanks':
            return self._pick(["Всегда пожалуйста! 😊", "Рад помочь! 🤗", "Не за что! ✨"])
        if key == 'bye':
            return "До встречи! 👋 Возвращайся — будем писать сайты."
        if key == 'joke':
            return self._pick([
                "Почему программисты путают Хэллоуин и Рождество? Oct 31 == Dec 25 😄",
                "— Сколько программистов нужно, чтобы вкрутить лампочку?\n— Ни одного, это CSS. 😄",
                "Заходит RuWeb-код в бар. Бармен: «Как обычно — без английских тегов?» 😄"])
        if key == 'skills':
            return ("Я умею:\n• ⌨️ создавать сайты по теме с твоим названием\n"
                    "• ✂️ редактировать их: логотип, цвета, разделы, шрифт, переименование\n"
                    "• 🧠 понимать БОЛЬШИЕ запросы: пиши несколько команд через запятую или «и» — "
                    "выполню всё по порядку\n• 🧰 объяснять и чинить код, 💬 общаться")
        return None

    # ---------- база знаний студии ----------
    def _studio_help(self, low):
        KB = [
            (('сохранить', 'сохранение'), "Сохранить — **Ctrl+S** или кнопка «Сохранить». Облачный уйдёт в облако, локальный — в файл."),
            (('экспорт', 'выгрузить'), "Экспорт в HTML — «Экспорт» или **Ctrl+E**. Получишь готовый .html для хостинга."),
            (('предпросмотр', 'превью'), "Предпросмотр — «⟳ Перезапуск» или **F5**. **Ctrl+S** тоже обновляет."),
            (('облак', 'синхронизац'), "Облачные проекты — в твоём Google-аккаунте. Создай с «☁ В облаке». Удаляются крестиком."),
            (('импорт',), "Импорт: «📥 Импорт» в хабе → выбери .ruweb → он откроется."),
            (('подписк', 'купить', 'оплат', '45'), "Подписка RuWeb AI — 45 ₽/30 дней. «🤖 RuWeb AI» → «Оформить» → ЮMoney."),
            (('горячие', 'клавиш'), "Клавиши: Ctrl+S сохранить, Ctrl+E экспорт, F5 предпросмотр, Ctrl+колесо зум, Tab/Shift+Tab отступы."),
            (('тем', 'светл', 'тёмн', 'темн'), "Тема: «⚙ Настройки» → «Тема» → Тёмная/Светлая."),
            (('консол',), "Консоль показывает вывести() и ошибки JS."),
            (('масштаб', 'зум'), "Масштаб — Ctrl + колесо мыши над редактором."),
            (('версия',), "Сейчас RuWeb Studio **v4.0**, язык RuWeb **v3.0** (отступы, без «конец»)."),
        ]
        for keys, ans in KB:
            if any(k in low for k in keys):
                return ans
        return None

    def _lang_help(self, low):
        eng = self.engine
        if eng is None:
            return None
        if re.search(r'(теги|тег\b|разметка языка)', low):
            tags = list(eng.tag_map.keys())
            return ("🏷 Теги RuWeb (всего " + str(len(tags)) + "): " + ", ".join(tags[:18]) +
                    " …\nПример: кнопка класс=\"кнопка\" ид=\"моя\" \"Жми\"")
        if 'свойств' in low:
            props = list(eng.css_props.keys())
            return ("🎨 CSS-свойства на русском (всего " + str(len(props)) + "): " + ", ".join(props[:15]) +
                    " …\nПример: | .кнопка { граница-радиус: 14px; тень: 0 8px 20px rgba(0,0,0,0.3); }")
        if re.search(r'(команды js|js команды|ключевые слова)', low):
            keys = list(eng.russian_js.keys())
            return ("⌨️ JS-команды на русском (всего " + str(len(keys)) + "): " + ", ".join(keys[:15]) +
                    " …\nПример: функция клик() … получить_по_ид(\"моя\").слушать(\"click\", клик)")
        return None

    # ---------- диагностика ----------
    def _diagnose(self, code):
        issues = self._lint(code)
        lines = ["Давай разберёмся, почему не работает. 🔍"]
        if issues:
            lines.append("\nНашёл в коде:")
            lines += [f"• {i}" for i in issues]
        lines.append("\nПроверь также:")
        lines += [
            "• Нажми ⟳ Перезапуск / F5 — предпросмотр мог не обновиться.",
            "• Открой Консоль — там видны ошибки JS.",
            "• Сверь ид в получить_по_ид с ид=\"...\" в разметке.",
            "• Убедись, что функция определена ДО слушать.",
        ]
        lines.append("\nОпиши, что именно происходит (кнопка не жмётся? пусто? ошибка?) — подскажу точнее.")
        return "\n".join(lines)

    def _explain(self, code):
        if not code.strip():
            return "В редакторе пока пусто. Напиши код — и я объясню."
        tags = re.findall(r'^\s*(страница|голова|тело|заголовок_блок|подвал|основной|секция|блок|кнопка|абзац|заголовок\d|форма|ввод|список|ссылка|изображение)', code, re.M)
        ids = re.findall(r'ид="([^"]+)"', code)
        txt = "Разбор кода:\n"
        txt += f"• Тегов разметки: {len(tags)}\n"
        txt += f"• Стили: {'есть' if 'стили' in code else 'нет'}\n"
        txt += f"• Скрипт: {'есть' if 'сценарий' in code else 'нет'}\n"
        if ids:
            txt += f"• ид: {', '.join(ids[:6])}\n"
        txt += "\nСтруктура: страница → голова → тело (разметка + сценарий).\nХочешь — «найди ошибки», «сделай стили красивее» или «сделай кнопку»."
        return txt

    def _fix(self, code):
        issues = self._lint(code)
        if not issues:
            return "✅ Явных ошибок не нашёл. Если что-то не работает — напиши «почему не работает», дам диагностику."
        return "🔧 Проблемы:\n" + "".join(f"• {i}\n" for i in issues) + "\nИсправь и нажми ⟳."

    def _lint(self, code):
        issues = []
        eng = self.engine
        ids_def = set(re.findall(r'ид="([^"]+)"', code))
        ids_use = set(re.findall(r"получить_по_ид\('([^']+)'\)", code)) | \
                  set(re.findall(r'получить_по_ид\("([^"]+)"\)', code))
        for u in ids_use:
            if u not in ids_def:
                issues.append(f"ид «{u}» используется, но не объявлен")
        f_def = set(re.findall(r'функция\s+([\wа-яА-Я_]+)', code))
        f_use = set(re.findall(r'слушать\([^,]+,\s*([\wа-яА-Я_]+)\)', code))
        for f in f_use:
            if f not in f_def:
                issues.append(f"функция «{f}» в слушать, но не определена")
        if eng is None:
            return issues
        in_s = in_st = False
        base = 0
        for raw in code.split('\n'):
            s = raw.strip()
            if not s:
                continue
            ind = len(raw) - len(raw.lstrip())
            if s.startswith('сценарий'):
                in_s, in_st, base = True, False, ind
                continue
            if s.startswith('стили'):
                in_st, in_s, base = True, False, ind
                continue
            if (in_s or in_st) and ind <= base:
                in_s = in_st = False
            if in_s:
                continue
            if in_st:
                if s.startswith('|'):
                    for prop in re.findall(r'([а-яА-ЯёЁ][\w-]*)\s*:', s):
                        if prop not in eng.css_props:
                            issues.append(f"неизвестное css-свойство «{prop}»")
                continue
            if s.startswith(('|', '#', '/')):
                continue
            first = s.split(maxsplit=1)[0].rstrip('/')
            if first == 'документ_html':
                continue
            if first not in eng.tag_map:
                issues.append(f"неизвестный тег «{first}»")
        if 'тело' not in code:
            issues.append("нет блока «тело»")
        return issues

    # ---------- генерация ----------
    def _gen_items(self, low, msg=""):
        G = []
        if 'кликер' in low:
            G.append(('кликер', self._gen_clicker))
        if 'кноп' in low:
            G.append(('кнопка', self._gen_button))
        if 'счётчик' in low or 'счетчик' in low:
            G.append(('счётчик', self._gen_counter))
        if 'форм' in low:
            G.append(('форма', self._gen_form))
        if 'меню' in low:
            G.append(('меню', self._gen_menu))
        if 'галере' in low:
            G.append(('галерея', self._gen_gallery))
        if 'таймер' in low or 'часы' in low:
            G.append(('таймер', self._gen_timer))
        if 'спис' in low:
            G.append(('список', self._gen_list))
        if 'таблиц' in low:
            G.append(('таблица', self._gen_table))
        if 'градиент' in low:
            G.append(('градиент', self._gen_gradient))
        if 'анимац' in low:
            G.append(('анимация', self._gen_animation))
        if 'сайт' in low and re.search(self.CREATE_RE, low) and not G:
            G.append(('сайт', lambda: self._gen_site(low, msg)))
        return G

    def _generate(self, low, msg=""):
        items = self._gen_items(low, msg)
        if not items:
            return None
        labels = [lab for lab, _ in items]
        code = "\n\n".join(fn() for _, fn in items)
        return code, labels

    # ---------- конструктор сайтов ----------
    def _assemble_site(self, title, styles, body, js):
        L = ['документ_html', 'страница язык="ru"', '  голова',
             '    мета кодировка="utf-8"/',
             '    мета имя="viewport" значение="width=device-width, initial-scale=1.0"/',
             '    заголовок "' + title + '"',
             '    стили']
        L += ['      | ' + s for s in styles]
        L += ['  тело']
        L += ['    ' + b for b in body]
        L += ['    сценарий']
        L += ['      ' + j for j in js]
        return '\n'.join(L)

    def _site_styles(self, g1, g2, a1, a2):
        return [
            '* { отступ: 0; поля: 0; размер-блока: в-рамку; }',
            "тело { шрифт-семейство: 'Segoe UI', sans-serif; фон: линейный-градиент(135град, %s, %s); цвет: белый; мин-высота: 100vh; }" % (g1, g2),
            '.нав { дисплей: гибкий; gap: 24px; justify-содержимое: центр; поля: 24px; }',
            '.нав a { цвет: белый; текст-оформление: нет; шрифт-вес: полужирный; переход: all 0.2s плавное; }',
            '.нав a:hover { цвет: %s; }' % a1,
            '.hero { текст-выравнивание: центр; поля: 60px 20px 40px; }',
            '.hero заголовок1 { шрифт-размер: 54px; шрифт-вес: полужирный; текст-тень: 0 6px 30px rgba(0,0,0,0.5); }',
            '.hero абзац { цвет: rgba(255,255,255,0.75); шрифт-размер: 18px; отступ-снизу: 24px; }',
            '.секция { макс-ширина: 1100px; отступ: 0 авто; поля: 40px 20px; }',
            'заголовок2 { шрифт-размер: 34px; шрифт-вес: полужирный; отступ-снизу: 20px; }',
            '.сетка { дисплей: сетка; сетка-шаблон-колонки: repeat(3, 1fr); gap: 20px; }',
            '.карточка { фон: rgba(255,255,255,0.08); фильтр-фона: размытие(12px); граница: 1px сплошной rgba(255,255,255,0.15); граница-радиус: 20px; поля: 26px; тень: 0 10px 30px rgba(0,0,0,0.35); переход: all 0.3s плавное; }',
            '.карточка:hover { трансформация: перемещение-y(-6px); }',
            '.цена { шрифт-размер: 22px; шрифт-вес: полужирный; цвет: %s; }' % a1,
            'таблица { ширина: 100%; }',
            'ячейка, ячейка_заг { поля: 12px 16px; граница-снизу: 1px сплошной rgba(255,255,255,0.15); текст-выравнивание: слева; }',
            '.кнопка { фон: линейный-градиент(135град, %s, %s); цвет: белый; граница: нет; поля: 15px 36px; граница-радиус: 14px; курсор: указатель; шрифт-размер: 16px; шрифт-вес: полужирный; тень: 0 8px 24px rgba(0,0,0,0.35); переход: all 0.2s плавное; }' % (a1, a2),
            '.кнопка:hover { трансформация: масштаб(1.06); }',
            '.кнопка2 { фон: нет; цвет: белый; граница: 1px сплошной rgba(255,255,255,0.4); поля: 15px 36px; граница-радиус: 14px; курсор: указатель; переход: all 0.2s плавное; }',
            '.кнопка2:hover { фон: rgba(255,255,255,0.1); }',
            '.ввод { дисплей: блок; ширина: 100%; поля: 14px; отступ-снизу: 14px; граница: 1px сплошной rgba(255,255,255,0.25); граница-радиус: 12px; фон: rgba(255,255,255,0.08); цвет: белый; }',
            '.подвал { текст-выравнивание: центр; поля: 36px; цвет: rgba(255,255,255,0.5); }',
        ]

    def _gen_site(self, low, msg=""):
        name = self._extract_name(msg)
        t = self._site_topic(low)
        if t == 'game':
            return self._site_game(name)
        if t == 'business':
            return self._site_business(name)
        if t == 'cafe':
            return self._site_cafe(name)
        if t == 'shop':
            return self._site_shop(name)
        if t == 'portfolio':
            return self._site_portfolio(name)
        return self._site_generic(name)

    def _site_game(self, name):
        name = name or 'Nova'
        styles = self._site_styles('#0d0221', '#26123b', '#00e5ff', '#ff2ec4')
        body = [
            'навигация класс="нав"',
            '  ссылка ссылка="#hero" "Главная"',
            '  ссылка ссылка="#features" "Особенности"',
            '  ссылка ссылка="#req" "Требования"',
            '  ссылка ссылка="#download" "Скачать"',
            'заголовок_блок класс="hero" ид="hero"',
            '  заголовок1 "' + name + ' — игра нового поколения 🎮"',
            '  абзац "Киберпанк-экшен в открытом мире. Твой город. Твои правила."',
            '  кнопка класс="кнопка" ид="кнопка_демо" "Скачать демо"',
            '  кнопка класс="кнопка2" ид="кнопка_трейлер" "Смотреть трейлер"',
            'секция класс="секция" ид="features"',
            '  заголовок2 "Особенности"',
            '  блок класс="сетка"',
            '    блок класс="карточка"',
            '      заголовок3 "🌍 Открытый мир"',
            '      абзац "Гигантский мегаполис без загрузочных экранов."',
            '    блок класс="карточка"',
            '      заголовок3 "⚔️ Динамичные бои"',
            '      абзац "Катаны, импланты и стильные комбо."',
            '    блок класс="карточка"',
            '      заголовок3 "🤝 Кооператив"',
            '      абзац "Проходи сюжет вместе с друзьями."',
            'секция класс="секция" ид="req"',
            '  заголовок2 "Системные требования"',
            '  таблица',
            '    строка',
            '      ячейка_заг ""',
            '      ячейка_заг "Минимальные"',
            '      ячейка_заг "Рекомендуемые"',
            '    строка',
            '      ячейка "Система"',
            '      ячейка "Windows 10"',
            '      ячейка "Windows 11"',
            '    строка',
            '      ячейка "Видеокарта"',
            '      ячейка "GTX 1060"',
            '      ячейка "RTX 3070"',
            'секция класс="секция" ид="download"',
            '  заголовок2 "Готов начать?"',
            '  абзац ид="скачивания" "Уже 1 000 000+ загрузок"',
            '  кнопка класс="кнопка" ид="кнопка_скачать" "Скачать бесплатно"',
            'подвал класс="подвал"',
            '  абзац "© ' + name + ', 2026. Сделано в RuWeb Studio."',
        ]
        js = [
            'перем скачиваний = 1000000',
            'функция скачать()',
            '  скачиваний = скачиваний + 1',
            '  получить_по_ид("скачивания").текст = "Загрузок: " + скачиваний',
            '  предупредить("Загрузка ' + name + ' началась! 🎮")',
            'функция трейлер()',
            '  предупредить("Трейлер скоро! 🎬")',
            'получить_по_ид("кнопка_скачать").слушать("click", скачать)',
            'получить_по_ид("кнопка_демо").слушать("click", скачать)',
            'получить_по_ид("кнопка_трейлер").слушать("click", трейлер)',
        ]
        return self._assemble_site(name + " — официальный сайт игры", styles, body, js)

    def _site_business(self, name):
        name = name or 'BizPro'
        styles = self._site_styles('#0f2027', '#2c5364', '#667eea', '#764ba2')
        body = [
            'навигация класс="нав"',
            '  ссылка ссылка="#hero" "Главная"',
            '  ссылка ссылка="#services" "Услуги"',
            '  ссылка ссылка="#about" "О нас"',
            '  ссылка ссылка="#contact" "Контакты"',
            'заголовок_блок класс="hero" ид="hero"',
            '  заголовок1 "Выводим бизнес на новый уровень 🚀"',
            '  абзац "' + name + ': стратегия, автоматизация и рост прибыли — под ключ."',
            '  кнопка класс="кнопка" ид="кнопка_старт" "Начать проект"',
            '  кнопка класс="кнопка2" ид="кнопка_узнать" "Узнать больше"',
            'секция класс="секция" ид="services"',
            '  заголовок2 "Наши услуги"',
            '  блок класс="сетка"',
            '    блок класс="карточка"',
            '      заголовок3 "📈 Маркетинг"',
            '      абзац "Продвижение и реклама, которые окупаются."',
            '    блок класс="карточка"',
            '      заголовок3 "⚙️ Автоматизация"',
            '      абзац "CRM и отчёты без рутины."',
            '    блок класс="карточка"',
            '      заголовок3 "🤝 Консалтинг"',
            '      абзац "Личные консультации для владельцев."',
            'секция класс="секция" ид="about"',
            '  заголовок2 "Почему ' + name + '"',
            '  абзац "12 лет опыта, 240+ проектов, 98% клиентов рекомендуют нас."',
            'секция класс="секция" ид="contact"',
            '  заголовок2 "Оставить заявку"',
            '  форма ид="форма_заявка"',
            '    ввод класс="ввод" тип="text" подсказка="Ваше имя" обязательный/',
            '    ввод класс="ввод" тип="email" подсказка="Email" обязательный/',
            '    кнопка класс="кнопка" ид="кнопка_заявка" "Отправить"',
            'подвал класс="подвал"',
            '  абзац "© ' + name + ', 2026. Сделано в RuWeb Studio."',
        ]
        js = [
            'перем заявок = 0',
            'функция старт()',
            '  предупредить("Отлично! Оставьте контакты — мы предложим план 🚀")',
            'функция заявка()',
            '  заявок = заявок + 1',
            '  предупредить("Спасибо! Заявка №" + заявок + " принята 📩")',
            'получить_по_ид("кнопка_старт").слушать("click", старт)',
            'получить_по_ид("кнопка_заявка").слушать("click", заявка)',
        ]
        return self._assemble_site(name + " — решения для бизнеса", styles, body, js)

    def _site_cafe(self, name):
        name = name or 'Зёрнышко'
        styles = self._site_styles('#2b1510', '#4a2c2a', '#ff9966', '#ff5e62')
        body = [
            'навигация класс="нав"',
            '  ссылка ссылка="#hero" "Главная"',
            '  ссылка ссылка="#menu" "Меню"',
            '  ссылка ссылка="#about" "О нас"',
            'заголовок_блок класс="hero" ид="hero"',
            '  заголовок1 "Кофейня «' + name + '» ☕"',
            '  абзац "Свежая обжарка и уют в центре города."',
            '  кнопка класс="кнопка" ид="кнопка_стол" "Забронировать столик"',
            'секция класс="секция" ид="menu"',
            '  заголовок2 "Меню"',
            '  блок класс="сетка"',
            '    блок класс="карточка"',
            '      заголовок3 "Капучино"',
            '      абзац "Классика на зерне собственной обжарки."',
            '      абзац класс="цена" "190 ₽"',
            '    блок класс="карточка"',
            '      заголовок3 "Раф ванильный"',
            '      абзац "Нежный, сливочный, сладкий."',
            '      абзац класс="цена" "240 ₽"',
            '    блок класс="карточка"',
            '      заголовок3 "Круассан"',
            '      абзац "Свежая выпечка каждое утро."',
            '      абзац класс="цена" "180 ₽"',
            'секция класс="секция" ид="about"',
            '  заголовок2 "О нас"',
            '  абзац "Обжариваем зерно сами каждую неделю. Работаем с 8:00 до 22:00."',
            'подвал класс="подвал"',
            '  абзац "© ' + name + ', 2026."',
        ]
        js = [
            'функция стол()',
            '  предупредить("Столик забронирован! Ждём вас ☕")',
            'получить_по_ид("кнопка_стол").слушать("click", стол)',
        ]
        return self._assemble_site("Кофейня «" + name + "»", styles, body, js)

    def _site_shop(self, name):
        name = name or 'TechZone'
        styles = self._site_styles('#062e2b', '#0f6f5c', '#38ef7d', '#11998e')
        body = [
            'навигация класс="нав"',
            '  ссылка ссылка="#hero" "Главная"',
            '  ссылка ссылка="#goods" "Товары"',
            '  абзац класс="цена" ид="корзина" "🛒 Корзина: 0"',
            'заголовок_блок класс="hero" ид="hero"',
            '  заголовок1 "' + name + ' — техника, которая впечатляет ⚡"',
            '  абзац "Гарантия 2 года, доставка завтра."',
            'секция класс="секция" ид="goods"',
            '  заголовок2 "Хиты продаж"',
            '  блок класс="сетка"',
            '    блок класс="карточка"',
            '      заголовок3 "Смартфон X10"',
            '      абзац "Экран 6.7, 256 ГБ, камера 50 Мп."',
            '      абзац класс="цена" "59 990 ₽"',
            '      кнопка класс="кнопка" ид="купить1" "Купить"',
            '    блок класс="карточка"',
            '      заголовок3 "Ноутбук AirBook"',
            '      абзац "Лёгкий, 16 часов батареи."',
            '      абзац класс="цена" "84 990 ₽"',
            '      кнопка класс="кнопка" ид="купить2" "Купить"',
            '    блок класс="карточка"',
            '      заголовок3 "Наушники BudsPro"',
            '      абзац "Шумоподавление и 30 часов музыки."',
            '      абзац класс="цена" "12 990 ₽"',
            '      кнопка класс="кнопка" ид="купить3" "Купить"',
            'подвал класс="подвал"',
            '  абзац "© ' + name + ', 2026."',
        ]
        js = [
            'перем корзина = 0',
            'функция купить()',
            '  корзина = корзина + 1',
            '  получить_по_ид("корзина").текст = "🛒 Корзина: " + корзина',
            'получить_по_ид("купить1").слушать("click", купить)',
            'получить_по_ид("купить2").слушать("click", купить)',
            'получить_по_ид("купить3").слушать("click", купить)',
        ]
        return self._assemble_site(name + " — магазин техники", styles, body, js)

    def _site_portfolio(self, name):
        name = name or 'Алекс'
        styles = self._site_styles('#0f0c29', '#302b63', '#f093fb', '#f5576c')
        body = [
            'навигация класс="нав"',
            '  ссылка ссылка="#hero" "Главная"',
            '  ссылка ссылка="#skills" "Навыки"',
            '  ссылка ссылка="#contact" "Контакты"',
            'заголовок_блок класс="hero" ид="hero"',
            '  заголовок1 "Привет, я — ' + name + ' 👋"',
            '  абзац "Дизайнер и разработчик интерфейсов."',
            '  кнопка класс="кнопка" ид="кнопка_контакт" "Связаться"',
            'секция класс="секция" ид="skills"',
            '  заголовок2 "Что я умею"',
            '  блок класс="сетка"',
            '    блок класс="карточка"',
            '      заголовок3 "🎨 Дизайн"',
            '      абзац "Интерфейсы, которые понимают с первого взгляда."',
            '    блок класс="карточка"',
            '      заголовок3 "💻 Код"',
            '      абзац "Чистый фронтенд без лишних библиотек."',
            '    блок класс="карточка"',
            '      заголовок3 "🚀 Запуск"',
            '      абзац "От идеи до релиза за недели."',
            'секция класс="секция" ид="contact"',
            '  заголовок2 "Написать мне"',
            '  форма ид="форма_контакт"',
            '    ввод класс="ввод" тип="text" подсказка="Твоё имя" обязательный/',
            '    ввод класс="ввод" тип="email" подсказка="Email" обязательный/',
            '    кнопка класс="кнопка" ид="кнопка_отправить" "Отправить"',
            'подвал класс="подвал"',
            '  абзац "© ' + name + ', 2026. Сделано в RuWeb Studio."',
        ]
        js = [
            'функция контакт()',
            '  предупредить("Пиши на hello@ruweb.ru 💌")',
            'функция отправить()',
            '  предупредить("Спасибо! Отвечу в течение дня 💌")',
            'получить_по_ид("кнопка_контакт").слушать("click", контакт)',
            'получить_по_ид("кнопка_отправить").слушать("click", отправить)',
        ]
        return self._assemble_site(name + " — портфолио", styles, body, js)

    def _site_generic(self, name):
        styles = self._site_styles('#0f0c29', '#24243e', '#667eea', '#764ba2')
        h1 = (name + " ✨") if name else "Твой новый сайт ✨"
        body = [
            'навигация класс="нав"',
            '  ссылка ссылка="#hero" "Главная"',
            '  ссылка ссылка="#features" "Возможности"',
            '  ссылка ссылка="#contact" "Контакты"',
            'заголовок_блок класс="hero" ид="hero"',
            '  заголовок1 "' + h1 + '"',
            '  абзац "Современный дизайн, собранный на RuWeb."',
            '  кнопка класс="кнопка" ид="кнопка_старт" "Начать"',
            '  кнопка класс="кнопка2" ид="кнопка_узнать" "Подробнее"',
            'секция класс="секция" ид="features"',
            '  заголовок2 "Возможности"',
            '  блок класс="сетка"',
            '    блок класс="карточка"',
            '      заголовок3 "⚡ Быстро"',
            '      абзац "Сайт готов за секунды."',
            '    блок класс="карточка"',
            '      заголовок3 "🎨 Красиво"',
            '      абзац "Градиенты, стекло и hover-эффекты."',
            '    блок класс="карточка"',
            '      заголовок3 "🇷 На русском"',
            '      абзац "Код читается как текст."',
            'секция класс="секция" ид="contact"',
            '  заголовок2 "Связаться"',
            '  форма ид="форма_контакт"',
            '    ввод класс="ввод" тип="text" подсказка="Имя" обязательный/',
            '    ввод класс="ввод" тип="email" подсказка="Email" обязательный/',
            '    кнопка класс="кнопка" ид="кнопка_отправить" "Отправить"',
            'подвал класс="подвал"',
            '  абзац "© ' + (name or 'Мой сайт') + ', 2026. Сделано в RuWeb Studio."',
        ]
        js = [
            'функция старт()',
            '  предупредить("Поехали! 🚀")',
            'функция отправить()',
            '  предупредить("Спасибо! Сообщение отправлено 📩")',
            'получить_по_ид("кнопка_старт").слушать("click", старт)',
            'получить_по_ид("кнопка_отправить").слушать("click", отправить)',
        ]
        return self._assemble_site(name or "Мой сайт", styles, body, js)

    # ---------- мелкие генераторы ----------
    def _gen_styles(self):
        return '\n'.join([
            'стили',
            '  | * { отступ: 0; поля: 0; размер-блока: в-рамку; }',
            "  | тело { шрифт-семейство: 'Segoe UI', sans-serif; фон: линейный-градиент(135град, #0f0c29, #302b63, #24243e); цвет: белый; мин-высота: 100vh; }",
            '  | .контейнер { макс-ширина: 1100px; отступ: 0 авто; поля: 40px 20px; }',
            '  | заголовок1 { шрифт-размер: 52px; шрифт-вес: полужирный; текст-выравнивание: центр; }',
            '  | абзац { высота-строки: 1.6; }',
            '  | .карточка { фон: rgba(255,255,255,0.08); фильтр-фона: размытие(12px); граница: 1px сплошной rgba(255,255,255,0.15); граница-радиус: 20px; поля: 30px; тень: 0 10px 30px rgba(0,0,0,0.35); переход: all 0.3s плавное; }',
            '  | .карточка:hover { трансформация: перемещение-y(-6px); }',
            '  | .кнопка { фон: линейный-градиент(135град, #667eea, #764ba2); цвет: белый; граница: нет; поля: 14px 34px; граница-радиус: 14px; курсор: указатель; шрифт-размер: 16px; шрифт-вес: полужирный; переход: all 0.2s плавное; }',
            '  | .кнопка:hover { трансформация: масштаб(1.05); тень: 0 8px 20px rgba(102,126,234,0.5); }',
            '  | .сетка { дисплей: сетка; сетка-шаблон-колонки: repeat(3, 1fr); gap: 20px; }',
            '  | .подвал { текст-выравнивание: центр; поля: 30px; цвет: rgba(255,255,255,0.5); }',
        ])

    def _gen_button(self):
        return ('кнопка класс="кнопка" ид="моя_кнопка" "Нажми меня"\n'
                'стили\n'
                '  | .кнопка { фон: линейный-градиент(135град, #667eea, #764ba2); цвет: белый; граница: нет; поля: 14px 30px; граница-радиус: 14px; курсор: указатель; шрифт-вес: полужирный; тень: 0 6px 18px rgba(102,126,234,0.4); переход: all 0.2s плавное; }\n'
                '  | .кнопка:hover { трансформация: масштаб(1.06); }\n'
                'сценарий\n'
                '  функция нажатие()\n'
                '    предупредить("Кнопка работает!")\n'
                '  получить_по_ид("моя_кнопка").слушать("click", нажатие)')

    def _gen_counter(self):
        return ('абзац ид="счётчик" класс="число" "0"\n'
                'кнопка класс="кнопка" ид="плюс" "Увеличить"\n'
                'стили\n'
                '  | .число { шрифт-размер: 80px; шрифт-вес: полужирный; текст-выравнивание: центр; текст-тень: 0 4px 20px rgba(0,0,0,0.4); }\n'
                '  | .кнопка { фон: линейный-градиент(135град, #11998e, #38ef7d); цвет: белый; граница: нет; поля: 14px 34px; граница-радиус: 14px; курсор: указатель; переход: all 0.2s плавное; }\n'
                '  | .кнопка:hover { трансформация: масштаб(1.06); }\n'
                'сценарий\n'
                '  перем n = 0\n'
                '  функция плюс()\n'
                '    n = n + 1\n'
                '    получить_по_ид("счётчик").текст = n\n'
                '  получить_по_ид("плюс").слушать("click", плюс)')

    def _gen_form(self):
        return ('форма ид="моя_форма"\n'
                '  ввод тип="text" подсказка="Имя" обязательный/\n'
                '  ввод тип="email" подсказка="Email"/\n'
                '  кнопка тип="submit" "Отправить"')

    def _gen_menu(self):
        return ('навигация класс="меню"\n'
                '  ссылка ссылка="#home" "Главная"\n'
                '  ссылка ссылка="#about" "О нас"\n'
                '  ссылка ссылка="#contact" "Контакты"\n'
                'стили\n'
                '  | .меню { дисплей: гибкий; gap: 20px; поля: 20px; justify-содержимое: центр; }\n'
                '  | .меню a { цвет: белый; текст-оформление: нет; переход: all 0.2s плавное; }\n'
                '  | .меню a:hover { цвет: #667eea; }')

    def _gen_gallery(self):
        return ('блок класс="галерея"\n'
                '  изображение источник="1.jpg" альтернатива="Фото"/\n'
                '  изображение источник="2.jpg" альтернатива="Фото"/\n'
                'стили\n'
                '  | .галерея { дисплей: сетка; сетка-шаблон-колонки: repeat(3, 1fr); gap: 12px; }\n'
                '  | .галерея img { ширина: 100%; граница-радиус: 12px; тень: 0 6px 18px rgba(0,0,0,0.3); переход: all 0.3s плавное; }\n'
                '  | .галерея img:hover { трансформация: масштаб(1.04); }')

    def _gen_timer(self):
        return ('заголовок2 ид="часы" "00:00:00"\n'
                'сценарий\n'
                '  функция тик()\n'
                '    перем d = новая_дата()\n'
                '    получить_по_ид("часы").текст = d.toLocaleTimeString()\n'
                '  интервал(тик, 1000)')

    def _gen_list(self):
        return ('список\n  элемент "Первый"\n  элемент "Второй"\n  элемент "Третий"')

    def _gen_table(self):
        return ('таблица\n  строка\n    ячейка_заг "Имя"\n    ячейка_заг "Возраст"\n'
                '  строка\n    ячейка "Иван"\n    ячейка "25"')

    def _gen_gradient(self):
        return ('стили\n'
                '  | тело { фон: линейный-градиент(135град, #667eea, #764ba2); }\n'
                '  | .карточка { фон: линейный-градиент(135град, #f093fb, #f5576c); граница-радиус: 20px; поля: 30px; тень: 0 10px 30px rgba(0,0,0,0.35); }')

    def _gen_animation(self):
        return ('стили\n'
                '  | .блок { анимация: парение 3s плавное-вход-выход бесконечно; }\n'
                '  | @keyframes парение {\n'
                '  |   0%, 100% { трансформация: перемещение(0, 0); }\n'
                '  |   50% { трансформация: перемещение(0, -20px); }\n'
                '  | }')

    def _gen_clicker(self):
        return '\n'.join([
            'блок класс="центр"',
            '  заголовок1 ид="очки" "0"',
            '  абзац "Кликай по кнопке и качай очки! 🚀"',
            '  кнопка класс="кнопка" ид="клик" "КЛИК!"',
            '  кнопка класс="кнопка2" ид="сброс" "Сброс"',
            'стили',
            '  | тело { фон: линейный-градиент(135град, #11998e, #38ef7d); цвет: белый; текст-выравнивание: центр; }',
            '  | .центр { поля: 60px авто; }',
            '  | заголовок1 { шрифт-размер: 90px; шрифт-вес: полужирный; текст-тень: 0 6px 24px rgba(0,0,0,0.35); }',
            '  | .кнопка { фон: белый; цвет: #11998e; граница: нет; поля: 20px 50px; граница-радиус: 999px; шрифт-размер: 24px; шрифт-вес: полужирный; курсор: указатель; тень: 0 8px 24px rgba(0,0,0,0.25); переход: all 0.15s плавное; }',
            '  | .кнопка:hover { трансформация: масштаб(1.07); }',
            '  | .кнопка2 { фон: нет; цвет: белый; граница: нет; курсор: указатель; поля: 10px; }',
            'сценарий',
            '  перем n = 0',
            '  функция клик()',
            '    n = n + 1',
            '    получить_по_ид("очки").текст = n',
            '  функция сброс()',
            '    n = 0',
            '    получить_по_ид("очки").текст = n',
            '  получить_по_ид("клик").слушать("click", клик)',
            '  получить_по_ид("сброс").слушать("click", сброс)',
        ])

    # ---------- свободный ответ ----------
    def _free_talk(self, msg):
        name = f", {self.user_name}" if self.user_name else ""
        if '?' in msg:
            return self._pick([
                f"Хм, «{msg}» 🤔 Хороший вопрос. Уточни пару деталей — и я подскажу точнее. Это про код или про студию?",
                f"«{msg}» — интересно! 🤔 Давай разберёмся: расскажи, что именно ты имеешь в виду.",
                f"Дай подумать над «{msg}»… 🤔 А что ты уже пробовал? Так мне будет проще помочь."])
        return self._pick([
            f"Понял тебя{name}: «{msg}». 😊 Я рядом. Хочешь, сделаю кнопку, меню или форму? Или просто поболтаем.",
            f"«{msg}» — звучит интересно{name}! ✨ Чем займёмся: код, идеи или обсуждение?",
            f"Принял{name}. 🤗 Если хочешь действие — скажи «сделай …» или «добавь …» — я правлю код в редакторе.",
            f"Слышу тебя{name}: «{msg}». 👍 Кстати, я вижу твой код в редакторе — могу прокомментировать его, если хочешь."])


# ================= ОКНО ЧАТА =================
class RuWebAIWindow:
    def __init__(self, parent, ai, editor_widget, get_colors, open_login_cb):
        self.parent = parent
        self.ai = ai
        self.editor = editor_widget
        self.get_colors = get_colors
        self.open_login = open_login_cb
        self.window = None
        self.last_code_reply = ""

    def show(self):
        if not self.ai.auth.is_logged_in():
            if messagebox.askyesno("Требуется вход",
                                   "Для использования RuWeb AI нужно войти в аккаунт.\n\nВойти сейчас?"):
                self.open_login()
                return
        status = self.ai.check_subscription()
        if not status.get('active'):
            reason = status.get('reason', '')
            msg = (f"Подписка истекла {status.get('days_ago', 0)} дн. назад.\nПродлить за 45 ₽?"
                   if reason == 'expired' else
                   "У вас нет активной подписки на RuWeb AI.\n\nОформить за 45 ₽ на 30 дней?")
            if messagebox.askyesno("RuWeb AI", msg):
                webbrowser.open(self.ai.get_pay_url(), new=2)
            return
        self._show_chat()

    def _show_chat(self):
        c = self.get_colors()
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self._update_status()
            return
        self.window = tk.Toplevel(self.parent)
        self.window.title("🤖 RuWeb AI")
        self.window.geometry("620x720")
        self.window.minsize(500, 500)
        self.window.configure(bg=c['bg_dark'])
        head = tk.Frame(self.window, bg=c['bg_panel'], height=54)
        head.pack(fill=tk.X)
        head.pack_propagate(False)
        tk.Label(head, text="🤖 RuWeb AI", bg=c['bg_panel'], fg=c['text_primary'],
                 font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=18, pady=12)
        self.status_lbl = tk.Label(head, text="", bg=c['bg_panel'], fg=c['green'], font=('Segoe UI', 10, 'bold'))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)
        self._update_status()
        actions = tk.Frame(self.window, bg=c['bg_panel'], height=40)
        actions.pack(fill=tk.X)
        actions.pack_propagate(False)
        tk.Button(actions, text="📋 Взять код", bg=c['bg_hover'], fg=c['text_primary'],
                  font=('Segoe UI', 9), relief=tk.FLAT, cursor='hand2',
                  command=self._grab_code_to_input).pack(side=tk.LEFT, padx=8, pady=6)
        tk.Button(actions, text="✅ Вставить ответ", bg='#2f4f3f', fg='white',
                  font=('Segoe UI', 9, 'bold'), relief=tk.FLAT, cursor='hand2',
                  command=self._insert_last_code).pack(side=tk.LEFT, padx=4, pady=6)
        tk.Button(actions, text="🗑 Чат", bg='#5a2f2f', fg='white', font=('Segoe UI', 9),
                  relief=tk.FLAT, cursor='hand2', command=self._clear_chat).pack(side=tk.RIGHT, padx=8, pady=6)
        chat_frame = tk.Frame(self.window, bg=c['bg_dark'])
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))
        self.chat_text = tk.Text(chat_frame, bg=c['bg_card'], fg=c['text_primary'],
                                 font=('Segoe UI', 11), relief=tk.FLAT, padx=14, pady=10,
                                 wrap=tk.WORD, state=tk.DISABLED, cursor='arrow')
        self.chat_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sc = tk.Scrollbar(chat_frame, command=self.chat_text.yview)
        sc.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.config(yscrollcommand=sc.set)
        for tag, fg, font in [('user_name', '#4ec9b0', ('Segoe UI', 11, 'bold')),
                              ('ai_name', '#dcdcaa', ('Segoe UI', 11, 'bold')),
                              ('msg', c['text_primary'], ('Segoe UI', 11)),
                              ('code', '#ce9178', ('Cascadia Code', 10)),
                              ('thinking', '#8f9ab0', ('Segoe UI', 10, 'italic'))]:
            self.chat_text.tag_configure(tag, foreground=fg, font=font)
        self.chat_text.tag_configure('code', background='#0f131c', lmargin1=10, lmargin2=10)
        self._add_welcome()
        input_frame = tk.Frame(self.window, bg=c['bg_dark'])
        input_frame.pack(fill=tk.X, padx=8, pady=8)
        self.input_text = tk.Text(input_frame, bg=c['bg_input'], fg=c['text_primary'],
                                  font=('Segoe UI', 11), relief=tk.FLAT, padx=12, pady=8,
                                  wrap=tk.WORD, height=3, insertbackground='white')
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.input_text.bind('<Return>', self._on_enter)
        self.input_text.bind('<Shift-Return>', lambda e: None)
        self.input_text.focus_set()
        self.send_btn = tk.Button(input_frame, text="➤", bg=c['accent'], fg='white',
                                  font=('Segoe UI', 14, 'bold'), relief=tk.FLAT, width=3,
                                  cursor='hand2', command=self._send_message)
        self.send_btn.pack(side=tk.RIGHT, padx=(8, 0))

    def _update_status(self):
        if not self.status_lbl or not self.status_lbl.winfo_exists():
            return
        status = self.ai.check_subscription()
        if status.get('active'):
            self.status_lbl.config(text=f"✓ Активна · {status.get('days_left', 0)} дн.", fg='#43e97b')
        else:
            self.status_lbl.config(text="Не активна", fg='#f5576c')

    def _add_welcome(self):
        self._add_message("🤖 RuWeb AI",
                          "Привет! 👋 Я RuWeb AI. Понимаю БОЛЬШИЕ запросы — пиши несколько команд сразу:\n"
                          "• «убери всё, сделай сайт для игры название Beam, добавь логотип, кнопки красные»\n"
                          "• «сделай стили красивее и добавь раздел о нас»\n"
                          "• «почему не работает?» — дам диагностику", is_ai=True)

    def _add_message(self, author, text, is_ai=False):
        self.chat_text.config(state=tk.NORMAL)
        if self.chat_text.get('1.0', 'end-1c'):
            self.chat_text.insert(tk.END, '\n')
        self.chat_text.insert(tk.END, f"\n{author}\n", 'ai_name' if is_ai else 'user_name')
        parts = re.split(r'(```[a-zA-Z]*\n[\s\S]*?```)', text)
        for part in parts:
            if part.startswith('```') and part.endswith('```'):
                ct = part[3:-3]
                if ct.startswith('\n'):
                    ct = ct[1:]
                if '\n' in ct:
                    fl, rest = ct.split('\n', 1)
                    if fl.strip() in ('ruweb', 'css', 'js', 'html', 'javascript'):
                        ct = rest
                self.chat_text.insert(tk.END, '\n', 'msg')
                self.chat_text.insert(tk.END, ct, 'code')
                self.chat_text.insert(tk.END, '\n', 'msg')
            else:
                self.chat_text.insert(tk.END, part, 'msg')
        self.chat_text.insert(tk.END, '\n', 'msg')
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _note(self, text):
        try:
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.insert(tk.END, text + '\n', 'thinking')
            self.chat_text.see(tk.END)
            self.chat_text.config(state=tk.DISABLED)
        except Exception:
            pass

    def _start_thinking(self, text):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, '\n', 'msg')
        self.chat_text.mark_set('think_mark', tk.END)
        self.chat_text.mark_gravity('think_mark', 'left')
        self.chat_text.insert(tk.END, text + '\n', 'thinking')
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _update_thinking(self, text):
        if not (self.window and self.window.winfo_exists()):
            return
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert('think_mark', text + '\n', 'thinking')
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _stop_thinking(self):
        try:
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete('think_mark', 'end-1c')
            self.chat_text.config(state=tk.DISABLED)
        except Exception:
            pass

    def _apply_code(self, mode, code):
        try:
            if mode == 'replace':
                self.editor.delete('1.0', tk.END)
                self.editor.insert('1.0', code)
                self.editor.see('1.0')
            else:
                cur = self.editor.get('1.0', 'end-1c')
                self.editor.insert(tk.END, ('\n' if cur.strip() else '') + code)
                self.editor.see(tk.END)
            return True
        except Exception as e:
            self._note(f"⚠️ Не удалось вставить код в редактор: {e}")
            return False

    def _replace_styles_block(self, new_block):
        try:
            text = self.editor.get('1.0', 'end-1c')
            new = self.ai._set_styles(text, new_block)
            self.editor.delete('1.0', tk.END)
            self.editor.insert('1.0', new)
            self.editor.see('1.0')
            return True
        except Exception as e:
            self._note(f"⚠️ Не удалось обновить стили: {e}")
            return False

    def _clear_editor(self):
        try:
            self.editor.delete('1.0', tk.END)
            return True
        except Exception as e:
            self._note(f"⚠️ Не удалось очистить редактор: {e}")
            return False

    def _on_enter(self, event):
        if not event.state & 0x1:
            self._send_message()
            return 'break'
        return None

    def _grab_code_to_input(self):
        try:
            code = self.editor.get('1.0', 'end-1c')
            if code.strip():
                self.input_text.delete('1.0', tk.END)
                self.input_text.insert(tk.END, f"[Вот мой код:]\n```\n{code[:1500]}\n```\n\n[Вопрос:] ")
                self.input_text.see(tk.END)
                self.input_text.mark_set(tk.INSERT, 'end-1c')
        except Exception:
            pass

    def _insert_last_code(self):
        if not self.last_code_reply:
            messagebox.showinfo("RuWeb AI", "Нет кода для вставки")
            return
        if messagebox.askyesno("Вставить код", "Заменить текущий код ответом ИИ?\n\n(Ctrl+Z — отменить)"):
            try:
                self.editor.delete('1.0', tk.END)
                self.editor.insert('1.0', self.last_code_reply)
                messagebox.showinfo("Готово", "Код вставлен в редактор")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def _do_insert_direct(self):
        if self.last_code_reply:
            try:
                self.editor.insert(tk.INSERT, "\n" + self.last_code_reply)
            except Exception:
                pass

    def _clear_chat(self):
        if messagebox.askyesno("Очистить", "Очистить историю чата (память)?"):
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete('1.0', tk.END)
            self.chat_text.config(state=tk.DISABLED)
            self.ai.clear_history()
            self._add_welcome()

    def _send_message(self):
        msg = self.input_text.get('1.0', 'end-1c').strip()
        if not msg:
            return
        self.input_text.delete('1.0', tk.END)
        self._add_message("👤 Ты", msg, is_ai=False)
        try:
            code = self.editor.get('1.0', 'end-1c')
        except Exception:
            code = ""
        self._start_thinking("🤖 RuWeb AI думает…")
        self.send_btn.config(state='disabled', text='…')

        def worker():
            try:
                for text, delay in self.ai.thinking_stages(msg, code):
                    self.window.after(0, lambda t=text: self._update_thinking(t))
                    time.sleep(delay)
                reply, action = self.ai.chat(code, msg)
                blocks = re.findall(r'```[a-zA-Z]*\n([\s\S]*?)```', reply)
                if blocks:
                    self.last_code_reply = blocks[-1].strip()
                self.window.after(0, lambda: self._on_reply(reply, action))
            except Exception as e:
                self.window.after(0, lambda: self._on_reply(f"❌ Ошибка: {e}", None))
        threading.Thread(target=worker, daemon=True).start()

    def _on_reply(self, reply, action):
        self._stop_thinking()
        self._add_message("🤖 RuWeb AI", reply, is_ai=True)
        if action:
            mode = action.get('mode')
            if mode == 'last':
                self._do_insert_direct()
            elif mode == 'clear':
                self._clear_editor()
            elif mode == 'replace_styles':
                self._replace_styles_block(action.get('code', ''))
            elif mode in ('replace', 'append', 'set_code'):
                self.last_code_reply = action.get('code', '')
                self._apply_code('replace' if mode == 'set_code' else mode, self.last_code_reply)
        self.send_btn.config(state='normal', text='➤')