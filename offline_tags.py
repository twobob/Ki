import argparse
from pathlib import Path
from transformers.models.blip_2 import Blip2Processor, Blip2ForConditionalGeneration
from PIL import Image
import spacy
import torch
import os
import platform
import json  # Added import
from tqdm import tqdm
from typing import Optional
from thumb_utils import folder_hash


def generate_thumb_filename(img_path: Path, base_dir: Path) -> str:
    """Create thumbnail filename matching make_thumbs.py with hash."""
    relative = img_path.relative_to(base_dir)
    sanitized_parts = [part.replace(' ', '_').replace('.', '_') for part in relative.parts]
    sanitized = '_'.join(sanitized_parts)
    path_hash = folder_hash(relative.parent)
    return f"{sanitized}_{path_hash}.THUMB.JPG"


def caption_image(image_path, processor, model, device):  # device parameter might become redundant
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    # Inputs should be moved to the model's device
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    out = model.generate(**inputs)
    return processor.decode(out[0], skip_special_tokens=True)


def extract_tags(caption, nlp):
    doc = nlp(caption)
    nouns = {token.lemma_.lower() for token in doc if token.pos_ == "NOUN"}
    return sorted(tag.upper() for tag in nouns)


def process_folder(
    folder_path_str: str,
    recurse: bool = False,
    verbose: bool = False,
    add: bool = False,
    delete: bool = False,
    thumb_dir: Optional[Path] = None,
    data_file: Optional[Path] = None,
):
    """Process a folder of images and update data.json.

    Args:
        folder_path_str: Path to the folder of images.
        recurse: If True, search folders recursively.
        add: Append new entries to existing data.json instead of overwriting.
        delete: Remove records (and thumbnails) for images in the folder.
        thumb_dir: Location of thumbnails. Defaults to script_dir/img/thumbs.
        data_file: Path to data.json. Defaults to script_dir/data.json.
    """
    # Determine the output path for data.json (in the script's directory)
    # Assuming the script is run from its location, __file__ should give its path.
    try:
        script_dir = Path(__file__).resolve().parent
    except NameError:
        script_dir = Path.cwd()

    output_json_path = data_file if data_file else script_dir / "data.json"
    thumb_directory = thumb_dir if thumb_dir else script_dir / "img" / "thumbs"

    # device variable might not be strictly needed if device_map works
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Try to use the fast image processor to avoid warning about slow processors
    try:
        processor = Blip2Processor.from_pretrained(
            "Salesforce/blip2-opt-2.7b", use_fast=True
        )
    except TypeError:
        # Older versions of transformers may not support the use_fast argument
        processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = Blip2ForConditionalGeneration.from_pretrained(
        "Salesforce/blip2-opt-2.7b",
        device_map="auto",
    )
    # model.to(device) # This line should no longer be needed
    nlp = spacy.load("en_core_web_sm")
    img_extensions = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

    existing_data = []
    if add or delete:
        if output_json_path.exists():
            with open(output_json_path, "r", encoding="utf-8") as f_existing:
                existing_data = json.load(f_existing).get("questions", [])

    all_questions_data = []  # Initialize list to hold all image data
    image_folder_path = Path(folder_path_str)
    if recurse:
        iter_paths = image_folder_path.rglob('*')
    else:
        iter_paths = image_folder_path.iterdir()
    image_paths = [p for p in sorted(iter_paths) if p.is_file() and p.suffix in img_extensions]

    # Handle deletion before any captioning work
    if delete:
        names_to_delete = {p.name for p in image_paths}
        remaining = [
            e
            for e in existing_data
            if e.get("img", {}).get("filename") not in names_to_delete
        ]
        for img_path in image_paths:
            thumb_name = generate_thumb_filename(img_path, image_folder_path)
            thumb_path = thumb_directory / thumb_name
            if thumb_path.exists():
                thumb_path.unlink()

        tag_counts = {}
        for entry in remaining:
            for tag in entry.get("question", {}).get("content", {}):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        with open(output_json_path, "w", encoding="utf-8") as f_json:
            json.dump({"questions": remaining, "tag_counts": tag_counts}, f_json, indent=4)
        print(f"Updated {output_json_path}")
        return

    existing_names = {e.get("img", {}).get("filename") for e in existing_data}

    if verbose:
        for img_path in image_paths:
            if add and img_path.name in existing_names:
                if verbose:
                    print(f"Skipping {img_path.name} as it already exists in the dataset.")
                continue
            try:
                caption = caption_image(img_path, processor, model, device)
                tags_list = extract_tags(caption, nlp)

                content_dict = {tag: "1.0" for tag in tags_list}
                thumb_filename = generate_thumb_filename(img_path, image_folder_path)
                image_data_entry = {
                    "img": {"filename": img_path.name},
                    "question": {"content": content_dict},
                    "thumb": {"filename": thumb_filename},
                }
                all_questions_data.append(image_data_entry)

                print(f"Tags for {img_path.name}: {', '.join(tags_list)}")
            except Exception as e:
                print(f"Error processing {img_path.name}: {e}")
    else:
        with tqdm(total=len(image_paths), desc="Captioning Images", unit="image") as pbar:
            for img_path in image_paths:
                if add and img_path.name in existing_names:
                    pbar.update(1)
                    continue
                try:
                    caption = caption_image(img_path, processor, model, device)
                    tags_list = extract_tags(caption, nlp)

                    content_dict = {tag: "1.0" for tag in tags_list}

                    thumb_filename = generate_thumb_filename(img_path, image_folder_path)
                    image_data_entry = {
                        "img": {"filename": img_path.name},
                        "question": {"content": content_dict},
                        "thumb": {"filename": thumb_filename},
                    }
                    all_questions_data.append(image_data_entry)
                    pbar.update(1)
                except Exception as e:
                    print(f"Error processing {img_path.name}: {e}")
                    pbar.update(1)

    if add:
        combined = existing_data + all_questions_data
    else:
        combined = all_questions_data

    tag_counts = {}
    for entry in combined:
        for tag in entry.get("question", {}).get("content", {}):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    final_output_data = {"questions": combined, "tag_counts": tag_counts}

    with open(output_json_path, "w", encoding="utf-8") as f_json:
        json.dump(final_output_data, f_json, indent=4)

    print(f"Successfully generated {output_json_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate single-word tags from images using BLIP-2 and output to data.json"
    )

    default_pictures_folder = ""
    help_text_default_folder = ""
    if platform.system() == "Windows":
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            default_pictures_folder = Path(user_profile) / "Pictures"
            help_text_default_folder = "%USERPROFILE%\\\\Pictures"
        else:  # Fallback if USERPROFILE is not set
            default_pictures_folder = Path.cwd()
            help_text_default_folder = "current working directory"
    else:  # Linux, macOS, etc.
        default_pictures_folder = Path.home() / "Pictures"
        help_text_default_folder = "~/Pictures"

    parser.add_argument(
        "folder",
        nargs="?",
        default=str(default_pictures_folder),
        help=f"Folder containing images. Output will be written to data.json in the script's directory. (default: {help_text_default_folder})",
    )
    parser.add_argument(
        "-R",
        "--recurse",
        action="store_true",
        help="Recurse into subdirectories when scanning for images.",
    )
    parser.add_argument(
        "-V",
        "--verbose",
        action="store_true",
        help="Show per-image tags and disable progress bars.",
    )
    parser.add_argument(
        "-A",
        "--add",
        action="store_true",
        help="Add images to existing data.json instead of overwriting.",
    )
    parser.add_argument(
        "-D",
        "--delete",
        action="store_true",
        help="Delete records and thumbnails for images in the folder.",
    )
    parser.add_argument(
        "--thumb_dir",
        type=Path,
        help="Thumbnail directory. Defaults to script_dir/img/thumbs.",
    )
    parser.add_argument(
        "--data_file",
        type=Path,
        help="Path to data.json. Defaults to script_dir/data.json.",
    )
    args = parser.parse_args()

    if args.add and args.delete:
        parser.error("-A/--add and -D/--delete cannot be used together")

    if not Path(args.folder).is_dir():
        print(f"Error: Folder does not exist: {args.folder}")
        if str(Path(args.folder)) == str(default_pictures_folder):
            print(
                f"The default folder ({default_pictures_folder}) was used. Please provide a valid image folder."
            )
        return

    process_folder(
        args.folder,
        args.recurse,
        args.verbose,
        add=args.add,
        delete=args.delete,
        thumb_dir=args.thumb_dir,
        data_file=args.data_file,
    )


if __name__ == "__main__":
    main()
