# Wagtail Developer Reference

**A visual auditing tool for Wagtail developers.** This package provides a live registry of your project's architecture, making it easy to track Page models and StreamField blocks across complex, multi-site setups.

## Why use this?
In large Wagtail projects, it’s easy to lose track of where specific blocks are used or which templates are being rendered. This tool gives you a "God-view" of your components without needing to dig through the database or shell.

## Features
* **Usage Tracking:** See exactly how many times a Page type or StreamField block is used across the site.
* **Template Discovery:** Instantly see the file path for the template associated with every component.
* **Interactive Audit:** Filter by type or search for specific field names to find where logic is implemented.
* **Zero-Config:** No extra database tables or complex settings. It inspects your models and content on the fly.

## Installation

1. Add \`wagtail_developer_reference\` to your \`INSTALLED_APPS\`:
   \`\`\`python
   INSTALLED_APPS = [
       ...,
       "wagtail_developer_reference",
   ]
   \`\`\`

2. **Usage:**
   * Login to the Wagtail Admin as a **superuser**.
   * Find the **"System Registry"** item in the sidebar menu.

## Settings

### `WAGTAIL_DEVELOPER_REFERENCE_ALLOW_ALL_ADMIN_USERS`

Defaults to `False`, preserving superuser-only access. Set this to `True` in
your Django settings to allow all users with access to the Wagtail admin
(`wagtailadmin.access_admin`) to open both the registry and usage detail pages,
without granting any additional permissions:

```python
WAGTAIL_DEVELOPER_REFERENCE_ALLOW_ALL_ADMIN_USERS = True
```

Users without Wagtail admin access remain unable to access the Developer Reference.

## License
**Internal Use Only** - Copyright © 2026 Fourdigits. All rights reserved.
