import numpy as np

class ndarray_shifted(np.ndarray):
    """NumPy ndarray with an attached origin offset in 3D space.

    This is used to carry array data together with a spatial origin so image
    coordinates can be interpreted in a shared 3D coordinate system without
    copying data into a separate wrapper object.

    Notes
    -----
    The ``origin`` attribute stores a coordinate offset (typically ``[z, y, x]``).
    Array behavior is otherwise the same as ``numpy.ndarray``.

    See Also
    --------
    castalign.utils.absolute_coords_to_voxel_coords
        Convert absolute coordinates to voxel indices using ``origin``.
    castalign.utils.voxel_coords_to_absolute_coords
        Convert voxel indices back to absolute coordinates.
    castalign.utils.crop_to_intersection
        Crop two shifted volumes to a shared overlapping field of view.

    Examples
    --------
    Create a shifted 3D array::

        >>> arr = ndarray_shifted(np.zeros((4, 5, 6)), origin=[10, 20, 30])
        >>> isinstance(arr, ndarray_shifted)
        True
        >>> isinstance(arr, np.ndarray)
        True
        >>> arr.origin.tolist()
        [10, 20, 30]

    Keep a plain ndarray when no shift is needed::

        >>> out = ndarray_shifted(np.zeros((3, 3, 3)), origin=[0, 0, 0], only_if_necessary=True)
        >>> isinstance(out, np.ndarray)
        True
        >>> isinstance(out, ndarray_shifted)
        False
    """
    def __new__(cls, a, origin=[0,0,0], only_if_necessary=False):
        if isinstance(a, cls):
            origin = a.origin
        if np.all(origin == np.asarray([0,0,0])) and only_if_necessary:
            return a
        arr = np.asarray(a).view(cls)
        if isinstance(origin, (float, int)):
            osigin = [origin]*a.ndim
        arr.origin = np.asarray(origin)
        # Finally, we must return the newly created object:
        return arr
    def __array_finalize__(self, obj):
        if obj is None: return
        self.origin = getattr(obj, 'origin', np.asarray([0,0,0]))
    def __repr__(self):
        s = super().__repr__()
        assert s[-1] == ")", "Cannot print"
        ret = s[:-1]
        if np.any(self.origin != [0,0,0]):
            ret += f", origin={list(self.origin)!r}"
        return ret+")"
