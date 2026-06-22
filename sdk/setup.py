"""
VaultWatch Python SDK — PyPI package setup.
"""

from setuptools import setup, find_packages

setup(
    name="vaultwatch",
    version="4.0.0",
    description="DeFi Risk Intelligence on Casper — Python SDK",
    long_description=open("../README.md", encoding="utf-8").read() if __import__("os").path.exists("../README.md") else "",
    long_description_content_type="text/markdown",
    author="VaultWatch",
    author_email="dev@vaultwatch.io",
    url="https://github.com/sodiq-code/vaultwatch",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "full": [
            "groq>=0.11.0",
            "opentelemetry-api>=1.25.0",
            "opentelemetry-sdk>=1.25.0",
            "fastapi>=0.111.0",
            "uvicorn>=0.30.0",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
    ],
    keywords="casper defi risk intelligence blockchain sdk vaultwatch",
)
