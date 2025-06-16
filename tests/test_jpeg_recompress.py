from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jpeg_recompress import recompress

def test_recompress_basic(tmp_path: Path):
    # Create a simple test image
    img = Image.new("RGB", (32, 32), color="red")
    infile = tmp_path / "in.jpg"
    outfile = tmp_path / "out.jpg"
    img.save(infile, format="JPEG", quality=95)

    # Run recompress using smallfry metric
    rc = recompress(
        infile,
        outfile,
        target=0.0,
        jpeg_min=40,
        jpeg_max=95,
        preset="low",
        loops=2,
        method="smallfry",
        progressive=True,
        accurate=False,
    )
    assert outfile.exists()
    assert rc in (0, 1)
    # Ensure file contains JPEG data
    assert outfile.read_bytes().startswith(b"\xFF\xD8")
