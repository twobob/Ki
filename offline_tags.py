import argparse
from pathlib import Path
from transformers.models.blip_2 import Blip2Processor, Blip2ForConditionalGeneration
from PIL import Image
import spacy
import torch
import os
import platform


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


def process_folder(folder):
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

    for img_path in sorted(Path(folder).iterdir()):
        if img_path.suffix in img_extensions:
            caption = caption_image(img_path, processor, model, device)
            tags = extract_tags(caption, nlp)
            with open(img_path.with_suffix(".txt"), "w", encoding="utf-8") as f:
                for tag in tags:
                    f.write(tag + "\n")
            print(f"{img_path.name}: {', '.join(tags)}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate single-word tags from images using BLIP-2"
    )

    default_pictures_folder = ""
    if platform.system() == "Windows":
        default_pictures_folder = Path(os.environ['USERPROFILE']) / "Pictures"
        help_text_default_folder = "%USERPROFILE%\\\\Pictures"
    else:  # Linux, macOS, etc.
        default_pictures_folder = Path.home() / "Pictures"
        help_text_default_folder = "~/Pictures"

    parser.add_argument(
        "folder",
        nargs="?",
        default=str(default_pictures_folder),
        help=f"Folder containing images. A .txt file will be created for each image. (default: {help_text_default_folder})"
    )
    args = parser.parse_args()
    process_folder(args.folder)


if __name__ == "__main__":
    main()
