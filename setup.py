#!/usr/bin/env python3
"""
Setup script for Multi-Platform Music Downloader
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="multi-platform-music-downloader",
    version="1.0.0",
    author="DJ Community",
    author_email="",
    description="A comprehensive tool for downloading music from SoundCloud, Spotify, and YouTube",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/soundcloud-downloader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "music-downloader=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
