# Tutorial

## Conceptual summary

There are three main components:

1. **<a href="api_transforms.html">Transforms</a>**.  A transform allows you to get from an input space to a target
   space through affine or nonlinear transforms.  It allows you to pass points
   or images from the input space to the target space.  For instance, a rotation
   matrix with a shift is an example of a <a href="api_transforms.html#castalign.base.Transform">Transform</a>.  There are many included by
   default, but you can also create your own.  Transforms can be composed and
   edited.  Transforms are the foundation of this library.
2. **GUIs to create transforms**.  It can be difficult to find the correct
   parameters for a transform, so multiple GUIs can assist you.  The simplest
   one (<a href="api_gui.html#castalign.gui.alignment_gui"><code>alignment_gui()</code></a>) allows you to pass two volumes and a Transform,
   and then interactively use that Transform to align the volumes.  A more
   advanced one (<a href="api_gui.html#castalign.gui.align_interactive"><code>align_interactive()</code></a>) allows you to align in steps by
   composing different transforms together.
3. **<a href="api_graphs.html">Graphs</a> to manage networks of transforms**.  In many practical applications,
   you may need to align many different images to the same target image, or
   other complex relationships between images.  It can quickly become unwieldly
   to organise all of these transforms and their corresponding images.  <a href="api_graphs.html">Graphs</a>
   make it easy to keep everything organised.  Several convenience methods are
   included for aligning within a graph.

CASTalign always uses (z,y,x) coordinate format.  Likewise, images are
expected to have the z position as its first coordinate, y as its second, and x
as its third.  The point (5,6,7) on an image ``im`` will be at the voxel
``im[5,6,7]``.  Note that when displaying images, as is the convention in
Python, the origin is shown at the top left of the screen, and positive y values
indicate closer to the bottom of the screen.  This format is compatible with
nearly all other Python image libraries, and so usually you should not need to
think about this.

CASTalign also uses an extension on numpy ndarrays to specify a coordinate
system origin.  These objects are called "<a href="api_shifted_arrays.html#castalign.ndarray_shifted.ndarray_shifted">ndarray_shifted</a>".  If you do not care
about the shift, you can use them like a normal numpy array.

## Transforms

A *<a href="api_transforms.html#castalign.base.Transform">Transform</a>* takes you from one coordinate space (the input space) to another
coordinate space (the target space).  The input is the "movable" image and the
target is the "base".  For instance, suppose you have a volumetric image , and a
second volumetric image rescaled to have uniform voxel size of 1um.  A Transform
could map points or images between the raw and rescaled coordinate spaces.

There are many types of transforms included by default.  These fall into two
main categories:

- *Parameter-based Transforms* use parametric values to define the Transform.
  For instance, <a href="api_transforms.html#castalign.base.TranslateParametric">TranslateParametric</a> is a parameter-based transform that receives an
  explicit z, y, and x shift.
- *Point-based Transforms* use a point cloud to define the Transform.  For
  point-based transforms, you must define the starting and ending positions of
  several keypoints.  For instance, a <a href="api_transforms.html#castalign.base.Translate">Translate</a> will find the z, y, and x
  shifts that best fit the keypoints.  You can choose these keypoints from a
  gui.  Some point-based transforms may also include parameters, such as a
  smoothness hyperparameter or a normal vector along which the Transform should
  occur.

**Transforms are invertible.**  You can use the <a href="api_transforms.html#castalign.base.Transform.invert"><code>Transform.invert()</code></a> function to perform
the inversion.  This occurs analytically for most transforms.

**Transforms may be specified or unspecified.**  A specified Transform includes
values for each of its parameters, and matching point clouds if it is a
Point-based Transform.  This is represented by an instance of the class.  An
unspecified Transform does not yet have chosen parameters or points, and is
represented by the uninsantiated class.  For instance,
``TranslateParametric(x=3,y=0,z=1)`` is specified, but ``TranslateParametric`` is
unspecified.  You cannot apply an unspecified Transform to points or an image,
because you have not yet defined what the transform should do.  Unspecified
transforms can be made specified through the GUI, or by calling them with the
appropriate parameters.

