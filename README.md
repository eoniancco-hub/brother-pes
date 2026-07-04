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

## Notes

- Input: PNG, JPG/JPEG, WebP, BMP, GIF.
- Output: PES, written with `pyembroidery`.
- The converter creates a simple horizontal fill stitch plan per color.
- Keep source art simple and remove backgrounds before converting for best
  results.
