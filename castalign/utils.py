import imageio
import numpy as np
import io
import scipy.stats
import zlib
import imageio.plugins.ffmpeg # If this fails, install the imageio-ffmpeg package with pip
import skimage
import skimage.registration
from .ndarray_shifted import ndarray_shifted

try: # Work around skimage bug in some versions
    phase_correlation = lambda x,y : skimage.registration.phase_cross_correlation(x, y, normalization=None)
    phase_correlation(np.asarray([1]), np.asarray([1]))
except TypeError:
    phase_correlation = lambda x,y : skimage.registration.phase_cross_correlation(x, y)

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

def blit(source, target, loc):
    """Paste one 3D block into another, clipping to valid bounds.

    This is an internal helper for building composite volumes (for example in
    :func:`bake_images`). It exists so higher-level code can place data by
    absolute location without manual slicing logic.

    Parameters
    ----------
    source : ndarray
        Source volume of shape ``(Z, Y, X)``
    target : ndarray
        Destination volume of shape ``(Z, Y, X)``. Modified in place.
    loc : array-like of int, shape (3,)
        Voxel coordinate in ``target`` where ``source[0, 0, 0]`` should be
        placed. Can be negative or out of bounds.

    Returns
    -------
    None
        ``target`` is modified in place.
    """
    source_size = np.asarray(source.shape)
    target_size = np.asarray(target.shape)
    # If we had infinite boundaries, where would we put it?
    target_loc_tl = loc
    target_loc_br = target_loc_tl + source_size
    # Compute the index for the source
    source_loc_tl = -np.minimum(0, target_loc_tl)
    source_loc_br = source_size - np.maximum(0, target_loc_br - target_size)
    # Recompute the index for the target
    target_loc_br = np.minimum(target_size, target_loc_tl+source_size)
    target_loc_tl = np.maximum(0, target_loc_tl)
    # Compute slices from positions
    target_slices = [slice(s1, s2) for s1,s2 in zip(target_loc_tl,target_loc_br)]
    source_slices = [slice(s1, s2) for s1,s2 in zip(source_loc_tl,source_loc_br)]
    # Perform the blit
    target[tuple(target_slices)] = source[tuple(source_slices)]

def bake_images(im_fixed, im_movable, transform):
    """Build one combined 3D volume from fixed and movable volumes.

    The function applies ``transform`` to the movable volume, finds a canvas
    large enough to hold both volumes in absolute space, and returns the merged
    result.

    Parameters
    ----------
    im_fixed : ndarray or ndarray_shifted
        Fixed/reference 3D volume in shape ``(Z, Y, X)``.
    im_movable : ndarray or ndarray_shifted
        Movable 3D volume in ``(Z, Y, X)`` order.
    transform : castalign.base.Transform
        Transform that maps movable-space coordinates into fixed-space
        coordinates

    Returns
    -------
    castalign.ndarray_shifted.ndarray_shifted
        Combined 3D volume in absolute coordinates.

    See Also
    --------
    castalign.base.Transform.transform_image
        Method used to resample the movable image into the fixed frame.
    castalign.base.Transform.origin_and_maxpos
        Method used to estimate transformed bounds before baking.
    castalign.utils.blit
        Internal helper used for clipped array placement.
    """
    origin = transform.origin_and_maxpos(im_movable)[0]
    ti = transform.transform_image(im_movable)
    fixed_origin = im_fixed.origin if isinstance(im_fixed, ndarray_shifted) else np.asarray([0,0,0])
    fixed_maxpos = fixed_origin + np.asarray(im_fixed.shape)
    new_dims_max = np.ceil(np.max([ti.shape + origin, fixed_maxpos], axis=0)).astype(int)
    new_dims_min = np.floor(np.min([origin, fixed_origin], axis=0)).astype(int)
    im = np.zeros(new_dims_max - new_dims_min, dtype=float)
    blit(im_fixed, im, tuple(fixed_origin - new_dims_min))
    blit(im_movable, im, tuple(origin.astype(int) - new_dims_min))
    return ndarray_shifted(im, origin=new_dims_min)

