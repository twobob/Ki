import argparse
from pathlib import Path
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import spacy
import torch


def caption_image(image_path, processor, model, device):
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)
    out = model.generate(**inputs)
    return processor.decode(out[0], skip_special_tokens=True)


def extract_tags(caption, nlp):
    doc = nlp(caption)
    nouns = {token.lemma_.lower() for token in doc if token.pos_ == "NOUN"}
    return sorted(tag.upper() for tag in nouns)


def process_folder(folder):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = BlipProcessor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip2-opt-2.7b"
    ).to(device)
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
    parser.add_argument(
        "folder", help="Folder containing images. A .txt file will be created for each image."
    )
    args = parser.parse_args()
    process_folder(args.folder)


if __name__ == "__main__":
    main()