**Transforms are composable.**  If you have two transforms, you can add them
together to get their composition.  For instance, the Transform that first
applies Transform A and then applied Transform B can be written in Python as
`A + B`. Two specified transforms may be composed, and their composition gives
another specified Transform.  A specified and unspecified Transform may also be
composed, but their composition gives an unspecified transform.  Currently, the
unspecified Transform must be the final term in the sum.  Two unspecified
transforms cannot be composed.

**Transforms are lossless.**  If you compose 
``RescaleParametric(x=.5, y=.5, z=.5) + RescaleParametric(x=2, y=2, z=2)`` 
and apply it to an image, the result will be identical
to your starting image, without the artifacts from resizing the image.  More
generally, under the hood, a long chain of composed transforms will all be
applied at once.

**All the information needed to save a Transform comes from its text
representation.**  So, you can simply call "print" and then copy and paste it
somewhere, or save the text of the Transform to a text file.  The string
representation is executable Python code that you can run to recreate your
Transform.  Nevertheless, there is also a <a href="api_transforms.html#castalign.base.Transform.save"><code>Transform.save()</code></a>
function which does this for you.

### List of Transforms

Different transforms are useful for different types of data.  For different
geometries of input (movable) images, different transforms may be advantageous.
Input images can be approximately one of three types:

- *Cake*: Approximately equally thick in all three dimensions.  For example, a
  three-dimensional z-stack.
- *Pancake*: Wide in two dimension, and somewhat thin (but not too thin) in the
  third dimension. For example, a histology section may be 10 mm in length and
  width, but only 0.1 mm in depth.
- *Rice paper*: A two-dimensional image, where the third dimension contains no
  useful information or does not exist at all (e.g. only one voxel thick). For
  example, a two-dimensional imaging plane.

transforms may be affine (linear) or non-linear.  Affine transforms, under the
hood, use the equation ``points @ self.matrix + self.shift`` to transform
points.

While creating your own Transform is easy, the following transforms are included
by default:

See also the [Transforms Gallery](transforms_gallery) for visual examples and parameter/default summaries.

| Name | Cake | Pancake | Rice paper | Point-based | Affine |
|------|------|---------|------------|-------------|--------|
| <a href="api_transforms.html#castalign.base.Identity">Identity</a> | X | X | X |  | X |
| <a href="api_transforms.html#castalign.base.Translate">Translate</a> | X | X | X | X | X |
| <a href="api_transforms.html#castalign.base.TranslateParametric">TranslateParametric</a> | X | X | X |  | X |
| <a href="api_transforms.html#castalign.base.Rigid">Rigid</a> | X | X | X | X | X |
| <a href="api_transforms.html#castalign.base.RigidParametric">RigidParametric</a> | X | X | X |  | X |
| <a href="api_transforms.html#castalign.base.Affine">Affine</a> | X | † |  | X | X |
| <a href="api_transforms.html#castalign.base.AffineParametric">AffineParametric</a> | X | † |  |  | X |
| <a href="api_transforms.html#castalign.base.PlaneConstrainedAffine">PlaneConstrainedAffine</a> |  | X | X | X | X |
| <a href="api_transforms.html#castalign.base.FlipParametric">FlipParametric</a> | X | X | X |  | X |
| <a href="api_transforms.html#castalign.base.MatrixParametric">MatrixParametric</a> | X | X | X |  | X |
| <a href="api_transforms.html#castalign.base.RescaleParametric">RescaleParametric</a> | X | X | X |  | X |
| <a href="api_transforms.html#castalign.base.Triangulation">Triangulation</a> | X |  |  | X |  |
| <a href="api_transforms.html#castalign.base.PlaneConstrainedTriangulation">PlaneConstrainedTriangulation</a> |  | X | ‡ | X |  |


† It is possible to do a successful <a href="api_transforms.html#castalign.base.Affine">Affine</a> with a pancake
geometry, but make sure to match at least one point at the top and bottom near
each of the four corners.  Otherwise, shear effects will dominate the transform.

‡ When using <a href="api_transforms.html#castalign.base.PlaneConstrainedTriangulation">PlaneConstrainedTriangulation</a> with a movable image that has a rice paper
geometry, it is generally more effective to set the rice paper image as the
target image when performing the alignment.