def absolute_coords_to_voxel_coords(img, coords):
    """Convert absolute coordinates to voxel indices for a 3D volume.

    For ndarrays, in index i refers to the i'th voxel, or equivalently, the
    voxel located at position i in the image's coordinate system.  However, in
    ndarray_shifted, these two do not necessarily coincide.  This converts
    position i in the ndarray_shifted's coordinate system into the voxel located
    at that position.

    Parameters
    ----------
    img : ndarray or ndarray_shifted
        3D volume. If plain ndarray, origin is assumed to be ``(0, 0, 0)``.
    coords : array-like
        Absolute coordinate(s), shape ``(3,)`` or ``(N, 3)``.

    Returns
    -------
    ndarray of int
        Rounded voxel indices: ``round(coords - img.origin)``.

    See Also
    --------
    castalign.utils.voxel_coords_to_absolute_coords
        Inverse conversion from voxel indices to absolute coordinates.
    castalign.ndarray_shifted.ndarray_shifted
        Array type that stores the ``origin`` used by this conversion.
    """
    if not isinstance(img, ndarray_shifted):
        img = ndarray_shifted(img)
    return np.round(coords - img.origin).astype(int)

def voxel_coords_to_absolute_coords(img, coords):
    """Convert voxel indices to absolute coordinates for a 3D volume.

    This is the inverse of :func:`castalign.utils.absolute_coords_to_voxel_coords`.

    Parameters
    ----------
    img : ndarray or ndarray_shifted
        3D volume. If plain ndarray, origin is assumed to be ``(0, 0, 0)``.
    coords : array-like
        Voxel coordinate(s), shape ``(3,)`` or ``(N, 3)``.

    Returns
    -------
    ndarray
        Absolute coordinates: ``coords + img.origin``.

    See Also
    --------
    castalign.utils.absolute_coords_to_voxel_coords
        Inverse conversion from absolute coordinates to voxel indices.
    castalign.ndarray_shifted.ndarray_shifted
        Array type that stores the ``origin`` used by this conversion.
    """
    if not isinstance(img, ndarray_shifted):
        img = ndarray_shifted(img)
    return coords + img.origin

def crop_to_intersection(img1, img2):
    """Crop two 3D volumes to the same overlapping region in absolute space.

    This is useful when two volumes are in the same coordinate frame and you
    need matching fields of view for comparison or visualization.

    Parameters
    ----------
    img1 : ndarray or ndarray_shifted
        First 3D volume.
    img2 : ndarray or ndarray_shifted
        Second 3D volume.

    Returns
    -------
    tuple of ndarray_shifted
        ``(img1_crop, img2_crop)`` with the same origin and shape.

    See Also
    --------
    castalign.utils.absolute_coords_to_voxel_coords
        Coordinate conversion used to compute voxel slices at the intersection.
    castalign.utils.voxel_coords_to_absolute_coords
        Coordinate conversion used to compute absolute intersection bounds.
    castalign.ndarray_shifted.ndarray_shifted
        Shift-aware array class used for inputs and outputs.
    """
    if not isinstance(img1, ndarray_shifted):
        img1 = ndarray_shifted(img1)
    if not isinstance(img2, ndarray_shifted):
        img2 = ndarray_shifted(img2)
    absolute_coords_to_voxel_coords = lambda img,coords: np.round(coords - img.origin).astype(int)
    voxel_coords_to_absolute_coords = lambda img,coords: coords + img.origin
    origin = np.max([img1.origin, img2.origin], axis=0)
    maxpos = np.min([voxel_coords_to_absolute_coords(img1, img1.shape), voxel_coords_to_absolute_coords(img2, img2.shape)], axis=0)
    output_img = np.zeros(img1.shape)
    i1 = absolute_coords_to_voxel_coords(img1, origin)
    i2 = absolute_coords_to_voxel_coords(img1, maxpos)
    img1_crop = np.array(img1)[i1[0]:i2[0],i1[1]:i2[1],i1[2]:i2[2]]
    i1 = absolute_coords_to_voxel_coords(img2, origin)
    i2 = absolute_coords_to_voxel_coords(img2, maxpos)
    img2_crop = np.array(img2)[i1[0]:i2[0],i1[1]:i2[1],i1[2]:i2[2]]
    return ndarray_shifted(img1_crop, origin), ndarray_shifted(img2_crop, origin)

    

