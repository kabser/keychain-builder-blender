# Keychain Maker for Blender

**by Sergey Kabanov (@kabser)**

> 🇷🇺 [Русская версия ниже](#keychain-maker-для-blender)

---

Generate 3D-printable personalised keychains in one click directly inside Blender.  
Type your text, pick a font, press **Create Keychain** — get a ready-to-print model.

![Keychains with names](https://raw.githubusercontent.com/kabser/keychain-builder-blender/main/images/Names.png)
![Keychains with phone numbers](https://raw.githubusercontent.com/kabser/keychain-builder-blender/main/images/Number_phone.png)
![Keychains with game themes](https://raw.githubusercontent.com/kabser/keychain-builder-blender/main/images/Games.png)

---

## Features

- Any text, any TTF/OTF font — including Cyrillic and any language
- Smooth base shape that automatically follows letter outlines (metaball method)
- Side ear with a round or oval hole for the key ring — left or right side
- Adjustable chamfer with configurable number of segments
- Adjustable ear Y-offset for better aesthetics
- Character spacing control
- **Smart Rebuild** — changing parameters and pressing Create updates the existing keychain; only a text or font change creates a new one
- Shade Auto Smooth applied automatically
- Full bilingual interface: English and Russian (switches with Blender language settings)
- Reset to defaults button
- Works with Blender 4.0 and newer

---

## Installation

1. Download `keychain_maker.py`
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the downloaded file and enable the addon
4. Open the **N-panel** in the 3D Viewport (press `N`) → tab **Keychain 1.1**

---

## Quick Start

1. Type your text in the **Text** field
2. Click the **Font (.ttf)** field to select a font file (TTF or OTF), or leave empty for the Blender default font
3. Adjust **Base Offset**, **Base Height** and **Letter Height** to taste
4. If you want an ear, enable **Add Ear**, choose the side and configure its dimensions
5. Press **Create Keychain**
6. Tweak any parameter and press **Create Keychain** again — the existing model is rebuilt in place (text and font changes create a new model instead)
7. Export via **File → Export → STL (.stl)** with **Selection Only** checked

---

## Parameters

### Text

| Parameter | Description |
|-----------|-------------|
| Text | The inscription on the keychain. Supports any language. |
| Font (.ttf) | Path to a TTF/OTF font file. Leave empty for Blender default. |
| Char Spacing | Character spacing multiplier. 1.0 = default, below 1.0 = tighter. |

### Base

| Parameter | Description |
|-----------|-------------|
| Base Offset (mm) | How far the base extends beyond the letter outlines. Recommended: 2–5 mm. |
| Base Height (mm) | Thickness of the base plate. Recommended: 2–5 mm. |
| Letter Height (mm) | How much letters protrude above the base. Recommended: 1.5–3 mm. |

### Ear

| Parameter | Description |
|-----------|-------------|
| Add Ear | Enable/disable the key ring ear. |
| Ear Side | Left or Right. |
| Ear Length X (mm) | Ear depth away from the base. Recommended: 6–12 mm. |
| Ear Width Y (mm) | Ear height. Recommended: 6–12 mm. |
| Chamfer (mm) | Rounding on outer vertical edges. 0 = no chamfer. |
| Chamfer Segments | 1 = flat 45° chamfer, 4–8 = smooth curve. |
| Y Offset (mm) | Shifts the ear up/down relative to the base centre. |
| Hole Diameter (mm) | Key ring hole diameter. Recommended: 2–4 mm. |
| Hole Edge Margin (mm) | Distance from the hole edge to the outer ear edge. Also controls oval height when Oval Hole is on. |
| Oval Hole | Expands the hole along Y so both Y-edges of the hole are exactly **Hole Edge Margin** away from the ear edges. X size stays equal to Hole Diameter. |

---

## Default Values

| Parameter | Default |
|-----------|---------|
| Base Offset | 2.0 mm |
| Base Height | 3.0 mm |
| Letter Height | 2.0 mm |
| Ear Side | Left |
| Ear Length X | 6.0 mm |
| Ear Width Y | 6.0 mm |
| Chamfer | 1.5 mm |
| Chamfer Segments | 4 |
| Hole Diameter | 2.0 mm |
| Hole Edge Margin | 2.0 mm |
| Oval Hole | Off |

---

## Requirements

- Blender **4.0** or newer
- Any TTF or OTF font file (optional — Blender default font works too)

---

## Support the Project

If this addon saves you time, consider supporting development ☕

- 🌍 International: [Gumroad](https://gumroad.com/YOUR_LINK_HERE) ← *temporarily inactive*
- 🇷🇺 Russia / СНГ: [Boosty](https://boosty.to/keychain)

Your support helps keep the addon growing.

---

## Feedback & Ideas

Found a bug or have a suggestion?

- 💬 Open an [Issue](https://github.com/kabser/keychain-builder-blender/issues) on GitHub
- 📣 Telegram channel: [t.me/keychain_for_you](https://t.me/keychain_for_you)

---

## License

GNU GPL v3 — see [LICENSE](LICENSE)

---
---

# Keychain Maker для Blender

**Автор: Sergey Kabanov (@kabser)**

Генерируй персонализированные брелоки для 3D-печати прямо в Blender, в один клик.  
Введи текст, выбери шрифт, нажми **Create Keychain** — получи готовую модель.

---

## Возможности

- Любой текст, любой шрифт TTF/OTF — включая кириллицу и любые языки
- Гладкое основание, которое автоматически повторяет контур букв (метод метабол)
- Боковое ушко с круглым или овальным отверстием под кольцо — слева или справа
- Настраиваемая фаска с регулируемым количеством сегментов
- Смещение ушка по оси Y для эстетической корректировки
- Управление расстоянием между символами
- **Умная пересборка** — при изменении параметров и нажатии Create брелок пересобирается на месте; новый создаётся только при изменении текста или шрифта
- Shade Auto Smooth применяется автоматически
- Полностью двуязычный интерфейс: английский и русский (переключается вместе с языком Blender)
- Кнопка сброса всех настроек
- Работает с Blender 4.0 и новее

---

## Установка

1. Скачай файл `keychain_maker.py`
2. В Blender: **Edit → Preferences → Add-ons → Install**
3. Выбери скачанный файл и включи аддон
4. Открой **N-панель** в 3D Viewport (клавиша `N`) → вкладка **Keychain 1.1**

---

## Быстрый старт

1. Введи текст в поле **Text**
2. Укажи путь к шрифту в поле **Font (.ttf)** (TTF или OTF), или оставь пустым для стандартного шрифта Blender
3. Настрой **Base Offset**, **Base Height** и **Letter Height** по вкусу
4. Если нужно ушко — включи **Add Ear**, выбери сторону и настрой параметры
5. Нажми **Create Keychain**
6. Измени любой параметр и нажми **Create Keychain** снова — существующая модель пересобирается на месте (изменение текста или шрифта создаёт новую модель)
7. Экспортируй через **File → Export → STL (.stl)** с включённым **Selection Only**

---

## Параметры

### Text (Надпись)

| Параметр | Описание |
|----------|----------|
| Text | Надпись на брелоке. Поддерживается любой язык. |
| Font (.ttf) | Путь к файлу шрифта TTF/OTF. Оставь пустым для шрифта по умолчанию. |
| Char Spacing | Межсимвольный интервал. 1.0 = стандартный, меньше = теснее. |

### Base (Подложка)

| Параметр | Описание |
|----------|----------|
| Base Offset (mm) | Насколько подложка выступает за контур букв. Рекомендуется: 2–5 мм. |
| Base Height (mm) | Толщина подложки. Рекомендуется: 2–5 мм. |
| Letter Height (mm) | На сколько буквы выступают над подложкой. Рекомендуется: 1.5–3 мм. |

### Ear (Ушко)

| Параметр | Описание |
|----------|----------|
| Add Ear | Включить/выключить ушко. |
| Ear Side | Слева или справа. |
| Ear Length X (mm) | Глубина ушка от подложки. Рекомендуется: 6–12 мм. |
| Ear Width Y (mm) | Высота ушка. Рекомендуется: 6–12 мм. |
| Chamfer (mm) | Скругление внешних вертикальных рёбер. 0 = без скругления. |
| Chamfer Segments | 1 = плоская фаска 45°, 4–8 = плавное скругление. |
| Y Offset (mm) | Смещение ушка вверх/вниз относительно центра подложки. |
| Hole Diameter (mm) | Диаметр отверстия для кольца. Рекомендуется: 2–4 мм. |
| Hole Edge Margin (mm) | Расстояние от края отверстия до внешнего края ушка. При включённом Oval Hole задаёт также отступ по оси Y. |
| Oval Hole | Расширяет отверстие по оси Y так, чтобы расстояние от его краёв до краёв ушка равнялось значению **Hole Edge Margin**. По оси X размер не меняется. |

---

## Значения по умолчанию

| Параметр | Значение |
|----------|----------|
| Base Offset | 2.0 мм |
| Base Height | 3.0 мм |
| Letter Height | 2.0 мм |
| Ear Side | Слева |
| Ear Length X | 6.0 мм |
| Ear Width Y | 6.0 мм |
| Chamfer | 1.5 мм |
| Chamfer Segments | 4 |
| Hole Diameter | 2.0 мм |
| Hole Edge Margin | 2.0 мм |
| Oval Hole | Выкл |

---

## Требования

- Blender **4.0** или новее
- Любой шрифт в формате TTF или OTF (необязательно — стандартный шрифт Blender тоже работает)

---

## Поддержать проект

Если аддон оказался полезным — поддержи разработку ☕

- 🌍 Международные карты: [Gumroad](https://gumroad.com/YOUR_LINK_HERE) ← *временно не активно*
- 🇷🇺 Россия / СНГ: [Boosty](https://boosty.to/keychain)

Это помогает развивать аддон дальше.

---

## Обратная связь

Нашёл баг или есть идея для улучшения?

- 💬 Открой [Issue](https://github.com/kabser/keychain-builder-blender/issues) на GitHub
- 📣 Telegram-канал: [t.me/keychain_for_you](https://t.me/keychain_for_you)

---

## Лицензия

GNU GPL v3 — см. [LICENSE](LICENSE)
