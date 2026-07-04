# Brother PES Web Converter

A small local web app that turns simple artwork into Brother-compatible `.pes`
embroidery files.

This is intended for logos, icons, and high-contrast illustrations. Photos and
very detailed images need manual cleanup in dedicated embroidery software.

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Deploy

This is a Python web app, so GitHub Pages cannot run it directly. Deploy it to a
Python-capable host such as Render:

1. Open Render and create a new Web Service.
2. Connect this GitHub repository.
3. Use the included `render.yaml`, or set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `HOST=0.0.0.0 python server.py`
4. After deploy, Render will provide a public `https://...onrender.com` URL.

## Notes

- Input: PNG, JPG/JPEG, WebP, BMP, GIF.
- Output: PES, written with `pyembroidery`.
- The converter creates a simple horizontal fill stitch plan per color.
- Keep source art simple and remove backgrounds before converting for best
  results.
