"""Generate the clearly labeled, fictional portfolio resume fixture offline."""

from pathlib import Path
import fitz

root = Path(__file__).resolve().parents[1]
source = root / 'docs/fixtures/resume-synthetic.txt'
target = root / 'docs/fixtures/resume-synthetic.pdf'
text = source.read_text()
with fitz.open() as document:
    page = document.new_page(width=595, height=842)
    remaining = page.insert_textbox(fitz.Rect(45, 40, 550, 800), text, fontsize=10, fontname='helv')
    if remaining < 0:
        raise SystemExit('Synthetic text does not fit the one-page fixture.')
    document.set_metadata({'title': 'SYNTHETIC RESUME - PORTFOLIO DEMO ONLY', 'author': 'Fictional portfolio fixture'})
    document.save(target, garbage=4, deflate=True)
with fitz.open(target) as document:
    extracted = ''.join(page.get_text() for page in document)
    assert document.page_count == 1 and 'SYNTHETIC RESUME' in extracted
    assert len(extracted) <= 50_000
assert target.stat().st_size < 5 * 1024 * 1024
print('Synthetic text-based PDF generated: one page, within all input limits.')
