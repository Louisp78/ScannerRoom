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
  sharpest   per output frame, the sharpest source frame within +-SHARP_WINDOW s
             (variance of the Laplacian): fights motion blur.
  denoise    non-local means on each frame (spatial denoise).
  temporal   motion-compensated temporal median: the neighbouring source frames
             within +-TEMPORAL_WINDOW s are warped onto the output frame with
             dense optical flow, then the per-pixel median is kept. Removes
             sensor noise, suspended particles and part of the flickering
             caustics, which do not follow the reef's motion.
  clahe      gray-world white balance then CLAHE on lightness (LAB): the
             classical enhancement reported best for SfM (Vrochidis et al.,
             ISPRS 2025).
  funie      FUnIE-GAN (Islam et al. 2020), a GAN trained on paired underwater
             images to restore colour and contrast.
  fish       open-vocabulary detection of fish (OWLv2, "a photo of a fish"),
             boxes inpainted from their surroundings, so moving animals do not
             leave ghost geometry.
Variants can be chained with '+', applied left to right (e.g. temporal+clahe).
"""
import argparse
import json
import subprocess
import sys
from collections import deque
from pathlib import Path

import cv2
import numpy as np

LONG_SIDE = 1036
SHARP_WINDOW = 0.1  # seconds
TEMPORAL_WINDOW = 0.05  # seconds: +-3 frames at 60 fps
ROOT = Path(__file__).resolve().parent.parent


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


def sharpness(img: np.ndarray) -> float:
    return float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), cv2.CV_32F).var())


def gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


_dis = None


def warp_onto(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """src warped onto ref with dense optical flow (DIS), so the reef lines up."""
    global _dis
    _dis = _dis or cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow = _dis.calc(gray(ref), gray(src), None)
    h, w = ref.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(src, gx + flow[..., 0], gy + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def temporal_median(window: list[np.ndarray], centre: int) -> np.ndarray:
    ref = window[centre]
    stack = [ref] + [warp_onto(f, ref) for i, f in enumerate(window) if i != centre]
    return np.median(np.stack(stack), axis=0).astype(np.uint8)


def denoise(img: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)


def contrast(img: np.ndarray) -> np.ndarray:
    """CLAHE on lightness only (LAB), 8x8 tiles over the frame whatever its size.
    Hue is untouched, so the blue haze still reads as water."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def clahe(img: np.ndarray) -> np.ndarray:
    f = img.astype(np.float32)
    f *= f.reshape(-1, 3).mean() / f.reshape(-1, 3).mean(0)  # gray world
    return contrast(f.clip(0, 255).astype(np.uint8))


_rng = np.random.default_rng(0)  # reseeded from --seed in main()


def control(img: np.ndarray) -> np.ndarray:
    """+-1 grey level of noise: an invisible change, to measure how much the
    metrics move for reasons unrelated to image quality (noise floor)."""
    return (img.astype(np.int16) + _rng.integers(-1, 2, img.shape)).clip(0, 255).astype(np.uint8)


_funie = None


