from setuptools import setup, find_packages

setup(
    name="inventario_app",
    version="0.1.0",
    description="Sistema de gestión de inventario con Tkinter y SQLAlchemy",
    author="Gian Lucas San Martin",
    author_email="",
    url="https://github.com/stredes/inventario_app",  # opcional
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "SQLAlchemy>=2.0",
    ],
    entry_points={
        "console_scripts": [
            "inventario-app=main:main",  # permite ejecutar `inventario-app` en consola
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
)
