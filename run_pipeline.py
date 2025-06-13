import subprocess
import argparse
import os
import sys
from pathlib import Path  # Added import
import platform  # Added import


# Added helper function
def get_default_pictures_folder() -> Path:
    system = platform.system()
    if system == "Windows":
        # Correctly get USERPROFILE and then append Pictures
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return Path(user_profile) / "Pictures"
        else:  # Fallback if USERPROFILE is not set
            return Path.cwd()  # Or some other sensible fallback
    elif system == "Darwin":  # macOS
        return Path.home() / "Pictures"
    elif system == "Linux":
        xdg_pictures_dir = os.environ.get("XDG_PICTURES_DIR")
        if xdg_pictures_dir:
            return Path(xdg_pictures_dir)
        return Path.home() / "Pictures"
    else:  # Fallback for other OSes
        return Path.cwd()


def run_script(script_path, args):
    """Helper function to run a Python script with arguments."""
    cmd = [sys.executable, script_path] + [str(arg) for arg in args]
    print(f"Running command: {' '.join(cmd)}")
    try:
        completed = subprocess.run(cmd)
        if completed.returncode != 0:
            print(f"Error running {script_path}. Return code: {completed.returncode}")
            return False
        print(f"Successfully ran {script_path}.")
        return True
    except Exception as e:
        print(f"Failed to run {script_path}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run the full image processing pipeline: thumbnails, tags, and JSON generation."
    )

    # Use the helper function for the default value
    default_originals_path = get_default_pictures_folder()
    parser.add_argument(
        "input_path",
        nargs="?",
        help=f"Directory containing original images. Defaults to OS pictures folder: {default_originals_path}",
    )

    parser.add_argument(
        "-I",
        "--input",
        type=str,
        help="Directory containing original images (overrides positional PATH).",
    )

    parser.add_argument(
        "-O",
        "--output",
        type=str,
        default=os.path.join("img", "thumbs"),
        help="Directory to store thumbnails.",
    )  # Updated help text
    # offline_tags.py will use the output directory for its --image_folder and --output_folder (where .txt files are saved)
    # build_data_json.py will use the output directory for its --tags_dir
    parser.add_argument(
        "--output_json",
        type=str,
        default="data.json",
        help="Path for the final data.json file (Note: offline_tags.py currently hardcodes output to data.json in script root).",
    )  # Updated help text
    parser.add_argument(
        "--watermark_path",
        type=str,
        default=os.path.join("img", "overlay", "watermark.png"),
        help="Path to the watermark image.",
    )
    parser.add_argument(
        "-C",
        "--clear",
        action="store_true",
        help="Clear the thumbnails directory before generating new thumbnails.",
    )
    parser.add_argument(
        "--thumb_size",
        type=int,
        default=256,
        help="Size of the thumbnails (width and height).",
    )
    parser.add_argument(
        "-Z",
        "--compress",
        action="store_true",
        help="Enable jpeg-recompress for thumbnails.",
    )
    parser.add_argument(
        "-J",
        "--jpegli",
        action="store_true",
        help="Use jpeglib for thumbnail compression.",
    )
    parser.add_argument(
        "-R",
        "--recurse",
        action="store_true",
        help="Recurse into subdirectories when processing images.",
    )
    parser.add_argument(
        "-V",
        "--verbose",
        action="store_true",
        help="Show per-image messages and disable progress bars in sub-scripts.",
    )

    args = parser.parse_args()

    if args.compress and args.jpegli:
        parser.error("-Z/--compress and -J/--jpegli cannot be used together.")

    # Determine the raw input argument (from -I/--input or positional PATH)
    raw_input_arg = args.input if args.input else (args.input_path or str(default_originals_path))

    # Fix common Windows quoting mistakes where extra flags become part of the
    # input path argument (e.g. `"C:\Users\me\Pictures\" -R -C`).
    # This happens when a trailing backslash escapes the closing quote.
    # If such a situation is detected, split the argument and recover the flags.
    parts = raw_input_arg.split()
    if len(parts) > 1 and any(p.startswith("-") for p in parts[1:]):
        raw_input_arg = parts[0].strip('"')
        for flag in parts[1:]:
            if flag in ("--recurse", "-R"):
                args.recurse = True
            elif flag in ("--clear", "-C", "--clear_thumbs"):
                args.clear = True
            elif flag in ("--compress", "-Z"):
                args.compress = True
            elif flag in ("--jpegli", "-J"):
                args.jpegli = True
            else:
                print(
                    f"Warning: Unrecognized token '{flag}' found in input path argument"
                )

    # Ensure paths are absolute for consistency, especially when calling subprocesses
    # However, the scripts themselves are designed to work with relative paths from project root.
    # Let's keep them relative for now, assuming the wrapper is run from the project root.
    input_dir = raw_input_arg
    output_dir = args.output
    output_json = args.output_json
    watermark_path = args.watermark_path
    recurse = args.recurse

    # Construct script paths relative to this script's location (project root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    make_thumbs_script = os.path.join(script_dir, "make_thumbs.py")
    offline_tags_script = os.path.join(script_dir, "offline_tags.py")
    # build_data_json_script = os.path.join(script_dir, 'build_data_json.py') # Removed

    print(f"Pipeline Configuration:")
    print(f"  Input Directory: {input_dir}")
    print(f"  Output Directory: {output_dir}")
    print(f"  Output JSON: {output_json}")
    print(f"  Watermark Path: {watermark_path}")
    print(f"  Clear Thumbnails: {args.clear}")
    print(f"  Compress Thumbnails: {args.compress}")
    print(f"  Jpeglib Compression: {args.jpegli}")
    print(f"  Thumbnail Size: {args.thumb_size}")
    print(f"  Recurse into subfolders: {recurse}")
    print(f"  Verbose output: {args.verbose}")
    print("-" * 30)

    # Prepare arguments for the individual steps
    make_thumbs_args = [
        "--source_dir",
        input_dir,
        "--thumb_dir",
        output_dir,
        "--overlay_path",
        watermark_path,  # Corrected: was --watermark
        # '--clear', str(args.clear), # Corrected logic below
        "--thumb_size",
        str(args.thumb_size),
    ]
    if args.clear:  # Correctly append --clear only if True
        make_thumbs_args.append("--clear")
    if args.compress:
        make_thumbs_args.append("--compress")
    if args.jpegli:
        make_thumbs_args.append("--jpegli")
    if recurse:
        make_thumbs_args.append("--recurse")

    offline_tags_args = [input_dir]
    if recurse:
        offline_tags_args.append("--recurse")
    if args.verbose:
        make_thumbs_args.append("--verbose")
        offline_tags_args.append("--verbose")

    print("\nStep 1: Generating thumbnails...")
    if not run_script(make_thumbs_script, make_thumbs_args):
        print("Thumbnail generation failed. Aborting pipeline.")
        return

    print("\nStep 2: Generating tags and data.json...")
    if not run_script(offline_tags_script, offline_tags_args):
        print("Tag and data.json generation failed. Aborting pipeline.")
        return

    # Step 3: Build data.json (This step is now handled by offline_tags.py)
    # print("\\nStep 3: Building data.json...")
    # build_data_json_args = [
    #     '--tags_dir', output_dir,
    #     '--output_file', output_json
    # ]
    # if not run_script(build_data_json_script, build_data_json_args):
    #     print("JSON generation failed. Aborting pipeline.")
    #     return

    print("\nPipeline completed successfully!")


if __name__ == "__main__":
    main()