### Using a Transform

There are two important methods:

- <a href="api_transforms.html#castalign.base.Transform.transform"><code>Transform.transform(points)</code></a> will apply the transform to either a single
  point, or to a list of points.  If ``points`` is a matrix, there should be
  three columns, corresponding to z, y, and x.
- <a href="api_transforms.html#castalign.base.Transform.transform_image"><code>Transform.transform_image(im)</code></a> will apply the transform to an image.  There
  are more arguments controlling how the image is generated, see the function
  documentation for more information.  The transformed image this function
  returns will be an "<a href="api_shifted_arrays.html#castalign.ndarray_shifted.ndarray_shifted">ndarray_shifted</a>", so if you plot it outside of the
  Transform library, it may not appear to be aligned unless you shift it by the
  position of the origin.  See the function documentation for more information.

### Examples

As a simple example, let's consider <a href="api_transforms.html#castalign.base.TranslateParametric">TranslateParametric</a>.  Here we show how to
transform points, as well as perform a composition of two transforms.

``` python
import numpy as np
import castalign as ca

# Example 1
t1 = ca.TranslateParametric(x=3, y=4, z=5)
assert np.all(t1.transform([10, 20, 30]) == [15, 24, 33])
assert np.all(t1.transform([[10, 20, 30], [40, 50, 60]]) == [[15, 24, 33], [45, 54, 63]])

# Example 2
t2 = ca.TranslateParametric(z=1, y=1, x=1)
t = t1 + t2
assert np.all(t.transform([10, 20, 30]) == [16, 25, 34])

# Example 3
t = t1 + ca.Identity()
assert np.all(t.transform([10, 20, 30]) == t1.transform([10, 20, 30]))
```

To transform an image, e.g., applying a rotation and a translation:

``` python
# Load example data
from skimage.data import cells3d
im = cells3d()[:,1]

# Define the Transform and apply it to the image
import castalign as ca
t = ca.RigidParametric(zrotate=30, x=60)
im_rotate = t.transform_image(im)

# Visualise the result
import napari
v = napari.Viewer()
v.add_image(im, blending="additive", colormap="Green")
v.add_image(im_rotate, translate=im_rotate.origin, blending="additive", colormap="Red")
```

We will show examples of point-based transforms once we explore the GUI.

## GUI

This library contains a GUI based on Napari that can be used to fit transforms
by hand, seeing the changes interactively as the Transform is edited.  There are
two primary interactive functionalities of the GUI:

- Adjusting Transform parameters
- Selecting points for point-based transforms

There are two ways to access the GUI.  The first, using the function
<a href="api_gui.html#castalign.gui.alignment_gui"><code>alignment_gui()</code></a>, allows you to create or edit a single Transform.  If you
pass it an unspecified Transform, it will create a new specified Transform.  If
you pass it a specified transform, it will allow you to edit it.

The second function is <a href="api_gui.html#castalign.gui.align_interactive"><code>align_interactive()</code></a>, which allows you to create
chains of composed transforms.  For example, it is often useful to perform a
manual translation or rotation before selecting keypoints for a point-based
transform, because it makes it easier to find the matching keypoints in both
images.


### Adjusting parameters

On the left-hand side pane of the Napari window, you will see some buttons and a
list of parameters, with text boxes or checkboxes to adjust their value.  If the
box "real-time" is selected, then every edit of these boxes will change the
value.  If real-time is not selected, you need to press the "Perform transform"
button after each edit.

For transforms that involve translation, you can adjust this interactively using
drag-and-drop with the mouse.  Simply hold down the Ctrl key, and then you can
drag-and-drop the movable image.  Note that this is only available in Napari's
2D visualisation, not the 3D visualisation.  Also note that you will only see
the results of this if the "real-time" checkbox is selected.

### Selecting points for point-based transforms

First, click on the "Add point" button on the side panel.  The "base" layer will
be highlighted and the "movable" layer will fade into the background.  Select
the key point on this layer by left clicking.  Once you do, this will fade into
the background and the "movable" layer will be highlighted.  Left click to
select the keypoint on this layer.  Continue adding keypoints until you have a
sufficient number for your Transform, and then click "Perform transform" to
morph the movable image according to your Transform.

