# Project instructions

- Preserve the existing Git author and committer identity. Do not change Git identity configuration, override identity with environment variables, or rewrite history.
- Do not add AI attribution, assistant signatures, or co-author trailers to commits, source comments, or project documentation.
- Prefer one coherent commit per completed task, including its implementation, tests, and documentation. Use two commits only when there is a clear reason to separate changes; do not make separate commits for each file, test, or documentation edit. Do not create artificial commits to increase activity.
- Apply commit preferences prospectively. Leave existing published history unchanged.
- Commit and push only when the user authorizes them. Stage explicit task files and preserve unrelated work.
- Review and improve the existing root README.md for each relevant task; create it only if missing. Cover the project overview, stack, setup, configuration, usage, tests, available screenshots, and known limitations, preserving accurate existing documentation.
- Preserve the React/FastAPI architecture and public endpoint compatibility unless the task calls for changes.
- Use synthetic resumes and stub providers in tests. Do not make live AI requests or use personal resumes without explicit authorization.
- Track any user-specified live-request budget across task follow-ups. A follow-up or preference update does not reset that budget or authorize another live request.
- Never include resume text, job descriptions, credentials, raw provider responses, or exception traces in application error responses or logs.
