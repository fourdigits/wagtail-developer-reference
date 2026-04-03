# Wagtail Developer Reference

[![PyPI version](https://img.shields.io/pypi/v/wagtail-developer-reference.svg)](https://pypi.org/project/wagtail-developer-reference/)
[![Python versions](https://img.shields.io/pypi/pyversions/wagtail-developer-reference.svg)](https://pypi.org/project/wagtail-developer-reference/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**A visual auditing tool for Wagtail developers.** `wagtail-developer-reference` provides a live registry of your project's architecture, making it easy to track Page models and StreamField blocks across complex, multi-site setups. Stop hunting through `models.py` files and discover your project structure directly within the Wagtail Admin.

---

## Why use this?

In large Wagtail projects, it’s easy to lose track of where specific blocks are used or which templates are being rendered. This tool gives you a **"God-view"** of your components without needing to dig through the database or the Django shell.

* **Audit on the fly:** No extra database tables or complex settings.
* **Developer Experience:** Built for developers, by developers at Four Digits.
* **Transparency:** Surface template paths and model relationships instantly.

## Features

* **Usage Tracking:** See exactly how many times a Page type or StreamField block is used across the site.
* **Template Discovery:** Instantly see the file path for the template associated with every component.
* **Interactive Audit:** Filter by type or search for specific field names to find where logic is implemented.
* **Zero-Config:** It inspects your models and content registry in real-time.

## Installation

1. **Install using pip:**
   ```bash
   pip install wagtail-developer-reference