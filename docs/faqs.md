# Frequently asked questions

## Why is the "Perform transform" button in the GUI slower than I expect?

The primary reason the CASTalign alignment GUI will be slow is if **the movable
image is very large or has many layers.**  Large images, or images with many
layers, require lots of processing to be performed each time "Perform transform"
is clicked.  Large images require more RAM to store the images, as well as more
compute power to perform the transform for each voxel.

However, we can make this faster by reducing how much data is rendered during
alignment without changing the final transform output. Use the `crop` argument
in <a href="api_gui.html#castalign.gui.alignment_gui"><code>alignment_gui(..., crop=...)</code></a> or <a href="api_gui.html#castalign.gui.align_interactive"><code>align_interactive(..., crop=...)</code></a>.

For example,

```python
t = ca.gui.alignment_gui(movable, base, transform=ca.RigidParametric, crop=True)
```

`crop` only affects preview/render speed and memory use; the resulting
transform still applies to the full image.

Another speedup is to align in downsampled coordinate spaces and then map the
result back to full resolution:

```python
s = ca.RescaleParametric(z=0.5, y=0.5, x=0.5)
g.add_node("movable_ds", image="movable_full")
g.add_node("base_ds", image="base_full")
g.add_edge("movable_full", "movable_ds", s)
g.add_edge("base_full", "base_ds", s)
t_ds = ca.gui.align_interactive("movable_ds", "base_ds", graph=g)
t_full = s + t_ds + s.invert()
```

Here `t_full` is the transform to apply to the original full-resolution images.

Another reason why CASTalign may be slow is if you are using a **non-linear
triangulation with many control points** (<a href="api_transforms.html#castalign.base.Triangulation"><code>Triangulation</code></a> / <a href="api_transforms.html#castalign.base.LaminarTriangulation"><code>LaminarTriangulation</code></a>).  This can only be fixed by reducing
the number of control points.

A final reason why CASTalign may be slower than expected is if
**GPU-acceleration is unavailable**.  While CASTalign is still relatively fast
on the CPU, it should be about 2-3x faster if cupy is available.  You can check
whether GPU acceleration is available with:

```python
>>> import castalign as ca
>>> print("Yes" if ca.base.GPU_AVAILABLE else "No")
```

If it is not available, install CuPy and check their documentation to ensure it
can find your GPU.
