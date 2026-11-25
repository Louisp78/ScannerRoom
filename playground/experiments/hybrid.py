"""Hybrid reconstruction on a bench run (step 2): SfM fixes the camera path,
LingBot-Map keeps the dense depth.

  python hybrid.py <run-dir> <sfm-dir> <mode>

Reads the run's recon.npz and the SfM model written by the SfM probe, writes a
new run next to <run-dir> (same frames) whose recon.npz is changed, so the
unchanged export and metrics can score it:

  lingbot  unchanged, only trimmed to the frames SfM covers: the reference.
  hybrid   SfM camera poses and focal, brought into LingBot's frame and
           scale, and each frame's LingBot depth corrected towards the SfM
           points it sees: a smooth correction field, so the model's relief
           is kept and only its scale and slow distortions are fixed.

Poses alone, LingBot's focal instead of SfM's, and gating confident pixels by
agreement were tried and dropped (see the hybrid results).

Frames SfM did not register, or registered without real geometry, keep
LingBot's motion, attached to the nearest trusted frame.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfm_probe import align  # noqa: E402

FIELD_SIGMA = 0.1                         # correction field smoothness, share of image width
OUTLIER_MAD = 3
MAX_SCALE_DRIFT = 1.5                     # SfM / LingBot depth ratio vs its local median, to trust a frame
TRUST_WINDOW = 10                         # seconds of video either side for that local median


def load_sfm(sfm_dir, names):
    import pycolmap

    models = [pycolmap.Reconstruction(p) for p in sorted((sfm_dir / "model").iterdir()) if p.is_dir()]
    best = max(models, key=lambda m: m.num_reg_images())
    index = {n: i for i, n in enumerate(names)}
    cam = best.cameras[next(iter(best.cameras))]
    frames = {}
    for img in best.images.values():
        if not img.has_pose:
            continue
        w2c = img.cam_from_world()
        R, t = w2c.rotation.matrix(), w2c.translation
        obs = [(p.xy, best.points3D[p.point3D_id].xyz) for p in img.points2D if p.has_point3D()]
        xy = np.array([o[0] for o in obs]) if obs else np.zeros((0, 2))
        X = np.array([o[1] for o in obs]) if obs else np.zeros((0, 3))
        frames[index[img.name]] = (R.T, img.projection_center(), xy, (X @ R.T + t)[:, 2])
    return frames, cam


def correction_field(xy, log_ratio, h, w):
    """Smooth per-pixel log correction from sparse samples (normalised
    convolution), falling back to the frame's median where samples are few."""
    import cv2

    med = np.median(log_ratio)
    mad = np.median(np.abs(log_ratio - med)) + 1e-6
    ok = np.abs(log_ratio - med) < OUTLIER_MAD * 1.4826 * mad
    num, den = np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)
    x, y = np.round(xy[ok, 0]).astype(int), np.round(xy[ok, 1]).astype(int)
    np.add.at(num, (y, x), log_ratio[ok])
    np.add.at(den, (y, x), 1.0)
    sigma = FIELD_SIGMA * w
    num, den = cv2.GaussianBlur(num, (0, 0), sigma), cv2.GaussianBlur(den, (0, 0), sigma)
    prior = den.max() * 0.05  # where samples are this sparse, lean on the median
    return (num + prior * np.median(log_ratio[ok])) / (den + prior)


