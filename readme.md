# Hello from Julieta

A minimal Flask 3 web app. It serves a single page at `/` that says "Hello from Julieta".

## Install

Requires Python 3.9 or newer.

```bash
python -m venv .venv
```

Windows (Git Bash):

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## Run

Windows (Git Bash):

```bash
.venv/Scripts/python app.py
```

macOS / Linux:

```bash
.venv/bin/python app.py
```

Then open http://127.0.0.1:5000/ in your browser. Press Ctrl+C to stop the server.

The app runs in debug mode, which is for local development only. Turn it off before you deploy.
