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


def process_folder(folder_path_str: str, recurse: bool = False, verbose: bool = False):
    """Process a folder of images and write captions/tags to data.json.

    Args:
        folder_path_str: Path to the folder of images.
        recurse: If True, search folders recursively.
    """
    # Determine the output path for data.json (in the script's directory)
    # Assuming the script is run from its location, __file__ should give its path.
    try:
        script_dir = Path(__file__).resolve().parent
    except NameError:  # Fallback if __file__ is not defined (e.g. interactive execution)
        script_dir = Path.cwd()
    output_json_path = script_dir / "data.json"

    # device variable might not be strictly needed if device_map works
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = Blip2ForConditionalGeneration.from_pretrained(
        "Salesforce/blip2-opt-2.7b",
        device_map="auto",
    )
    # model.to(device) # This line should no longer be needed
    nlp = spacy.load("en_core_web_sm")
    img_extensions = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

    all_questions_data = []  # Initialize list to hold all image data

    image_folder_path = Path(folder_path_str)
    if recurse:
        iter_paths = image_folder_path.rglob('*')
    else:
        iter_paths = image_folder_path.iterdir()
    image_paths = [p for p in sorted(iter_paths) if p.is_file() and p.suffix in img_extensions]

    if verbose:
        for img_path in image_paths:
            try:
                caption = caption_image(img_path, processor, model, device)
                tags_list = extract_tags(caption, nlp)

                content_dict = {tag: "1.0" for tag in tags_list}
                thumb_filename = f"{img_path.stem}.THUMB.JPG"
                image_data_entry = {
                    "img": {"filename": img_path.name},
                    "question": {"content": content_dict},
                    "thumb": {"filename": thumb_filename},
                }
                all_questions_data.append(image_data_entry)

                print(f"Tags for {img_path.name}: {', '.join(tags_list)}")
            except Exception as e:
                print(f"Error processing {img_path.name}: {e}")
            # Removed writing to individual .txt files
    else:
        with tqdm(total=len(image_paths), desc="Captioning Images", unit="image") as pbar:
            for img_path in image_paths:
                try:
                    caption = caption_image(img_path, processor, model, device)
                    tags_list = extract_tags(caption, nlp)  # Get list of tags

                    # Create the desired dictionary format for content
                    content_dict = {tag: "1.0" for tag in tags_list}

                    thumb_filename = f"{img_path.stem}.THUMB.JPG"
                    image_data_entry = {
                        "img": {"filename": img_path.name},
                        "question": {"content": content_dict},  # Changed "tags" to "content" and used the new dict
                        "thumb": {"filename": thumb_filename},
                    }
                    all_questions_data.append(image_data_entry)

                    # The progress bar already shows how many images were processed,
                    # so avoid printing per-image status messages that clutter the
                    # output.
                    pbar.update(1)
                except Exception as e:
                    print(f"Error processing {img_path.name}: {e}")
                    pbar.update(1)
                # Removed writing to individual .txt files

    final_output_data = {"questions": all_questions_data}

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
    args = parser.parse_args()

    if not Path(args.folder).is_dir():
        print(f"Error: Folder does not exist: {args.folder}")
        if str(Path(args.folder)) == str(default_pictures_folder):
            print(
                f"The default folder ({default_pictures_folder}) was used. Please provide a valid image folder."
            )
        return

    process_folder(args.folder, args.recurse, args.verbose)


if __name__ == "__main__":
    main()
