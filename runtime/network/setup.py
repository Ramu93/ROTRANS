import pathlib
import setuptools

HERE = pathlib.Path(__file__).parent


setuptools.setup(
    name="abc_network",
    version="2.8",
    description="Implements the network layer of the abc protocol.",
    long_description_content_type="text/x-rst",
    author="Amin Faez",
    author_email="aminfaez@mail.upb.de",
    classifiers=[
        "Distributed System",
        "Permissionless",
        "Network",
        "ABC",
        "Programming Language :: Python"
    ],
    install_requires=[
        'cryptography',
        'pyzmq',
        'pyyaml'
    ],
    packages=['abcnet'],
    python_requires=">=3.8"
)
