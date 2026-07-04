from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from PIL import Image


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


@dataclass(frozen=True)
class ConvertOptions:
    max_width_mm: float = 90.0
    colors: int = 5
    row_spacing_mm: float = 1.4
    stitch_length_mm: float = 2.6
    alpha_threshold: int = 32


@dataclass(frozen=True)
class ThreadPlan:
    rgb: Tuple[int, int, int]
    segments: List[List[Tuple[float, float]]]


def convert_image_to_pes(
    image_bytes: bytes,
    filename: str,
    options: ConvertOptions,
) -> bytes:
    _validate_filename(filename)
    image = Image.open(BytesIO(image_bytes))
    plans, design_name = _build_thread_plans(image, filename, options)
    return _write_pes(plans, design_name)


def _validate_filename(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type. Use one of: {allowed}.")


def _build_thread_plans(
    image: Image.Image,
    filename: str,
    options: ConvertOptions,
) -> Tuple[List[ThreadPlan], str]:
    if options.max_width_mm < 10 or options.max_width_mm > 180:
        raise ValueError("Max width must be between 10 mm and 180 mm.")
    if options.colors < 1 or options.colors > 12:
        raise ValueError("Colors must be between 1 and 12.")
    if options.row_spacing_mm < 0.8 or options.row_spacing_mm > 4.0:
        raise ValueError("Row spacing must be between 0.8 mm and 4.0 mm.")
    if options.stitch_length_mm < 1.0 or options.stitch_length_mm > 6.0:
        raise ValueError("Stitch length must be between 1.0 mm and 6.0 mm.")

    rgba = _trim_transparency(image.convert("RGBA"), options.alpha_threshold)
    resized, units_per_pixel = _resize_for_design(rgba, options.max_width_mm)
    alpha = resized.getchannel("A")

    opaque_rgb = Image.new("RGB", resized.size, "white")
    opaque_rgb.paste(resized.convert("RGB"), mask=alpha)
    quantized = opaque_rgb.quantize(colors=options.colors, method=Image.Quantize.MEDIANCUT)

    palette = quantized.getpalette() or []
    color_map: Dict[int, Tuple[int, int, int]] = {}
    for color_index in sorted(set(quantized.getdata())):
        base = color_index * 3
        color_map[color_index] = tuple(palette[base : base + 3])  # type: ignore[assignment]

    pixels = quantized.load()
    alpha_pixels = alpha.load()
    row_step_px = max(1, round((options.row_spacing_mm * 10) / units_per_pixel))
    stitch_step_units = options.stitch_length_mm * 10

    plans: List[ThreadPlan] = []
    for color_index, rgb in _sort_colors_by_coverage(quantized, alpha, color_map, options.alpha_threshold):
        segments: List[List[Tuple[float, float]]] = []
        reverse = False
        for y in range(0, quantized.height, row_step_px):
            runs = _find_color_runs(pixels, alpha_pixels, y, quantized.width, color_index, options.alpha_threshold)
            if reverse:
                runs = list(reversed(runs))
            for start_x, end_x in runs:
                points = _segment_points(
                    start_x,
                    end_x,
                    y,
                    units_per_pixel,
                    stitch_step_units,
                    reverse,
                )
                if len(points) >= 2:
                    segments.append(points)
            reverse = not reverse
        if segments:
            plans.append(ThreadPlan(rgb=rgb, segments=segments))

    if not plans:
        raise ValueError("No stitchable artwork was found. Try an image with visible opaque content.")

    design_name = Path(filename).stem[:8].upper() or "DESIGN"
    return plans, design_name


def _trim_transparency(image: Image.Image, alpha_threshold: int) -> Image.Image:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("The image is fully transparent.")
    return image.crop(box)


def _resize_for_design(image: Image.Image, max_width_mm: float) -> Tuple[Image.Image, float]:
    max_width_units = max_width_mm * 10
    units_per_pixel = max_width_units / image.width
    target_width_px = min(image.width, 360)
    target_height_px = max(1, round(image.height * (target_width_px / image.width)))
    if target_width_px != image.width:
        image = image.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
        units_per_pixel = max_width_units / target_width_px
    return image, units_per_pixel


def _sort_colors_by_coverage(
    quantized: Image.Image,
    alpha: Image.Image,
    color_map: Dict[int, Tuple[int, int, int]],
    alpha_threshold: int,
) -> Iterable[Tuple[int, Tuple[int, int, int]]]:
    counts: Dict[int, int] = {color_index: 0 for color_index in color_map}
    q_data = list(quantized.getdata())
    a_data = list(alpha.getdata())
    for color_index, alpha_value in zip(q_data, a_data):
        if alpha_value > alpha_threshold:
            counts[color_index] = counts.get(color_index, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    for color_index, count in ordered:
        if count:
            yield color_index, color_map[color_index]


def _find_color_runs(pixels, alpha_pixels, y: int, width: int, color_index: int, alpha_threshold: int) -> List[Tuple[int, int]]:
    runs: List[Tuple[int, int]] = []
    x = 0
    while x < width:
        while x < width and not (pixels[x, y] == color_index and alpha_pixels[x, y] > alpha_threshold):
            x += 1
        start = x
        while x < width and pixels[x, y] == color_index and alpha_pixels[x, y] > alpha_threshold:
            x += 1
        end = x - 1
        if end - start >= 1:
            runs.append((start, end))
    return runs


def _segment_points(
    start_x: int,
    end_x: int,
    y: int,
    units_per_pixel: float,
    stitch_step_units: float,
    reverse: bool,
) -> List[Tuple[float, float]]:
    x1 = start_x * units_per_pixel
    x2 = end_x * units_per_pixel
    y_units = y * units_per_pixel
    if reverse:
        x1, x2 = x2, x1
        step = -abs(stitch_step_units)
        keep_going = lambda current: current > x2
    else:
        step = abs(stitch_step_units)
        keep_going = lambda current: current < x2

    points = [(x1, y_units)]
    current = x1 + step
    while keep_going(current):
        points.append((current, y_units))
        current += step
    points.append((x2, y_units))
    return points


def _write_pes(plans: List[ThreadPlan], design_name: str) -> bytes:
    try:
        import pyembroidery
    except ImportError as exc:
        raise RuntimeError("pyembroidery is not installed. Run: pip install -r requirements.txt") from exc

    pattern = pyembroidery.EmbPattern()
    for plan in plans:
        thread = pyembroidery.EmbThread()
        thread.set_color(*plan.rgb)
        pattern.add_thread(thread)

    for plan_index, plan in enumerate(plans):
        if plan_index:
            pattern.add_command(pyembroidery.COLOR_CHANGE)
        for segment_index, points in enumerate(plan.segments):
            first_x, first_y = points[0]
            if segment_index:
                pattern.add_command(pyembroidery.TRIM)
                pattern.add_stitch_absolute(pyembroidery.JUMP, first_x, first_y)
            else:
                pattern.add_stitch_absolute(pyembroidery.JUMP, first_x, first_y)
            for x, y in points:
                pattern.add_stitch_absolute(pyembroidery.STITCH, x, y)

    pattern.add_command(pyembroidery.END)
    pattern.metadata("name", design_name)

    output = BytesIO()
    pyembroidery.write_pes(pattern, output)
    return output.getvalue()