def main():
    from PIL import Image

    run, sfm_dir, mode = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
    if mode not in ("lingbot", "hybrid"):
        sys.exit(f"Unknown mode {mode}; known: lingbot, hybrid")
    n_sfm = json.loads((sfm_dir / "match.json").read_text())["frames"]
    names = sorted(p.name for p in (run / "frames").glob("*.jpg"))[:n_sfm]
    src_w, src_h = Image.open(run / "frames" / names[0]).size
    d = dict(np.load(run / "recon.npz"))
    n = len(names)  # the SfM run may cover only the start of the excerpt
    for key in ("images", "depth", "depth_conf", "extrinsic_w2c", "extrinsic_c2w", "intrinsic"):
        d[key] = d[key][:n]
    c2w = d["extrinsic_w2c"].astype(np.float64)  # the port mislabels it: this is camera-to-world
    depth = d["depth"][..., 0].astype(np.float64)
    K = d["intrinsic"].astype(np.float64)
    S, H, W = depth.shape
    sx, sy = W / src_w, H / src_h  # source pixels -> model pixels (stretched like the model input)

    frames, cam = load_sfm(sfm_dir, names)
    # SfM can "register" a frame without real geometry (a stretch of cameras
    # collapsed onto one point while a diver crosses). Trust a frame only if
    # its SfM depths agree in scale with LingBot's, up to one global factor.
    log_scale = {}
    for k, (_, _, xy, z) in frames.items():
        xi = np.clip(np.round((xy[:, 0] + 0.5) * sx - 0.5), 0, W - 1).astype(int)
        yi = np.clip(np.round((xy[:, 1] + 0.5) * sy - 0.5), 0, H - 1).astype(int)
        ok = z > 0
        if ok.sum() >= 20 and np.median(z[ok]) > 0:
            log_scale[k] = float(np.median(np.log(z[ok] / depth[k, yi[ok], xi[ok]])))
    # The reference is local (frames within TRUST_WINDOW seconds): LingBot's own
    # depth scale drifts slowly along a long transect, which is what the
    # hybrid must correct, not a reason to distrust SfM. Only abrupt
    # disagreement marks a broken SfM frame.
    fps = json.loads((run / "frames.json").read_text())["fps"]
    half = max(1, round(TRUST_WINDOW * fps))
    keys = np.array(sorted(log_scale))
    vals = np.array([log_scale[k] for k in keys])
    reg = [int(k) for k, m in zip(keys, vals)
           if abs(m - np.median(vals[np.abs(keys - k) <= half])) < np.log(MAX_SCALE_DRIFT)]
    if not reg:
        sys.exit("SfM has no frame consistent with LingBot: nothing to correct")
    rot_sfm = np.array([frames[k][0] for k in reg])
    cen_sfm = np.array([frames[k][1] for k in reg])
    s, r, t = align(rot_sfm, cen_sfm, c2w[reg, :, :3], c2w[reg, :, 3])

    new = c2w.copy()
    if mode == "lingbot":  # unchanged, trimmed to the SfM frames: the reference
        reg = []
    for i, k in enumerate(reg):
        new[k, :, :3] = r @ rot_sfm[i]
        new[k, :, 3] = s * r @ cen_sfm[i] + t
    # Frames SfM could not place keep LingBot's motion, carried by the
    # correction of the nearest trusted frame so the path stays continuous.
    if reg:
        for k in sorted(set(range(S)) - set(reg)):
            j = reg[int(np.argmin(np.abs(np.array(reg) - k)))]
            fix_r = new[j, :, :3] @ c2w[j, :, :3].T
            new[k, :, :3] = fix_r @ c2w[k, :, :3]
            new[k, :, 3] = new[j, :, 3] + fix_r @ (c2w[k, :, 3] - c2w[j, :, 3])
    f = cam.params[0]
    if reg:
        K[:, 0, 0], K[:, 1, 1] = f * sx, f * sy
        K[:, 0, 2], K[:, 1, 2] = (cam.params[1] + 0.5) * sx - 0.5, (cam.params[2] + 0.5) * sy - 0.5
    info = {"mode": mode, "frames": S, "registeredSfm": len(frames), "trusted": len(reg)}

    if mode == "hybrid":
        scales = []
        for k in reg:
            _, _, xy, z_sfm = frames[k]
            xm, ym = (xy[:, 0] + 0.5) * sx - 0.5, (xy[:, 1] + 0.5) * sy - 0.5
            xi, yi = np.clip(np.round(xm), 0, W - 1).astype(int), np.clip(np.round(ym), 0, H - 1).astype(int)
            ok = z_sfm > 0
            if ok.sum() < 20:
                continue
            log_ratio = np.log(s * z_sfm[ok] / depth[k, yi[ok], xi[ok]])
            field = correction_field(np.stack([xm[ok], ym[ok]], 1), log_ratio, H, W)
            depth[k] *= np.exp(field)
            scales.append(float(np.exp(np.median(log_ratio))))
        info["depthScale"] = [round(float(np.percentile(scales, p)), 3) for p in (10, 50, 90)]

    d["extrinsic_w2c"] = new.astype(np.float32)  # keep the port's field naming
    d["intrinsic"] = K.astype(np.float32)
    d["depth"] = depth[..., None].astype(np.float32)
    out = run.parent / (mode + sfm_dir.name.removeprefix("sfm"))
    out.mkdir(exist_ok=True)
    (out / "frames").mkdir(exist_ok=True)
    for name in names:
        dst = out / "frames" / name
        if not dst.exists():
            dst.symlink_to(run / "frames" / name)
    shutil.copy(run / "frames.json", out / "frames.json")
    np.savez(out / "recon.npz", **d)
    (out / "hybrid.json").write_text(json.dumps(info, indent=2))
    print(out)
    print(json.dumps(info))


if __name__ == "__main__":
    main()
