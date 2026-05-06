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

Compatibility: Python 3.9+ and Wagtail 4.1 through 7.4 LTS. Wagtail 7.4
itself requires Python 3.10+.

1. Add \`wagtail_developer_reference\` to your \`INSTALLED_APPS\`:
   \`\`\`python
   INSTALLED_APPS = [
       ...,
       "wagtail_developer_reference",
   ]
   \`\`\`

2. Run migrations so Django creates the package permission:
   ```bash
   python manage.py migrate
   ```

3. Grant access in the Django admin:
   * Open a user or group in the Django admin.
   * Assign **Wagtail developer reference | developer reference access | Can access the
     Wagtail developer reference**.

4. **Usage:**
   * Login to the Wagtail Admin with an account that has that permission explicitly
     assigned.
   * Find the **"System Registry"** item in the sidebar menu.

By default, no account can see the menu item or access the URLs. Superusers are not
granted access automatically by this package; assign the permission directly or
through a group.

## License
**Internal Use Only** - Copyright © 2026 Fourdigits. All rights reserved.
