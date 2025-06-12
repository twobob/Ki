import argparse
import os
import platform
from pathlib import Path
from PIL import Image, ImageOps


def process_images(folder: Path) -> None:
    thumbs_dir = folder / "thumbs"
    overlay_path = folder / "overlay" / "watermark.png"
    thumbs_dir.mkdir(exist_ok=True)

    existing_thumbs = {
        p.name.replace(".THUMB.JPG", ".JPG") for p in thumbs_dir.glob("*.THUMB.JP*")
    }

    for img_path in sorted(folder.glob("*.JPG")):
        if img_path.name in existing_thumbs:
            continue

        try:
            image = Image.open(img_path)
            image = ImageOps.exif_transpose(image)
            thumb = image.resize((128, 128), Image.LANCZOS)

            if overlay_path.exists():
                logo = Image.open(overlay_path).convert("RGBA")
                thumb.paste(logo, (0, 0), logo)

            out_name = img_path.stem + ".THUMB.JPG"
            thumb.convert("RGB").save(thumbs_dir / out_name, "JPEG")
            print(f"Created {out_name}")
        except Exception as e:
            print(f"Failed to process {img_path}: {e}")


def main() -> None:
    default_pictures_folder = Path()
    if platform.system() == "Windows":
        default_pictures_folder = Path(os.environ["USERPROFILE"]) / "Pictures"
        help_text_default_folder = "%USERPROFILE%\\Pictures"
    else:
        default_pictures_folder = Path.home() / "Pictures"
        help_text_default_folder = "~/Pictures"

    parser = argparse.ArgumentParser(
        description="Create oriented thumbnails for JPG images"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=str(default_pictures_folder),
        help=f"Folder containing images (default: {help_text_default_folder})",
    )
    args = parser.parse_args()

    process_images(Path(args.folder))


if __name__ == "__main__":
    main()
