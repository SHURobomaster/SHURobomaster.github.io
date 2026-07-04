#!/usr/bin/env python3
"""Convert the SRM SolidWorks reference into a web-ready point cloud asset.

SolidWorks SLDPRT is proprietary. This script first scans the binary for
embedded preview images. If no extractable preview is present, it creates a
deterministic vehicle-shaped point cloud for browser rendering and records the
native-geometry limitation in metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_largest_embedded_preview(data: bytes, out_dir: Path) -> dict | None:
    for stale in out_dir.glob("sldprt-preview.*"):
        stale.unlink()

    candidates: list[tuple[int, int, str]] = []

    start = 0
    while True:
        begin = data.find(b"\xff\xd8", start)
        if begin < 0:
            break
        end = data.find(b"\xff\xd9", begin + 2)
        if end < 0:
            break
        end += 2
        if end - begin > 4096:
            candidates.append((begin, end, "jpg"))
        start = end

    png_sig = b"\x89PNG\r\n\x1a\n"
    start = 0
    while True:
        begin = data.find(png_sig, start)
        if begin < 0:
            break
        end = data.find(b"IEND", begin + len(png_sig))
        if end < 0:
            break
        end += 8
        if end - begin > 4096:
            candidates.append((begin, end, "png"))
        start = end

    valid: list[tuple[int, int, str, tuple[int, int]]] = []
    for begin, end, suffix in candidates:
        chunk = data[begin:end]
        try:
            with Image.open(BytesIO(chunk)) as image:
                image.verify()
            with Image.open(BytesIO(chunk)) as image:
                width, height = image.size
            if width >= 64 and height >= 64:
                valid.append((begin, end, suffix, (width, height)))
        except (UnidentifiedImageError, OSError, ValueError):
            continue

    if not valid:
        return None

    begin, end, suffix, size = max(valid, key=lambda item: item[1] - item[0])
    out_path = out_dir / f"sldprt-preview.{suffix}"
    out_path.write_bytes(data[begin:end])
    return {
        "path": str(out_path),
        "bytes": end - begin,
        "offset": begin,
        "kind": suffix,
        "width": size[0],
        "height": size[1],
    }


def add_box(points: list[list[float]], rng: random.Random, center, size, count, component) -> None:
    cx, cy, cz = center
    sx, sy, sz = size
    faces = [
        (0, sx / 2), (0, -sx / 2),
        (1, sy / 2), (1, -sy / 2),
        (2, sz / 2), (2, -sz / 2),
    ]
    for _ in range(count):
        axis, value = rng.choice(faces)
        x = (rng.random() - 0.5) * sx
        y = (rng.random() - 0.5) * sy
        z = (rng.random() - 0.5) * sz
        if axis == 0:
            x = value
        elif axis == 1:
            y = value
        else:
          z = value
        jitter = 0.015
        points.append([
            round(cx + x + rng.uniform(-jitter, jitter), 4),
            round(cy + y + rng.uniform(-jitter, jitter), 4),
            round(cz + z + rng.uniform(-jitter, jitter), 4),
            component,
        ])


def add_cylinder_x(points: list[list[float]], rng: random.Random, center, length, radius, count, component) -> None:
    cx, cy, cz = center
    for _ in range(count):
        theta = rng.random() * math.tau
        x = (rng.random() - 0.5) * length
        y = math.cos(theta) * radius
        z = math.sin(theta) * radius
        points.append([
            round(cx + x, 4),
            round(cy + y, 4),
            round(cz + z, 4),
            component,
        ])


def add_cylinder_z(points: list[list[float]], rng: random.Random, center, depth, radius, count, component) -> None:
    cx, cy, cz = center
    for _ in range(count):
        theta = rng.random() * math.tau
        z = (rng.random() - 0.5) * depth
        x = math.cos(theta) * radius
        y = math.sin(theta) * radius
        points.append([
            round(cx + x, 4),
            round(cy + y, 4),
            round(cz + z, 4),
            component,
        ])


def generate_vehicle_point_cloud(seed_hex: str) -> list[list[float]]:
    rng = random.Random(int(seed_hex[:16], 16))
    points: list[list[float]] = []

    add_box(points, rng, center=(0, 0, 0), size=(4.4, 0.62, 2.35), count=2400, component=0)
    add_box(points, rng, center=(0.12, 0.52, 0), size=(3.36, 0.28, 1.58), count=1300, component=1)
    add_box(points, rng, center=(0.46, 1.02, 0), size=(1.28, 0.74, 1.14), count=1000, component=2)
    add_cylinder_x(points, rng, center=(1.75, 1.04, 0), length=2.42, radius=0.17, count=760, component=3)
    add_box(points, rng, center=(-1.56, 0.9, 0.96), size=(0.3, 1.16, 0.12), count=480, component=4)
    add_box(points, rng, center=(-1.56, 0.9, -0.96), size=(0.3, 1.16, 0.12), count=480, component=4)
    add_box(points, rng, center=(1.18, -0.05, 0), size=(0.26, 0.13, 2.9), count=360, component=5)

    for wheel_x in (-1.55, 1.55):
        for wheel_z in (-1.28, 1.28):
            add_cylinder_z(points, rng, center=(wheel_x, -0.42, wheel_z), depth=0.42, radius=0.48, count=720, component=6)

    for _ in range(700):
        x = rng.uniform(-2.25, 2.25)
        z = rng.uniform(-1.34, 1.34)
        y = -0.76 + rng.uniform(-0.01, 0.01)
        points.append([round(x, 4), round(y, 4), round(z, 4), 7])

    return points


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--asset-dir", default=Path("assets"), type=Path)
    args = parser.parse_args()

    source = args.input
    asset_dir = args.asset_dir
    asset_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    data = source.read_bytes()
    digest = sha256_file(source)
    preview = extract_largest_embedded_preview(data, asset_dir)
    points = generate_vehicle_point_cloud(digest)

    payload = {
        "schema": "srm.vehicle.pointcloud.v1",
        "source": {
            "file": source.name,
            "bytes": source.stat().st_size,
            "sha256": digest,
            "nativeGeometryRead": False,
            "note": "SLDPRT native B-rep geometry was not readable in this environment; point cloud is a deterministic web visualization envelope generated from the CAD reference file metadata.",
        },
        "preview": preview,
        "units": "arbitrary_web_units",
        "components": [
            "底盘",
            "上层板",
            "云台",
            "发射管",
            "侧向装甲",
            "灯条",
            "轮组",
            "地面扫描面",
        ],
        "points": points,
    }
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    args.output.write_text(compact, encoding="utf-8")
    js_output = args.output.with_suffix(".js")
    js_output.write_text(f"window.SRM_VEHICLE_POINT_CLOUD={compact};\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "jsOutput": str(js_output),
        "points": len(points),
        "previewExtracted": bool(preview),
        "sha256": digest[:16],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
