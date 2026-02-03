# Tutorial

## Conceptual summary

There are three main components:

1. **[Transforms](api.md#transform)**.  A transform allows you to get from an input space to a target
   space through affine or nonlinear transforms.  It allows you to pass points
   or images from the input space to the target space.  For instance, a rotation
   matrix with a shift is an example of a [Transform](api.md#transform).  There are many included by
   default, but you can also create your own.  [Transforms](api.md#transform) can be composed and
   edited.  [Transforms](api.md#transform) are the foundation of this library.
2. **GUIs to create [Transforms](api.md#transform)**.  It can be difficult to find the correct
   parameters for a transform, so multiple GUIs can assist you.  The simplest
   one (([`alignment_gui()`](api.md#alignment_gui))) allows you to pass two volumes and a [Transform](api.md#transform),
   and then interactively use that [Transform](api.md#transform) to align the volumes.  A more
   advanced one ([`align_interactive()`](api.md#align_interactive)) allows you to align in steps by
   composing different [Transforms](api.md#transform) together.
3. **Graphs to manage networks of [Transforms](api.md#transform)**.  In many practical applications,
   you may need to align many different images to the same target image, or
   other complex relationships between images.  It can quickly become unwieldly
   to organise all of these [Transforms](api.md#transform) and their corresponding images.  [Graphs](api.md#graph)
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
system origin.  These objects are called "[ndarray_shifted](api.md#ndarray_shifted)".  If you do not care
about the shift, you can use them like a normal numpy array.

## [Transforms](api.md#transform)

A *[Transform](api.md#transform)* takes you from one coordinate space (the input space) to another
coordinate space (the target space).  The input is the "movable" image and the
target is the "base".  For instance, suppose you have a volumetric image , and a
second volumetric image rescaled to have uniform voxel size of 1um.  A [Transform](api.md#transform)
could map points or images between the raw and rescaled coordinate spaces.

There are many types of [Transforms](api.md#transform) included by default.  These fall into two
main categories:

- *Parameter-based Transforms* use parametric values to define the [Transform](api.md#transform).
  For instance, [TranslateFixed](api.md#translatefixed) is a parameter-based [Transform](api.md#transform) that receives an
  explicit z, y, and x shift.
- *Point-based Transforms* use a point cloud to define the [Transform](api.md#transform).  For
  point-based [Transforms](api.md#transform), you must define the starting and ending positions of
  several keypoints.  For instance, a [Translate](api.md#translate) will find the z, y, and x
  shifts that best fit the keypoints.  You can choose these keypoints from a
  gui.  Some point-based [Transforms](api.md#transform) may also include parameters, such as a
  smoothness hyperparameter or a normal vector along which the [Transform](api.md#transform) should
  occur.

**[Transforms](api.md#transform) are invertible.**  You can use the [`Transform.invert()`](api.md#transforminvert) function to perform
the inversion.  This occurs analytically for most [Transforms](api.md#transform).

**[Transforms](api.md#transform) may be specified or unspecified.**  A specified [Transform](api.md#transform) includes
values for each of its parameters, and matching point clouds if it is a
Point-based [Transform](api.md#transform).  This is represented by an instance of the class.  An
unspecified [Transform](api.md#transform) does not yet have chosen parameters or points, and is
represented by the uninsantiated class.  For instance,
``TranslateFixed(x=3,y=0,z=1)`` is specified, but ``TranslateFixed`` is
unspecified.  You cannot apply an unspecified [Transform](api.md#transform) to points or an image,
because you have not yet defined what the transform should do.  Unspecified
transforms can be made specified through the GUI, or by calling them with the
appropriate parameters.

**[Transforms](api.md#transform) are composable.**  If you have two [Transforms](api.md#transform), you can add them
together to get their composition.  For instance, the [Transform](api.md#transform) that first
applies [Transform](api.md#transform) A and then applied [Transform](api.md#transform) B can be written in Python as
`A + B`. Two specified [Transforms](api.md#transform) may be composed, and their composition gives
another specified [Transform](api.md#transform).  A specified and unspecified [Transform](api.md#transform) may also be
composed, but their composition gives an unspecified transform.  Currently, the
unspecified [Transform](api.md#transform) must be the final term in the sum.  Two unspecified
[Transforms](api.md#transform) cannot be composed.

**[Transforms](api.md#transform) are lossless.**  If you compose 
``Rescale(x=.5, y=.5, z=.5) + Rescale(x=2, y=2, z=2)`` 
and apply it to an image, the result will be identical
to your starting image, without the artifacts from resizing the image.  More
generally, under the hood, a long chain of composed transforms will all be
applied at once.

**All the information needed to save a [Transform](api.md#transform) comes from its text
representation.**  So, you can simply call "print" and then copy and paste it
somewhere, or save the text of the [Transform](api.md#transform) to a text file.  The string
representation is executable Python code that you can run to recreate your
[Transform](api.md#transform).  Nevertheless, there is also a [`Transform.save()`](api.md#transformsave)
function which does this for you.

### List of [Transforms](api.md#transform)

Different transforms are useful for different types of data.  For different
geometries of input (movable) images, different [Transforms](api.md#transform) may be advantageous.
Input images can be approximately one of three types:

- *Cake*: Approximately equally thick in all three dimensions.  For example, a
  three-dimensional z-stack.
- *Pancake*: Wide in two dimension, and somewhat thin (but not too thin) in the
  third dimension. For example, a histology section may be 10 mm in length and
  width, but only 0.1 mm in depth.
- *Rice paper*: A two-dimensional image, where the third dimension contains no
  useful information or does not exist at all (e.g. only one voxel thick). For
  example, a two-dimensional imaging plane.

[Transforms](api.md#transform) may be affine (linear) or non-linear.  Affine [Transforms](api.md#transform), under the
hood, use the equation ``points @ self.matrix + self.shift`` to transform
points.

While creating your own [Transform](api.md#transform) is easy, the following [Transforms](api.md#transform) are included
by default:



| Name                          | Cake | Pancake | Rice paper | Point-based | Invertable | Affine | Description                                                                       |
|-------------------------------|------|---------|------------|-------------|------------|--------|-----------------------------------------------------------------------------------|
| [Identity](api.md#identity)                      | X    | X       | X          |             | X          | X      | Do nothing                                                                        |
| [Translate](api.md#translate)                     | X    | X       | X          | X           | X          | X      | Translation                                                                       |
| [TranslateFixed](api.md#translatefixed)                | X    | X       | X          |             | X          | X      | Translation                                                                       |
| [TranslateRotate](api.md#translaterotate)               | X    | X       | X          | X           | X          | X      | Translation and rotation                                                          |
| [TranslateRotateFixed](api.md#translaterotatefixed)          | X    | X       | X          |             | X          | X      | Translation and rotation                                                          |
| [TranslateRotateRescale](api.md#translaterotaterescale)        | X    | †       |            | X           | X          | X      | Translation, rotation, rescaling                                                  |
| [TranslateRotateRescaleByPlane](api.md#translaterotaterescalebyplane) |      | X       | X          | X           | X          | X      | Translation, rotation, rescaling, independently for lowest-variance dimension     |
| [TranslateRotateRescaleFixed](api.md#translaterotaterescalefixed)   | X    | X       | X          |             | X          | X      | Translation, rotation, rescaling                                                  |
| [FlipFixed](api.md#flipfixed)                     | X    | X       | X          |             | X          | X      | Flip across an axis                                                               |
| [ShearFixed](api.md#shearfixed)                    | X    | X       | X          |             | X          | X      | Apply shear along a plane                                                         |
| [MatrixFixed](api.md#matrixfixed)                   | X    | X       | X          |             | X          | X      | Directly enter an augmented matrix                                                |
| [Rescale](api.md#rescale)                       | X    | X       | X          |             | X          | X      | Rescale, i.e. downsample or upsample (lossless)                                   |
| [Triangulation](api.md#triangulation)                 | X    |         |            | X           | X          |        | Perform piecewise affine transforms between a triangulation of the control points |
| [Triangulation2D](api.md#triangulation2d)               |      | X       | ‡          | X           | X          |        | Project to a 2D space, perform piecewise 2D transforms, and then return to 3D     |
| [DistanceWeightedAverageGaussian](api.md#distanceweightedaveragegaussian)       | X    | X       |            | X           |            |        | Compute a displacement field as a distance weighted average of control points     |


† It is possible to do a successful [TranslateRotateRescale](api.md#translaterotaterescale) with a pancake
geometry, but make sure to match at least one point at the top and bottom near
each of the four corners.  Otherwise, shear effects will dominate the transform.

‡ When using [Triangulation2D](api.md#triangulation2d) with a movable image that has a rice paper
geometry, it is generally more effective to set the rice paper image as the
target image when performing the alignment.

### Using a [Transform](api.md#transform)

There are two important methods:

- [`Transform.transform(points)`](api.md#transformtransform) will apply the transform to either a single
  point, or to a list of points.  If ``points`` is a matrix, there should be
  three columns, corresponding to z, y, and x.
- [`Transform.transform_image(im)`](api.md#transformtransform_image) will apply the transform to an image.  There
  are more arguments controlling how the image is generated, see the function
  documentation for more information.  The transformed image this function
  returns will be an "[ndarray_shifted](api.md#ndarray_shifted)", so if you plot it outside of the
  [Transform](api.md#transform) library, it may not appear to be aligned unless you shift it by the
  position of the origin.  See the function documentation for more information.

### Examples

As a simple example, let's consider [TranslateFixed](api.md#translatefixed).  Here we show how to
transform points, as well as perform a composition of two transforms.

``` python
import numpy as np
import castalign as ca

# Example 1
t1 = ca.TranslateFixed(x=3, y=4, z=5)
assert np.all(t1.transform([10, 20, 30]) == [15, 24, 33])
assert np.all(t1.transform([[10, 20, 30], [40, 50, 60]]) == [[15, 24, 33], [45, 54, 63]])

# Example 2
t2 = ca.TranslateFixed(z=1, y=1, x=1)
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
t = ca.TranslateRotateFixed(zrotate=30, x=60)
im_rotate = t.transform_image(im)

# Visualise the result
import napari
v = napari.Viewer()
v.add_image(im, blending="additive", colormap="Green")
v.add_image(im_rotate, translate=im_rotate.origin, blending="additive", colormap="Red")
```

We will show examples of point-based transforms once we explore the GUI.

## GUI

This library contains a GUI based on Napari that can be used to fit [Transforms](api.md#transform)
by hand, seeing the changes interactively as the [Transform](api.md#transform) is edited.  There are
two primary interactive functionalities of the GUI:

- Adjusting [Transform](api.md#transform) parameters
- Selecting points for point-based [Transforms](api.md#transform)

There are two ways to access the GUI.  The first, using the function
[`alignment_gui()`](api.md#alignment_gui), allows you to create or edit a single [Transform](api.md#transform).  If you
pass it an unspecified [Transform](api.md#transform), it will create a new specified [Transform](api.md#transform).  If
you pass it a specified transform, it will allow you to edit it.

The second function is [`align_interactive()`](api.md#align_interactive), which allows you to create
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

For [Transforms](api.md#transform) that involve translation, you can adjust this interactively using
drag-and-drop with the mouse.  Simply hold down the Ctrl key, and then you can
drag-and-drop the movable image.  Note that this is only available in Napari's
2D visualisation, not the 3D visualisation.  Also note that you will only see
the results of this if the "real-time" checkbox is selected.

### Selecting points for point-based [Transforms](api.md#transform)

First, click on the "Add point" button on the side panel.  The "base" layer will
be highlighted and the "movable" layer will fade into the background.  Select
the key point on this layer by left clicking.  Once you do, this will fade into
the background and the "movable" layer will be highlighted.  Left click to
select the keypoint on this layer.  Continue adding keypoints until you have a
sufficient number for your [Transform](api.md#transform), and then click "Perform transform" to
morph the movable image according to your [Transform](api.md#transform).

If the location of the keypoint is brighter than its surroundings, such as a
cell, you can right click instead of left click, and the location of peak
brightness near the cursor will be detected, and the keypoint will be placed here.

If you wish to revert to the original [Transform](api.md#transform), click the "revert" button.  The
keypoints will be saved, but the original [Transform](api.md#transform) will be applied, ignoring
the keypoints.  Note that the active transform displayed on the screen will be
the one returned, so if you revert before closing the window, the keypoints will
not be saved.  Likewise, if you do not click "perform transform" before closing,
the previously performed transform will be returned.


- *Adjusting parameters by directly setting their value.*  As soon as the value
  is changed, the display is updated, allowing the results to be
- *Adjusting the translation by dragging and dropping the movable image.*  This is
  accomplished by holding the Ctrl key while clicking and dragging.  This only works if the translatoi

### Examples using the GUI





### [Graphs](api.md#graph)

With most real-world data, many [Transforms](api.md#transform) will be needed, and all of these
[Transforms](api.md#transform) will relate to each other, possibly in complex ways.  It can quickly
become difficult to manage which [Transform](api.md#transform) takes you from which space to which
other space.  We can organise all of these [Transforms](api.md#transform) into a [Graph](api.md#graph).

A [Graph](api.md#graph) is an undirected graph of [Transforms](api.md#transform) from each space to each
other space.  Each space (e.g., image) is identified by a unique name, and is
represented by a node in the graph.  Each edge connecting the nodes in the graph
is a [Transform](api.md#transform).  To create a new node in a [Graph](api.md#graph) ``g``, run
[`g.add_node(node_name)`](api.md#graphadd_node).  To specify a [Transform](api.md#transform) between two nodes, i.e., an
edge, run [`g.add_edge(node1, node2, tform)`](api.md#graphadd_edge).

This library always uses the "from -> to" convention in the order of arguments.
So in the previous example, the [Transform](api.md#transform) ``tform`` converts points in space
``node1`` to the space ``node2``.  Or, equivalently, "movable image -> base
image", where ``node1`` is the movable image and ``node2`` is the base image.

To obtain the transform between two nodes, use the function
[`g.get_transform(node1, node2)`](api.md#graphget_transform).  Even if ``node1`` and ``node2`` are not
directly connected, the shortest path of [Transform](api.md#transform) compositions will be computed
and returned.  If two nodes have no connection, this will raise an error.

To visualise the structure of the graph, run [`g.visualise()`](api.md#graphvisualise).  For extremely
large graphs, you can use the "nearby" argument to specify a node, and the
visualisation will only include nodes directly connected to the given node.

Often, a [Graph](api.md#graph) may also contain the raw images themselves.  This is accomplished
by passing the "image" argument to [`g.add_node`](api.md#graphadd_node).  The images will be
aggressively compressed with minimal loss in quality through the use of video
codecs, with compression rates on high-resolution microscopy images often
approaching 100:1 or higher.

When images are included directly, several convenience methods can be used.
Most notably, the [`GraphViewer`](api.md#graphviewer) is a napari viewer that accepts node names as
image or label layers.  The base coordinate system is the first added image, and
all subsequent added images will be transformed into the space of first image.
If there is no path of [Transforms](api.md#transform) in the graph, adding the other images will
return an error.  Additionally, it allows using [`graph_alignment_gui`](api.md#graph_alignment_gui), a
shortcut version of [`alignment_gui()`](api.md#alignment_gui) that accepts node names instead of images.

### [ndarray_shifted](api.md#ndarray_shifted)

Normally you should not encounter [ndarray_shifted](api.md#ndarray_shifted) objects.  This is an internal data
storage which adds a origin offset to an NDArray.  This allows efficient
representation and modification of images which undergoes translation relative
to another image.