def funie(img: np.ndarray) -> np.ndarray:
    """FUnIE-GAN generator (fully convolutional U-Net, trained on 256x256 images).
    Run at half size, i.e. LingBot-Map's own input scale and closer to the
    training scale, padded to a multiple of 32, then resized back."""
    global _funie
    import torch
    if _funie is None:
        sys.path.insert(0, str(ROOT / "vendor/FUnIE-GAN/PyTorch"))
        from nets.funiegan import GeneratorFunieGAN
        _funie = GeneratorFunieGAN()
        _funie.load_state_dict(torch.load(ROOT / "vendor/FUnIE-GAN/PyTorch/models/funie_generator.pth",
                                          map_location="cpu"))
        _funie.eval()
    full_h, full_w = img.shape[:2]
    small = cv2.resize(img, (full_w // 2, full_h // 2), interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    ph, pw = -h % 32, -w % 32
    x = np.pad(small, ((0, ph), (0, pw), (0, 0)), mode="reflect").astype(np.float32) / 127.5 - 1
    with torch.no_grad():
        y = _funie(torch.from_numpy(x).permute(2, 0, 1)[None])[0].permute(1, 2, 0).numpy()
    y = ((y[:h, :w] + 1) * 127.5).clip(0, 255).astype(np.uint8)
    return cv2.resize(y, (full_w, full_h), interpolation=cv2.INTER_CUBIC)


_owl = None
fish_boxes_total = 0


def remove_fish(img: np.ndarray) -> np.ndarray:
    """Detect fish with OWLv2 and inpaint their (slightly enlarged) boxes."""
    global _owl, fish_boxes_total
    import torch
    from PIL import Image
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    if _owl is None:
        name = "google/owlv2-base-patch16-ensemble"
        _owl = Owlv2Processor.from_pretrained(name), Owlv2ForObjectDetection.from_pretrained(name).eval()
    proc, model = _owl
    h, w = img.shape[:2]
    inputs = proc(text=[["a photo of a fish"]], images=Image.fromarray(img), return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
    # OWLv2 pads the image to a square: boxes are relative to the padded side.
    side = max(h, w)
    res = proc.post_process_grounded_object_detection(out, threshold=0.2,
                                                      target_sizes=torch.tensor([[side, side]]))[0]
    mask = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in res["boxes"].numpy():
        # Fish are small next to a frame: anything over a tenth of it is a
        # false positive on reef or water.
        if (x1 - x0) * (y1 - y0) > 0.1 * h * w:
            continue
        mx, my = 0.15 * (x1 - x0), 0.15 * (y1 - y0)
        cv2.rectangle(mask, (int(x0 - mx), int(y0 - my)), (int(x1 + mx), int(y1 + my)), 255, -1)
        fish_boxes_total += 1
    return cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA) if mask.any() else img


FILTERS = {"baseline": lambda x: x, "control": control, "denoise": denoise, "contrast": contrast,
           "clahe": clahe, "funie": funie, "fish": remove_fish}
WINDOW_VARIANTS = {"sharpest", "temporal"}


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
    unknown = [s for s in steps if s not in FILTERS and s not in WINDOW_VARIANTS]
    if unknown:
        sys.exit(f"Unknown variant(s) {unknown}; known: {sorted([*FILTERS, *WINDOW_VARIANTS])}")
    # Window variants pick or merge source frames, so they must come first.
    window_steps = [s for s in steps if s in WINDOW_VARIANTS]
    if steps[:len(window_steps)] != window_steps or len(window_steps) > 1:
        sys.exit("sharpest / temporal must come first, and only one of them")

    src_fps, length, w, h = probe(args.video)
    half = {"sharpest": round(SHARP_WINDOW * src_fps), "temporal": round(TEMPORAL_WINDOW * src_fps)}.get(
        window_steps[0] if window_steps else "", 0)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()

    # Output frame k is the source frame closest to start + k / fps; keep a
    # rolling buffer of +-half source frames around it.
    step = src_fps / args.fps
    buf: deque = deque(maxlen=2 * half + 1)
    k, written = 0, 0
    for i, frame in enumerate(decode(args.video, args.start, args.duration)):
        buf.append(frame)
        centre = round(k * step)
        if i < centre + half:
            continue
        window = list(buf)
        c = len(window) - 1 - half
        if window_steps == ["sharpest"]:
            img = max(window, key=sharpness)
        elif window_steps == ["temporal"]:
            img = temporal_median(window, c)
        else:
            img = window[c]
        for s in steps[len(window_steps):]:
            img = FILTERS[s](img)
        written += 1
        cv2.imwrite(str(out / f"frame_{written:04d}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 95])
        k += 1
    meta = {"video": Path(args.video).name, "fps": args.fps, "start": args.start, "length": length,
            "portrait": h > w, "variant": args.variant, "seed": args.seed}
    if "fish" in steps:
        meta["fishBoxes"] = fish_boxes_total
    Path(f"{out}.json").write_text(json.dumps(meta) + "\n")
    print(f"{written} frames ({args.variant}) -> {out}" + (f", {fish_boxes_total} fish boxes" if "fish" in steps else ""))


if __name__ == "__main__":
    main()
