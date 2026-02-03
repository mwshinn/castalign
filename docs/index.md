# CASTalign

CASTalign (Coppafish, Antibody Staining, and Two-photon alignment) is a Python
library for registering 3D microscopy images to each other and to in vivo
two-photon imaging. It is optimized for aligning CoppaFISH 3D volumes, antibody
staining (e.g., immunofluorescence), and in vivo imaging.

## Main features

- Align images across modalities with shared, composable transforms.
- Edit and fit transforms using interactive Napari GUIs.
- Organize many transforms and images with a graph-based workflow.

## Quick Start

Install dependencies:

```bash
pip install numpy scipy napari magicgui vispy scikit-image imageio imageio-ffmpeg
```

Then follow the [tutorial](tutorial) to learn how transforms, GUIs, and graphs fit together.

## Documentation Map

- [Tutorial](tutorial.md): Conceptual overview, examples, and GUIs.
- [API Reference](api.md): Public classes and functions.
- [Contact](contact.md): Questions, bugs, and feedback.

