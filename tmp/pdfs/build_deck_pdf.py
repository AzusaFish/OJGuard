from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
SLIDES = ROOT / "tmp" / "ppt-expanded" / "compact-final-render"
OUTPUT = ROOT / "output" / "submission" / "OJGuard_项目介绍.pdf"
PAGE_WIDTH = 960.0
PAGE_HEIGHT = 540.0


def main() -> None:
    images = sorted(SLIDES.glob("slide-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
    if len(images) != 12:
        raise ValueError(f"Expected 12 rendered slides, found {len(images)}")
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(PAGE_WIDTH, PAGE_HEIGHT), pageCompression=1)
    pdf.setTitle("OJGuard - 在线测评事故响应与可信重评")
    for image_path in images:
        pdf.drawImage(ImageReader(str(image_path)), 0, 0, PAGE_WIDTH, PAGE_HEIGHT)
        pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    main()
