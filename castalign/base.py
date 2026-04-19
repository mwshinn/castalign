import os
import concurrent.futures
import numpy as np
import scipy
from .ndarray_shifted import ndarray_shifted
from .utils import blit, invert_function_numerical, image_is_label
import threadpoolctl

# TODO:
# - implement posttransforms, allowing the unfitted transform to be on the left hand side

def rotation_matrix(z, y, x):
    """Build a clockwise 3D rotation matrix from Euler angles.

    Parameters
    ----------
    z : float
        Clockwise rotation angle (degrees) around the z axis.
    y : float
        Clockwise rotation angle (degrees) around the y axis.
    x : float
        Clockwise rotation angle (degrees) around the x axis.

    Returns
    -------
    numpy.ndarray
        Rotation matrix with shape ``(3, 3)``.
    """
    sin = lambda x : np.sin(np.deg2rad(x))
    cos = lambda x : np.cos(np.deg2rad(x))
    zy_rotation = lambda theta : \
        np.asarray([[cos(theta), sin(theta), 0],
                    [-sin(theta), cos(theta), 0],
                    [0, 0, 1]])
    yx_rotation = lambda theta : np.roll(zy_rotation(theta), 1, axis=(0,1))
    xz_rotation = lambda theta : np.roll(zy_rotation(theta), -1, axis=(0,1))
    return yx_rotation(z) @ xz_rotation(y) @ zy_rotation(x)


