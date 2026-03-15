"""Package setup for CodeDebt Guardian."""
from setuptools import setup, find_packages

setup(
    name="codedebt-guardian",
    version="1.0.0",
    description="AI-Powered Multi-Agent System for Technical Debt Detection & Remediation",
    author="Priyansh Jain",
    license="MIT",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.10",
    install_requires=[
        "google-generativeai>=0.8.0",
        "requests>=2.32.0",
        "python-dotenv>=1.0.0",
        "streamlit>=1.41.0",
        "plotly>=5.24.0",
        "pandas>=2.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-cov>=6.0.0",
            "ruff>=0.8.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "codedebt=main:main",
        ]
    },
)
