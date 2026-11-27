"""Extract frames from a transect video excerpt, applying one pre-processing variant.

Usage: preprocess.py <video> <out-frame-dir> <variant> [--start 0] [--duration 20] [--fps 3]

Writes <out-frame-dir>/frame_NNNN.jpg plus <out-frame-dir>.json, the same sidecar
02-extract-frames.sh writes, so reconstruct.py and export-web.py run unchanged.

The video is decoded once at full temporal rate (every source frame), downscaled
to LONG_SIDE px: twice LingBot-Map's 518 px input, so the model's own resize
still averages the remaining noise while filters work on enough detail. Every
variant, baseline included, goes through this same decode so only the filter
differs between runs. Each variant is generic: no per-video parameter, sizes are
relative to the frame or expressed in seconds of video.

Variants:
  baseline   no filter (the current pipeline, at LONG_SIDE px)
  control    +-1 grey level of random noise: invisible, measures the noise
             floor of the metrics (how much they move for no real reason)
  contrast   CLAHE on lightness only: local contrast without touching hue.
Variants can be chained with '+', applied left to right (e.g. contrast+control).

Round 1 also tried motion-blur picking, spatial and temporal denoising, white
balance, an underwater GAN and fish inpainting: none helped (see the README),
so they were removed; git history has them.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

LONG_SIDE = 1036


def probe(video: str) -> tuple[float, float, int, int]:
    """Frame rate, length (s), and the displayed (rotation applied) width/height."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate,width,height:stream_side_data=rotation:format=duration",
         "-of", "json", video], capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    s = info["streams"][0]
    num, den = map(int, s["r_frame_rate"].split("/"))
    w, h = s["width"], s["height"]
    rot = next((abs(int(d.get("rotation", 0))) for d in s.get("side_data_list", []) if "rotation" in d), 0)
    if rot in (90, 270):
        w, h = h, w
    return num / den, float(info["format"]["duration"]), w, h


def decode(video: str, start: float, duration: float):
    """Yield every source frame of the excerpt as uint8 RGB, long side LONG_SIDE px."""
    _, _, w, h = probe(video)
    s = LONG_SIDE / max(w, h)
    ow, oh = int(round(w * s / 2) * 2), int(round(h * s / 2) * 2)
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration), "-i", video,
         "-vf", f"scale={ow}:{oh}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    size = ow * oh * 3
    while (buf := proc.stdout.read(size)) and len(buf) == size:
        yield np.frombuffer(buf, np.uint8).reshape(oh, ow, 3)
    proc.wait()


def contrast(img: np.ndarray) -> np.ndarray:
    """CLAHE on lightness only (LAB), 8x8 tiles over the frame whatever its size.
    Hue is untouched, so the blue haze still reads as water."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


_rng = np.random.default_rng(0)  # reseeded from --seed in main()


def control(img: np.ndarray) -> np.ndarray:
    """+-1 grey level of noise: an invisible change, to measure how much the
    metrics move for reasons unrelated to image quality (noise floor)."""
    return (img.astype(np.int16) + _rng.integers(-1, 2, img.shape)).clip(0, 255).astype(np.uint8)


FILTERS = {"baseline": lambda x: x, "control": control, "contrast": contrast}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("variant")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--duration", type=float, default=20)
    ap.add_argument("--fps", type=float, default=3)
    # Seed of the control noise: repeat a variant with +control and several
    # seeds to tell a real effect from the model's sensitivity to tiny changes.
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    global _rng
    _rng = np.random.default_rng(args.seed)

    steps = args.variant.split("+")
    unknown = [s for s in steps if s not in FILTERS]
    if unknown:
        sys.exit(f"Unknown variant(s) {unknown}; known: {sorted(FILTERS)}")

    src_fps, length, w, h = probe(args.video)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()

    # Output frame k is the source frame closest to start + k / fps.
    step = src_fps / args.fps
    k, written = 0, 0
    for i, frame in enumerate(decode(args.video, args.start, args.duration)):
        if i < round(k * step):
            continue
        img = frame
        for s in steps:
            img = FILTERS[s](img)
        written += 1
        cv2.imwrite(str(out / f"frame_{written:04d}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 95])
        k += 1
    meta = {"video": Path(args.video).name, "fps": args.fps, "start": args.start, "length": length,
            "portrait": h > w, "variant": args.variant, "seed": args.seed}
    Path(f"{out}.json").write_text(json.dumps(meta) + "\n")
    print(f"{written} frames ({args.variant}) -> {out}")


if __name__ == "__main__":
    main()
