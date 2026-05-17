# CASTalign

CASTalign (Coppafish, Antibody Staining, and Two-photon alignment) is a Python
library for registering 3D microscopy images to each other and to in vivo
two-photon imaging. It is optimized for aligning CoppaFISH 3D volumes, antibody
staining (e.g., immunofluorescence), and in vivo imaging.

CASTalign is described in the coppaFISH 3D preprint:
[Prankerd and Shinn et al., 2026](https://doi.org/10.64898/2026.05.15.725413).

## Main features

- Align images across modalities with shared, composable transforms.
- Edit and fit transforms using interactive Napari GUIs.
- Organize many transforms and images with a graph-based workflow.

## Quick Start

Install with `pip`:

```bash
pip install castalign
```

Then follow the [tutorial](tutorial) to learn how transforms, GUIs, and graphs fit together.

## Documentation Map

- [Tutorial](tutorial): Conceptual overview, examples, and GUIs.
- [Transforms Gallery](transforms_gallery): Visual transform examples with geometry and parameter defaults.
- [FAQs](faqs): FAQs
- [Citation](citation): Paper citation and BibTeX.
- [API Reference](api): Public classes and functions.
- [Contact](contact.md): Questions, bugs, and feedback.

```{toctree}
:maxdepth: 2
:caption: Contents

self
tutorial
Tutorial Video <https://www.youtube.com/watch?v=iE1r0Dmu-ok>
transforms_gallery
faqs
citation
api
contact
```