If the location of the keypoint is brighter than its surroundings, such as a
cell, you can right click instead of left click, and the location of peak
brightness near the cursor will be detected, and the keypoint will be placed here.

If you wish to revert to the original Transform, click the "revert" button.  The
keypoints will be saved, but the original Transform will be applied, ignoring
the keypoints.  Note that the active transform displayed on the screen will be
the one returned, so if you revert before closing the window, the keypoints will
not be saved.  Likewise, if you do not click "perform transform" before closing,
the previously performed transform will be returned.


- *Adjusting parameters by directly setting their value.*  As soon as the value
  is changed, the display is updated, allowing the results to be
- *Adjusting the translation by dragging and dropping the movable image.*  This is
  accomplished by holding the Ctrl key while clicking and dragging.  This only works if the translatoi

### Examples using the GUI





### <a href="api_graphs.html">Graphs</a>

With most real-world data, many transforms will be needed, and all of these
transforms will relate to each other, possibly in complex ways.  It can quickly
become difficult to manage which Transform takes you from which space to which
other space.  We can organise all of these transforms into a <a href="api_graphs.html#castalign.graph.Graph">Graph</a>.

A <a href="api_graphs.html#castalign.graph.Graph">Graph</a> is an undirected graph of transforms from each space to each
other space.  Each space (e.g., image) is identified by a unique name, and is
represented by a node in the graph.  Each edge connecting the nodes in the graph
is a Transform.  To create a new node in a <a href="api_graphs.html#castalign.graph.Graph">Graph</a> ``g``, run
<a href="api_graphs.html#castalign.graph.Graph.add_node"><code>g.add_node(node_name)</code></a>.  To specify a Transform between two nodes, i.e., an
edge, run <a href="api_graphs.html#castalign.graph.Graph.add_edge"><code>g.add_edge(node1, node2, tform)</code></a>.

This library always uses the "from -> to" convention in the order of arguments.
So in the previous example, the Transform ``tform`` converts points in space
``node1`` to the space ``node2``.  Or, equivalently, "movable image -> base
image", where ``node1`` is the movable image and ``node2`` is the base image.

To obtain the transform between two nodes, use the function
<a href="api_graphs.html#castalign.graph.Graph.get_transform"><code>g.get_transform(node1, node2)</code></a>.  Even if ``node1`` and ``node2`` are not
directly connected, the shortest path of Transform compositions will be computed
and returned.  If two nodes have no connection, this will raise an error.

To visualise the structure of the graph, run <a href="api_graphs.html#castalign.graph.Graph.visualise"><code>g.visualise()</code></a>.  For extremely
large graphs, you can use the "nearby" argument to specify a node, and the
visualisation will only include nodes directly connected to the given node.

Often, a <a href="api_graphs.html#castalign.graph.Graph">Graph</a> may also contain the raw images themselves.  This is accomplished
by passing the "image" argument to <a href="api_graphs.html#castalign.graph.Graph.add_node"><code>g.add_node</code></a>.  The images will be
aggressively compressed with minimal loss in quality through the use of video
codecs, with compression rates on high-resolution microscopy images often
approaching 100:1 or higher.

When images are included directly, several convenience methods can be used.
Most notably, the <a href="api_gui.html#castalign.gui.GraphViewer"><code>GraphViewer</code></a> is a napari viewer that accepts node names as
image or label layers.  The base coordinate system is the first added image, and
all subsequent added images will be transformed into the space of first image.
If there is no path of transforms in the graph, adding the other images will
return an error.  Additionally, it allows using `graph_alignment_gui`, a
shortcut version of <a href="api_gui.html#castalign.gui.alignment_gui"><code>alignment_gui()</code></a> that accepts node names instead of images.

### <a href="api_shifted_arrays.html#castalign.ndarray_shifted.ndarray_shifted">ndarray_shifted</a>

Normally you should not encounter <a href="api_shifted_arrays.html#castalign.ndarray_shifted.ndarray_shifted">ndarray_shifted</a> objects.  This is an internal data
storage which adds a origin offset to an NDArray.  This allows efficient
representation and modification of images which undergoes translation relative
to another image.
