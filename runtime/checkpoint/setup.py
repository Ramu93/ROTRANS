import pathlib
import setuptools

HERE = pathlib.Path(__file__).parent


setuptools.setup(
    name="abc_checkpoint",
    version="1.0",
    description="Implements the checkpoint layer of the abc protocol.",
    long_description_content_type="text/x-rst",
    author="Akhila Jose,Amit Kumar",
    author_email="akhilaj@mail.upb.de",
    classifiers=[
        "ABC",
        "Programming Language :: Python"
    ],
    install_requires=[
        'cryptography',
        'scipy',
        'abc_network'
    ],
    packages=['abcckpt'],
    python_requires=">=3.8"
)
