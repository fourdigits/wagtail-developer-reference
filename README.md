Wagtail Developer Reference

A plug-and-play auditing tool for Wagtail developers. It provides a visual registry of all Page models and StreamField blocks, tracking their usage across multiple sites.

Quick Start

1. Add wagtail_developer_reference to your INSTALLED_APPS:
   
   INSTALLED_APPS = [
       ...,
       "wagtail_developer_reference",
   ]
   
2. Login to the Wagtail Admin as a superuser.
3. Find the System Registry item in the sidebar menu.

Features
- Live vs Draft Tracking: See exactly how many times a block or page type is being used.
- Interactive Audit: Filter by type or search for specific field names.
- Template Discovery: Automatically finds the file path for the template associated with each component.
- No Configuration Needed: All styling and scripts are bundled inline.

License
MIT
