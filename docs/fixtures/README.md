# Synthetic portfolio fixtures

These fixtures describe a fictional junior developer and a fictional role. They
contain no real person's contact information, employer, education, or work history.
All skills and projects are fictional demonstration data, not qualifications
claimed by the repository author.

- `resume-synthetic.txt`: editable source, explicitly labeled synthetic.
- `resume-synthetic.pdf`: one-page, text-based PDF generated from that source.
- `job-description-synthetic.txt`: matching fictional junior full-stack role.

The resume describes Python, FastAPI, Pydantic, React, JavaScript, SQLite, Git, and
automated tests. PostgreSQL, Docker, and production deployment are explicitly not
claimed; the role lists those as optional learning goals. This gives a reviewer
concrete gaps to check if a future authorized live attempt produces feedback.

Regenerate the PDF offline, from the repository root:

```sh
backend/venv/bin/python scripts/generate_synthetic_resume.py
```

Generation checks that the text fits one page, extraction works, and the file/text
are within application limits. PDF metadata identifiers may vary on regeneration;
compare extracted content rather than expecting byte-identical PDF output.

The 2026-11-07 live attempt used these fixtures once. It returned a sanitized error,
not an analysis. See [the live verification record](../live-verification.md).
Neither fixture is a model-quality benchmark or an ATS-scoring reference answer.

## Short Free-tier live fixture

- `resume-free-tier-fictional.txt`: short fictional source with no personal details.
- `resume-free-tier-fictional.pdf`: one-page text PDF, 1,547 bytes in the live record.
- `job-description-free-tier-fictional.txt`: matching fictional role with required
  basic SQL and optional Docker, explicitly not claimed in the resume.

The [2026-11-10 live check](../live-verification-gptoss.md) used these files once
and returned real, validated feedback. This was the second live request overall;
no further request is authorized. The examples do not claim the author's skills
or demonstrate scoring accuracy.

Regenerate the short PDF offline from the root (PDF identifiers may change):

```sh
backend/venv/bin/python - <<'PY'
from pathlib import Path
import fitz
folder = Path('docs/fixtures')
with fitz.open() as document:
    page = document.new_page()
    assert page.insert_textbox(fitz.Rect(45, 45, 550, 795),
        (folder / 'resume-free-tier-fictional.txt').read_text(),
        fontsize=11, fontname='helv') >= 0
    document.set_metadata({'title': 'Fictional resume - live verification demo only',
                           'author': 'Fictional demonstration'})
    document.save(folder / 'resume-free-tier-fictional.pdf')
PY
```
