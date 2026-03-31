from setuptools import setup, find_packages

setup(
    name="wagtail-developer-reference",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "wagtail>=4.1",
    ],
)