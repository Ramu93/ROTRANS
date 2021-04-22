import pathlib
import setuptools

HERE = pathlib.Path(__file__).parent

setuptools.setup(
    name="abc_core",
    version="1.0",
    description="Implements the core abc protocol.",
    long_description_content_type="text/x-rst",
    classifiers=[
        "Distributed System",
        "Permissionless",
        "ABC",
        "Programming Language :: Python"
    ],
    install_requires=[
        'cryptography',
        'abc_network'
    ],
    packages=['abccore'],
    python_requires=">=3.8"
)
