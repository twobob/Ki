#!/usr/bin/env python3
"""JPEG recompression utility supporting several quality metrics.

This script is a small, self contained variant of ``jpeg-recompress`` from the
jpeg-archive project.  It provides SSIM, MS-SSIM, and the "smallfry" metric that
jpeg-archive uses.  It can also measure mean pixel error (MPE).

The ``recompress`` function can be used programmatically and is relied on by the
thumbnail generation script in this repository.  A command line interface is
also provided for ad-hoc use.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageFile
from skimage.metrics import structural_similarity as ssim

ImageFile.LOAD_TRUNCATED_IMAGES = True

# ---------------------------------------------------------------------------
# Metric implementations
# ---------------------------------------------------------------------------

# Target values when using the smallfry metric.  These are roughly compatible
# with the defaults used by jpeg-archive.
PRESETS_SMALLFRY = {
    "low": 100.75,
    "medium": 102.25,
    "high": 103.8,
    "veryhigh": 105.5,
}

METHODS = ("ssim", "ms-ssim", "smallfry", "mpe")


def load_image_luma(path: Path | BytesIO) -> np.ndarray:
    """Load an image and return the normalised luminance as ``float32``."""

    with Image.open(path) as im:
        gray = im.convert("L")
        arr = np.asarray(gray, dtype=np.float32) / 255.0
    return arr


def compute_ssim(orig: np.ndarray, comp: np.ndarray) -> float:
    """Standard single scale SSIM."""

    return float(ssim(orig, comp, data_range=1.0))


def compute_ms_ssim(orig: np.ndarray, comp: np.ndarray) -> float:
    """A very small MS-SSIM approximation using three scales."""

    score = 0.0
    weight = 1.0 / 3
    for scale in (1, 2, 4):
        small_o = Image.fromarray((orig * 255).astype(np.uint8)).resize(
            (orig.shape[1] // scale, orig.shape[0] // scale), Image.LANCZOS
        )
        small_c = Image.fromarray((comp * 255).astype(np.uint8)).resize(
            (orig.shape[1] // scale, orig.shape[0] // scale), Image.LANCZOS
        )
        so = np.asarray(small_o, dtype=np.float32) / 255.0
        sc = np.asarray(small_c, dtype=np.float32) / 255.0
        score += weight * ssim(so, sc, data_range=1.0)
    return float(score)


# ----------------------------- smallfry metric -----------------------------
# Ported from jpeg-archive.  The calculation is quite involved but completely
# self contained so that the tool has no external dependencies aside from
# Pillow and NumPy.


def _smallfry_psnr_factor(orig: np.ndarray, cmp: np.ndarray, maxv: int) -> float:
    diff = orig.astype(np.int16) - cmp.astype(np.int16)
    mse = np.mean(diff * diff)
    ret = 10.0 * np.log10(65025.0 / (mse if mse != 0 else 1))
    if maxv > 128:
        ret /= 50.0
    else:
        ret /= (0.0016 * (maxv ** 2)) - (0.38 * maxv + 72.5)
    return max(min(ret, 1.0), 0.0)


def _smallfry_aae_factor(orig: np.ndarray, cmp: np.ndarray, maxv: int) -> float:
    old = orig.astype(np.int16)
    new = cmp.astype(np.int16)
    height, width = old.shape
    sumv = 0.0
    cnt = 0
    for i in range(height):
        for j in range(7, width - 1, 8):
            cnt += 1
            calc = abs(abs(old[i, j] - new[i, j]) - abs(old[i, j + 1] - new[i, j + 1]))
            denom = (
                abs(abs(old[i, j - 1] - new[i, j - 1]) - abs(old[i, j] - new[i, j]))
                + abs(abs(old[i, j + 1] - new[i, j + 1]) - abs(old[i, j + 2] - new[i, j + 2]))
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
            calc = abs(abs(old[i, j] - new[i, j]) - abs(old[i + 1, j] - new[i + 1, j]))
            denom = (
                abs(abs(old[i - 1, j] - new[i - 1, j]) - abs(old[i, j] - new[i, j]))
                + abs(abs(old[i + 1, j] - new[i + 1, j]) - abs(old[i + 2, j] - new[i + 2, j]))
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


def metric_smallfry(a: np.ndarray, b: np.ndarray) -> float:
    a = (a * 255).astype(np.uint8)
    b = (b * 255).astype(np.uint8)
    maxv = int(np.max(a))
    p = _smallfry_psnr_factor(a, b, maxv)
    aae = _smallfry_aae_factor(a, b, maxv)
    return float(p * 37.1891885161239 + aae * 78.5328607296973)


def compute_mpe(orig: np.ndarray, comp: np.ndarray) -> float:
    return float(np.mean(np.abs(orig - comp)))


# Mapping of metric names to functions
METRIC_FUNCS = {
    "ssim": compute_ssim,
    "ms-ssim": compute_ms_ssim,
    "smallfry": metric_smallfry,
    "mpe": compute_mpe,
}

# ---------------------------------------------------------------------------
# Recompression logic
# ---------------------------------------------------------------------------


def recompress(
    infile: Path,
    outfile: Path,
    *,
    target: float = 0.0,
    jpeg_min: int = 40,
    jpeg_max: int = 95,
    preset: str = "medium",
    loops: int = 6,
    method: str = "ssim",
    progressive: bool = True,
    accurate: bool = False,
    subsample: str | int = "default",
    keep_metadata: bool = True,
    copy_allowed: bool = True,
    quiet: bool = False,
) -> int:
    """Recompress ``infile`` and write the result to ``outfile``.

    Returns ``0`` if the output file is smaller than the input and ``1`` if it is
    larger (or equal).  This mirrors the behaviour of jpeg-archive.
    """

    orig_buf = infile.read_bytes()
    orig_size = len(orig_buf)
    orig_luma = load_image_luma(infile)

    if target <= 0:
        if method == "smallfry":
            target = PRESETS_SMALLFRY.get(preset, PRESETS_SMALLFRY["medium"])
        elif method == "ssim":
            target = 0.9999
        elif method == "ms-ssim":
            target = 0.94
        else:  # mpe
            target = 0.0

    subsample_val = 0 if str(subsample) == "disable" or subsample == 0 else 2

    best_q = jpeg_max
    low, high = jpeg_min, jpeg_max
    final_buf = None

    for i in range(loops):
        q = (low + high) // 2
        bufio = BytesIO()
        save_args = dict(
            format="JPEG",
            quality=q,
            optimize=(accurate or (i == loops - 1)),
            progressive=progressive,
            subsampling=subsample_val,
        )
        if keep_metadata:
            with Image.open(infile) as im:
                if "exif" in im.info:
                    save_args["exif"] = im.info["exif"]
        Image.open(infile).convert("RGB").save(bufio, **save_args)
        buf = bufio.getvalue()
        comp_luma = load_image_luma(BytesIO(buf))

        metric = METRIC_FUNCS[method](orig_luma, comp_luma)
        if not quiet:
            print(f"Attempt {i + 1}/{loops}: q={q}, {method}={metric:.5f}", file=sys.stderr)

        if metric >= target:
            best_q = q
            final_buf = buf
            high = q - 1
        else:
            low = q + 1

    if final_buf is None:
        final_buf = orig_buf
        best_q = jpeg_max

    if len(final_buf) >= orig_size and copy_allowed:
        if not quiet:
            print("Result is larger than original; copying original.", file=sys.stderr)
        shutil.copy2(infile, outfile)
        return 0

    outfile.write_bytes(final_buf)

    new_size = len(final_buf)
    if not quiet:
        saved_kb = (orig_size - new_size) / 1024
        pct = new_size * 100 // orig_size
        print(
            f"New size: {new_size/1024:.2f} KB ({pct}% of original), saved {saved_kb:.2f} KB",
            file=sys.stderr,
        )

    return 0 if new_size < orig_size else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recompress a JPEG keeping visual quality (SSIM/MS-SSIM/Smallfry/MPE)."
    )
    p.add_argument("infile", help="input JPEG")
    p.add_argument("outfile", help="output JPEG")
    p.add_argument("-m", "--method", choices=METHODS, default="ssim", help="quality metric to use")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("-q", "--quality", choices=PRESETS_SMALLFRY.keys(), help="smallfry quality preset")
    grp.add_argument("-t", "--target", type=float, help="explicit target metric value")
    p.add_argument("-n", "--min", type=int, default=40, dest="qmin", help="minimum JPEG quality")
    p.add_argument("-x", "--max", type=int, default=95, dest="qmax", help="maximum JPEG quality")
    p.add_argument("-l", "--loops", type=int, default=6, dest="loops", help="binary search iterations")
    p.add_argument(
        "-S",
        "--subsample",
        choices=("default", "disable"),
        default="default",
        help="chroma subsample: default=4:2:0, disable=4:4:4",
    )
    p.add_argument("-s", "--strip", action="store_true", help="strip all metadata")
    p.add_argument("-p", "--no-progressive", action="store_true", help="disable progressive encoding")
    p.add_argument("-a", "--accurate", action="store_true", help="favor accuracy over speed")
    p.add_argument("-c", "--no-copy", action="store_false", dest="copy", help="do not copy if output is larger")
    p.add_argument("-Q", "--quiet", action="store_true", help="quiet mode (errors only)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.target is None:
        if args.quality:
            if args.method != "smallfry":
                print("Preset quality only applies to smallfry method.", file=sys.stderr)
                sys.exit(255)
            target = PRESETS_SMALLFRY[args.quality]
        else:
            target = 0.9999 if args.method == "ssim" else 0.94 if args.method == "ms-ssim" else PRESETS_SMALLFRY["medium"]
    else:
        target = args.target

    exit_code = recompress(
        infile=Path(args.infile),
        outfile=Path(args.outfile),
        target=target,
        jpeg_min=args.qmin,
        jpeg_max=args.qmax,
        preset=args.quality or "medium",
        loops=args.loops,
        method=args.method,
        progressive=not args.no_progressive,
        accurate=args.accurate,
        subsample=args.subsample,
        keep_metadata=not args.strip,
        copy_allowed=args.copy,
        quiet=args.quiet,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
