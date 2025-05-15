from setuptools import setup, find_packages

setup(
    name="LoQQueiPrintManager",
    version="2.0.0",
    author="LoQQuei",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "wxPython>=4.1.0",
        "requests>=2.28.0",
        "pillow>=9.0.0",
    ],
    extras_require={
        "dev": [
            "pyinstaller>=5.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "print_manager = main:main",
        ]
    },
)