def load_image(fn, channel=None):
    """Load a 2D image file and convert it to a single-slice 3D volume.

    CASTalign is built for 3D volumes. This helper exists mostly for convenience
    of converting a 2D channel-last image into ``(1, Y, X)`` 3D image

    Parameters
    ----------
    fn : str or path-like
        Path to an image readable by ``imageio.imread``.
    channel : int or None, optional
        Channel index to extract from a ``(Y, X, C)`` image. If ``None``,
        non-blank channels are averaged.

    Returns
    -------
    ndarray
        Single-slice volume with shape ``(1, Y, X)``.
    """
    img = imageio.imread(fn)
    if channel is None:
        axes = list(np.any((img!=0) & (img!=255), axis=(0,1)))
        return np.mean(img[:,:,axes], axis=2)[None]
    else:
        return img[:,:,channel][None]

def image_is_label(img):
    """Guess whether a 3D volume is a label volume.

    Internally used as a heuristic to pick things like compression behavior for
    label-like vs intensity-like data.

    Parameters
    ----------
    img : ndarray
        3D volume of shape ``(Z, Y, X)``.

    Returns
    -------
    bool
        ``True`` if sampled stats look label-like, else ``False``.
    """
    plane = img[img.shape[0]//2] # Pick a plane in the middle
    # First a quick test to eliminate most cases quickly
    pmini = plane[0:100,0:100]
    if len(np.unique(pmini)) > len(pmini.flat)/2:
        return False
    if np.median(np.abs(np.diff(plane, axis=0))) >= 1: # Should be mostly flat
        return False
    # Now a more complete test
    vals,counts = np.unique(plane, return_counts=True)
    if len(vals) > plane.shape[0]*plane.shape[1] / 25: # There are too many "labels"
        return False
    if not np.all(np.isclose(vals, vals.astype(int))): # Don't fall on integer values
        return False
    if len(vals) == 1: # All black
        return False
    # if 0 not in vals or np.max(counts) != counts[vals==0][0]: # Zero isn't the most common
    #     return False
    return True

def _image_compression_transform(img, transform_id):
    """Apply an internal pre-compression intensity transform.

    This internal helper exists to make lossy compression work better on skewed
    3D microscopy volumes.

    Parameters
    ----------
    img : ndarray
        3D volume data.
    transform_id : int
        Internal transform code:
        - ``0``: no transform
        - ``1``: ``log(10 + max(img, 0))``

    Returns
    -------
    ndarray
        Transformed 3D volume.

    Notes
    -----
    Internal-only helper for :func:`compress_image`.
    """
    if transform_id == 0: # None
        return img
    if transform_id == 1: # Truncated log + 10
        return np.log(10+np.maximum(0, img))

def _image_decompression_transform(img, transform_id):
    """Undo internal intensity transforms after decompression.

    Internal companion to :func:`_image_compression_transform`, used by
    :func:`decompress_image`.

    Parameters
    ----------
    img : ndarray
        Decoded 3D volume in transformed intensity space.
    transform_id : int
        Internal transform code:
        - ``0``: no transform
        - ``1``: ``exp(img) - 10``

    Returns
    -------
    ndarray
        Inverse-transformed 3D volume.

    Notes
    -----
    Internal-only helper for :func:`decompress_image`.
    """
    if transform_id == 0: # None
        return img
    if transform_id == 1: # Truncated log + 10
        return np.exp(img)-10

def _image_detect_transform(img):
    """Pick which internal intensity transform to use before compression.

    This internal helper exists so callers do not have to tune transform choice
    manually for every 3D volume.

    Parameters
    ----------
    img : ndarray
        Input 3D volume.

    Returns
    -------
    int
        Transform code: ``1`` when skewness is high, else ``0``.
    """
    _img = img if np.prod(img.shape) < 10000000 else img[::4,::4,::4] # Hack for big images
    if scipy.stats.skew(_img.reshape(-1)) > 25:
        return 1 # Truncated log + 10
    return 0 # None

def compress_image(img, level="normal"):
    """Compress a 3D volume for CASTalign storage.

    This is the main package helper used when image volumes need to be saved in
    graph files or passed around compactly.

    Parameters
    ----------
    img : ndarray
        Volume data of shape ``(Z, Y, X)`` or ``(Y, X)`` (interpreted
        as ``(1, Y, X)``)
    level : {'low', 'normal', 'high', 'label'}, optional
        Compression mode.

        - ``'label'`` forces lossless label-style compression.
        - ``'low'``, ``'normal'``, ``'high'`` are lossy settings for

          non-label-like data.

    Returns
    -------
    data : bytes-like or ndarray of uint8
        Compressed payload.
    kind : list
        Metadata used by :func:`decompress_image` to decode ``data``.
    """
    assert level in ["low", "normal", "high", "label"], "Invalid level"
    # Format code 0 == no compression
    # Format code 1 == vp9 video stack
    # Format code 2 == jpegs
    if img.ndim == 2:
        img = np.asarray([img])
    if False: # Image code 0 is uncompressed, which we don't use anymore.
        return img, [0]
    if level == "label" or image_is_label(img): # Lossless compression with gzip (format code 3)
        if np.max(img) < 2**8 and np.min(img) >= 0:
            img = img.astype("uint8")
        elif np.max(img) < 2**16 and np.min(img) >= 0:
            img = img.astype("uint16")
        # Gzip is fast but not great, so we compress twice and this works well (but why?)
        comp = zlib.compress(zlib.compress(img, 9), 9)
        return comp, [3, str(img.dtype), *img.shape]
    if min(img.shape) > 10: # Compress volumes as a video in vp9 format (format code 1)
        transform_id = _image_detect_transform(img)
        img = _image_compression_transform(img, transform_id)
        bitrate = 20000000 if level == "normal" else 40000000 if level == "high" else 10000000
        # We normalise in a complicated way to reduce memory usage for large images
        maxplanes = np.quantile(img, .999)
        minplanes = np.min(img)
        imgnorm = img.copy()
        imgnorm[imgnorm>maxplanes] = maxplanes
        imgnorm -= minplanes
        for i in range(0, imgnorm.shape[0]):
            imgnorm[i] = imgnorm[i]/(maxplanes-minplanes)*255
        imgnorm = imgnorm.astype("uint8")
        zdim = np.argmin(imgnorm.shape) # Thin dimension may not be z
        imgnorm = imgnorm.swapaxes(zdim, 0)
        # We need to make the image a size multiple of 16
        pady = 16 - (imgnorm.shape[1] % 16) % 16
        padx = 16 - (imgnorm.shape[2] % 16) % 16
        imgnorm = np.pad(imgnorm, ((0,0), (0,pady), (0,padx)))
        kind = [1, transform_id, bitrate, maxplanes, minplanes, pady, padx, zdim]
        pseudofile = io.BytesIO()
        writer = imageio.get_writer(pseudofile, format="webm", fps=30, bitrate=bitrate, codec="vp9", macro_block_size=16)
        for p in imgnorm:
            writer.append_data(p)
        writer.close()
        return np.frombuffer(pseudofile.getvalue(), dtype=np.uint8), kind
    else: # Compress as jpegs (format code 2)
        transform_id = _image_detect_transform(img)
        img = _image_compression_transform(img, transform_id)
        quality = 90 if level == "normal" else 95 if level == "high" else 80
        files = []
        maxes = []
        mins = []
        for i in range(0, img.shape[0]):
            pseudofile = io.BytesIO()
            maxval = np.quantile(img[i], .999)
            minval = np.min(img[i])
            maxes.append(maxval)
            mins.append(minval)
            im = ((np.minimum(maxval, img[i])-minval)/(maxval-minval)*255).astype("uint8")
            imageio.v3.imwrite(pseudofile, im, format_hint=".jpeg", quality=quality)
            files.append(np.frombuffer(pseudofile.getvalue(), dtype=np.uint8))
        lens = list(map(len, files))
        info = np.concatenate(list(zip(lens, maxes, mins)))
        kind = [2, transform_id, quality]+info.tolist()
        return np.concatenate(files), kind

def decompress_image(data, kind):
    """Decompress a volume payload produced by :func:`compress_image`.

    This is the read-side helper used when loading graph data.

    Parameters
    ----------
    data : bytes-like or ndarray
        Compressed payload bytes/array.
    kind : sequence
        Metadata returned by :func:`compress_image`. ``kind[0]`` is the format
        code (0/1/2/3).

    Returns
    -------
    ndarray
        Decompressed volume array (typically ``(Z, Y, X)``).
    """
    if int(kind[0]) == 0:
        return data
    if int(kind[0]) == 1:
        _,transform_id,bitrate,maxval,minval,pady,padx,zdim = kind
        padx = int(padx)
        pady = int(pady)
        pseudofile = io.BytesIO(data.tobytes())
        r = imageio.get_reader(pseudofile, format="webm")
        d = np.asarray([it[:(it.shape[0]-pady),:(it.shape[1]-padx),0] for it in r.iter_data()], dtype="float32")
        d = d.swapaxes(int(zdim), 0)
        r.close()
        return _image_decompression_transform(d/255.0*(maxval-minval)+minval, int(transform_id))
    if int(kind[0]) == 2:
        transform_id,quality = kind[1:3]
        lens = np.asarray(kind[3::3]).astype(int)
        maxes = kind[4::3]
        mins = kind[5::3]
        ibase = 0
        ims = []
        for i,l in enumerate(lens):
            pseudofile = io.BytesIO(data[ibase:(ibase+l)].tobytes())
            im = np.asarray(imageio.v3.imread(pseudofile, format_hint=".jpeg"))
            im = _image_decompression_transform(im/255.0*(maxes[i]-mins[i])+mins[i], int(transform_id))
            ims.append(im)
            ibase += l
        return np.asarray(ims, dtype="float32")
    if int(kind[0]) == 3:
        imgfile = zlib.decompress(zlib.decompress(data))
        return np.frombuffer(imgfile, dtype=kind[1]).reshape(*np.asarray(kind[2:]).astype('int'))
    raise ValueError(f"Invalid kind {kind}")

def invert_function_numerical(func, point):
    """Numerically find an input point that maps to a target output point.

    This is an internal optimization helper used by invert_transform_numerical.

    Parameters
    ----------
    func : callable
        Forward point-mapping function. It is called as
        ``func(np.asarray([x]))``.
    point : array-like
        Target coordinate of shape ``(3,)``.

    Returns
    -------
    ndarray
        Estimated input point.
    """
    point = np.asarray(point)
    obj = lambda x : np.sum(np.square(point-func(np.asarray([x]))))
    starts = [[0, 0, 0], point]
    opts = []
    for start in starts:
        opts.append(scipy.optimize.minimize(obj, x0=start))
    return min(opts, key=lambda x : x.fun).x

def invert_transform_numerical(tform, points):
    """Invert one or more 3D points through a transform.

    This is used internally for transform types without an analytic inverse.

    Parameters
    ----------
    tform : object
        Transform object with ``invert()`` and ``transform(...)`` methods.
    points : array-like
        Point(s) in ``(z, y, x)`` order. Shape ``(3,)`` or ``(N, 3)``.

    Returns
    -------
    ndarray
        Inverse-mapped point(s).
    """
    points = np.asarray(points)
    try:
        if points.ndim == 2:
            return tform.invert().transform(points)[0]
        else:
            return tform.invert().transform(np.asarray([points]))[0]
    except NotImplementedError:
        pass
    if points.ndim == 2:
        return np.asarray([invert_transform_numerical(tform, points[i]) for i in range(0, points.shape[0])])
    return invert_function_numerical(tform.transform, np.asarray([x]))
