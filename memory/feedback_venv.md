---
name: feedback-venv
description: Always use the project .venv and keep requirements.txt updated when running Python
metadata:
  type: feedback
---

Always activate `.venv` (`.venv/bin/python`) when running Python scripts in this project. Do not use the system `python3` or `pip` directly.

**Why:** The project has a `.venv` virtual environment. Running outside it will fail with missing module errors, and installing globally pollutes the system Python.

**How to apply:** Use `.venv/bin/python <script>` to run, and `.venv/bin/pip install <pkg>` to add packages. After adding packages, update `requirements.txt` with `.venv/bin/pip freeze | grep <relevant-packages> > requirements.txt`.
