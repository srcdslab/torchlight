import os
from typing import Dict, List

from setuptools import find_packages, setup


def rel(*xs: str) -> str:
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), *xs)


with open(rel("README.md")) as f:
    long_description = f.read()


with open(rel("src", "torchlight", "__init__.py")) as f:
    version_marker = "__version__ = "
    for line in f:
        if line.startswith(version_marker):
            _, version = line.split(version_marker)
            version = version.strip().strip('"')
            break
    else:
        raise RuntimeError("Version marker not found.")


dependencies = ["click", "geoip2", "aiohttp"]

extra_dependencies: Dict[str, List[str]] = {}

extra_dependencies["all"] = list(set(sum(extra_dependencies.values(), [])))
extra_dependencies["dev"] = extra_dependencies["all"] + [
    # Linting
    "autoflake",
    "flake8",
    "flake8-bugbear",
    "flake8-quotes",
    "isort",
    "black==22.10.0",
    "mypy>=0.982",
]

setup(
    name="torchlight",
    version=version,
    author="BotoX",
    author_email="github@botox.bz",
    description="Stream music and more for srcds games",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages("src", exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=True,
    python_requires=">=3.8",
    install_requires=dependencies,
    extras_require=extra_dependencies,
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
    ],
    entry_points={"console_scripts": ["torchlight=torchlight.cli:cli"]},
)
