#!/usr/bin/env python3
"""JPEG recompression utility with smallfry metric.

This is a simplified Python port of the `jpeg-recompress` tool from the
jpeg-archive project. Only a subset of features is implemented here.
"""

import argparse
import math
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity, peak_signal_noise_ratio

# Quality presets map roughly to a target metric value
QUALITY_PRESETS = {
    "low": 0.5,
    "medium": 0.75,
    "subhigh": 0.875,
    "high": 0.9375,
    "veryhigh": 0.96875,
}


def metric_smallfry(a: np.ndarray, b: np.ndarray) -> float:
    """Smallfry perceptual metric as used by jpeg-archive."""

    a = (a * 255).astype(np.uint8)
    b = (b * 255).astype(np.uint8)
    height, width = a.shape

    def psnr_factor(orig: np.ndarray, cmp: np.ndarray, maxv: int) -> float:
        diff = orig.astype(np.int16) - cmp.astype(np.int16)
        mse = np.mean(diff * diff)
        ret = 10.0 * math.log10(65025.0 / (mse if mse != 0 else 1))
        if maxv > 128:
            ret /= 50.0
        else:
            ret /= (0.0016 * (maxv**2)) - (0.38 * maxv + 72.5)
        return max(min(ret, 1.0), 0.0)

    def aae_factor(orig: np.ndarray, cmp: np.ndarray, maxv: int) -> float:
        old = orig.astype(np.int16)
        new = cmp.astype(np.int16)
        sumv = 0.0
        cnt = 0
        for i in range(height):
            for j in range(7, width - 1, 8):
                cnt += 1
                calc = abs(
                    abs(old[i, j] - new[i, j]) - abs(old[i, j + 1] - new[i, j + 1])
                )
                denom = (
                    abs(abs(old[i, j - 1] - new[i, j - 1]) - abs(old[i, j] - new[i, j]))
                    + abs(
                        abs(old[i, j + 1] - new[i, j + 1])
                        - abs(old[i, j + 2] - new[i, j + 2])
                    )
                    + 0.0001
                ) / 2.0
                calc /= denom
                if calc > 5.0:
                    sumv += 1.0
                elif calc > 2.0:
                    sumv += (calc - 2.0) / (5.0 - 2.0)

        for i in range(7, height - 2, 8):
            for j in range(width):
                cnt += 1
                calc = abs(
                    abs(old[i, j] - new[i, j]) - abs(old[i + 1, j] - new[i + 1, j])
                )
                denom = (
                    abs(abs(old[i - 1, j] - new[i - 1, j]) - abs(old[i, j] - new[i, j]))
                    + abs(
                        abs(old[i + 1, j] - new[i + 1, j])
                        - abs(old[i + 2, j] - new[i + 2, j])
                    )
                    + 0.0001
                ) / 2.0
                calc /= denom
                if calc > 5.0:
                    sumv += 1.0
                elif calc > 2.0:
                    sumv += (calc - 2.0) / (5.0 - 2.0)

        ret = 1 - (sumv / cnt if cnt else 0)
        if maxv > 128:
            cfmax = 0.65
        else:
            cfmax = 0.65 + 0.35 * ((128.0 - maxv) / 128.0)
        cf = max(cfmax, min(1.0, 0.25 + (1000.0 * cnt) / (sumv if sumv != 0 else 1)))
        return ret * cf

    maxv = int(np.max(a))
    p = psnr_factor(a, b, maxv)
    aae = aae_factor(a, b, maxv)
    return p * 37.1891885161239 + aae * 78.5328607296973


def metric_psnr(a: np.ndarray, b: np.ndarray) -> float:
    return peak_signal_noise_ratio(a, b, data_range=1.0)


def metric_ssim(a: np.ndarray, b: np.ndarray) -> float:
    return structural_similarity(a, b, data_range=1.0)


METRIC_FUNCS = {
    "smallfry": metric_smallfry,
    "psnr": metric_psnr,
    "ssim": metric_ssim,
}


def compute_metric(method: str, ref: np.ndarray, cmp: np.ndarray) -> float:
    if method not in METRIC_FUNCS:
        raise NotImplementedError(f"Metric '{method}' not implemented")
    return METRIC_FUNCS[method](ref, cmp)


def recompress(
    in_path: Path,
    out_path: Path,
    *,
    target: float,
    jpeg_min: int,
    jpeg_max: int,
    preset: str,
    loops: int,
    method: str,
    progressive: bool,
    accurate: bool,
) -> None:
    with Image.open(in_path) as im:
        im = im.convert("RGB")
        original = np.asarray(im.convert("L"), dtype=np.float32) / 255.0

    if target <= 0 and preset:
        target = QUALITY_PRESETS.get(preset, QUALITY_PRESETS["medium"])

    low = jpeg_min
    high = jpeg_max
    best_q = high

    for _ in range(loops):
        q = (low + high + 1) // 2
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=q, optimize=False, progressive=False)
        buf.seek(0)
        cmp_im = Image.open(buf).convert("L")
        gray_cmp = np.asarray(cmp_im, dtype=np.float32) / 255.0

        metric = compute_metric(method, original, gray_cmp)
        if metric >= target:
            best_q = q
            high = q - 1
        else:
            low = q + 1

    im.save(
        out_path,
        format="JPEG",
        quality=best_q,
        optimize=accurate,
        progressive=progressive,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Recompress JPEG using smallfry metric"
    )
    parser.add_argument("input", help="input image path")
    parser.add_argument("output", help="output image path")
    parser.add_argument(
        "-t", "--target", type=float, default=0.0, help="target metric value"
    )
    parser.add_argument(
        "-n",
        "--min",
        dest="jpeg_min",
        type=int,
        default=40,
        help="minimum JPEG quality",
    )
    parser.add_argument(
        "-x",
        "--max",
        dest="jpeg_max",
        type=int,
        default=98,
        help="maximum JPEG quality",
    )
    parser.add_argument(
        "-l", "--loops", type=int, default=6, help="number of binary search iterations"
    )
    parser.add_argument(
        "-m",
        "--method",
        default="smallfry",
        choices=list(METRIC_FUNCS.keys()),
        help="metric to use",
    )
    parser.add_argument(
        "-q",
        "--quality",
        choices=list(QUALITY_PRESETS.keys()),
        default="medium",
        help="quality preset",
    )
    parser.add_argument(
        "-p",
        "--no-progressive",
        action="store_true",
        help="disable progressive encoding",
    )
    parser.add_argument(
        "-a", "--accurate", action="store_true", help="favor accuracy over speed"
    )
    args = parser.parse_args()

    recompress(
        Path(args.input),
        Path(args.output),
        target=args.target,
        jpeg_min=args.jpeg_min,
        jpeg_max=args.jpeg_max,
        preset=args.quality,
        loops=args.loops,
        method=args.method,
        progressive=not args.no_progressive,
        accurate=args.accurate,
    )


if __name__ == "__main__":
    main()
