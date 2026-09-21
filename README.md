# Mini Radio Player

Мини-радиоплеер для Windows на Python + PySide6. Работает в фоне, сворачивается в системный трей и умеет автоматически включать/выключать поток по расписанию.

## Возможности

- Воспроизведение потокового URL (по умолчанию `https://stream.ipdj.ru/listen/cafe/radio.mp3`)
- Play / Stop с плавным изменением громкости
- Регулировка громкости
- Работа в системном трее
- Автовоспроизведение по расписанию, включая интервалы через полночь
- Повторная попытка подключения после ошибки потока
- Опция запуска свернутым
- Сохранение настроек в `%APPDATA%/MiniRadioPlayer/settings.json`

## Запуск из исходников

Требуется Python 3.8+.

```bash
pip install -r requirements.txt
python main.py
```

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
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm --noconsole --onefile --name MiniRadioPlayer main.py
```

Готовый файл появится в `dist/MiniRadioPlayer.exe`.

## Сборка через GitHub Actions

Workflow `.github/workflows/build-exe.yml` запускается:

- автоматически при изменениях `main.py`, `requirements.txt`, `build.bat` или самого workflow в ветке `main`;
- вручную через **Actions → Build Windows EXE → Run workflow**.

После успешной сборки скачайте artifact `MiniRadioPlayer-windows` со страницы запуска workflow.
