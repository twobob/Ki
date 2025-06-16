import argparse
import os
import platform
from pathlib import Path
from PIL import Image, ImageOps
import tempfile
import numpy as np
import jpeglib
from thumb_utils import folder_hash

from jpeg_recompress import recompress
import shutil
from tqdm import tqdm


def generate_thumb_filename(img_path: Path) -> str:
    """Generate a thumbnail filename using the full image path with a short hash."""
    absolute = img_path.resolve()
    relative = absolute.relative_to(absolute.anchor)
    sanitized_parts = [part.replace(' ', '_').replace('.', '_') for part in relative.parts]
    sanitized = '_'.join(sanitized_parts)
    path_hash = folder_hash(absolute.parent)
    return f"{sanitized}_{path_hash}.THUMB.JPG"


def process_images(
    source_dir: Path,
    thumb_dir: Path,
    overlay_path: Path,
    thumb_size: int,
    clear_existing_thumbs: bool,
    recurse: bool = False,
    verbose: bool = False,
    compress: bool = False,
    jpegli: bool = False,
) -> None:
    script_dir = (
        Path(__file__).resolve().parent
    )  # Get the directory of the currently running script
    # Use provided thumb_dir and overlay_path directly

    if compress and jpegli:
        raise ValueError("-Z and -J options are mutually exclusive")

    if clear_existing_thumbs:
        if thumb_dir.exists():
            print(f"--clear specified. Clearing all items from {thumb_dir}...")
            for item in thumb_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif (
                    item.is_dir()
                ):  # If there happen to be subdirectories, remove them too
                    shutil.rmtree(item)
            print(f"Directory {thumb_dir} cleared.")
        else:
            print(
                f"--clear specified, but directory {thumb_dir} does not exist. Will create it."
            )

    thumb_dir.mkdir(
        parents=True, exist_ok=True
    )  # Ensure it exists, create parents if necessary

    # Collect stems of original images for which .THUMB.JPG thumbnails already exist.
    # This will be empty if thumbs were just cleared.
    existing_thumb_names = {p.name for p in thumb_dir.glob("*.THUMB.JPG")}

    source_image_paths = []
    img_glob_patterns = ["*.[jJ][pP][gG]", "*.[jJ][pP][eE][gG]", "*.[pP][nN][gG]"]
    for pattern in img_glob_patterns:
        if recurse:
            source_image_paths.extend(source_dir.rglob(pattern))
        else:
            source_image_paths.extend(source_dir.glob(pattern))

    total_source_images = len(source_image_paths)
    thumbnails_created_this_run = 0
    images_skipped_this_run = 0

    print(f"Processing images from: {source_dir}")
    print(f"Saving thumbnails to: {thumb_dir}")
    print(f"Looking for watermark at: {overlay_path}")
    if overlay_path.exists():
        print("Watermark found.")
    else:
        print("Watermark not found, proceeding without it.")
    print(f"Found {total_source_images} source image(s) to consider.")

    iterator = sorted(source_image_paths)
    pbar = None
    if not verbose:
        pbar = tqdm(total=total_source_images, desc="Creating Thumbnails", unit="image")

    for img_path in iterator:
        thumb_filename = generate_thumb_filename(img_path)
        thumb_save_path = thumb_dir / thumb_filename

        # Skip processing if this thumbnail already exists
        if thumb_filename in existing_thumb_names:
            if verbose:
                print(f"Thumbnail for {img_path.name} already exists (as {thumb_filename}), skipping.")
            images_skipped_this_run += 1
            if pbar:
                pbar.update(1)
            continue

        try:
            image = Image.open(img_path)
            if image is None:
                print(f"Failed to open image {img_path.name}, skipping.")
                images_skipped_this_run += 1  # Count as skipped if cannot be opened
                if pbar:
                    pbar.update(1)
                continue

            current_image_format = image.format  # Store format before exif_transpose
            image = ImageOps.exif_transpose(image)
            if image is None:
                image = Image.open(img_path)
                if image is None:
                    print(
                        f"Failed to process EXIF data for {img_path.name} and could not re-open, skipping."
                    )
                    images_skipped_this_run += 1
                    if pbar:
                        pbar.update(1)
                    continue

            # Use Image.Resampling.LANCZOS for newer Pillow versions
            # For older versions, Image.LANCZOS is used.
            if hasattr(Image, "Resampling"):
                resample_filter = Image.Resampling.LANCZOS
            else:
                resample_filter = Image.LANCZOS
            thumb = image.resize((thumb_size, thumb_size), resample_filter)

            # Apply overlay if watermark.png exists
            if overlay_path.exists():
                try:
                    logo_original = Image.open(overlay_path).convert("RGBA")
                    logo = (
                        logo_original.copy()
                    )  # Work with a copy to avoid modifying the original if opened multiple times

                    thumb_width, thumb_height = thumb.size
                    logo_width, logo_height = logo.size

                    # 1. Scale the watermark if it's larger than the thumbnail
                    if logo_width > thumb_width or logo_height > thumb_height:
                        scale_ratio = min(
                            thumb_width / logo_width, thumb_height / logo_height
                        )
                        new_logo_width = int(logo_width * scale_ratio)
                        new_logo_height = int(logo_height * scale_ratio)

                        # Use Image.Resampling.LANCZOS for newer Pillow versions for logo resizing
                        if hasattr(Image, "Resampling"):
                            resample_filter_logo = Image.Resampling.LANCZOS
                        else:
                            resample_filter_logo = Image.LANCZOS
                        logo = logo.resize(
                            (new_logo_width, new_logo_height), resample_filter_logo
                        )
                        logo_width, logo_height = (
                            logo.size
                        )  # Update dimensions after resize

                    # 2. Calculate position for bottom-right placement
                    x_pos = thumb_width - logo_width
                    y_pos = thumb_height - logo_height

                    # Ensure thumb is RGBA to handle logo transparency correctly
                    if thumb.mode != "RGBA":
                        thumb = thumb.convert("RGBA")

                    # Paste the (potentially resized) logo at the bottom-right
                    # The third argument 'logo' uses the alpha channel of the logo as the mask
                    thumb.paste(logo, (x_pos, y_pos), logo)

                except Exception as e_overlay:
                    print(f"Failed to apply overlay to {img_path.name}: {e_overlay}")

            # Save the thumbnail
            # Ensure the image is in RGB format before saving as JPEG
            if (
                thumb.mode == "RGBA" or thumb.mode == "P"
            ):  # P is for paletted images like some GIFs/PNGs
                thumb = thumb.convert("RGB")

            if compress:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    thumb.save(tmp.name, "JPEG", quality=98)
                    tmp_path = Path(tmp.name)

                try:
                    recompress(
                        tmp_path,
                        thumb_save_path,
                        target=0.0,
                        jpeg_min=40,
                        jpeg_max=98,
                        preset="low",
                        loops=6,
                        method="smallfry",
                        progressive=True,
                        accurate=False,
                    )
                finally:
                    try:
                        tmp_path.unlink()
                    except FileNotFoundError:
                        pass
            elif jpegli:
                arr = np.array(thumb.convert("RGB"))
                jpeg_img = jpeglib.from_spatial(arr)
                jpeg_img.write_spatial(str(thumb_save_path), qt=90)
            else:
                thumb.save(thumb_save_path, "JPEG", quality=98)
            thumbnails_created_this_run += 1
            existing_thumb_names.add(thumb_filename)
            if verbose:
                print(f"Created thumbnail: {thumb_save_path}")
            if pbar:
                pbar.update(1)

        except FileNotFoundError:
            print(
                f"Source image {img_path.name} not found during processing, skipping."
            )
            images_skipped_this_run += 1
            if pbar:
                pbar.update(1)
        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")
            images_skipped_this_run += 1
            if pbar:
                pbar.update(1)

    if pbar:
        pbar.close()

    print("\n--- Summary ---")
    print(f"Total source images found: {total_source_images}")
    print(f"Thumbnails created in this run: {thumbnails_created_this_run}")
    print(f"Images skipped (already had thumbnail or error): {images_skipped_this_run}")

    # Verification: Count .THUMB.JPG files in thumbs_dir
    final_thumb_count = len(list(thumb_dir.glob("*.THUMB.JPG")))
    print(f"Total .THUMB.JPG files in {thumb_dir}: {final_thumb_count}")

    if not clear_existing_thumbs:
        # If we didn\'t clear, the final count should be initial existing + newly created
        # This logic is a bit complex if some were skipped due to already existing,
        # so a simpler check is if created + skipped equals total.
        if thumbnails_created_this_run + images_skipped_this_run == total_source_images:
            print("Counts match: (Created + Skipped) == Total Source Images.")
        else:
            print(
                "Warning: Count mismatch detected. (Created + Skipped) != Total Source Images."
            )
    else:
        # If we cleared, the final count should be equal to those created in this run
        if final_thumb_count == thumbnails_created_this_run:
            print(
                "Counts match: Final Thumbnails == Created This Run (after clearing)."
            )
        else:
            print(
                "Warning: Count mismatch detected after clearing. Final Thumbnails != Created This Run."
            )


