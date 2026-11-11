"""Run LingBot-Map (MLX port) on a frame folder and save what export-web.py reads.

Usage (from the port's folder, which resolves checkpoints/ relatively):
    reconstruct.py <frame-folder> <out.npz>

Same model, settings and streaming inference as the port's create_map.py, with
the memory kept bounded so a full-length transect (~1000 frames) fits on a
16-18 GB Mac without swapping:
- frames are loaded as uint8 and turned into float16 on the GPU (create_map.py
  goes through float32 lists, stacks and copies: ~7 GB at 1000 frames);
- MLX's buffer cache, which otherwise keeps every freed buffer (float32 weights
  at model creation, the image stack...), is capped;
- none of create_map.py's exports: it also unprojects every pixel with the
  wrong pose reading (see export-web.py) into "world_points" and writes them as
  a .ply, ~90 M points and ~5 GB that nothing downstream uses.
The archive holds images (uint8), depth, confidence and the camera parameters.
"""
import sys
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
from mlx.utils import tree_map
from PIL import Image, ImageOps

sys.path.insert(0, str(Path.cwd()))
from create_map import resolve_weight_file  # noqa: E402
from lingbot_map_mlx.load_weights import load_weights  # noqa: E402
from lingbot_map_mlx.models.gct_stream import GCTStream  # noqa: E402
from lingbot_map_mlx.utils.geometry import closed_form_inverse_se3_general  # noqa: E402
from lingbot_map_mlx.utils.pose_enc import pose_encoding_to_extri_intri  # noqa: E402

# The temporal positional embedding is precomputed for this many frames.
MAX_FRAMES = 1024
SCALE_FRAMES = 4
IMAGE_SIZE, PATCH = 518, 14


def load_frames(folder: str) -> np.ndarray:
    """Frames as uint8 (S, H, W, 3), resized like create_map.load_images: longest
    side 518 px, multiple of the 14 px patch, portrait frames turned clockwise."""
    paths = sorted(Path(folder).glob("*.jpg"))
    if not paths:
        sys.exit(f"No .jpg frame in {folder}")
    if len(paths) > MAX_FRAMES:
        sys.exit(f"{len(paths)} frames: LingBot-Map handles {MAX_FRAMES} at most, lower FPS.")
    w, h = ImageOps.exif_transpose(Image.open(paths[0])).size
    scale = IMAGE_SIZE / max(w, h)
    size = (int(max(w, h) * scale) // PATCH * PATCH, int(min(w, h) * scale) // PATCH * PATCH)
    frames = np.empty((len(paths), size[1], size[0], 3), np.uint8)
    for i, p in enumerate(paths):
        img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        if img.height > img.width:
            img = img.transpose(Image.ROTATE_270)
        frames[i] = np.asarray(img.resize(size, Image.LANCZOS))
    return frames


frames_dir, out = sys.argv[1], Path(sys.argv[2])
frames = load_frames(frames_dir)
S, H, W = frames.shape[:3]
print(f"{S} frames of {W}x{H}")

model = GCTStream(
    img_size=IMAGE_SIZE, patch_size=PATCH, embed_dim=1024,
    enable_camera=True, enable_depth=True, enable_point=False, enable_local_point=False,
    kv_cache_sliding_window=16, kv_cache_scale_frames=min(SCALE_FRAMES, S),
    camera_num_iterations=2, enable_3d_rope=True, enable_camera_3d_rope=True,
    max_frame_num=MAX_FRAMES,
)
model.eval()
load_weights(model, resolve_weight_file("checkpoints/lingbot-map-fp16.safetensors"))
model.update(tree_map(
    lambda x: x.astype(mx.float16) if isinstance(x, mx.array) and x.dtype == mx.float32 else x,
    model.parameters()))
mx.eval(model.parameters())
# Per-frame buffers are a few hundred MB: a 1 GB cache keeps them reusable
# without hoarding everything freed so far.
mx.set_cache_limit(1 << 30)
mx.clear_cache()

images = mx.array(frames[None]).astype(mx.float16) / 255
mx.eval(images)
del frames

t0 = time.time()
pred = model.inference_streaming(images, num_scale_frames=min(SCALE_FRAMES, S), keyframe_interval=1)
for v in pred.values():
    if isinstance(v, mx.array):
        mx.eval(v)
print(f"inference: {S} frames in {time.time() - t0:.0f} s, peak GPU memory {mx.get_peak_memory() / 1e9:.1f} GB")

w2c, intri = pose_encoding_to_extri_intri(pred["pose_enc"], image_size_hw=(H, W))
e4x4 = mx.concatenate([w2c, mx.zeros((*w2c.shape[:-2], 1, 4)).at[..., 0, 3].add(1.0)], axis=-2)
out.parent.mkdir(parents=True, exist_ok=True)
# Key names match create_map.py's archive, so export-web.py reads both.
np.savez(
    out,
    images=(np.array(pred["images"][0].astype(mx.float32)) * 255).round().clip(0, 255).astype(np.uint8),
    depth=np.array(pred["depth"][0], dtype=np.float32).reshape(S, H, W, 1),
    depth_conf=np.array(pred["depth_conf"][0], dtype=np.float32).reshape(S, H, W),
    extrinsic_w2c=np.array(w2c[0], dtype=np.float32),
    extrinsic_c2w=np.array(closed_form_inverse_se3_general(e4x4)[0, :, :3, :4], dtype=np.float32),
    intrinsic=np.array(intri[0], dtype=np.float32),
)
print(f"saved {out} ({out.stat().st_size / 1e9:.2f} GB)")
