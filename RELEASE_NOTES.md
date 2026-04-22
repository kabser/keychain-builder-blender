# Keychain Maker v1.1.2

> 🇷🇺 [Русская версия ниже](#-что-нового-в-версии-120)

---

## 🆕 What's New in v1.1.2

---

### 🥚 Oval Hole

A new **Oval Hole** checkbox in the Ear section makes the key ring hole oval instead of round. When enabled, the hole expands along the Y axis so that the distance from each Y-edge of the hole to the nearest ear edge equals the **Hole Edge Margin** value. The X size stays equal to **Hole Diameter** — only the height changes.

This is useful when the ear is tall and you want the hole to fill it more naturally, reducing unnecessary material and improving aesthetics.

The oval option is ignored if the resulting Y radius would be smaller than or equal to the circle radius (the ear is too narrow to benefit).

---

### 🔄 Smart Rebuild

Pressing **Create Keychain** a second time no longer stacks a new model on top of the existing one.

- **Same text and font** → the existing keychain is deleted and rebuilt in place with the updated parameters. The viewport stays clean.
- **Text or font changed** → a new keychain is created alongside the existing one, so you can compare or keep both.

The addon tracks the last-created keychain automatically — no manual cleanup needed.

---

## 📦 Files in This Release

| File | Description |
|------|-------------|
| `Keychain_Builder_for_Blender.py` | The add-on. Install via Edit → Preferences → Add-ons → Install |
| `keychain_maker_manual.docx` | User manual (English + Russian) |

---

## ⚙️ Requirements

- Blender **4.0** or newer

---

## 🔗 Links

- 📣 Telegram: [t.me/keychain_for_you](https://t.me/keychain_for_you)
- ⭐ Support on Boosty: [boosty.to/keychain](https://boosty.to/keychain)

---
---

## 🆕 Что нового в версии 1.1.2

---

### 🥚 Овальное отверстие

Новый чекбокс **Oval Hole** в секции ушка делает отверстие под кольцо овальным вместо круглого. При включении отверстие расширяется по оси Y так, чтобы расстояние от каждого края отверстия по Y до ближайшего края ушка равнялось значению **Hole Edge Margin**. Размер по оси X остаётся равным **Hole Diameter** — меняется только высота.

Удобно, когда ушко высокое и хочется, чтобы отверстие заполняло его естественнее — меньше лишнего материала, лучше эстетика.

Параметр игнорируется, если расчётный радиус по Y окажется меньше или равен радиусу круга (ушко слишком узкое).

---

### 🔄 Умная пересборка

Повторное нажатие **Create Keychain** больше не создаёт новую модель поверх существующей.

- **Текст и шрифт не изменились** → существующий брелок удаляется и пересобирается на том же месте с обновлёнными параметрами. Сцена остаётся чистой.
- **Текст или шрифт изменились** → новый брелок создаётся рядом со старым, чтобы можно было сравнить или оставить оба.

Аддон автоматически запоминает последний созданный объект — никакой ручной очистки не нужно.

---

## 📦 Файлы релиза

| Файл | Описание |
|------|----------|
| `Keychain_Builder_for_Blender.py` | Аддон. Установка через Edit → Preferences → Add-ons → Install |
| `keychain_maker_manual.docx` | Руководство пользователя (английский + русский) |

---

## ⚙️ Требования

- Blender **4.0** или новее

---

## 🔗 Ссылки

- 📣 Telegram: [t.me/keychain_for_you](https://t.me/keychain_for_you)
- ⭐ Поддержать на Boosty: [boosty.to/keychain](https://boosty.to/keychain)

---
---

# Keychain Maker v1.1.0

> 🇷🇺 [Русская версия ниже](#-что-нового-в-версии-110)

---

## 🆕 What's New in v1.1.0

This is a major update with a fully rewritten base generation algorithm, a new ear system, and a bilingual interface.

---

### 🔷 Base Shape — New Algorithm

The base is now generated using a **metaball method**: metaballs are placed along the letter edges, merged into a single shape, and the outline is extracted. This produces a smooth, organic base that closely follows the letter contours — no more jagged or angular edges.

---

### 🔗 Ear (Key Ring Lug) — Full Rework

The ear is now fully integrated into the base geometry before extrusion, giving a clean seamless weld with no visible joint.

- **Left or Right** side placement
- **Chamfer** on outer vertical edges with configurable number of segments (1 = flat 45°, 4–8 = smooth curve)
- **Y Offset** — shift the ear up or down relative to the base centre for better aesthetics
- **Hole diameter** is configurable; the hole is automatically positioned 2 mm from the outer edge

---

### ✏️ Character Spacing Control

New **Char Spacing** parameter lets you tighten or expand the space between characters. Useful for long names or decorative fonts.

---

### 🌐 Bilingual Interface — English & Russian

The entire interface — parameter names, tooltips, buttons, error messages — is now available in both **English** and **Russian**. The language switches automatically with the Blender interface language setting (**Preferences → Interface → Translation**).

---

### ✨ Shade Auto Smooth

Shade Auto Smooth (30°) is applied to the finished model automatically. No manual post-processing needed.

---

### 🔄 Reset Settings Button

A new **Reset Settings** button at the bottom of the panel restores all parameters to their default values in one click.

---

## 📦 Files in This Release

| File | Description |
|------|-------------|
| `Keychain_Builder_for_Blender.py` | The add-on. Install via Edit → Preferences → Add-ons → Install |
| `keychain_maker_manual.docx` | User manual (English + Russian) |

---

## ⚙️ Requirements

- Blender **4.0** or newer

---

## 🔗 Links

- 📣 Telegram: [t.me/keychain_for_you](https://t.me/keychain_for_you)
- ⭐ Support on Boosty: [boosty.to/keychain](https://boosty.to/keychain)

---
---

## 🆕 Что нового в версии 1.1.0

Крупное обновление: полностью переписан алгоритм генерации подложки, переработана система ушка, добавлен двуязычный интерфейс.

---

### 🔷 Подложка — новый алгоритм

Подложка теперь генерируется методом **метабол**: шары расставляются вдоль рёбер букв, сливаются в единую форму, из которой извлекается контур. Это даёт гладкую органичную подложку, плотно повторяющую форму букв — никаких угловатых краёв.

---

### 🔗 Ушко — полная переработка

Ушко теперь полностью вшивается в геометрию подложки до экструзии, что даёт чистый бесшовный стык без видимого шва.

- Размещение **слева или справа**
- **Фаска** на внешних вертикальных рёбрах с настраиваемым числом сегментов (1 = прямая 45°, 4–8 = плавное скругление)
- **Смещение по Y** — сдвиг ушка вверх или вниз относительно центра подложки
- **Диаметр отверстия** настраивается; отверстие автоматически располагается в 2 мм от внешнего края

---

### ✏️ Управление расстоянием между символами

Новый параметр **Char Spacing** позволяет сжимать или расширять межсимвольный интервал. Удобно для длинных имён или декоративных шрифтов.

---

### 🌐 Двуязычный интерфейс — английский и русский

Весь интерфейс — названия параметров, подсказки, кнопки, сообщения об ошибках — теперь доступен на **английском** и **русском** языках. Язык переключается автоматически вместе с языком интерфейса Blender (**Preferences → Interface → Translation**).

---

### ✨ Shade Auto Smooth

Shade Auto Smooth (30°) применяется к готовой модели автоматически. Ручная постобработка не нужна.

---

### 🔄 Кнопка сброса настроек

Новая кнопка **Reset Settings** внизу панели возвращает все параметры к значениям по умолчанию одним нажатием.

---

## 📦 Файлы релиза

| Файл | Описание |
|------|----------|
| `Keychain_Builder_for_Blender.py` | Аддон. Установка через Edit → Preferences → Add-ons → Install |
| `keychain_maker_manual.docx` | Руководство пользователя (английский + русский) |

---

## ⚙️ Требования

- Blender **4.0** или новее

---

## 🔗 Ссылки

- 📣 Telegram: [t.me/keychain_for_you](https://t.me/keychain_for_you)
- ⭐ Поддержать на Boosty: [boosty.to/keychain](https://boosty.to/keychain)