def get_default_pictures_folder() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.path.expandvars("%USERPROFILE%")) / "Pictures"
    elif system == "Darwin":  # macOS
        return Path.home() / "Pictures"
    elif system == "Linux":
        # Try XDG standard, fallback to ~/Pictures
        xdg_pictures_dir = os.environ.get("XDG_PICTURES_DIR")
        if xdg_pictures_dir:
            return Path(xdg_pictures_dir)
        return Path.home() / "Pictures"
    else:  # Fallback for other OSes
        return Path.cwd()  # Current working directory as a last resort


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create 256x256 thumbnails for images in a folder, with an optional overlay, and save them to a centralized img/thumbs directory relative to the script. Handles JPG, JPEG, and PNG."
    )
    script_dir = Path(__file__).resolve().parent

    default_pictures_folder = get_default_pictures_folder()
    if platform.system() == "Windows":
        help_text_default_folder = "%USERPROFILE%\\Pictures"
    else:
        help_text_default_folder = "~/Pictures"
    parser.add_argument(
        "--source_dir",
        type=Path,
        default=default_pictures_folder,
        help=(
            "Directory containing the original images. "
            f"Defaults to your OS's default pictures folder ({help_text_default_folder})."
        ),
    )
    parser.add_argument(
        "--thumb_dir",
        type=Path,
        default=script_dir / "img" / "thumbs",
        help="Directory to store the thumbnails. Defaults to '[script_dir]/img/thumbs'.",
    )
    parser.add_argument(
        "--overlay_path",
        type=Path,
        default=script_dir / "img" / "overlay" / "watermark.png",
        help="Path to the watermark image. Defaults to '[script_dir]/img/overlay/watermark.png'.",
    )
    parser.add_argument(
        "--thumb_size",
        type=int,
        default=256,
        help="Size of the thumbnails (width and height). Defaults to 256.",
    )
    parser.add_argument(
        "-C",
        "--clear",
        action="store_true",
        help="Clear the thumbnail directory before generating new thumbnails.",
    )
    parser.add_argument(
        "--recurse",
        action="store_true",
        help="Recurse into subdirectories when searching for images.",
    )
    parser.add_argument(
        "-V",
        "--verbose",
        action="store_true",
        help="Show per-image processing messages instead of a progress bar.",
    )
    parser.add_argument(
        "-Z",
        "--compress",
        action="store_true",
        help="Enable jpeg-recompress for thumbnails. Disabled by default.",
    )
    parser.add_argument(
        "-J",
        "--jpegli",
        action="store_true",
        help="Use jpeglib for thumbnail compression. Disabled by default.",
    )
    args = parser.parse_args()

    process_images(
        args.source_dir,
        args.thumb_dir,
        args.overlay_path,
        args.thumb_size,
        args.clear,
        args.recurse,
        args.verbose,
        args.compress,
        args.jpegli,
    )