class Transform:
    """Base class for all transforms.

    This is the core transform interface used across CASTalign. A transform maps
    3D volume coordinates from one space to another, and can also be applied to
    full volumetric images through resampling.

    Conceptually, transforms in CASTalign are usually either:
    - point-based (see ``PointTransform``), or
    - parameterized transforms that do not use correspondence points.

    ``DEFAULT_PARAMETERS`` serves two purposes:
    - it provides default values, and
    - it defines the complete set of constructor keyword parameters accepted by
      that transform class.

    Parameter values are stored in ``self.params`` and can be edited in the
    GUI. These are for user-settable controls (for example shifts, scales,
    toggles), not values that are fit from selected points.

    Notes
    -----
    To implement a new subclass:

    - Implement ``_transform(points)`` for forward mapping.
    - Implement ``invert()`` for reverse mapping.
    - Implement ``_fit()`` if parameters must be derived from point data.
      ``_fit()`` is called during initialization when present.
    - If there is no analytic inverse, subclass
      ``PointTransformNoAnalyticInverse``.

    Any transform must be exactly reconstructible from ``__repr__`` output.

    """
    NAME = ""
    SHORTCUT_KEY = ""
    SORT_WEIGHT = 0 # How to sort when listing all transforms
    DEFAULT_PARAMETERS = {}
    GUI_DRAG_PARAMETERS = [None, None, None]
    def __init__(self, **kwargs):
        # Initialise parameters to either pass values or defaults
        self.params = {}
        for k in self.DEFAULT_PARAMETERS.keys():
            self.params[k] = kwargs[k] if k in kwargs else self.DEFAULT_PARAMETERS[k]
        # Check for invalid arguments
        for k in kwargs.keys():
            assert k in self.DEFAULT_PARAMETERS.keys(), f"Keyword argument {k} is not valid for the transform {type(self)}, instead try {list(self.DEFAULT_PARAMETERS.keys())}"
        # If this transform needs to be fit, then fit it.
        if hasattr(self, "_fit"):
            self._fit()
    def __repr__(self):
        ret = self.__class__.__name__
        ret += "("
        parts = []
        for k,v in self.params.items():
            parts.append(f"{k}={v}")
        ret += ", ".join(parts)
        ret += ")"
        return ret
    def __eq__(self, other):
        return repr(self) == repr(other)
    def __add__(self, other):
        return compose_transforms(self, other)
    def __call__(self, data, *args, **kwargs):
        """Apply this transform to points or an image.

        This convenience method lets you use a transform like a function. If
        ``data`` looks like point coordinates, it routes to ``transform``;
        otherwise it treats ``data`` as image data and routes to
        ``transform_image``.

        Parameters
        ----------
        data : array-like
            Either:
            - 3D point coordinates in ``(z, y, x)`` form (``(3,)`` or ``(N, 3)``), or
            - image-like array data.
        *args, **kwargs
            Forwarded to ``transform`` or ``transform_image`` depending on
            input type.

        Returns
        -------
        numpy.ndarray or ndarray_shifted
            Transformed points or transformed image data.
        """
        adata = np.asarray(data)
        if (adata.ndim == 2 and adata.shape[1] == 3) or (adata.ndim == 1 and adata.shape[0] == 3):
            return self.transform(adata, *args, **kwargs)
        return self.transform_image(adata, *args, **kwargs)
    def save(self, filename):
        """Save this transform to disk as a reconstructible text string.

        Parameters
        ----------
        filename : str or path-like
            Output file path.

        Notes
        -----
        The saved content is ``repr(self)`` and is intended to be read back with
        :meth:`load`.
        """
        with open(filename, "w") as f:
            f.write(repr(self))
    @staticmethod
    def load(filename):
        """Load a transform from a file written by :meth:`save`.

        Parameters
        ----------
        filename : str or path-like
            Input file path containing a transform repr string.

        Returns
        -------
        Transform
            Reconstructed transform object.
        """
        with open(filename, "r") as f:
            text = f.read()
        return eval(text, globals(), None)
    def transform(self, points):
        """Transform 3D point coordinates from source space to target space.

        Use this when you want to move landmarks, annotations, or other
        coordinate sets into the transformed image space.

        Parameters
        ----------
        points : array-like
            Point coordinates in ``(z, y, x)`` order. Accepts either a single
            point ``(3,)`` or many points ``(N, 3)``.

        Returns
        -------
        numpy.ndarray
            Transformed coordinates, with the same single-point vs multi-point
            structure as the input.
        """
        points = np.asarray(points)
        is_1d = False
        if points.ndim == 1:
            points = points[None]
            is_1d = True
        if 0 in points.shape: # If any dimensions don't exist, no points to transform
            return points
        assert points.shape[1] == 3, "Input points must be in volume space"
        if is_1d:
            return self._transform(points)[0]
        else:
            return self._transform(points)
    def _transform(self, points):
        """Map points from source space to target space.

        Parameters
        ----------
        points : numpy.ndarray
            Array with shape ``(N, 3)``.

        Returns
        -------
        numpy.ndarray
            Transformed points with shape ``(N, 3)``.
        """
        raise NotImplementedError("Please subclass and replace")
    def inverse_transform(self, points):
        """Map points from target space back to source space.

        Parameters
        ----------
        points : numpy.ndarray
            Array with shape ``(N, 3)`` or a single point ``(3,)``.

        Returns
        -------
        numpy.ndarray
            Inverse-transformed points with the same leading shape as input.

        Notes
        -----
        Override this for a faster implementation; default is
        ``self.invert().transform(points)``.
        """
        return self.invert().transform(points)
    def invert(self):
        """Return the inverse transform.

        Use this when you need to map coordinates or images in the opposite
        direction (target space back to source space).

        Returns
        -------
        Transform
            A transform representing the inverse mapping.

        Notes
        -----
        Subclasses must implement this.
        """
        raise NotImplementedError("Please subclass and replace")
    def origin_and_maxpos(self, img, output_size=None, force_size=True):
        """Compute output-space bounds for a transformed image.

        This is used internally to inspect or control the output coordinate box
        before calling ``transform_image``. This is especially useful when you
        need consistent output extents across multiple transformed volumes.

        Parameters
        ----------
        img : numpy.ndarray or ndarray_shifted
            Input 3D image.
        output_size : None, sequence, or sequence of 2-tuples, optional
            Output bounds:
            - ``None``: tight bounds from transformed corners.
            - ``(z, y, x)``: explicit upper bounds from origin 0.
            - ``((zmin, zmax), (ymin, ymax), (xmin, xmax))``: explicit bounds.
            ``None`` values inside explicit bounds are treated as open bounds.
        force_size : bool, optional
            If ``True``, use explicit bounds exactly. If ``False``, treat them
            as limits and allow smaller computed bounds.

        Returns
        -------
        tuple of numpy.ndarray
            ``(origin, maxpos)`` each with shape ``(3,)``.

        Examples
        --------
        Use automatic tight bounds:
        >>> origin, maxpos = t.origin_and_maxpos(img)

        Force a specific output size from origin 0:
        >>> origin, maxpos = t.origin_and_maxpos(img, output_size=(80, 256, 256))

        Force explicit coordinate bounds:
        >>> origin, maxpos = t.origin_and_maxpos(
        ...     img,
        ...     output_size=((10, 90), (20, 220), (30, 230)),
        ...     force_size=True,
        ... )
        """
        input_bounds = img.shape
        origin_offset = img.origin if isinstance(img, ndarray_shifted) else [0,0,0]
        corners_pretransform = [[a, b, c] for a in [0, input_bounds[0]] for b in [0, input_bounds[1]] for c in [0, input_bounds[2]]]
        corners_pretransform = (corners_pretransform) + np.asarray(origin_offset)
        if isinstance(self, PointTransform): # For nonlinear transforms a box is not enough.  This is also not enough but it is better than nothing.
            origin = np.min(np.concatenate([self.transform(corners_pretransform), self.points_end]), axis=0).astype("float32")
            maxpos = np.max(np.concatenate([self.transform(corners_pretransform), self.points_end]), axis=0).astype("float32")
        else:
            origin = np.min(self.transform(corners_pretransform), axis=0).astype("float32")
            maxpos = np.max(self.transform(corners_pretransform), axis=0).astype("float32")
        if output_size is None: # the default
            pass
        elif isinstance(output_size, (list,tuple,np.ndarray)): # Manually specifying coordinates
            maxpos_ = np.asarray([r[1] if isinstance(r, (list,tuple,np.ndarray)) else r if r is not None else np.inf for r in output_size], dtype="float32")
            origin_ = np.asarray([r[0] if isinstance(r, (list,tuple,np.ndarray)) else 0 if r is not None else -np.inf for r in output_size], dtype="float32")
            if force_size:
                origin = origin_
                maxpos = maxpos_
            else:
                origin = np.max([origin_, origin], axis=0)
                maxpos = np.min([maxpos_, maxpos], axis=0)
        else:
            raise ValueError(f"Invalid value of `output_size` passed: {output_size}")
        return origin,maxpos
    def transform_image(self, img, output_size=None, labels=None, force_size=True):
        """Transform an image

        ``output_size`` controls the output coordinate box. If it is ``None``,
        the transformed image uses a tight bounding box based on transformed
        corners (and point targets for point-based transforms). If it is
        explicit, it can be either ``(z, y, x)`` max bounds from origin 0, or
        full per-axis bounds ``((zmin, zmax), (ymin, ymax), (xmin, xmax))``.
        With ``force_size=True`` these bounds are used exactly; with
        ``force_size=False`` they are treated as limits and the method may return
        a smaller box when possible.

        Parameters
        ----------
        img : numpy.ndarray or ndarray_shifted
            Input image. 2D images are promoted to 3D single-slice volumes.
        output_size : None, sequence, or sequence of 2-tuples, optional
            Output bounds, same formats as ``origin_and_maxpos``.
        labels : bool or None, optional
            Label mode:
            - ``True``: nearest-neighbor interpolation.
            - ``False``: linear interpolation.
            - ``None``: auto-detect with ``image_is_label``.
        force_size : bool, optional
            If ``False``, output size may be smaller than ``output_size``
            if the output would include empty space

        Returns
        -------
        ndarray_shifted or numpy.ndarray
            Transformed image in output coordinates.

        Notes
        -----
        Generic implementation for non-rigid transforms. Subclasses can override
        with faster special cases.

        Examples
        --------
        Transform with automatic tight output bounds:
        >>> out = t.transform_image(img)

        Transform a label volume with nearest-neighbor interpolation:
        >>> out = t.transform_image(labels_img, labels=True)

        Transform with explicit output bounds:
        >>> out = t.transform_image(
        ...     img,
        ...     output_size=((10, 90), (20, 220), (30, 230)),
        ... )
        """
        # First, if we have an ndarray_shifted object, shift it first with another transform.
        if isinstance(img, ndarray_shifted) and np.any(img.origin != np.asarray([0,0,0])):
            shift = TranslateParametric(z=img.origin[0], y=img.origin[1], x=img.origin[2])
            return (shift + self).transform_image(np.asarray(img), output_size=output_size, labels=labels, force_size=force_size)
        # Housekeeping
        if labels is None:
            labels = image_is_label(img)
        if img.ndim == 2:
            img = img[None]
        origin, maxpos = self.origin_and_maxpos(img, output_size=output_size, force_size=force_size)
        shape = (maxpos - origin).astype(int)
        img_offset = ndarray_shifted(img).origin
        img   = np.ascontiguousarray(img,  dtype=np.float32 if not labels else img.dtype)
        origin = origin.astype(np.float32)
        # shape = np.round(np.ceil(maxpos - origin)/downsample_output).astype(int) # Maybe this is better?
        # shape = np.asarray(img.shape).astype(int) # Pulled from old code

        if img.shape[0] == 1: # This is a hack to get around thickness=1 images disappearing in the map_coordinates function 
            img = np.concatenate([img, img])
        if img.shape[1] == 1:
            img = img*np.ones((1,2,1), dtype=img.dtype)
        if img.shape[2] == 1:
            img = img*np.ones((1,1,2), dtype=img.dtype)
        # For memory efficiency, we split coords into chunks
        zcoords = np.arange(0, shape[0], dtype="float32")
        ycoords = np.arange(0,shape[1], dtype="float32")
        xcoords = np.arange(0,shape[2], dtype="float32")
        def chunker(zcoords, ycoords, xcoords, chunksize=10_000_000):
            """Yield z-plane chunks to limit peak memory usage.

            Parameters
            ----------
            zcoords, ycoords, xcoords : numpy.ndarray
                Output coordinate vectors.
            chunksize : int, optional
                Approximate voxel budget per chunk.

            Yields
            ------
            tuple
                ``(coords, chunk_shape, inds)`` for one chunk.
            """
            zsize = len(ycoords)*len(xcoords)
            n_z_per_chunk = np.maximum(chunksize // zsize, 1)
            single_plane = np.asarray([np.repeat(ycoords, len(xcoords)), np.tile(xcoords, len(ycoords))], dtype="float32")
            zcoords_float32 = np.asarray(zcoords, dtype="float32")
            for i in range(0, 100000):
                zfrom, zto = n_z_per_chunk*i,n_z_per_chunk*(i+1)
                if zfrom >= len(zcoords):
                    return
                if zto > len(zcoords):
                    zto = len(zcoords)
                inds = (slice(zfrom,zto), slice(None), slice(None))
                chunk_shape = (zto-zfrom, len(ycoords), len(xcoords))
                coords = np.concatenate([np.repeat(zcoords_float32[zfrom:zto], single_plane.shape[1])[None,:], np.tile(single_plane, zto-zfrom)], axis=0).T
                yield coords, chunk_shape, inds

        # First, we construct a list of coordinates of all the pixels in the
        # image, and transform them to find out which point is mapped to which
        # other point.  Then, we inverse transform them to construct a matrix of
        # mappings.  We turn this matrix of mappings into a matrix of pointers
        # from the destination image to the source image, and then use the
        # map_coordinates function to perform this mapping.
        output = np.zeros((len(zcoords),len(ycoords),len(xcoords)), dtype=(img.dtype if labels else "float32"))
        def _process_chunk(args):
            grid, chunk_shape, inds = args
            grid = grid + origin
            mapped = self.inverse_transform(grid)
            if isinstance(img, ndarray_shifted):
                mapped += img.origin
            disp = mapped.reshape(*chunk_shape, 3).transpose(3, 0, 1, 2)
            block = scipy.ndimage.map_coordinates(img, disp, prefilter=False, order=(0 if labels else 1))
            return inds, block
        with threadpoolctl.threadpool_limits(limits=1): # Parallelise here, so disable parallelisation on threads
            with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
                for inds, block in pool.map(_process_chunk, chunker(zcoords, ycoords, xcoords, chunksize=4_000_000)):
                    output[inds] = block
        return ndarray_shifted(output, origin=origin, only_if_necessary=True) # Added -origin from origin due to TranslateParametric + Rescale on a ndarray_shifted but not sure if this is the right spot
    @staticmethod
    def pretransform(*args, **kwargs):
        """Return the fixed pre-transform applied before this transform.

        Returns
        -------
        Transform
            Pre-transform to apply first. The default is ``Identity()``.

        Notes
        -----
        Most transform classes should keep this default. Override it when a
        class represents a composed transform where only part of the chain is
        meant to be fit from data (for example, when an earlier component is
        fixed and only the final component is fit).
        """
        return Identity()

class PointTransform(Transform):
    """Base class for transforms fit from point correspondences.

    This class stores matched 3D points and is the base for transforms that are
    learned from those matches.

    Notes
    -----
    Subclasses can rely on:
    - ``self.points_start``: source coordinates.
    - ``self.points_end``: target coordinates.

    Subclasses are expected to implement the standard transform behavior:
    - forward mapping through ``_transform``,
    - inverse mapping through ``invert``,
    - and optional fitting logic in ``_fit``.
    """
    def __init__(self, points_start=None, points_end=None, **kwargs):
        """Initialize a point-based transform from matched coordinates.

        Parameters
        ----------
        points_start : array-like, optional
            Source-space points, shaped ``(N, 3)`` in ``(z, y, x)``
            order.
        points_end : array-like, optional
            Target-space points matched one-to-one with ``points_start``,
            shaped ``(N, 3)``.
        **kwargs
            Additional transform parameters accepted by this class (defined by
            ``DEFAULT_PARAMETERS`` on the subclass).

        Raises
        ------
        AssertionError
            If ``points_start`` and ``points_end`` do not have the same shape.
        """
        # Save and process the points for the transform
        points_start = np.asarray(points_start)
        points_end = np.asarray(points_end)
        assert points_start.shape == points_end.shape, "Points start and end must be the same size"
        self.points_start = points_start
        self.points_end = points_end
        super().__init__(**kwargs)
    @classmethod
    def from_transform(cls, transform, *args, **kwargs):
        """Construct a point transform from another transform's points.

        Parameters
        ----------
        transform : Transform
            Existing transform providing ``points_start`` and ``points_end``.
        *args, **kwargs
            Additional constructor args for ``cls``.

        Returns
        -------
        PointTransform
            New instance initialized with copied correspondences.
        """
        return cls(points_start=transform.points_start, points_end=transform.points_end, *args, **kwargs)
    def __repr__(self):
        ret = self.__class__.__name__
        ret += "("
        ret += f"points_start={self.points_start.tolist()}, points_end={self.points_end.tolist()}"
        for k,v in self.params.items():
            ret += f", {k}={v}"
        ret += ")"
        return ret

class AffineTransform:
    """Mixin implementing affine transform behavior.

    This class provides shared affine logic for transform classes that represent
    mappings of the form:
    ``output = input @ matrix - shift``.

    Notes
    -----
    Subclasses should use ``_fit`` to set:
    - ``self.matrix`` with shape ``(3, 3)``
    - ``self.shift`` with shape ``(3,)``

    This mixin is designed for multiple inheritance with ``Transform`` or
    ``PointTransform``-derived classes.
    """
    def _transform(self, points):
        return points @ self.matrix - self.shift
    def transform_image(self, image, output_size=None, labels=None, force_size=True):
        # Optimisation for the case where no image transform needs to be
        # performed.
        if np.all(self.matrix == np.eye(3)) and ((not isinstance(image, ndarray_shifted)) or np.all(image.origin==[0,0,0])):
            if output_size is None:
                return ndarray_shifted(image, origin=-self.shift, only_if_necessary=True)
            # else:
            #     newimg = np.zeros_like(image)
            #     blit(image, newimg, self.shift) # TODO test, not sure if this works
            #     return newimg
        return super().transform_image(image, output_size=output_size, labels=labels, force_size=force_size)
    def invert(self):
        """Invert the transform.

        Note: This will return incorrect results for some non-affine transforms.
        Currently it just swaps the order of the points.

        """
        return self.__class__(points_start=self.points_end, points_end=self.points_start, **self.params)

# TODO improve optimisation with the jacobian
class PointTransformNoAnalyticInverse(PointTransform):
    """Base class for point transforms without an analytic inverse.

    This class uses numerical inversion when needed, for transforms that are
    still bijective but do not have a closed-form inverse.

    Notes
    -----
    Subclasses should:
    - include ``{"invert": False}`` in ``DEFAULT_PARAMETERS``
    - implement ``_transform(points, points_start, points_end)``

    By default, this class treats ``_transform`` as the inverse-direction map,
    which is typically the faster direction for image resampling workflows.
    Passing ``invert=False`` flips that behavior.
    """
    def __init__(self, *args, **kwargs):
        self._inv_transform_cache = {}
        super().__init__(*args, **kwargs)
    # Use the inverse transform by default
    def transform(self, points):
        points = np.asarray(points)
        is_1d = False
        if points.ndim == 1:
            is_1d = True
            points = points[None]
        assert points.shape[1] == 3, "Input points must be in volume space"
        if self.params["invert"]:
            print("Fast inverse transform of", points.shape)
            res = self._transform(points, points_start=self.points_start, points_end=self.points_end)
        else:
            print("Slow transform of", points.shape)
            if points.shape[0] > 1000:
                raise ValueError("Too many points to invert, this will take forever.")
            res = np.asarray([self._inv_transform_cache[tuple(p)] if tuple(p) in self._inv_transform_cache.keys() else invert_function_numerical(lambda x,self=self : self._transform(x, self.points_end, self.points_start), p) for p in points])
        return res[0] if is_1d else res
    def invert(self):
        return self.__class__(points_start=self.points_end, points_end=self.points_start, invert=(not self.params["invert"]))

########## Transforms ##########

class Identity(AffineTransform,Transform):
    NAME = "No transform"
    def _fit(self):
        self.matrix = np.eye(3)
        self.shift = np.zeros(3)
    def _transform(self, points):
        return points
    def invert(self):
        return self.__class__()
    def transform_image(self, image, output_size=None, labels=None, force_size=True):
        """Apply the identity transform

        This can obviously be a faster implementation than the default.

        Parameters
        ----------
        image : numpy.ndarray or ndarray_shifted
            Input image data.
        output_size : optional
            Forwarded when generic path is required.
        labels : bool or None, optional
            Forwarded when generic path is required.
        force_size : bool, optional
            Forwarded when generic path is required.

        Returns
        -------
        numpy.ndarray or ndarray_shifted
            Original image when possible, otherwise generic resampled output.
        """
        # TODO This doesn't work for different output_size values
        if output_size is not None:
            return super().transform_image(image, output_size=output_size, labels=labels, force_size=force_size)
        return image

class Rigid(AffineTransform,PointTransform):
    NAME = "Rigid"
    SHORTCUT_KEY = "R"
    SORT_WEIGHT = -99
    def _fit(self):
        demeaned_start = self.points_start - np.mean(self.points_start, axis=0)
        demeaned_end = self.points_end - np.mean(self.points_end, axis=0)
        U,S,V = np.linalg.svd(demeaned_start.T @ demeaned_end)
        self.matrix = U@V
        self.shift = np.mean(self.points_start @ self.matrix - self.points_end, axis=0)

class RigidParametric(AffineTransform,Transform):
    NAME = "Rigid"
    SHORTCUT_KEY = "r"
    SORT_WEIGHT = -99
    DEFAULT_PARAMETERS = {"z": 0.0, "y": 0.0, "x": 0.0, "zrotate": 0.0, "yrotate": 0.0, "xrotate": 0.0, "invert": False}
    GUI_DRAG_PARAMETERS = ["z", "y", "x"]
    def _fit(self):
        self.matrix = rotation_matrix(self.params["zrotate"], self.params["yrotate"], self.params["xrotate"])
        if self.params['invert']:
            self.matrix = self.matrix.T
        self.shift = np.asarray([-self.params["z"], -self.params["y"], -self.params["x"]])
    def invert(self):
        newzyx = [self.params["z"], self.params["y"], self.params["x"]] @ self.matrix.T
        return self.__class__(zrotate=self.params["zrotate"], yrotate=self.params["yrotate"], xrotate=self.params["xrotate"], z=-newzyx[0], y=-newzyx[1], x=-newzyx[2], invert=(not self.params['invert']))

class Affine(AffineTransform,PointTransform):
    NAME = "Affine"
    SHORTCUT_KEY = "A"
    SORT_WEIGHT = -97
    DEFAULT_PARAMETERS = {"invert": False}
    def _fit(self):
        if self.params['invert']:
            _start = self.points_end
            _end = self.points_start
        else:
            _start = self.points_start
            _end = self.points_end
        start = np.hstack([np.ones((_start.shape[0],1)), _start])
        reg_coefs = np.linalg.inv(start.T @ start) @ start.T @ _end
        self.matrix = reg_coefs[1:]
        if self.params['invert']:
            self.matrix = np.linalg.inv(self.matrix)
        self.shift = np.mean(self.points_start @ self.matrix - self.points_end, axis=0)
    def invert(self):
        return self.__class__(points_start=self.points_end, points_end=self.points_start, invert=(not self.params["invert"]))

class AffineParametric(AffineTransform,Transform):
    NAME = "Affine"
    SHORTCUT_KEY = "a"
    SORT_WEIGHT = -94
    DEFAULT_PARAMETERS = {"z": 0.0, "y": 0.0, "x": 0.0, "zrotate": 0.0, "yrotate": 0.0, "xrotate": 0.0, "zscale": 1.0, "yscale": 1.0, "xscale": 1.0, "yzshear": 0.0, "xzshear": 0.0, "xyshear": 0.0, "invert": False}
    GUI_DRAG_PARAMETERS = ["z", "y", "x"]
    def _fit(self):
        self.matrix = rotation_matrix(self.params["zrotate"], self.params["yrotate"], self.params["xrotate"]) @ np.asarray([[self.params["zscale"], 0, 0], [0, self.params["yscale"], 0], [0, 0, self.params["xscale"]]]) @ np.asarray([[1, 0, 0], [self.params["yzshear"], 1, 0], [self.params["xzshear"], self.params["xyshear"], 1]])
        if self.params["invert"]:
            self.matrix = np.linalg.inv(self.matrix)
        self.shift = np.asarray([-self.params["z"], -self.params["y"], -self.params["x"]])
    def invert(self):
        newzyx = [self.params["z"], self.params["y"], self.params["x"]] @ np.linalg.inv(self.matrix)
        return self.__class__(zrotate=self.params["zrotate"], yrotate=self.params["yrotate"], xrotate=self.params["xrotate"], zscale=self.params["zscale"], yscale=self.params["yscale"], xscale=self.params["xscale"], yzshear=self.params["yzshear"], xzshear=self.params["xzshear"], xyshear=self.params["xyshear"], z=-newzyx[0], y=-newzyx[1], x=-newzyx[2], invert=(not self.params["invert"]))

class MatrixParametric(AffineTransform,Transform):
    """Affine transform defined directly by matrix coefficients.

    Exposes all 3x3 matrix entries and translation terms as parameters.

    Notes
    -----
    Matrix validity is not checked. Invalid/singular matrices may give unstable
    or undefined results.
    """
    NAME = "Transformation matrix"
    DEFAULT_PARAMETERS = {"a11": 1, "a12": 0, "a13": 0, "a21": 0, "a22": 1, "a23": 0, "a31": 0, "a32": 0, "a33": 1, "x": 0, "y": 0, "z": 0}
    GUI_DRAG_PARAMETERS = ["z", "y", "x"]
    SHORTCUT_KEY = "m"
    SORT_WEIGHT = -90
    def _fit(self):
        p = lambda num : self.params[f"a{num}"]
        self.matrix = np.asarray([[p(11), p(12), p(13)], [p(21), p(22), p(23)], [p(31), p(32), p(33)]])
        self.shift = np.asarray([-self.params["z"], -self.params["y"], -self.params["x"]])
    def invert(self):
        p = lambda num : self.params[f"a{num}"]
        newzyx = [self.params["z"], self.params["y"], self.params["x"]] @ self.matrix.T
        return self.__class__(a11=p(11), a12=p(21), a13=p(31), a21=p(12), a22=p(22), a23=p(32), a31=p(13), a32=p(23), a33=p(33), z=-newzyx[0], y=-newzyx[1], x=-newzyx[2])

class PlaneConstrainedAffine(AffineTransform,PointTransform):
    """Affine fit constrained to a dominant plane (e.g., section-like data).

    Splits fitting into high-variance in-plane components plus low-variance
    normal-depth component to reduce skew in thin volumes.
    """
    NAME = "Plane-constrained affine"
    SHORTCUT_KEY = "P"
    SORT_WEIGHT = -96
    DEFAULT_PARAMETERS = {"invert": False}
    def _fit(self):
        if self.params['invert']:
            _start = self.points_end
            _end = self.points_start
        else:
            _start = self.points_start
            _end = self.points_end
        # PCA
        demeaned_start = _start - np.mean(_start, axis=0)
        demeaned_end = _end - np.mean(_end, axis=0)
        U,S,V = np.linalg.svd(demeaned_start.T @ demeaned_end)
        assert np.all(np.sort(S)[::-1] == S), "SVD is not sorted correctly"
        # Regression for the high-variance dimensions
        proj_start = demeaned_start @ U[:,:2]
        proj_end = demeaned_end @ V.T[:,:2]
        _proj_start = np.hstack([np.ones((proj_start.shape[0],1)), proj_start])
        reg_coefs = np.linalg.inv(_proj_start.T @ _proj_start) @ _proj_start.T @ proj_end
        # Regression for the low-variance dimension
        depth_start = demeaned_start @ U[:,[2]]
        depth_end = demeaned_end @ V.T[:,[2]]
        _depth_start = np.hstack([np.ones((depth_start.shape[0],1)), depth_start])
        depth_reg_coefs = np.linalg.inv(_depth_start.T @ _depth_start) @ _depth_start.T @ depth_end
        # Combine the two
        self.matrix = U @ (scipy.linalg.block_diag(reg_coefs[1:], 0) + np.diag([0, 0, depth_reg_coefs[1,0]])) @ V
        if self.params['invert']:
            self.matrix = np.linalg.inv(self.matrix)
        self.shift = np.mean(self.points_start @ self.matrix - self.points_end, axis=0)
    def invert(self):
        return self.__class__(points_start=self.points_end, points_end=self.points_start, invert=(not self.params["invert"]))

class FlipParametric(AffineTransform,Transform):
    NAME = "Flip"
    DEFAULT_PARAMETERS = {"z": False, "y": False, "x": False, "zthickness": 0, "ythickness": 0, "xthickness": 0}
    def _fit(self):
        sign = lambda x : -1 if self.params[x] else 1
        self.matrix = np.asarray([[sign("z"), 0, 0], [0, sign("y"), 0], [0, 0, sign("x")]])
        self.shift = -np.asarray([self.params[c+"thickness"]*int(self.params[c]) for c in ["z", "y", "x"]])
    def invert(self):
        return self

class RescaleParametric(AffineTransform,Transform):
    NAME = "Rescale"
    DEFAULT_PARAMETERS = {"z": 1.0, "y": 1.0, "x": 1.0}
    SHORTCUT_KEY = "z"
    def _fit(self):
        self.matrix = np.diag([self.params["z"], self.params["y"], self.params["x"]])
        self.shift = np.asarray([0, 0, 0])
    def invert(self):
        return self.__class__(z=1/self.params["z"], y=1/self.params["y"], x=1/self.params["x"])

class Triangulation(PointTransform):
    """Nonlinear 3D deformation using piecewise-affine triangulation.

    This transform warps a 3D volume by building a Delaunay triangulation over
    control points, then applying a local affine map per tetrahedron.

    Notes
    -----
    The implementation supports both directions of mapping. For one direction it
    can use ``find_simplex`` directly; for the other it manually checks
    tetrahedron containment, because SciPy does not provide the exact
    arbitrary-triangulation path needed for this workflow.
    """
    NAME = "Nonlinear 3D triangulation"
    SHORTCUT_KEY = "V"
    SORT_WEIGHT = 100
    DEFAULT_PARAMETERS = {"invert": True} # Start with inverted because inverted is slower for points and faster for images
    def _fit(self):
        # To avoid out of bounds, we add a few pseudo points.  We do this by
        # finding the convex hull, centering it, and scaling it, and then
        # shifting the scaled points back from the centering.  To avoid sharp
        # angles for near-coplannar point clouds, we shift the points in all
        # dimensions by a small value first.  We assign these points a simple
        # linear transformed version of the points they are derived from.
        SCALE_FACTOR = 1000
        if self.params["invert"]:
            before = self.points_end
            after = self.points_start
        else:
            before = self.points_start
            after = self.points_end
        _rns = np.random.RandomState(0).randn(*before.shape)*.0001 # Break symmetry
        before = before + _rns
        t = scipy.spatial.Delaunay(before) # Triangulation
        assert np.all(t.points == before), "Coplannar points"
        hull_points_inds = np.unique(t.convex_hull.flatten())
        hull_points_vecs = after[hull_points_inds] - before[hull_points_inds]
        hull_mean_shift = np.mean(before[hull_points_inds], axis=0)
        if self.params["invert"]:
            self.pseudopoints_end = SCALE_FACTOR*(before[hull_points_inds] - hull_mean_shift) + hull_mean_shift
            #self.pseudopoints_end += 5*SCALE_FACTOR*np.sign(self.pseudopoints_end-hull_mean_shift)
            self.pseudopoints_start = self.pseudopoints_end + hull_points_vecs
        else:
            self.pseudopoints_start = SCALE_FACTOR*(before[hull_points_inds] - hull_mean_shift) + hull_mean_shift
            #self.pseudopoints_start += 5*SCALE_FACTOR*np.sign(self.pseudopoints_start-hull_mean_shift)
            self.pseudopoints_end = self.pseudopoints_start + hull_points_vecs
        self.all_points_start = np.concatenate([self.points_start, self.pseudopoints_start])
        self.all_points_end = np.concatenate([self.points_end, self.pseudopoints_end])
    def _transform(self, points):
        points = np.asarray(points)
        start = self.all_points_start
        end = self.all_points_end
        tri_points = self.all_points_start if not self.params["invert"] else self.all_points_end
        _rns = np.random.RandomState(0).randn(*tri_points.shape)*.0001 # Break symmetry
        delaunay = scipy.spatial.Delaunay(tri_points+_rns)
        assert np.max(delaunay.points-tri_points)<.1, "Wrong order of Delaunay triangulation, are some points coplannar?"
        if self.params['invert']:
            newpoints = np.zeros_like(points)*np.nan
            for simp in delaunay.simplices:
                insimp = scipy.spatial.Delaunay(start[simp]).find_simplex(points)>=0
                if np.sum(insimp) == 0: continue
                coefs_rhs = np.concatenate([start[simp], np.ones(len(simp))[:,None]], axis=1)
                coefs_lhs = end[simp]
                params = np.linalg.inv(coefs_rhs) @ coefs_lhs
                newpoints[insimp] = np.concatenate([points[insimp], np.ones(sum(insimp))[:,None]], axis=1) @ params
            assert not np.any(np.isnan(newpoints)), "Point was outside of simplex or invalid input points"
            return newpoints
        else: # For the non-inverted case, we can use the original triangulation and improve performance
            insimp = delaunay.find_simplex(points)
            assert np.all(insimp>=0), "Points outside domain, increase scale factor in code"
            newpoints = np.zeros_like(points)*np.nan
            for i,simp in enumerate(delaunay.simplices):
                if np.sum(insimp==i) == 0: continue
                coefs_rhs = np.concatenate([start[simp], np.ones(len(simp))[:,None]], axis=1)
                coefs_lhs = end[simp]
                params = np.linalg.inv(coefs_rhs) @ coefs_lhs
                newpoints[insimp==i] = np.concatenate([points[insimp==i], np.ones(sum(insimp==i))[:,None]], axis=1) @ params
            assert not np.any(np.isnan(newpoints)), "Not sure why this should ever happen?"
            return newpoints
    def invert(self):
        return self.__class__(invert=(not self.params["invert"]), points_start=self.points_end, points_end=self.points_start)

class PlaneConstrainedTriangulation(PointTransform):
    """Nonlinear triangulation constrained to a fitted 2D plane in 3D.

    This is generally the recommended nonlinear transform for mostly flat
    section-like 3D data (broad in two dimensions, thinner in the third).

    If ``normal_z``, ``normal_y``, and ``normal_x`` are all zero, the normal is
    estimated automatically from the input points.

    Notes
    -----
    The transform triangulates points after projection into the fitted plane,
    then computes local 3D affine maps using those projected triangles plus a
    normal-direction anchor so depth is handled consistently.

    As with ``Triangulation``, one mapping direction can use
    ``find_simplex`` directly, while the other uses manual triangle containment
    checks due to SciPy API limitations for this specific inverse workflow.
    """
    NAME = "Plane-constrained triangulation"
    SHORTCUT_KEY = "N"
    SORT_WEIGHT = 99
    DEFAULT_PARAMETERS = {"invert": True, "normal_z": 0.0, "normal_y": 0.0, "normal_x": 0.0} # Start with inverted because inverted is slower for points and faster for images
    def _fit(self):
        # To avoid out of bounds, we add a few pseudo points.  We do this by
        # finding the convex hull, centering it, and scaling it, and then
        # shifting the scaled points back from the centering.  To avoid sharp
        # angles for near-coplannar point clouds, we shift the points in all
        # dimensions by a small value first.  We assign these points a simple
        # linear transformed version of the points they are derived from.
        SCALE_FACTOR = 100
        if self.params["invert"]:
            before = self.points_end
            after = self.points_start
        else:
            before = self.points_start
            after = self.points_end
        # Automatically find the normal if it wasn't manually specified
        if self.params['normal_z'] == 0 and self.params['normal_y'] == 0 and self.params['normal_x'] == 0:
            demeaned_before = before - np.mean(before, axis=0)
            U,S,V = np.linalg.svd(demeaned_before.T @ demeaned_before)
            assert np.all(np.sort(S)[::-1] == S), "SVD is not sorted correctly"
            self.normal = U[:,2]
        else:
            self.normal = np.asarray([self.params["normal_z"], self.params["normal_y"], self.params["normal_x"]])
            self.normal /= np.sqrt(np.sum(np.square(self.normal)))
        # Find two vectors to form the basis for the plane.  Suffix "B" to indicate we are in this basis
        vec1 = np.asarray([1., 0, 0]) if np.asarray([1., 0, 0]) @ self.normal < .99 else np.asarray([0, 1., 0]) # Can be any vector in a different direction than the normal, these are a bit easier to interpret
        vec1 -= (vec1 @ self.normal) * self.normal
        vec1 /= np.sqrt(np.sum(np.square(vec1)))
        self.B = np.asarray([vec1, np.cross(self.normal, vec1)]).T
        beforeB = before @ self.B
        t = scipy.spatial.Delaunay(beforeB) # Triangulation
        assert np.all(t.points == beforeB), "Coplannar points"
        hull_points_inds = np.unique(t.convex_hull.flatten())
        hull_points_vecs = after[hull_points_inds] - before[hull_points_inds]
        hull_mean_shift = np.mean(before[hull_points_inds], axis=0)
        if self.params["invert"]:
            self.pseudopoints_end = SCALE_FACTOR*(before[hull_points_inds] - hull_mean_shift) + hull_mean_shift
            #self.pseudopoints_end += 5*SCALE_FACTOR*np.sign(self.pseudopoints_end-hull_mean_shift)
            self.pseudopoints_start = self.pseudopoints_end + hull_points_vecs
        else:
            self.pseudopoints_start = SCALE_FACTOR*(before[hull_points_inds] - hull_mean_shift) + hull_mean_shift
            #self.pseudopoints_start += 5*SCALE_FACTOR*np.sign(self.pseudopoints_start-hull_mean_shift)
            self.pseudopoints_end = self.pseudopoints_start + hull_points_vecs
        self.all_points_start = np.concatenate([self.points_start, self.pseudopoints_start])
        self.all_points_end = np.concatenate([self.points_end, self.pseudopoints_end])
    def _transform(self, points):
        # Project all points into the basis defined in _fit.  This is indicated
        # by "B" suffix.  Then perform the triangulation in that 2-dimensional
        # space, and then compute the new points in 3D by holding the
        # interpolation constant in the direction normal to the space.
        points = np.asarray(points)
        pointsB = points @ self.B
        start = self.all_points_start
        startB = start @ self.B
        end = self.all_points_end
        tri_pointsB = (self.all_points_start if not self.params["invert"] else self.all_points_end) @ self.B
        delaunay = scipy.spatial.Delaunay(tri_pointsB)
        assert np.all(delaunay.points == tri_pointsB), "Coplannar points"
        if self.params['invert']:
            newpoints = np.zeros_like(points)*np.nan
            if points.shape[0] > 1000:
                print("Warning, using slow transform to transform many points, try inverting")
            for simp in delaunay.simplices:
                insimp = scipy.spatial.Delaunay(startB[simp]).find_simplex(pointsB)>=0
                if np.sum(insimp) == 0: continue
                _start = np.concatenate([start[simp], start[[simp[0]]]+self.normal], axis=0)
                _end = np.concatenate([end[simp], end[[simp[0]]]+self.normal], axis=0)
                coefs_rhs = np.concatenate([_start, np.ones(len(simp)+1)[:,None]], axis=1)
                coefs_lhs = _end
                params = np.linalg.inv(coefs_rhs) @ coefs_lhs
                newpoints[insimp] = np.concatenate([points[insimp], np.ones(np.sum(insimp))[:,None]], axis=1) @ params
            assert not np.any(np.isnan(newpoints)), "Point was outside of simplex or invalid input points"
            return newpoints
        else: # For the non-inverted case, we can use the original triangulation and improve performance
            insimp = delaunay.find_simplex(pointsB)
            assert np.all(insimp>=0), "Points outside domain, increase scale factor in code"
            newpoints = np.zeros_like(points)*np.nan
            for i,simp in enumerate(delaunay.simplices):
                if np.sum(insimp==i) == 0: continue
                # Perform linear regression to get a map from the start to the
                # end.  Add an extra point with the normal added so we get a
                # 3D-to-3D map.
                _start = np.concatenate([start[simp], start[[simp[0]]]+self.normal], axis=0)
                _end = np.concatenate([end[simp], end[[simp[0]]]+self.normal], axis=0)
                coefs_rhs = np.concatenate([_start, np.ones(len(simp)+1)[:,None]], axis=1)
                coefs_lhs = _end
                params = np.linalg.inv(coefs_rhs) @ coefs_lhs
                newpoints[insimp==i] = np.concatenate([points[insimp==i], np.ones(np.sum(insimp==i))[:,None]], axis=1) @ params
            assert not np.any(np.isnan(newpoints)), "Not sure why this should ever happen?"
            return newpoints
    def invert(self):
        return self.__class__(invert=(not self.params["invert"]), points_start=self.points_end, points_end=self.points_start, normal_z=self.params["normal_z"], normal_y=self.params["normal_y"], normal_x=self.params["normal_x"])

########## Composing transforms ##########

def compose_transforms(a, b):
    """Compose two transforms into one transform chain.

    This is the implementation behind ``a + b``. It handles composing transform
    instances, and also the mixed case where ``a`` is an already-fit transform
    instance and ``b`` is a transform class.

    Parameters
    ----------
    a : Transform
        Left-hand transform. Must be an instantiated transform.
    b : Transform or type
        Right-hand transform, either as an instance or as a transform class.

    Returns
    -------
    Transform or type
        Depending on inputs:
        - If both are instances, returns an instantiated composed transform.
        - If ``b`` is a class, returns a composed transform class.
        - Identity components are simplified away when possible.

    Notes
    -----
    For affine + affine composition, the returned composed class uses affine
    shortcuts (combined matrix/shift). For non-affine composition, point mapping
    is composed directly.
    """
    # Skip for the identity transform
    if isinstance(a, Identity):
        return b
    if isinstance(b, Identity):
        return a
    # Special cases for linear and for adding to a class (not yet fitted)
    if isinstance(a, Transform) and isinstance(b, Transform):
        if isinstance(b, PointTransform):
            return compose_transforms(a, b.__class__)(points_start=b.points_start, points_end=b.points_end, **b.params)
        else:
            return compose_transforms(a, b.__class__)(**b.params)
    # if isinstance(a, Transform) and isinstance(b, Transform):
    #     return Composed(a, b)
    if isinstance(a, Transform) and not isinstance(b, Transform):
        inherit = PointTransform if issubclass(b, PointTransform) else Transform
        if isinstance(a, AffineTransform) and issubclass(b, AffineTransform):
            class ComposedPartialAffine(AffineTransform,inherit):
                DEFAULT_PARAMETERS = b.DEFAULT_PARAMETERS # b.params # Changed from b.DEFAULT_PARAMETERS
                GUI_DRAG_PARAMETERS = b.GUI_DRAG_PARAMETERS
                def __new__(cls, *args, **kwargs): # Strip identity if necessary
                    if b is Identity:
                        return a
                    return super(ComposedPartialAffine, cls).__new__(cls)
                def __init__(self, points_start=None, points_end=None, *args, **kwargs):
                    extra_args = {}
                    if points_start is not None and points_end is not None:
                        extra_args['points_start'] = points_start
                        extra_args['points_end'] = points_end
                    self.b_type = b
                    self.b = b(*args, **kwargs, **extra_args)
                    super().__init__(*args, **kwargs, **extra_args)
                    if self.b_type is Identity:
                        self = self.a
                def _fit(self):
                    self.matrix = a.matrix @ self.b.matrix
                    self.shift = a.shift @ self.b.matrix + self.b.shift
                def __repr__(self):
                    return repr(a) + " + " + repr(self.b)
                @staticmethod
                def pretransform(*args, **kwargs):
                    return a
                def invert(self):
                    return self.b.invert() + a.invert()
            return ComposedPartialAffine
        else:
            class ComposedPartial(inherit):
                DEFAULT_PARAMETERS = b.DEFAULT_PARAMETERS #  b.params # Changed from b.DEFAULT_PARAMETERS
                GUI_DRAG_PARAMETERS = b.GUI_DRAG_PARAMETERS
                def __new__(cls, *args, **kwargs): # Strip identity if necessary
                    if b is Identity:
                        return a
                    return super(ComposedPartial, cls).__new__(cls)
                def __init__(self, points_start=None, points_end=None, *args, **kwargs):
                    extra_args = {}
                    if points_start is not None and points_end is not None:
                        extra_args['points_start'] = points_start
                        extra_args['points_end'] = points_end
                    self.b_type = b
                    self.b = b(*args, **kwargs, **extra_args)
                    super().__init__(**extra_args, **self.b.params)
                def _transform(self, points):
                    return self.b.transform(a.transform(points))
                def inverse_transform(self, points):
                    return a.inverse_transform(self.b.inverse_transform(points))
                def invert(self):
                    raise NotImplementedError
                def __repr__(self):
                    return repr(a) + " + " + repr(self.b)
                def invert(self):
                    return self.b.invert() + a.invert()
                @staticmethod
                def pretransform(*args, **kwargs):
                    return a
            return ComposedPartial
    raise NotImplementedError("Invalid composition")


########## Deprecated ##########



class TranslateRotate2D(AffineTransform,PointTransform): # Deprecated
    NAME = "Translate and rotate in 2D only"
    def _fit(self):
        demeaned_start = self.points_start - np.mean(self.points_start, axis=0)
        demeaned_end = self.points_end - np.mean(self.points_end, axis=0)
        U,S,V = np.linalg.svd(demeaned_start[:,1:3].T @ demeaned_end[:,1:3])
        corner_matrix = U@V
        self.matrix = np.vstack([[[1, 0, 0]], np.hstack([[[0],[0]], corner_matrix])])
        self.shift = np.mean(self.points_start @ self.matrix - self.points_end, axis=0)

class Translate(AffineTransform,PointTransform):
    NAME = "Translate"
    SORT_WEIGHT = -100
    def _fit(self):
        self.matrix = np.eye(3)
        self.shift = np.mean(self.points_start - self.points_end, axis=0)

class Flip(AffineTransform,Transform): # Deprecated
    NAME = "Flip"
    DEFAULT_PARAMETERS = {"z": False, "y": False, "x": False, "zthickness": 0, "ythickness": 0, "xthickness": 0}
    def _fit(self):
        sign = lambda x : -1 if self.params[x] else 1
        self.matrix = np.asarray([[sign("z"), 0, 0], [0, sign("y"), 0], [0, 0, sign("x")]])
        self.shift = np.asarray([max(0, self.params[c+"thickness"]-1)*int(self.params[c]) for c in ["z", "y", "x"]])
    def invert(self):
        return self

class TranslateParametric(AffineTransform,Transform):
    NAME = "Translate"
    DEFAULT_PARAMETERS = {"z": 0.0, "y": 0.0, "x": 0.0}
    GUI_DRAG_PARAMETERS = ["z", "y", "x"]
    def _fit(self):
        self.matrix = np.eye(3)
        self.shift = np.asarray([-self.params["z"], -self.params["y"], -self.params["x"]])
    def invert(self):
        return self.__class__(x=-self.params["x"], y=-self.params["y"], z=-self.params["z"])

class TranslateRotateRescaleParametric(AffineTransform,Transform): # Deprecated
    NAME = "Translate, rotate, and rescale"
    #SHORTCUT_KEY = "r"
    SORT_WEIGHT = -98
    DEFAULT_PARAMETERS = {"z": 0.0, "y": 0.0, "x": 0.0, "zrotate": 0.0, "yrotate": 0.0, "xrotate": 0.0, "zscale": 1.0, "yscale": 1.0, "xscale": 1.0, "invert": False}
    GUI_DRAG_PARAMETERS = ["z", "y", "x"]
    def _fit(self):
        self.matrix = rotation_matrix(self.params["zrotate"], self.params["yrotate"], self.params["xrotate"]) @ np.asarray([[self.params["zscale"], 0, 0], [0, self.params["yscale"], 0], [0, 0, self.params["xscale"]]])
        if self.params['invert']:
            self.matrix = np.linalg.inv(self.matrix)
        self.shift = np.asarray([-self.params["z"], -self.params["y"], -self.params["x"]])
    def invert(self):
        newzyx = [self.params["z"], self.params["y"], self.params["x"]] @ np.linalg.inv(self.matrix)
        return self.__class__(zrotate=self.params["zrotate"], yrotate=self.params["yrotate"], xrotate=self.params["xrotate"], z=-newzyx[0], y=-newzyx[1], x=-newzyx[2], zscale=self.params["zscale"], yscale=self.params["yscale"], xscale=self.params["xscale"], invert=(not self.params['invert']))

class TranslateRotateRescale2DParametric(AffineTransform,Transform): # Deprecated
    DEFAULT_PARAMETERS = {"y": 0.0, "x": 0.0, "rotate": 0.0, "scale": 1.0}
    GUI_DRAG_PARAMETERS = [None, "y", "x"]
    def _fit(self):
        self.matrix = rotation_matrix(self.params["rotate"], 0, 0) @ np.asarray([[1, 0, 0], [0, self.params["scale"], 0], [0, 0, self.params["scale"]]])
        self.shift = np.asarray([0, -self.params["y"], -self.params["x"]])
    def invert(self):
        newzyx = [0, self.params["y"], self.params["x"]] @ self.matrix.T
        return self.__class__(rotate=-self.params["rotate"], y=-newzyx[1], x=-newzyx[2], scale=1/self.params["scale"])

class ShearParametric(AffineTransform,Transform): # Deprecated
    NAME = "Shear"
    DEFAULT_PARAMETERS = {"yzshear": 0, "xzshear": 0, "xyshear": 0, "zshift": 0, "yshift": 0, "xshift": 0}
    # SHORTCUT_KEY = "z"
    GUI_DRAG_PARAMETERS = ["zshift", "yshift", "xshift"]
    SORT_WEIGHT = -95
    def _fit(self):
        self.shift = np.zeros(3)
        self.shift = np.asarray([-self.params["zshift"], -self.params["yshift"], -self.params["xshift"]])
        self.matrix = np.asarray([[1, 0, 0], [self.params["yzshear"], 1, 0], [self.params["xzshear"], self.params["xyshear"], 1]])
    def invert(self):
        s = np.asarray([-self.params["zshift"], -self.params["yshift"], -self.params["xshift"]]) @ np.asarray([[1, 0, 0], [-self.params["yzshear"], 1, 0], [self.params["yzshear"]*self.params["xyshear"]-self.params["xzshear"], -self.params["xyshear"], 1]])
        return self.__class__(yzshear=-self.params["yzshear"], xzshear=self.params["xyshear"]*self.params["yzshear"]-self.params["xzshear"], xyshear=-self.params["xyshear"], zshift=s[0], yshift=s[1], xshift=s[2])

# This doesn't work very well
class DistanceWeightedAverageGaussian(PointTransformNoAnalyticInverse): # Deprecated
    DEFAULT_PARAMETERS = {"extent": 1, "invert": False}
    def _transform(self, points, points_start, points_end):
        points = np.asarray(points, dtype="float")
        baseline = np.zeros_like(points[:,0])
        pos = np.zeros_like(points)
        for i in range(0, len(points_start)):
            mvn = scipy.stats.multivariate_normal(points_start[i], np.eye(3)*self.params["extent"])
            baseline += mvn.pdf(points)
            for j in range(0, 3):
                pos[:,j] += mvn.pdf(points)*(points_end[i][j]-points_start[i][j])
        epsilon = 1e-100 # For numerical stability
        pos += np.mean(points_end-points_start, axis=0, keepdims=True)*epsilon
        pos /= (baseline[:,None] + epsilon)
        return points + pos

Shear = ShearParametric
TranslateRotateRescale = Affine # Old name, technically incorrect
