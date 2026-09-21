# Mini Radio Player

Мини-радиоплеер для Windows на Python + PySide6. Работает в фоне, сворачивается в системный трей и умеет автоматически включать/выключать поток по расписанию.

## Возможности

- Быстрый выбор одной из встроенных станций IPDJ или собственного URL
- Воспроизведение потокового URL (по умолчанию `https://stream.ipdj.ru/listen/cafe/radio.mp3`)
- Play / Stop с плавным изменением громкости
- Регулировка громкости
- Работа в системном трее: сворачивание и закрытие окна полностью убирают его с панели задач
- Фирменная иконка в окне, трее и собранном EXE
- Тёмная системная строка заголовка Windows
- Автовоспроизведение по расписанию, включая интервалы через полночь
- Повторная попытка подключения после ошибки потока
- Опция запуска свернутым
- Сохранение настроек в `%APPDATA%/MiniRadioPlayer/settings.json`

## Запуск из исходников

Требуется Python 3.10+.

```bash
pip install -r requirements.txt
python main.py
```

## Встроенные станции

В интерфейсе доступен выпадающий список:

- **Cafe — Soulful House** — `https://stream.ipdj.ru/listen/cafe/radio.mp3`
- **Restaurant — Lounge** — `https://stream.ipdj.ru/listen/restouran/radio.mp3`
- **Beer Restaurant — Jazz & Blues** — `https://stream.ipdj.ru/listen/pivrest/radio.mp3`
- **Bar — Rock & Grunge** — `https://stream.ipdj.ru/listen/bar/radio.mp3`
- **Barbershop — Rap & Bass House** — `https://stream.ipdj.ru/listen/barber/radio.mp3`
- **Custom URL** — позволяет ввести любой совместимый поток вручную.

При выборе встроенной станции её URL подставляется автоматически. Если воспроизведение уже запущено, поток переключается сразу.

## Настройки

Настройки сохраняются автоматически в `%APPDATA%/MiniRadioPlayer/settings.json`.

- `stream_url` — URL аудиопотока
- `start_time` — начало автоматического воспроизведения (`HH:MM`)
- `end_time` — окончание автоматического воспроизведения (`HH:MM`)
- `volume` — громкость (`0.0`–`1.0`)
- `start_minimized` — запуск в свернутом виде (`true`/`false`)

Если `start_time == end_time`, расписание считается отключенным.

## Сборка EXE локально

На Windows запустите:

```bat
build.bat
```

Или вручную:

```bash
python -m pip install -r requirements.txt pyinstaller pillow
python build_icon.py
python -m PyInstaller --clean --noconfirm --noconsole --onefile --name MiniRadioPlayer --icon assets/MiniRadioPlayer.ico --add-data "assets/MiniRadioPlayer.svg;assets" main.py
```

Готовый файл появится в `dist/MiniRadioPlayer.exe`. Исходник иконки хранится в `assets/MiniRadioPlayer.svg`; `build_icon.py` генерирует Windows ICO перед сборкой.

## GitHub Actions и Releases

Workflow `.github/workflows/build-exe.yml`:

- автоматически собирает EXE при изменениях приложения в ветке `main`;
- может запускаться вручную через **Actions → Build Windows EXE → Run workflow**;
- при push тега вида `v*` собирает EXE, создаёт GitHub Release, генерирует release notes и прикрепляет `MiniRadioPlayer.exe`;
- после обычной сборки сохраняет EXE как artifact `MiniRadioPlayer-windows` на 14 дней.

Для публикации новой версии:

```bash
git tag v1.0.0
git push origin v1.0.0
```

После успешного workflow релиз `v1.0.0` появится в разделе **Releases** с прикреплённым `MiniRadioPlayer.exe`.
