# API Reference

This page documents the public classes and functions in the `castalign` package. It follows the (z, y, x) coordinate convention described in the README, and images are expected to be shaped as `(z, y, x)` (or `(y, x)` for 2D inputs).

**Notes**

- When you see a type name like [Transform](#transform), [Graph](#graph), or [ndarray_shifted](#ndarray_shifted), it links to that type's entry in this file.
- Functions or methods that start with `_` are intentionally omitted.

## rotation_matrix
Perform a clockwise rotation (in degrees) about the z, y, and x axes.

**Arguments**

- `z` (float): Rotation in degrees about the z axis.
- `y` (float): Rotation in degrees about the y axis.
- `x` (float): Rotation in degrees about the x axis.

**Returns**

- `numpy.ndarray` of shape `(3, 3)`: The rotation matrix.

**Notes**

- This is used internally by several fixed-parameter transforms such as [TranslateRotateFixed](#translaterotatefixed) and [TranslateRotateRescaleFixed](#translaterotaterescalefixed).

## Transform
Base class for all transforms. A [Transform](#transform) maps points and images from a "movable" space into a "base" space. [Transform](#transform) instances can be composed with `+` and saved/loaded from text.

**Inherits**

- `object`

### Transform.__init__
Construct a transform, applying any DEFAULT_PARAMETERS and validating keyword arguments.

**Arguments**

- `**kwargs` (dict): Parameter values. Keys must match the class's `DEFAULT_PARAMETERS` dict.

**Returns**

- [Transform](#transform) instance.

**Notes**

- If the subclass defines `_fit`, it is called during construction.

### Transform.__repr__
Return a string representation that can be evaluated to reconstruct the transform.

**Returns**

- `str`: Executable constructor string.

### Transform.__eq__
Compare two transforms by their string representation.

**Arguments**

- `other` (any): The object to compare.

**Returns**

- `bool`: True if representations match.

### Transform.__add__
Compose this transform with another transform using `+`.

**Arguments**

- `other` ([Transform](#transform) or [Transform](#transform) subclass): The transform to apply after this one.

**Returns**

- A composed [Transform](#transform) (instance or class depending on inputs). See [compose_transforms](#compose_transforms).

### Transform.__call__
Apply the transform to points or an image depending on input shape.

**Arguments**

- `data` (array-like): If a shape of `(3,)` or `(N, 3)` is detected, it is treated as points. Otherwise it is treated as an image.
- `*args, **kwargs`: Passed to the underlying `transform` or `transform_image` method.

**Returns**

- `numpy.ndarray` or [ndarray_shifted](#ndarray_shifted): Transformed points or image.

### Transform.save
Save the transform's `repr` text to a file.

**Arguments**

- `filename` (str or path-like): File to write.

**Returns**

- `None`.

### Transform.load
Load a transform from a file created by `save` or by writing a transform's `repr` text.

**Arguments**

- `filename` (str or path-like): File to read.

**Returns**

- [Transform](#transform) instance.

### Transform.transform
Apply the forward mapping to points.

**Arguments**

- `points` (array-like): Either a single point `(3,)` or a matrix `(N, 3)`.

**Returns**

- `numpy.ndarray`: Transformed points with the same shape as input.

**Notes**

- Points must be in (z, y, x) order.

### Transform.inverse_transform
Apply the inverse mapping to points.

**Arguments**

- `points` (array-like): Either a single point `(3,)` or a matrix `(N, 3)`.

**Returns**

- `numpy.ndarray`: Inversely transformed points.

**Notes**

- The default implementation uses `invert().transform(points)`; subclasses can override for efficiency.

### Transform.invert
Return an inverse transform.

**Returns**

- [Transform](#transform): An inverse transform.

### Transform.origin_and_maxpos
Compute the output image bounding box after a transform.

**Arguments**

- `img` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted)): Input image.
- `output_size` (None, tuple, or list):
- If `None`, a tight bounding box is used.
- If `(z, y, x)` integers, an output size is enforced.
- If `((zmin, zmax), (ymin, ymax), (xmin, xmax))`, those bounds are used.
- `force_size` (bool): If False, treats `output_size` as a maximum bounding box and may shrink for efficiency.

**Returns**

- `(origin, maxpos)` tuple of `numpy.ndarray` values with dtype `float32`.

### Transform.transform_image
Apply the transform to an image.

**Arguments**

- `img` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted)): 2D `(y, x)` or 3D `(z, y, x)` image.
- `output_size` (None, tuple, or list): See [Transform.origin_and_maxpos](#transformorigin_and_maxpos).
- `labels` (bool or None): If True, uses nearest-neighbor interpolation. If None, auto-detects labels via [image_is_label](#image_is_label).
- `force_size` (bool): If False, treats `output_size` as a maximum bounding box.

**Returns**

- [ndarray_shifted](#ndarray_shifted): The transformed image with origin metadata.

**Notes**

- For `ndarray_shifted` inputs, an internal [TranslateFixed](#translatefixed) is used to adjust non-zero origins.

### Transform.pretransform
Return a fixed transform to apply before fitting this transform.

**Returns**

- [Identity](#identity): The default implementation.

## PointTransform
Transform defined by matching corresponding point sets for a [Transform](#transform).

**Inherits**

- [Transform](#transform)

### PointTransform.__init__
Construct a point-based transform.

**Arguments**

- `points_start` (array-like): Source points shaped `(N, 3)`.
- `points_end` (array-like): Target points shaped `(N, 3)`.
- `**kwargs`: Optional parameters defined in `DEFAULT_PARAMETERS`.

**Returns**

- [PointTransform](#pointtransform) instance.

**Notes**

- `points_start` and `points_end` must have the same shape.

### PointTransform.from_transform
Construct a point-based transform using the points from an existing transform.

**Arguments**

- `transform` ([Transform](#transform)): Source transform with `points_start` and `points_end`.
- `*args, **kwargs`: Passed to the class constructor.

**Returns**

- A new instance of the class.

### PointTransform.__repr__
Return a string representation including point lists and parameters.

**Returns**

- `str`.

## AffineTransform
Mixin providing affine behavior for point-based transforms.

**Inherits**

- `object` (intended to be combined with [PointTransform](#pointtransform))

### AffineTransform.transform_image
Optimized image transformation for affine transforms.

**Arguments**

- `image` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted))
- `output_size`, `labels`, `force_size`: See [Transform.transform_image](#transformtransform_image).

**Returns**

- [ndarray_shifted](#ndarray_shifted) or `numpy.ndarray`: Transformed image.

### AffineTransform.invert
Return an inverse affine transform by swapping points.

**Returns**

- Instance of the same class.

**Notes**

- This assumes an affine mapping and may be incorrect for non-affine subclasses.

## PointTransformNoInverse
Point-based transform without an analytic inverse. Uses numerical inversion.

**Inherits**

- [PointTransform](#pointtransform)

### PointTransformNoInverse.__init__
Construct with numerical inverse support.

**Arguments**

- `*args, **kwargs`: Passed to [PointTransform](#pointtransform).

**Returns**

- Instance.

### PointTransformNoInverse.transform
Apply the transform, numerically inverting if necessary.

**Arguments**

- `points` (array-like): `(N, 3)` or `(3,)` points.

**Returns**

- `numpy.ndarray`: Transformed points.

**Notes**

- If `params["invert"]` is False, this numerically inverts and is slow for large point sets (raises for >1000 points).

### PointTransformNoInverse.invert
Return an inverted version of this transform, toggling the `invert` parameter.

**Returns**

- Instance of the same class.

## TranslateRotate
Translate and rotate using point matches (SVD-based).

**Inherits**

- [AffineTransform](#affinetransform)
- [PointTransform](#pointtransform)

### TranslateRotate.__init__
Uses [PointTransform](#pointtransform) construction.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).

**Returns**

- Instance.

## TranslateRotateRescaleByPlane
Translate, rotate, and rescale using a dominant plane (good for "pancake" images).

**Inherits**

- [AffineTransform](#affinetransform)
- [PointTransform](#pointtransform)

### TranslateRotateRescaleByPlane.__init__
Uses [PointTransform](#pointtransform) construction plus `invert` parameter.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).
- `invert` (bool, default False): If True, swaps the regression direction and matrix inversion.

**Returns**

- Instance.

## TranslateRotateRescale
Translate, rotate, and rescale using full 3D regression.

**Inherits**

- [AffineTransform](#affinetransform)
- [PointTransform](#pointtransform)

### TranslateRotateRescale.__init__
Uses [PointTransform](#pointtransform) construction plus `invert` parameter.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).
- `invert` (bool, default False): If True, swaps regression direction and inverts the matrix.

**Returns**

- Instance.

## TranslateRotate2D
Deprecated. Translate and rotate in 2D only.

**Inherits**

- [AffineTransform](#affinetransform)
- [PointTransform](#pointtransform)

## Translate
Translate using point matches.

**Inherits**

- [AffineTransform](#affinetransform)
- [PointTransform](#pointtransform)

### Translate.__init__
Uses [PointTransform](#pointtransform) construction.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).

**Returns**

- Instance.

## Flip
Deprecated. Flip along axes using parameters.

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### Flip.__init__
Construct a flip transform.

**Arguments**

- `z`, `y`, `x` (bool): Whether to flip along each axis.
- `zthickness`, `ythickness`, `xthickness` (float or int): Axis sizes used to compute the shift when flipping.

**Returns**

- Instance.

## FlipFixed
Flip along axes using fixed parameters (non-point-based).

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### FlipFixed.__init__
Construct a flip transform.

**Arguments**

- `z`, `y`, `x` (bool): Whether to flip along each axis.
- `zthickness`, `ythickness`, `xthickness` (float or int): Axis sizes used to compute the shift when flipping.

**Returns**

- Instance.

## TranslateFixed
Translate using fixed parameters (non-point-based).

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### TranslateFixed.__init__
Construct a fixed translation transform.

**Arguments**

- `z`, `y`, `x` (float): Translation offsets.

**Returns**

- Instance.

## TranslateRotateFixed
Translate and rotate using fixed parameters (non-point-based).

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### TranslateRotateFixed.__init__
Construct a fixed translate+rotate transform.

**Arguments**

- `z`, `y`, `x` (float): Translation offsets.
- `zrotate`, `yrotate`, `xrotate` (float): Rotation angles in degrees.
- `invert` (bool): If True, uses the transpose of the rotation matrix.

**Returns**

- Instance.

## TranslateRotateRescaleFixed
Translate, rotate, and rescale using fixed parameters (non-point-based).

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### TranslateRotateRescaleFixed.__init__
Construct a fixed translate+rotate+rescale transform.

**Arguments**

- `z`, `y`, `x` (float): Translation offsets.
- `zrotate`, `yrotate`, `xrotate` (float): Rotation angles in degrees.
- `zscale`, `yscale`, `xscale` (float): Scale factors. Must be non-zero to allow inversion.
- `invert` (bool): If True, inverts the combined matrix.

**Returns**

- Instance.

## TranslateRotateRescale2DFixed
Deprecated. Translate, rotate, and rescale in 2D only.

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### TranslateRotateRescale2DFixed.__init__
Construct a 2D fixed transform.

**Arguments**

- `y`, `x` (float): Translation offsets in the 2D plane.
- `rotate` (float): Rotation angle in degrees.
- `scale` (float): Scale factor. Must be non-zero to allow inversion.

**Returns**

- Instance.

## ShearFixed
Apply a shear transform using fixed parameters.

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### ShearFixed.__init__
Construct a shear transform.

**Arguments**

- `yzshear`, `xzshear`, `xyshear` (float): Shear coefficients.

**Returns**

- Instance.

**Notes**

- `Shear` is an alias of `ShearFixed`.

## MatrixFixed
Apply a direct 3x3 transformation matrix plus translation.

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### MatrixFixed.__init__
Construct a transform from explicit matrix elements and translation.

**Arguments**

- `a11`..`a33` (float): Elements of the 3x3 matrix in row-major order.
- `x`, `y`, `z` (float): Translation offsets.

**Returns**

- Instance.

**Notes**

- This does not validate matrix properties. Use with care.

## Identity
No-op transform.

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### Identity.__init__
Construct an identity transform.

**Arguments**

- None.

**Returns**

- Instance.

### Identity.transform_image
More efficient image transformation that returns the original image when possible.

**Arguments**

- `image`, `output_size`, `labels`, `force_size`: See [Transform.transform_image](#transformtransform_image).

**Returns**

- The original image or a transformed image if `output_size` is specified.

## Rescale
Uniform or axis-specific rescaling.

**Inherits**

- [AffineTransform](#affinetransform)
- [Transform](#transform)

### Rescale.__init__
Construct a rescale transform.

**Arguments**

- `z`, `y`, `x` (float): Scale factors. Must be non-zero to allow inversion.

**Returns**

- Instance.

## Triangulation
Piecewise affine transform based on a 3D Delaunay triangulation.

**Inherits**

- [PointTransform](#pointtransform)

### Triangulation.__init__
Construct a triangulation transform.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).
- `invert` (bool, default True): Start in inverse mode because inverse is faster for images.

**Returns**

- Instance.

## Triangulation2D
Piecewise affine transform in a projected 2D space.

**Inherits**

- [PointTransform](#pointtransform)

### Triangulation2D.__init__
Construct a triangulation transform with an optional fixed normal vector.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).
- `invert` (bool, default True): Start in inverse mode for image efficiency.
- `normal_z`, `normal_y`, `normal_x` (float): If all are zero, the normal is auto-detected.

**Returns**

- Instance.

## DistanceWeightedAverageGaussian
Deprecated. Nonlinear, numerically inverted transform using a Gaussian distance-weighted average.

**Inherits**

- [PointTransformNoInverse](#pointtransformnoinverse)

### DistanceWeightedAverageGaussian.__init__
Construct the transform.

**Arguments**

- `points_start`, `points_end`: See [PointTransform.__init__](#pointtransform__init__).
- `extent` (float): Gaussian standard deviation. Should be positive.
- `invert` (bool, default False): Controls inversion behavior in [PointTransformNoInverse](#pointtransformnoinverse).

**Returns**

- Instance.

## compose_transforms
Compose two transforms or a transform and a transform class.

**Arguments**

- `a` ([Transform](#transform)): A specified transform instance.
- `b` ([Transform](#transform) instance or subclass): The transform to apply after `a`.

**Returns**

- A composed transform instance or a composed transform class.

**Notes**

- If `a` or `b` is [Identity](#identity), it returns the other without extra composition.
- Composition is also available via [Transform.__add__](#transform__add__).

## Graph
[Graph](#graph) structure for managing nodes (images) and transforms between them.

**Inherits**

- `object`

**Notes**

- [TransformGraph](#graph) is an alias of [Graph](#graph) for backward compatibility (from `castalign.graph`).

### Graph.__init__
Create an empty graph.

**Arguments**

- `name` (str): Optional graph name.

**Returns**

- [Graph](#graph) instance.

### Graph.__eq__
Compare graphs by name, nodes, edges, and which nodes have images loaded (not the image data).

**Arguments**

- `other` (any): The object to compare.

**Returns**

- `bool`.

### Graph.__getitem__
Convenience access for images and transforms.

**Arguments**

- `item` (str): Returns `get_image(item)`.
- `item` (slice): If `item.start` and `item.stop` are node names, returns `get_transform(start, stop)`.

**Returns**

- `numpy.ndarray` or [ndarray_shifted](#ndarray_shifted) for images.
- [Transform](#transform) for transforms.

### Graph.__setitem__
Convenience assignment for images and transforms.

**Arguments**

- `name` (str): Calls `add_node(name, image=value)`.
- `name` (slice): Calls `add_edge(start, stop, value)`.

**Returns**

- `None`.

### Graph.__delitem__
Delete nodes or edges via indexing.

**Arguments**

- `name` (str): Calls `remove_node(name)`.
- `name` (slice): Calls `remove_edge(start, stop)`.

**Returns**

- `None`.

### Graph.__contains__
Check if a node or edge exists.

**Arguments**

- `item` (str): Returns True if node exists.
- `item` (tuple/list of length 2): Returns True if edge exists.

**Returns**

- `bool`.

### Graph.save
Persist the graph to disk as a SQLite `.db` file.

**Arguments**

- `filename` (str or path-like, optional): Output file path. If missing, uses `self.filename`.

**Returns**

- `None`.

**Notes**

- If `filename` has no extension, `.db` is appended.
- Saving to `.npz` is no longer supported.
- If a different `filename` is provided and `self.filename` already exists, it copies first and then updates.

### Graph.load
Load a graph from `.db` or legacy `.npz`.

**Arguments**

- `filename` (str or path-like): File to read.

**Returns**

- [Graph](#graph) instance.

### Graph.add_node
Add a node, optionally with an image or a reference to another node's image.

**Arguments**

- `name` (str): New node name. Must be unique.
- `image` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str, optional): Image data or a node name to reference.
- `compression` (str): One of `low`, `normal`, `high` for image compression.
- `metadata` (any, optional): Node metadata stored in `node_metadata`.

**Returns**

- `None`.

### Graph.remove_node
Remove a node and its edges.

**Arguments**

- `name` (str): Node name.

**Returns**

- `None`.

### Graph.replace_node_image
Replace or remove a node's image without changing edges.

**Arguments**

- `name` (str): Node name.
- `image` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str, optional): New image or reference node.
- `compression` (str): One of `low`, `normal`, `high`.

**Returns**

- `None`.

### Graph.add_edge
Add or update a transform edge between nodes.

**Arguments**

- `frm` (str): Source node name.
- `to` (str): Destination node name.
- `transform` ([Transform](#transform)): Transform from `frm` to `to`.
- `update` (bool): If False, edge must not exist. If True, edge must already exist.

**Returns**

- `None`.

**Notes**

- Automatically adds the inverse edge using `transform.invert()`.

### Graph.remove_edge
Remove a transform edge.

**Arguments**

- `frm` (str): Source node name.
- `to` (str): Destination node name.

**Returns**

- `None`.

### Graph.connected_components
Compute connected components of the graph.

**Returns**

- `list` of `set` of node names.

### Graph.unload
Unload in-memory images to free memory, keeping compressed forms on disk.

**Returns**

- `None`.

### Graph.get_chain
Find a transform path between nodes.

**Arguments**

- `frm` (str): Source node name.
- `to` (str): Destination node name.

**Returns**

- `tuple` of node names representing the path.

### Graph.get_transform
Get a composed transform from `frm` to `to`.

**Arguments**

- `frm` (str): Source node name.
- `to` (str): Destination node name.

**Returns**

- [Transform](#transform).

### Graph.has_transform
Check whether a transform exists between two nodes.

**Arguments**

- `frm` (str): Source node name.
- `to` (str): Destination node name.

**Returns**

- `bool`.

### Graph.get_image
Get a node's image, loading and decompressing if necessary.

**Arguments**

- `node` (str): Node name.

**Returns**

- `numpy.ndarray` or [ndarray_shifted](#ndarray_shifted).

### Graph.visualise
Render the graph using `graphviz`.

**Arguments**

- `filename` (str, optional): Output filename. If None, uses a temp file.
- `nearby` (str, optional): If provided, only shows edges incident to this node.

**Returns**

- `None`.

**Notes**
- Requires the `graphviz` Python package.

## load
Load either a [Graph](#graph) or a [Transform](#transform) from a file.

**Arguments**

- `fn` (str or path-like): File path.

**Returns**

- [Graph](#graph) or [Transform](#transform).

## GraphViewer
Napari viewer subclass that can render nodes and transforms from a [Graph](#graph).

**Inherits**

- `napari.Viewer`

### GraphViewer.__init__
Construct a viewer bound to a graph.

**Arguments**

- `graph` ([Graph](#graph))
- `space` (str, optional): If set, the viewer shows everything in this space.
- `*args, **kwargs`: Passed to `napari.Viewer`.

**Returns**

- Instance.

### GraphViewer.add_image
Add an image layer, optionally transforming into the viewer space.

**Arguments**

- `data` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str): Image or node name.
- `space` (str, optional): The image's coordinate space.
- `name` (str, optional): Layer name.
- `**kwargs`: Passed to `napari.Viewer.add_image`.

**Returns**

- `napari.layers.Image`.

### GraphViewer.add_labels
Add a labels layer, optionally transforming into the viewer space.

**Arguments**

- `data` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str): Label image or node name.
- `space` (str, optional): The label image's coordinate space.
- `name` (str, optional): Layer name.
- `**kwargs`: Passed to `napari.Viewer.add_labels`.

**Returns**

- `napari.layers.Labels`.

### GraphViewer.add_points
Add a points layer, transforming to viewer space if needed.

**Arguments**

- `data` (array-like): Points in (z, y, x) order.
- `space` (str, optional): The points' coordinate space.
- `**kwargs`: Passed to `napari.Viewer.add_points`.

**Returns**

- `napari.layers.Points`.

## alignment_gui
Interactive GUI to create or edit a single transform using Napari.

**Arguments**

- `movable_image` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str, or tuple/list of those): Image(s) to transform.
- `base_image` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str, or tuple/list of those): Target image(s).
- `transform` ([Transform](#transform) instance or subclass, optional): If instance, edits it. If class, creates a new specified transform. If None, defaults to [Identity](#identity) or a graph transform.
- `graph` ([Graph](#graph), optional): If provided, node names can be used for `movable_image` and `base_image`.
- `references` (list): Additional images to show for alignment. Each element is `(image, transform)` or a node name if `graph` is provided.
- `crop` (bool or tuple): Crop region for display. If True, uses the movable/base intersection. If tuple, can be `(zmax, ymax, xmax)` or `((zmin, zmax), (ymin, ymax), (xmin, xmax))`.
- `transform_type` (deprecated): Use `transform` instead.

**Returns**

- [Transform](#transform): The fitted transform.

## align_interactive
Command-line driven interactive alignment, building chains of composed transforms.

**Arguments**

- `nodes_movable` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str, or list/tuple): Movable image(s) or node name(s).
- `nodes_fixed` (numpy.ndarray, [ndarray_shifted](#ndarray_shifted), or str, or list/tuple): Fixed image(s) or node name(s).
- `graph` ([Graph](#graph), optional): Enables node-name mode and saving to graph.
- `transform` ([Transform](#transform) instance or str, optional): Starting transform. If str and graph is provided, uses the transform from that node to `nodes_fixed[0]`.
- `references` (list): Additional reference images or node names.
- `start` (deprecated): Use `transform` instead.

**Returns**

- [Transform](#transform): The final composed transform.

## ndarray_shifted
Subclass of `numpy.ndarray` that carries a spatial origin.

**Inherits**

- `numpy.ndarray`

### ndarray_shifted.__new__
Create a shifted array view.

**Arguments**

- `a` (array-like): Input data.
- `origin` (list/tuple/array of 3 numbers or scalar): Origin in (z, y, x) coordinates. If scalar, it is repeated for all dims.
- `only_if_necessary` (bool): If True and `origin` is zero, returns the input array without wrapping.

**Returns**

- [ndarray_shifted](#ndarray_shifted).

### ndarray_shifted.__array_finalize__
Propagate the `origin` attribute on new views.

**Arguments**

- `obj` (numpy.ndarray or None): The source array for the view.

**Returns**

- `None`.

### ndarray_shifted.__repr__
Represent the array, including `origin` when non-zero.

**Returns**

- `str`.

## apply_transform_to_2D_colour_image
Apply a transform to each color channel of a 2D image file and save a new file.

**Arguments**

- `image_filename` (str or path-like): Input image file.
- `transform` ([Transform](#transform)): Transform to apply to each channel.
- `flip` (bool): If True, flips the image vertically before transforming.

**Returns**

- `None`.

**Notes**

- The output filename inserts `transform` before the original extension.

## blit
Copy a source array into a target array at a specified location, clipping to bounds.

**Arguments**

- `source` (numpy.ndarray): Source array.
- `target` (numpy.ndarray): Target array.
- `loc` (array-like): Top-left corner location in target coordinates.

**Returns**

- `None`.

## bake_images
Combine a fixed image and a transformed movable image into a single canvas.

**Arguments**

- `im_fixed` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted))
- `im_movable` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted))
- `transform` ([Transform](#transform))

**Returns**

- [ndarray_shifted](#ndarray_shifted): Combined image with a new origin.

## absolute_coords_to_voxel_coords
Convert absolute coordinates to voxel coordinates for a shifted image.

**Arguments**

- `img` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted))
- `coords` (array-like): Absolute coordinates in (z, y, x).

**Returns**

- `numpy.ndarray` of ints: Voxel coordinates.

## voxel_coords_to_absolute_coords
Convert voxel coordinates to absolute coordinates for a shifted image.

**Arguments**

- `img` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted))
- `coords` (array-like): Voxel coordinates in (z, y, x).

**Returns**

- `numpy.ndarray`: Absolute coordinates.

## crop_to_intersection
Crop two images to their overlapping region.

**Arguments**

- `img1`, `img2` (numpy.ndarray or [ndarray_shifted](#ndarray_shifted))

**Returns**

- Tuple of `[ndarray_shifted](#ndarray_shifted)` images cropped to the intersection.

**Notes**

- Does not currently support downsampling (per code comment).

## load_image
Load a 2D image file and return a single-channel `(1, y, x)` array.

**Arguments**

- `fn` (str or path-like): Image filename.
- `channel` (int or None): If None, averages "informative" channels. If int, uses that channel index.

**Returns**

- `numpy.ndarray` with shape `(1, y, x)`.

## image_is_label
Heuristically determine whether an image is a label/segmentation image.

**Arguments**

- `img` (numpy.ndarray)

**Returns**

- `bool`.

## compress_image
Compress a 2D or 3D image into a byte buffer and metadata.

**Arguments**

- `img` (numpy.ndarray): 2D `(y, x)` or 3D `(z, y, x)`.
- `level` (str): One of `low`, `normal`, `high`.

**Returns**

- `(data, kind)` tuple:
- `data` (numpy.ndarray or bytes): Compressed data.
- `kind` (list): Metadata describing compression format and parameters.

**Notes**

- Label images are compressed losslessly with zlib.
- Large volumes are compressed as VP9 (WebM) video; small ones as JPEG stacks.

## decompress_image
Decompress image data produced by [compress_image](#compress_image).

**Arguments**

- `data` (numpy.ndarray of `uint8` or bytes): Compressed data.
- `kind` (list): Metadata returned by [compress_image](#compress_image).

**Returns**

- `numpy.ndarray`: Decompressed image data.

## invert_function_numerical
Numerically invert a function at a given point by optimization.

**Arguments**

- `func` (callable): Function mapping a point to a point.
- `point` (array-like): Target point in (z, y, x).

**Returns**

- `numpy.ndarray`: Estimated pre-image of the point.

## invert_transform_numerical
Numerically invert a transform at one or more points.

**Arguments**

- `tform` ([Transform](#transform))
- `points` (array-like): `(N, 3)` or `(3,)` points.

**Returns**

- `numpy.ndarray`: Inverted points.

