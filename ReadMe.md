# Offerte Vergelijker
Deze applicatie vergelijkt offertes ingevuld in een Excel template m.b.v. BM25Okapi en een Sentence Embedding Model.

## Builden App

```bash
  uv run pyinstaller --noconfirm --onedir --windowed --icon "assets/icon.ico" --name "Offertevergelijker" --add-data "models;models" --add-data "assets;assets" --hidden-import "PySide6.QtNetwork" --exclude-module "tkinter" --exclude-module "PyQt5" --exclude-module "PyQt6" src/app.py
```