from setuptools import find_packages, setup

setup(
    name="wagtail-developer-reference",
    version="0.1.3",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "wagtail>=4.1,<7.5",
    ],
)
