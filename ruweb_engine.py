import re
import os

class RuwebEngine:
    """Движок трансляции .ruweb в HTML5 + JavaScript (v6.0)"""
    
    def __init__(self):
        self.tag_map = {
            'страница': 'html', 'голова': 'head', 'тело': 'body',
            'заголовок': 'title', 'мета': 'meta', 'стили': 'style',
            'сценарий': 'script', 'секция': 'section', 'статья': 'article',
            'навигация': 'nav', 'боковая': 'aside', 'заголовок_блок': 'header',
            'подвал': 'footer', 'основной': 'main', 'заголовок1': 'h1',
            'заголовок2': 'h2', 'заголовок3': 'h3', 'заголовок4': 'h4',
            'заголовок5': 'h5', 'заголовок6': 'h6', 'абзац': 'p',
            'блок': 'div', 'строчный': 'span', 'перенос': 'br',
            'горизонтальная': 'hr', 'список': 'ul', 'список_нум': 'ol',
            'элемент': 'li', 'таблица': 'table', 'строка': 'tr',
            'ячейка': 'td', 'ячейка_заг': 'th', 'голова_табл': 'thead',
            'тело_табл': 'tbody', 'изображение': 'img', 'ссылка': 'a',
            'форма': 'form', 'ввод': 'input', 'кнопка': 'button',
            'метка': 'label', 'текст_область': 'textarea', 'выбор': 'select',
            'опция': 'option', 'жирный': 'b', 'важный': 'strong',
            'курсив': 'i', 'акцент': 'em', 'подчеркнутый': 'u',
            'зачеркнутый': 's', 'маленький': 'small', 'код': 'code',
            'цитата': 'blockquote', 'фрейм': 'iframe', 'видео': 'video',
            'аудио': 'audio', 'источник': 'source', 'холст': 'canvas',
            'детали': 'details', 'сводка': 'summary', 'диалог': 'dialog',
            'прогресс': 'progress', 'шаблон': 'template',
        }
        self.self_closing = ['мета', 'перенос', 'горизонтальная', 'изображение',
                             'ввод', 'источник', 'фрейм', 'ссылка_стиль']
        self.attr_map = {
            'класс': 'class', 'ид': 'id', 'стиль': 'style', 'язык': 'lang',
            'ссылка': 'href', 'источник': 'src', 'альтернатива': 'alt',
            'ширина': 'width', 'высота': 'height', 'тип': 'type',
            'имя': 'name', 'значение': 'value', 'подсказка': 'placeholder',
            'обязательный': 'required', 'отключен': 'disabled',
            'цель': 'target', 'при_клике': 'onclick',
            'при_изменении': 'onchange', 'при_отправке': 'onsubmit',
            'при_загрузке': 'onload', 'кодировка': 'charset',
            'автовоспроизведение': 'autoplay', 'управление': 'controls',
            'зацикленный': 'loop', 'загрузка': 'download',
            'только_чтение': 'readonly', 'автофокус': 'autofocus',
            'макс_длина': 'maxlength', 'мин_длина': 'minlength',
            'при_наведении': 'onmouseover', 'при_уходе': 'onmouseout',
            'при_фокусе': 'onfocus', 'при_потере_фокуса': 'onblur',
            'при_нажатии': 'onkeydown', 'при_вводе': 'oninput',
        }
        self.css_props = {
            'шрифт-семейство': 'font-family', 'шрифт-размер': 'font-size',
            'шрифт-вес': 'font-weight', 'шрифт-стиль': 'font-style',
            'высота-строки': 'line-height', 'межбуквенный-интервал': 'letter-spacing',
            'текст-выравнивание': 'text-align', 'текст-преобразование': 'text-transform',
            'текст-оформление': 'text-decoration', 'текст-тень': 'text-shadow',
            'граница-радиус': 'border-radius', 'граница-ширина': 'border-width',
            'граница-стиль': 'border-style', 'граница-цвет': 'border-color',
            'граница-сверху': 'border-top', 'граница-снизу': 'border-bottom',
            'граница-слева': 'border-left', 'граница-справа': 'border-right',
            'отступ-снизу': 'margin-bottom', 'отступ-сверху': 'margin-top',
            'отступ-слева': 'margin-left', 'отступ-справа': 'margin-right',
            'поля-снизу': 'padding-bottom', 'поля-сверху': 'padding-top',
            'поля-слева': 'padding-left', 'поля-справа': 'padding-right',
            'макс-ширина': 'max-width', 'мин-ширина': 'min-width',
            'макс-высота': 'max-height', 'мин-высота': 'min-height',
            'отступ': 'margin', 'поля': 'padding', 'фон': 'background',
            'цвет-фона': 'background-color', 'фон-изображение': 'background-image',
            'фон-позиция': 'background-position', 'фон-размер': 'background-size',
            'фон-повтор': 'background-repeat', 'цвет': 'color',
            'ширина': 'width', 'высота': 'height', 'граница': 'border',
            'курсор': 'cursor', 'дисплей': 'display', 'позиция': 'position',
            'тень': 'box-shadow', 'прозрачность': 'opacity',
            'видимость': 'visibility', 'переполнение': 'overflow',
            'переполнение-х': 'overflow-x', 'переполнение-у': 'overflow-y',
            'лево': 'left', 'право': 'right', 'верх': 'top', 'низ': 'bottom',
            'z-индекс': 'z-index', 'трансформация': 'transform',
            'переход': 'transition', 'анимация': 'animation',
            'анимация-задержка': 'animation-delay', 'фильтр': 'filter',
            'фильтр-фона': 'backdrop-filter', 'маска': 'mask',
            'флекс': 'flex', 'флекс-направление': 'flex-direction',
            'флекс-обёртка': 'flex-wrap', 'флекс-основа': 'flex-basis',
            'флекс-рост': 'flex-grow', 'флекс-сжатие': 'flex-shrink',
            'выравнивание-элементов': 'align-items',
            'выравнивание-содержимого': 'align-content',
            'выравнивание-себя': 'align-self',
            'justify-содержимое': 'justify-content', 'gap': 'gap',
            'сетка-шаблон-колонки': 'grid-template-columns',
            'сетка-шаблон-строки': 'grid-template-rows',
            'сетка-колонка': 'grid-column', 'сетка-строка': 'grid-row',
            'размер-блока': 'box-sizing', 'контур': 'outline',
            'стиль-списка': 'list-style', 'соотношение-сторон': 'aspect-ratio',
        }
        self.css_vals = {
            'линейный-градиент(': 'linear-gradient(',
            'радиальный-градиент(': 'radial-gradient(',
            'размытие(': 'blur(', 'яркость(': 'brightness(', 'контраст(': 'contrast(',
            'перемещение(': 'translate(', 'перемещение-x(': 'translateX(',
            'перемещение-y(': 'translateY(', 'поворот(': 'rotate(',
            'масштаб(': 'scale(', 'наклон(': 'skew(',
            'красный': 'red', 'синий': 'blue', 'зелёный': 'green',
            'желтый': 'yellow', 'оранжевый': 'orange', 'фиолетовый': 'purple',
            'розовый': 'pink', 'серый': 'gray', 'белый': 'white',
            'чёрный': 'black', 'прозрачный': 'transparent',
            'центр': 'center', 'слева': 'left', 'справа': 'right',
            'сверху': 'top', 'снизу': 'bottom',
            'начало-флекс': 'flex-start', 'конец-флекс': 'flex-end',
            'между': 'space-between', 'вокруг': 'space-around',
            'равномерно': 'space-evenly', 'растянуть': 'stretch',
            'нет': 'none', 'авто': 'auto', 'блок': 'block',
            'встроенный': 'inline', 'гибкий': 'flex', 'сетка': 'grid',
            'относительная': 'relative', 'абсолютная': 'absolute',
            'фиксированная': 'fixed', 'липкая': 'sticky',
            'скрыто': 'hidden', 'видно': 'visible', 'прокрутка': 'scroll',
            'полужирный': 'bold', 'нормальный': 'normal', 'курсивный': 'italic',
            'подчёркнутый': 'underline', 'зачёркнутый': 'line-through',
            'заглавные': 'uppercase', 'строчные': 'lowercase',
            'капитализация': 'capitalize', 'по-ширине': 'justify',
            'не-повторять': 'no-repeat', 'повторять': 'repeat',
            'покрыть': 'cover', 'содержать': 'contain',
            'в-рамку': 'border-box', 'в-содержимое': 'content-box',
            'указатель': 'pointer', 'умолчание': 'default',
            'бесконечно': 'infinite', 'чередовать': 'alternate',
            'плавное': 'ease', 'плавное-вход': 'ease-in',
            'плавное-выход': 'ease-out', 'плавное-вход-выход': 'ease-in-out',
            'линейное': 'linear', 'сплошной': 'solid',
            'град': 'deg',
        }
        # ПОЛНОСТЬЮ РУССКИЙ JS — все ключевые слова, функции и методы
        self.russian_js = {
            # Переменные и типы
            'перем': 'let', 'конст': 'const', 'функция': 'function',
            'возврат': 'return', 'асинхронная': 'async', 'ожидать': 'await',
            'класс': 'class', 'конструктор': 'constructor', 'новый': 'new',
            'этот': 'this', 'супер': 'super', 'наследует': 'extends',
            # Условия и циклы
            'если': 'if', 'иначе_если': 'else if', 'иначе': 'else',
            'когда': 'switch', 'случай': 'case', 'по_умолчанию': 'default',
            'для': 'for', 'пока': 'while', 'цикл': 'do',
            'прервать': 'break', 'продолжить': 'continue',
            'для_каждого': 'forEach', 'из': 'of', 'в': 'in',
            # Значения
            'истина': 'true', 'ложь': 'false', 'ничего': 'null',
            'неопределено': 'undefined',
            # Операторы
            'и': '&&', 'или': '||', 'не': '!',
            'равно': '===', 'не_равно': '!==',
            'больше_равно': '>=', 'меньше_равно': '<=',
            'больше': '>', 'меньше': '<',
            # Вывод
            'вывести': 'console.log', 'предупредить': 'alert',
            'спросить': 'prompt', 'подтвердить': 'confirm',
            'вывести_ошибку': 'console.error',
            # Math
            'округлить': 'Math.round', 'случайное': 'Math.random',
            'максимум': 'Math.max', 'минимум': 'Math.min',
            'степень': 'Math.pow', 'корень': 'Math.sqrt',
            'абсолют': 'Math.abs', 'потолок': 'Math.ceil', 'пол': 'Math.floor',
            # Числа
            'целое': 'parseInt', 'дробное': 'parseFloat',
            # Строки
            'в_верхний': 'toUpperCase', 'в_нижний': 'toLowerCase',
            'заменить': 'replace', 'разделить': 'split', 'обрезать': 'trim',
            'подстрока': 'substring', 'начинается_с': 'startsWith',
            'заканчивается_на': 'endsWith', 'включает': 'includes',
            'индекс': 'indexOf', 'длина': 'length',
            # Массивы
            'добавить': 'push', 'срез': 'slice', 'соединить': 'join',
            'сортировать': 'sort', 'перевернуть': 'reverse',
            'фильтр': 'filter', 'карта': 'map', 'найти': 'find',
            'в_начало': 'unshift', 'в_конец': 'push',
            'удалить_первый': 'shift', 'удалить_последний': 'pop',
            'вставить': 'splice', 'объединить': 'concat',
            'заполнить': 'fill', 'каждый': 'every', 'некоторый': 'some',
            'уменьшить': 'reduce', 'найти_индекс': 'findIndex',
            # DOM
            'получить_элемент': 'document.querySelector',
            'получить_все': 'document.querySelectorAll',
            'получить_по_ид': 'document.getElementById',
            'получить_по_классу': 'document.getElementsByClassName',
            'создать_элемент': 'document.createElement',
            'добавить_класс': 'classList.add', 'убрать_класс': 'classList.remove',
            'переключить_класс': 'classList.toggle',
            'содержит_класс': 'classList.contains',
            'текст': 'textContent', 'внутренний_HTML': 'innerHTML',
            'установить_атрибут': 'setAttribute',
            'получить_атрибут': 'getAttribute', 'удалить_элемент': 'remove',
            'добавить_в': 'appendChild', 'родитель': 'parentElement',
            'стиль_элемента': 'style', 'слушать': 'addEventListener',
            'перестать_слушать': 'removeEventListener',
            'предотвратить': 'preventDefault',
            'остановить_всплытие': 'stopPropagation',
            'цель_события': 'event.target',
            # Дата и время
            'сейчас': 'Date.now', 'новая_дата': 'new Date',
            'таймер': 'setTimeout', 'интервал': 'setInterval',
            'остановить_таймер': 'clearTimeout',
            'остановить_интервал': 'clearInterval',
            # Promise и JSON
            'обещание': 'Promise', 'затем': 'then', 'поймать': 'catch',
            'наконец': 'finally', 'в_JSON': 'JSON.stringify',
            'из_JSON': 'JSON.parse', 'очистить_консоль': 'console.clear',
            # Массив как класс
            'Массив': 'Array',
            # Canvas методы — русские названия для контекста
            'получить_контекст': 'getContext',
            'запросить_кадр': 'requestAnimationFrame',
            'очистить_прямоугольник': 'clearRect',
            'заполнить_прямоугольник': 'fillRect',
            'обвести_прямоугольник': 'strokeRect',
            'заполнить_круг': 'fillCircle',
            'обвести_круг': 'strokeCircle',
            'заполнить_текст': 'fillText',
            'обвести_текст': 'strokeText',
            'начать_путь': 'beginPath',
            'закрыть_путь': 'closePath',
            'переместить_к': 'moveTo',
            'линия_к': 'lineTo',
            'дуга': 'arc',
            'заполнить': 'fill',
            'обвести': 'stroke',
            'цвет_фона': 'fillStyle',
            'цвет_линии': 'strokeStyle',
            'ширина_линии': 'lineWidth',
            'шрифт': 'font',
            'выравнивание_текста': 'textAlign',
            'получить_границы': 'getBoundingClientRect',
            # Объект
            'ключи': 'Object.keys', 'значения': 'Object.values',
            'записи': 'Object.entries', 'назначить': 'Object.assign',
            # Console
            'таблица': 'console.table', 'группа': 'console.group',
            'конец_группы': 'console.groupEnd',
        }
        self.js_block_openers = ['функция ', 'если ', 'иначе_если ', 'иначе',
                                 'для ', 'пока ', 'цикл ', 'когда ',
                                 'попробовать', 'поймать_ошибку']
        self.js_block_continuers = ['иначе', 'иначе_если', 'поймать_ошибку']
    
    def translate_russian_code(self, code):
        lines = []
        for raw in code.split('\n'):
            s = raw.rstrip()
            if not s.strip():
                lines.append((0, '', True)); continue
            ind = len(s) - len(s.lstrip())
            lines.append((ind, s.lstrip(), False))
        result = []
        stack = []
        for ind, text, empty in lines:
            if empty:
                result.append(''); continue
            while stack and stack[-1] >= ind:
                stack.pop(); result.append('    ' * len(stack) + '}')
            if text in ('конец', '}', 'конец_функции'):
                if stack:
                    stack.pop(); result.append('    ' * len(stack) + '}')
                continue
            prefix = '    ' * len(stack)
            if text.startswith('#'):
                result.append(prefix + '//' + text[1:].strip()); continue
            tr = self._translate_line(text)
            is_open = any(text.startswith(k) for k in self.js_block_openers)
            is_cont = any(text == k or text.startswith(k + ' ') or text.startswith(k + '(')
                          for k in self.js_block_continuers)
            if is_cont:
                if stack and stack[-1] >= ind:
                    stack.pop(); result.append('    ' * len(stack) + '}')
                result.append('    ' * len(stack) + tr + ' {'); stack.append(ind)
            elif is_open:
                result.append(prefix + tr + ' {'); stack.append(ind)
            else:
                result.append(prefix + tr)
        while stack:
            stack.pop(); result.append('    ' * len(stack) + '}')
        return '\n'.join(result)
    
    def _translate_line(self, line):
        strings = []
        def stash(m):
            strings.append(m.group(0)); return f"\x00{len(strings)-1}\x00"
        protected = re.sub(r'("[^"]*"|\'[^\']*\')', stash, line)
        result = protected.replace(' равно ', ' === ')
        for rus in sorted(self.russian_js.keys(), key=len, reverse=True):
            pat = r'(?<![а-яА-Яa-zA-Z_])' + re.escape(rus) + r'(?![а-яА-Яa-zA-Z_])'
            result = re.sub(pat, self.russian_js[rus], result)
        for old, new in [('больше_равно', '>='), ('меньше_равно', '<='),
                         ('не_равно', '!=='), ('больше', '>'), ('меньше', '<')]:
            result = result.replace(old, new)
        return re.sub(r'\x00(\d+)\x00', lambda m: strings[int(m.group(1))], result)
    
    def translate_css(self, css):
        css = re.sub(r'(\d)\s*град(?![а-яА-ЯёЁ\w])', r'\1deg', css)
        for v in sorted(self.css_vals.keys(), key=len, reverse=True):
            pat = (r'(?<![а-яА-ЯёЁ\w-])' + re.escape(v)) if v.endswith('(') else \
                  (r'(?<![а-яА-ЯёЁ\w-])' + re.escape(v) + r'(?![а-яА-ЯёЁ\w-])')
            css = re.sub(pat, self.css_vals[v], css)
        for p in sorted(self.css_props.keys(), key=len, reverse=True):
            css = re.sub(r'(?<![а-яА-ЯёЁ\w-])' + re.escape(p) + r'\s*:',
                         self.css_props[p] + ':', css)
        for rus in sorted(self.tag_map.keys(), key=len, reverse=True):
            css = re.sub(r'(?<![.#а-яА-ЯёЁ\w_-])' + re.escape(rus) + r'(?![а-яА-ЯёЁ\w-])',
                         self.tag_map[rus], css)
        return css
    
    def _parse_attributes(self, s):
        attrs = {}
        for m in re.finditer(r'([a-zA-Zа-яА-Я_][\w-]*)\s*=\s*"([^"]*)"', s):
            attrs[self.attr_map.get(m.group(1), m.group(1))] = m.group(2)
        return attrs
    
    def _attributes_to_string(self, a):
        return (' ' + ' '.join(f'{k}="{v}"' for k, v in a.items())) if a else ''
    
    def translate_line(self, line):
        line = line.rstrip()
        if not line.strip():
            return ''
        indent = len(line) - len(line.lstrip())
        line = line.lstrip()
        pad = '  ' * (indent // 2)
        if line.startswith('документ_html'):
            return '<!DOCTYPE html>'
        if line.startswith('#') or line.startswith('//'):
            c = line[1:].strip() if line.startswith('#') else line[2:].strip()
            return f'{pad}<!-- {c} -->'
        if line.startswith('| '):
            return f'{pad}{line[2:]}'
        if line.startswith('/'):
            return f'{pad}</{self.tag_map.get(line[1:].strip(), line[1:].strip())}>'
        parts = line.split(maxsplit=1)
        tag = parts[0]; rest = parts[1] if len(parts) > 1 else ''
        self_close = tag.endswith('/')
        if self_close:
            tag = tag[:-1]
        html_tag = self.tag_map.get(tag, tag)
        attrs = self._parse_attributes(rest) if rest else {}
        remaining = re.sub(r'([a-zA-Zа-яА-Я_][\w-]*)\s*=\s*"[^"]*"', '', rest).strip() if rest else ''
        if remaining.endswith('/'):
            remaining = remaining[:-1].strip(); self_close = True
        tm = re.search(r'"([^"]*)"', remaining)
        text = tm.group(1) if tm else ''
        a = self._attributes_to_string(attrs)
        if self_close or tag in self.self_closing:
            return f'{pad}<{html_tag}{a}>'
        if text:
            return f'{pad}<{html_tag}{a}>{text}</{html_tag}>'
        return f'{pad}<{html_tag}{a}>'
    
    def translate(self, ruweb_code):
        lines = ruweb_code.split('\n')
        out = []
        tag_stack = []
        i, n = 0, len(lines)
        def close_to(indent):
            while tag_stack and tag_stack[-1][0] >= indent:
                ind, tag = tag_stack.pop()
                out.append('  ' * (ind // 2) + f'</{tag}>')
        while i < n:
            raw = lines[i]
            if not raw.strip():
                i += 1; continue
            indent = len(raw) - len(raw.lstrip())
            stripped = raw.strip()
            if stripped == 'стили' or stripped.startswith('стили '):
                close_to(indent)
                rest = stripped[len('стили'):].strip()
                a = self._attributes_to_string(self._parse_attributes(rest)) if rest else ''
                out.append('  ' * (indent // 2) + f'<style{a}>')
                buf = []; i += 1
                while i < n:
                    r2 = lines[i]; s2 = r2.strip()
                    if s2.startswith('/стили'):
                        i += 1; break
                    if s2 and (len(r2) - len(r2.lstrip())) <= indent:
                        break
                    if s2:
                        buf.append(s2[1:].strip() if s2.startswith('|') else s2)
                    i += 1
                out.append(self.translate_css('\n'.join(buf)))
                out.append('  ' * (indent // 2) + '</style>')
                continue
            if stripped == 'сценарий' or stripped.startswith('сценарий '):
                close_to(indent)
                rest = stripped[len('сценарий'):].strip()
                a = self._attributes_to_string(self._parse_attributes(rest)) if rest else ''
                out.append('  ' * (indent // 2) + f'<script{a}>')
                buf = []; i += 1
                while i < n:
                    r2 = lines[i]; s2 = r2.strip()
                    if s2.startswith('/сценарий'):
                        i += 1; break
                    if s2 and (len(r2) - len(r2.lstrip())) <= indent:
                        break
                    buf.append(r2)
                    i += 1
                out.append(self.translate_russian_code('\n'.join(buf)))
                out.append('  ' * (indent // 2) + '</script>')
                continue
            close_to(indent)
            html_line = self.translate_line(raw)
            if html_line:
                if html_line.strip().lower() == '<head>':
                    out.append(html_line); out.append(self.CONSOLE_BRIDGE)
                else:
                    out.append(html_line)
                first = stripped.split(maxsplit=1)[0]
                tag = first.rstrip('/')
                is_close = first.startswith('/')
                is_self = first.endswith('/') or tag in self.self_closing
                rest = stripped.split(maxsplit=1)[1] if ' ' in stripped else ''
                has_text = False
                if rest:
                    rem = re.sub(r'([a-zA-Zа-яА-Я_][\w-]*)\s*=\s*"[^"]*"', '', rest).strip()
                    if rem.endswith('/'):
                        is_self = True
                    if re.search(r'"[^"]*"', rem):
                        has_text = True
                if not is_close and not is_self and not has_text and tag in self.tag_map:
                    tag_stack.append((indent, self.tag_map[tag]))
            i += 1
        close_to(-1)
        return '\n'.join(out)
    
    CONSOLE_BRIDGE = """<script>
(function(){
var oL=console.log,oE=console.error,oW=console.warn;
function send(l,a){try{var m=Array.prototype.map.call(a,function(x){
if(x===null)return'null';if(x===undefined)return'undefined';
if(typeof x==='object'){try{return JSON.stringify(x)}catch(e){return String(x)}}
return String(x)}).join(' ');
var x=new XMLHttpRequest();x.open('POST','/log',true);
x.setRequestHeader('Content-Type','text/plain');x.send(l+': '+m);}catch(e){}}
console.log=function(){oL.apply(console,arguments);send('log',arguments)};
console.error=function(){oE.apply(console,arguments);send('error',arguments)};
console.warn=function(){oW.apply(console,arguments);send('warn',arguments)};
window.addEventListener('error',function(e){send('error',['RuntimeError: '+e.message])});
})();
</script>"""
    
    def get_base_template(self):
        return '''документ_html
страница язык="ru"
  голова
    мета кодировка="utf-8"/
    мета имя="viewport" значение="width=device-width, initial-scale=1.0"/
    заголовок "Мой RuWeb сайт"
  стили
    | * { отступ: 0; поля: 0; размер-блока: в-рамку; }
    | тело {
    |   шрифт-семейство: 'Segoe UI', sans-serif;
    |   фон: линейный-градиент(135град, #0f0c29, #302b63, #24243e);
    |   цвет: белый;
    |   мин-высота: 100vh;
    | }
    | .контейнер { макс-ширина: 1100px; отступ: 0 авто; поля: 40px 20px; }
    | .шапка {
    |   фон: rgba(255,255,255,0.1);
    |   фильтр-фона: размытие(16px);
    |   граница: 1px сплошной rgba(255,255,255,0.2);
    |   граница-радиус: 24px; поля: 60px 40px;
    |   текст-выравнивание: центр; отступ-снизу: 40px;
    | }
    | .шапка h1 { шрифт-размер: 56px; шрифт-вес: полужирный; }
    | .кнопка-главная {
    |   фон: линейный-градиент(135град, #667eea, #764ba2);
    |   цвет: белый; граница: нет; поля: 16px 40px;
    |   шрифт-размер: 17px; граница-радиус: 14px; курсор: указатель;
    |   отступ-сверху: 20px;
    | }
    | .счётчик-число { шрифт-размер: 96px; шрифт-вес: полужирный; отступ: 20px 0; }
    | .подвал { текст-выравнивание: центр; поля: 30px; цвет: rgba(255,255,255,0.5); }
  тело
    основной класс="контейнер"
      заголовок_блок класс="шапка"
        заголовок1 "Добро пожаловать в RuWeb"
        абзац "Создавай красивые сайты на русском языке"
      секция класс="шапка"
        заголовок2 "Интерактивный счётчик"
        абзац ид="счётчик" класс="счётчик-число" "0"
        кнопка класс="кнопка-главная" ид="кнопка_плюс" "Увеличить"
      подвал класс="подвал"
        абзац "Создано в RuWeb Studio 2026"
    сценарий
      перем счёт = 0
      функция увеличить()
        счёт = счёт + 1
        получить_по_ид('счётчик').текст = счёт
        вывести('Счётчик: ' + счёт)
      получить_по_ид('кнопка_плюс').слушать('click', увеличить)
      вывести('Сайт на RuWeb загружен!')
'''