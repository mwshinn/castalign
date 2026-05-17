from setuptools import setup, Extension

with open("castalign/_version.py", "r") as f:
    exec(f.read())

with open("README.md", "r") as f:
    long_desc = f.read()


setup(
    name = "castalign",
    version = __version__,
    description =  "Coppafish, Antibody Staining, and Two-photon alignment: 3D alignment framework for microscopy and in vivo imaging",
    long_description = long_desc,
    long_description_content_type='text/markdown',
    author = 'Max Shinn',
    author_email = 'm.shinn@ucl.ac.uk',
    maintainer = 'Max Shinn',
    maintainer_email = 'm.shinn@ucl.ac.uk',
    license = 'MIT',
    python_requires='>=3.7',
    url='https://github.com/mwshinn/castalign',
    project_urls={
        'Publication': 'https://doi.org/10.64898/2026.05.15.725413',
        'Documentation': 'https://castalign.readthedocs.io/en/latest/',
    },
    packages = ['castalign'],
    install_requires = ["numpy", "scipy", "napari", "magicgui", "scikit-image", "imageio", "imageio-ffmpeg", "threadpoolctl", "pyqt5"],
    classifiers = [
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Multimedia :: Graphics",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
    ]
)
