# CASTalign: Coppafish, Antibody Staining, and Two-photon alignment

CASTalign allows you to register 3D microscopy images to each other and to *in
vivo* two-photon imaging.  It is optimised to allow registration between
CoppaFISH 3D, antibody staining (e.g., immunofluorescence), and *in vivo*
imaging.

# Installation

To install:

    pip install castalign

You may also want to install (optional) GPU acceleration with cupy.  Depending
on the version of CUDA, install one of these:

    pip install cupy-cuda13x # For CUDA 13.x
    pip install cupy-cuda12x # Fox CUDA 12.x

Alternatively, you can install from github:

    pip install git+https://github.com/mwshinn/castalign.git

# Usage

See the [tutorial](https://castalign.readthedocs.io/en/latest/tutorial/) in the [documentation](https://castalign.readthedocs.io/en/latest/).
