from setuptools import setup, find_packages

with open("README.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="kgtorrent",
    version="0.0.1",
    author="Alireza",
    author_email="asady529@gmail.com",
    description="kgtorrent with setup.py",
    long_description=long_description,
    long_description_content_type="text/rst",
    url="https://github.com/alirezaAsadi2018/KGTorrent/",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Bug Tracker": "https://github.com/alirezaAsadi2018/KGTorrent/issues",
    },
    package_dir={"": "KGTorrent"},
    packages=find_packages(where="KGTorrent"),
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "sample=kgtorrent:main",
        ],
    },
)
