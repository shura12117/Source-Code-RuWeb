# Ruweb Studio 2026

[🇷🇺 Русский](#русский)

---

# 🇷🇺 Русский

## 📖 О проекте

**Ruweb Studio** - это современная среда разработки для создания веб-сайтов на русском языке. Пишите код на русском, используя интуитивно понятный синтаксис на основе отступов, а движок автоматически транслирует его в стандартный HTML5 + CSS + JavaScript.
# Ruweb Studio 2026 — версия 5.0

**Среда разработки веб-сайтов на русском языке.**
Пишите теги, стили и скрипты по-русски — движок транслирует их в HTML5 + CSS + JavaScript.


[🇷🇺 Русский](#-русский)

---

## 📖 О проекте

**Ruweb Studio** - это IDE, в которой весь веб-код пишется русскими словами:

```ruweb
заголовок1 "Привет, мир!"
кнопка класс="кнопка" ид="кнопка_плюс" "Увеличить"

сценарий
  перем счёт = 0
  
  функция увеличить()
    счёт = счёт + 1
    вывести(счёт)


Возможности:

Русский синтаксис для HTML тегов, CSS стилей и JavaScript
Отступы вместо закрывающих тегов — структура определяется вложенностью
Полный CSS на русском — более 100 свойств и значений переведено
Живой предпросмотр HTML+CSS в реальном времени (слева)
Полный предпросмотр в браузере (F5) с работающим JavaScript
Управление проектами — создавайте, открывайте, удаляйте проекты
Экспорт в HTML — готовый файл для размещения на сервере
Горячие клавиши для быстрой работы (работают на любой раскладке!)
Зум кода через Ctrl + колёсико
Файлы .ruweb — собственный формат проектов


Быстрый старт:

Создание первого проекта:
Нажмите "+ Новый проект"
Введите название проекта (например, мой_сайт)
Нажмите "Создать проект"
Проект автоматически откроется в редакторе

Пример кода:

документ_html
страница язык="ru"
  голова
    мета кодировка="utf-8"/
    заголовок "Мой сайт"
    стили
      | тело { фон: #1a1a2e; цвет: белый; }
  тело
    заголовок1 "Привет, мир!"
    
    сценарий
      перем имя = "Мир"
      
      функция поздороваться()
        предупредить('Привет, ' + имя + '!')
      
      поздороваться()

Обратите внимание: нет закрывающих тегов (/страница, /тело, /стили, /сценарий) и нет слова конец в JavaScript. Структура определяется отступами.

Как работают отступы:

страница                   # отступ 0 → <html>
  голова                   # отступ 2 → <head> внутри <html>
    заголовок "Сайт"       # отступ 4 → <title> внутри <head>
    стили                  # отступ 4 → <style> внутри <head>
      | тело { цвет: белый; }
  тело                     # отступ 2 → <body>, <head> закрылся автоматически
    заголовок1 "Привет"    # отступ 4 → <h1> внутри <body>
    блок                   # отступ 4 → <div> внутри <body>
      абзац "Текст"        # отступ 6 → <p> внутри <div>
      кнопка "Жми"         # отступ 6 → <button> внутри <div>
    подвал                 # отступ 2 → <footer> внутри <body>, <div> закрылся
      абзац "© 2026"


Структура документа:

Ruweb HTML
документ_html <!DOCTYPE html>
страница <html>
голова <head>
тело <body>
заголовок <title>
мета <meta>
стили <style>…</style>
сценарий <script>…</script>
Секции и текст:
Ruweb HTML
заголовок_блок <header>
заголовок1…6 <h1>…<h6>
подвал <footer>
абзац <p>
основной <main>
блок <div>
секция <section>
строчный <span>
статья <article>
перенос

навигация <nav>
горизонтальная <hr>
боковая <aside>
код <code>

Списки и таблицы:

Ruweb HTML
форма, ввод, кнопка, метка <form>, <input>, <button>, <label>
текст_область, выбор, опция <textarea>, <select>, <option>
изображение, ссылка, видео, аудио <img>, <a>, <video>, <audio>
Правила строк:
Текст тега пишется в кавычках после атрибутов: абзац ид="привет" "Текст".
Самозакрывающиеся теги — со слэшем: мета кодировка="utf-8"/.
Структура блоков определяется отступами — закрывающих тегов нет.
Комментарии — # комментарий.
Строки CSS внутри стили начинаются с |.

Синтаксис: атрибуты

Ruweb HTML
класс class
ид id
стиль style
язык lang
ссылка href
источник src
альтернатива alt
ширина / высота width / height
тип type
имя name
значение value
подсказка placeholder
обязательный required
отключен disabled
при_клике onclick
при_отправке onsubmit
при_вводе oninput
при_фокусе onfocus
Пример формы:
форма при_отправке="обработать()"
ввод тип="текст" подсказка="Имя" обязательный/
кнопка тип="отправить" "Отправить"

Синтаксис: CSS на русском

CSS пишется внутри стили и переводится автоматически. Блок закрывается когда отступ возвращается на уровень родителя.
стили
| тело { фон: #1a1a2e; цвет: белый; шрифт-семейство: 'Arial'; }
| .кнопка {
| фон: линейный-градиент(135град, #667eea, #764ba2);
| граница-радиус: 8px; курсор: указатель; текст-выравнивание: центр;
| }

Свойства (шрифт и текст):

RuWeb CSS
шрифт font
шрифт-семейство font-family
шрифт-размер font-size
шрифт-вес font-weight
шрифт-стиль font-style
шрифт-вариант font-variant
шрифт-растяжение font-stretch
высота-строки line-height
межбуквенный-интервал letter-spacing
межсловный-интервал word-spacing
текст-выравнивание text-align
текст-преобразование text-transform
текст-оформление text-decoration
текст-оформление-стиль text-decoration-style
текст-оформление-цвет text-decoration-color
текст-оформление-линия text-decoration-line
текст-тень text-shadow
текст-отступ text-indent
текст-переполнение text-overflow
выравнивание-вертикальное vertical-align
разрыв-слова word-break
перенос-слов word-wrap
переполнение-обёртка overflow-wrap
белое-пространство white-space
дефисы hyphens
табуляция-размер tab-size
направление direction
юникод-двунаправленность unicode-bidi
режим-записи writing-mode
ориентация-текста text-orientation

Свойства (фон и границы):

RuWeb CSS
фон background
цвет-фона background-color
фон-изображение background-image
фон-позиция background-position
фон-размер background-size
фон-повтор background-repeat
фон-прикрепление background-attachment
фон-происхождение background-origin
фон-клип background-clip
цвет color
граница border
граница-радиус border-radius
граница-ширина border-width
граница-стиль border-style
граница-цвет border-color
граница-сверху border-top
граница-снизу border-bottom
граница-слева border-left
граница-справа border-right
граница-коллапс border-collapse
граница-разделение border-spacing
граница-изображение border-image
контур outline
контур-цвет outline-color
контур-стиль outline-style
контур-ширина outline-width
контур-смещение outline-offset
тень box-shadow
размер-блока box-sizing

Свойства (размеры и отступы):

RuWeb CSS
ширина width
высота height
макс-ширина max-width
макс-высота max-height
мин-ширина min-width
мин-высота min-height
соотношение-сторон aspect-ratio
отступ margin
отступ-снизу margin-bottom
отступ-сверху margin-top
отступ-слева margin-left
отступ-справа margin-right
поля padding
поля-снизу padding-bottom
поля-сверху padding-top
поля-слева padding-left
поля-справа padding-right
Свойства (раскладка):
RuWeb CSS
дисплей display
позиция position
лево left
право right
верх top
низ bottom
z-индекс z-index
видимость visibility
прозрачность opacity
переполнение overflow
переполнение-х overflow-x
переполнение-у overflow-y
курсор cursor
флекс flex
флекс-направление flex-direction
флекс-обёртка flex-wrap
флекс-основа flex-basis
флекс-рост flex-grow
флекс-сжатие flex-shrink
выравнивание-элементов align-items
выравнивание-содержимого align-content
выравнивание-себя align-self
justify-содержимое justify-content
justify-элементы justify-items
place-элементы place-items
place-содержимое place-content
gap gap
gap-строки row-gap
gap-колонки column-gap
порядок order
сетка grid (значение)
сетка-шаблон-колонки grid-template-columns
сетка-шаблон-строки grid-template-rows
сетка-шаблон-области grid-template-areas
сетка-шаблон grid-template
сетка-колонка grid-column
сетка-строка grid-row
сетка-область grid-area
сетка-авто-поток grid-auto-flow
сетка-авто-колонки grid-auto-columns
сетка-авто-строки grid-auto-rows
колонки columns
колонки-счётчик column-count
колонки-зазор column-gap
колонки-правило column-rule

Свойства (трансформация, анимация, переходы):

RuWeb CSS
трансформация transform
трансформация-происхождение transform-origin
трансформация-стиль transform-style
перспектива perspective
перспектива-происхождение perspective-origin
обратная-сторона-видимость backface-visibility
переход transition
переход-свойство transition-property
переход-длительность transition-duration
переход-функция-тайминга transition-timing-function
переход-задержка transition-delay
анимация animation
анимация-имя animation-name
анимация-длительность animation-duration
анимация-функция-тайминга animation-timing-function
анимация-задержка animation-delay
анимация-повторение animation-iteration-count
анимация-направление animation-direction
анимация-режим-заполнения animation-fill-mode
анимация-состояние-воспроизведения animation-play-state

Свойства (фильтры, маски, эффекты):

RuWeb CSS
фильтр filter
фильтр-фона backdrop-filter
маска mask
маска-изображение mask-image
маска-режим mask-mode
маска-позиция mask-position
маска-размер mask-size
маска-повтор mask-repeat
клип-путь clip-path
режим-смешивания mix-blend-mode
изоляция isolation
декорация-разрыва box-decoration-break
воля-изменения will-change

Свойства (разное):

RuWeb CSS
содержимое content
пользователь-выбор user-select
события-указателя pointer-events
поведение-прокрутки scroll-behavior
привязка-прокрутки scroll-snap-type
привязка-прокрутки-остановка scroll-snap-stop
привязка-прокрутки-выравнивание scroll-snap-align
сенсорное-действие touch-action
внешний-вид appearance
изменение-размера resize
поведение-цвета color-scheme
цветовая-схема color-scheme
цвет-каретки caret-color
цвет-акцента accent-color
цитаты quotes
сироты orphans
вдовы widows
разрыв-до break-before
разрыв-после break-after
разрыв-внутри break-inside
объект-вписывание object-fit
объект-позиция object-position
все all

Значения:

RuWeb CSS
указатель pointer
центр center
белый white
чёрный black
красный red
синий blue
зелёный green
жёлтый yellow
оранжевый orange
фиолетовый purple
розовый pink
серый gray
коричневый brown
прозрачный transparent
нет none
авто auto
блок block
встроенный inline
гибкий flex
сетка grid
таблица table
строка-таблица table-row
ячейка-таблица table-cell
содержимое contents
скрыто hidden
видно visible
схлопнуто collapse
раздельно separate
относительная relative
абсолютная absolute
фиксированная fixed
липкая sticky
статическая static
полужирный bold
нормальный normal
курсивный italic
подчёркнутый underline
зачёркнутый line-through
заглавные uppercase
строчные lowercase
капитализация capitalize
по-ширине justify
слева left
справа right
сверху top
снизу bottom
наследовать inherit
исходное initial
сбросить unset
вернуть revert
в-строку row
в-столбец column
оборачивать wrap
не-оборачивать nowrap
начало-флекс flex-start
конец-флекс flex-end
базовая-линия baseline
между space-between
вокруг space-around
равномерно space-evenly
растянуть stretch
мин-содержимое min-content
макс-содержимое max-content
вписать-содержимое fit-content
содержать contain
покрыть cover
в-рамку border-box
в-содержимое content-box
в-поля padding-box
масштаб-вниз scale-down
заполнить fill
не-повторять no-repeat
повторять repeat
повторять-х repeat-x
повторять-у repeat-y
плавное ease
плавное-вход ease-in
плавное-выход ease-out
плавное-вход-выход ease-in-out
линейное linear
бесконечно infinite
чередовать alternate
чередовать-обратно alternate-reverse
вперёд forwards
назад backwards
оба both
проигрывается running
пауза paused
перемещение translate()
поворот rotate()
масштаб scale()
наклон skew()
размытие blur()
яркость brightness()
контраст contrast()
оттенки-серого grayscale()
поворот-оттенка hue-rotate()
инверсия invert()
насыщенность saturate()
сепия sepia()
тень-падения drop-shadow()
линейный-градиент( linear-gradient(
радиальный-градиент( radial-gradient(
конический-градиент( conic-gradient(
повтор-линейный-градиент( repeating-linear-gradient(
повтор-радиальный-градиент( repeating-radial-gradient(
повтор-конический-градиент( repeating-conic-gradient(
град deg
процент %
Синтаксис: JavaScript на русском
Код пишется внутри сценарий. Блоки определяются отступами — слово «конец» больше не нужно:
сценарий
перем x = 10
конст PI = 3.14
функция сложить(а, б)
возврат а + б
если (x больше 5)
вывести('x больше 5')
иначе
вывести('x <= 5')
для (перем i = 0; i меньше 10; i = i + 1)
вывести(i)
получить_по_ид('кнопка').слушать('click', увеличить)

Основные команды:

RuWeb JavaScript
перем let
конст const
функция function
возврат return
если / иначе if / else
для / пока for / while
истина / ложь true / false
и / или / не && / || / !
равно ===
не_равно !==
больше / меньше > / <
больше_равно / меньше_равно >= / <=
вывести console.log
предупредить alert
спросить prompt
подтвердить confirm
таймер / интервал setTimeout / setInterval
ожидать await
прервать break
продолжить continue

Работа с DOM:

RuWeb JavaScript
получить_по_ид document.getElementById
получить_элемент document.querySelector
получить_все document.querySelectorAll
получить_по_классу document.getElementsByClassName
создать_элемент document.createElement
слушать addEventListener
перестать_слушать removeEventListener
текст textContent
внутренний_HTML innerHTML
добавить_класс / убрать_класс classList.add / remove
переключить_класс classList.toggle
содержит_класс classList.contains
установить_атрибут setAttribute
получить_атрибут getAttribute
удалить_элемент remove
добавить_в appendChild
родитель parentElement
дети children
стиль_элемента style

Пример: интерактивный счётчик

документ_html
страница язык="ru"
  голова
    мета кодировка="utf-8"/
    заголовок "Счётчик"
    стили
      | тело {
      |   фон: #0f0c29;
      |   цвет: белый;
      |   шрифт-семейство: sans-serif;
      |   поля: 40px;
      | }
      | .число {
      |   шрифт-размер: 72px;
      |   шрифт-вес: полужирный;
      |   цвет: #667eea;
      | }
      | .кнопка {
      |   фон: #667eea;
      |   цвет: белый;
      |   граница: нет;
      |   поля: 14px 32px;
      |   шрифт-размер: 16px;
      |   граница-радиус: 10px;
      |   курсор: указатель;
      | }
  тело
    заголовок1 "Кликай!"
    абзац ид="число" класс="число" "0"
    кнопка класс="кнопка" ид="btn" "Увеличить"
    
    сценарий
      перем счёт = 0
      
      функция увеличить()
        счёт = счёт + 1
        получить_по_ид('число').текст = счёт
        вывести('Счётчик: ' + счёт)
      
      получить_по_ид('btn').слушать('click', увеличить)

Горячие клавиши:

Сочетание Действие
Ctrl + S / Ctrl + Ы Сохранить и обновить предпросмотр
F5 Перезапустить предпросмотр
Ctrl + E / Ctrl + У Экспорт в HTML
Ctrl + Z / Ctrl + Я Отменить
Ctrl + Y Повторить
Ctrl + A / Ctrl + Ф Выделить всё
Ctrl + C / Ctrl + С Копировать
Ctrl + V / Ctrl + М Вставить
Ctrl + X / Ctrl + Ч Вырезать
Ctrl + колёсико Масштаб кода
Tab / Shift+Tab Увеличить / уменьшить отступ блока



Спасибо за прочтение!

Наши соц сети:
Telegram - https://t.me/BazukaHome_Creator
Lolka - https://lolka.gg/1rg8Lg1oI
