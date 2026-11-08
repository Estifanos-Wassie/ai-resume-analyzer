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
