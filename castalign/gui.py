from .base import Identity, Translate, Transform, PointTransform, AffineTransform, FlipParametric
import numpy as np
import scipy.ndimage
import napari
import magicgui
import vispy
from . import utils
from .ndarray_shifted import ndarray_shifted


class GraphViewer(napari.Viewer):
    def __init__(self, graph, space=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "space", space)
        if isinstance(space, str):
            self.title = f"Alignment in {space} space"
    def _get_data_origin_name(self, data, space, name=None, labels=False):
        if isinstance(data, str):
            name = name or data
            space = data if space is None else space
            data = self.graph.get_image(data)
        if self.space is None and space is not None: # First image sets the space if unset
            object.__setattr__(self, "space", space)
            self.title = f"Alignment in {space} space"
        if data.shape[0] == 1:
            data = data * np.ones((2,1,1), dtype=data.dtype) # TODO Hack for now when we can't see 1-plane images in napari
        if self.space is not None and space is not None and self.space != space:
            data = self.graph.get_transform(space, self.space).transform_image(data, labels=labels)
        origin = data.origin if isinstance(data, ndarray_shifted) else np.zeros_like(data.shape)
        return data, origin, name or "data"
    def add_image(self, data, space=None, name=None, **kwargs):
        data, origin, name = self._get_data_origin_name(data, space, name)
        return super().add_image(data, translate=origin, name=name, **kwargs)
    def add_labels(self, data, space=None, name=None, **kwargs):
        data, origin, name = self._get_data_origin_name(data, space, name, labels=True)
        return super().add_labels(data, translate=origin, name=name, **kwargs)
    def add_points(self, data, space=None, **kwargs):
        if space is not None and self.space is not None:
            data = self.graph.get_transform(space, self.space).transform(data)
        return super().add_points(data, **kwargs)

def alignment_gui(movable_image, base_image, transform=None, graph=None, references=[], crop=False, transform_type=None):
    """Align images

    `base_image` and `movable_image` should be 2D or 3D numpy ndarrays.
    Alternatively, if they are tuples, they will be interpreted as
    multi-channel, with each channel shown as a separate napari layer.

    `transform` is a Transform, either the class itself (an unfitted
    transform), or one with parameters/data.  If the latter, the existing
    parameters/data can be modified.  This can also be None, in which case it
    will be taken from the graph (if it exists) or else set to Identity().

    `references` is a list of additional images to show to aid with alingment.
    This should be a list of tuples, where each tuple is (image, transform)

    "crop" allows you to reduce the drawn area of the transformed image, making
    transforms faster and use less memory.  If True, it will only show the area
    of the movable image that intersects with the first base image.  If a tuple
    of numbers, it will show the region (zmax,ymax,xmax).  If a tuple of tuples,
    it will show the region ((zmin,zmax),(ymin,ymax),(xmin,xmax)).
    """
    if transform_type is not None:
        print("The `transform_type` parameter is deprecated, use `transform` instead")
    if transform is None:
        transform = transform_type
    if not isinstance(base_image, (tuple, list)):
        base_image = [base_image]
    if not isinstance(movable_image, (tuple, list)):
        movable_image = [movable_image]
    if transform is None and graph is not None:
        try:
            transform = graph.get_transform(movable_image[0], base_image[0])
        except:
            pass
    if transform is None:
        transform = Identity
    # Put all of the pre-images and post-images into the same space.  Currently only supported for graphs.
    if graph is not None and isinstance(movable_image[0], str):
        movable_image_img = tuple(ndarray_shifted(graph.get_image(n)) if n == movable_image[0] else ndarray_shifted(graph.get_transform(n, movable_image[0]).transform_image(graph.get_image(n))) for n in movable_image)
    else:
        movable_image_img = tuple(ndarray_shifted(mi) for mi in movable_image)
    if graph is not None and isinstance(base_image[0], str):
        base_image_img = tuple(graph.get_image(n) if n == base_image[0] else graph.get_transform(n, base_image[0]).transform_image(graph.get_image(n)) for n in base_image)
    else:
        base_image_img = tuple(base_image)
    if graph is not None and len(references)>0 and isinstance(references[0], str):
        references_img = tuple((graph.get_image(n), graph.get_transform(n, base_image[0])) for n in references)
    else:
        references_img = tuple(references)
    bi0 = ndarray_shifted(base_image_img[0])
    outsize = None if crop is False else tuple(zip(bi0.origin, bi0.origin+bi0.shape)) if crop is True else crop
    pretransform = transform.pretransform()
    tform = pretransform
    # Test if we are editing an existing transform
    movable_points = []
    base_points = []
    if isinstance(transform, Transform):
        if isinstance(transform, PointTransform):
            movable_points = list(transform.points_start)
            base_points = list(transform.points_end)
        params = transform.params.copy()
        transform = transform.__class__
    else:
        print("Setting default params")
        params = transform.DEFAULT_PARAMETERS.copy()
    is_point_transform = issubclass(transform, PointTransform)
    _prev_matrix = None # A special case optimisation for linear transforms
    _prev_translate = None # A special case optimisation for linear transforms
    v = napari.Viewer()
    # v.window._qt_viewer._dockLayerList.setVisible(False)
    # v.window._qt_viewer._dockLayerControls.setVisible(False)
    tform_type = transform
    layers_base = []
    for bi in base_image_img:
        if utils.image_is_label(bi):
            layers_base.append(v.add_labels(bi, name="base", translate=(bi.origin if isinstance(bi, ndarray_shifted) else [0,0,0])))
        else:
            layers_base.append(v.add_image(bi, colormap="red", blending="additive", name="base", translate=(bi.origin if isinstance(bi, ndarray_shifted) else [0,0,0])))
    layers_movable = []
    for mi in movable_image_img:
        tfi = ndarray_shifted(tform.transform_image(mi, output_size=outsize, force_size=False))
        if utils.image_is_label(mi):
            layers_movable.append(v.add_labels(tfi, name="movable", translate=tfi.origin))
        else:
            layers_movable.append(v.add_image(tfi, colormap="green", blending="additive", name="movable", translate=tfi.origin))
    layers_reference = []
    for i,(ri,rt) in enumerate(references_img):
        if utils.image_is_label(ri):
            layers_reference.append(v.add_labels(rt.transform_image(ri, output_size=outsize, force_size=False), name=f"reference_{i}", translate=rt.origin_and_maxpos(ri, output_size=outsize, force_size=False)[0]))
        else:
            layers_reference.append(v.add_image(rt.transform_image(ri, output_size=outsize, force_size=False), colormap="blue", blending="additive", name=f"reference_{i}", translate=rt.origin_and_maxpos(ri, output_size=outsize, force_size=False)[0]))
    if is_point_transform:
        layer_base_points = v.add_points(None, ndim=3, name="base points", border_width=0, face_color=[1, .6, .6, 1])
        layer_movable_points = v.add_points(None, ndim=3, name="movable points", border_width=0, face_color=[.6, 1, .6, 1])
        layer_base_points.data = base_points
        layer_movable_points.data = movable_points
        layer_base_points.editable = False
        layer_movable_points.editable = False
    # Disable the transform button in napari, because this doesn't actually work in napari and is just confusing
    for l in v.layers:
        try:
            v._window._qt_viewer._controls.widgets[l]._MODE_BUTTONS['transform'].hide()
        except:
            pass
    # Disable other buttons that might mess things up
    try:
        v._window._qt_viewer._layersButtons.deleteButton.hide()
        v._window._qt_viewer._layersButtons.newLabelsButton.hide()
        v._window._qt_viewer._layersButtons.newPointsButton.hide()
        v._window._qt_viewer._layersButtons.newShapesButton.hide()
    except:
        pass
    def select_base_movable():
        # The logic to get this to work is out of order, so please read code in the
        # order specified in the comments.
        temp_points = []
        # Utility function: local ascent
        def find_local_maximum(image, starting_point, w=3, stdev=2):
            """Find the local maximum near a point.

            This algorithm performs gradient ascent to find a local maximum.  It
            smooths first in a local region to avoid plateaus, often caused by
            quantized data.

            Parameter `w` describes how big of a window to look for when
            performing gradient ascent.  Parameter `stdev` is the smoothing
            amount.  Set `stdev` to 0 to avoid smoothing.  For positive `stdev`
            values, select a bigger region than specified by `w`, smooth it, and
            then select the desired size.

            """
            point = np.round(starting_point).astype(int)
            l = np.maximum(point-w, point*0)
            u = point+w
            if stdev == 0:
                region = image[tuple([slice(i,j+1) for i,j in zip(l,u)])]
            else:
                w_extra = np.ceil(stdev).astype(int)*2 + w
                l_extra = np.maximum(point-w_extra, point*0)
                u_extra = point+w_extra
                region_pre = image[tuple([slice(i,j+1) for i,j in zip(l_extra,u_extra)])]
                region_smooth = scipy.ndimage.gaussian_filter(region_pre, stdev)
                region = region_smooth[tuple([slice(i-ie,j-je if je>j else None) for i,ie,j,je in zip(l,l_extra,u,u_extra)])]
            peak_ind = tuple(np.unravel_index(np.argmax(region), region.shape)+point-np.minimum(point, 0*point+w))
            point = tuple(point)
            if np.all(image[peak_ind] == image[point]): # Can't compare directly in case neighbours have same value
                return point
            return find_local_maximum(image, peak_ind)
        def best_layer(layers):
            for l in layers:
                if l.visible:
                    return l
            return layers[0]
        # Step 2: Processe base layer click
        def base_click_callback(viewer, e):
            if e.type != "mouse_press":
                return
            # If right click, find the nearby peak
            if e.button == 2 and not isinstance(best_layer(layers_base), napari.layers.Labels): # Right click
                bl = best_layer(layers_base)
                try:
                    pos = find_local_maximum(bl.data, e.position - bl.translate) + bl.translate
                except RecursionError:
                    pos = e.position
            else:
                pos = e.position
            # Step 2a: Process base layer click
            temp_points.append(pos)
            for layer_base in layers_base:
                layer_base.mouse_drag_callbacks.pop()
            for layer_movable in layers_movable:
                layer_movable.mouse_drag_callbacks.append(movable_click_callback)
            layer_base_points.data = np.vstack([layer_base_points.data, pos])
            set_point_size()
            # Step 2b: Prepare for movable layer click
            v.layers.selection = set([layers_movable[0]])
            for layer_movable in layers_movable:
                layer_movable.opacity = 1
            for layer_base in layers_base:
                layer_base.opacity = .1
        # Step 3: Process movable layer click
        def movable_click_callback(viewer, e):
            nonlocal tform
            if e.type != "mouse_press":
                return
            # If right click, find the nearby peak
            if e.button == 2 and not isinstance(best_layer(layers_movable), napari.layers.Labels): # Right click
                bl = best_layer(layers_movable)
                try:
                    pos = find_local_maximum(bl.data, e.position - bl.translate) + bl.translate
                except RecursionError:
                    pos = e.position
            else:
                pos = e.position
            # Step 3a: Process movable layer click
            base_points.append(temp_points[0])
            movable_points.append(pretransform.transform(utils.invert_transform_numerical(tform, pos)))
            for layer_movable in layers_movable:
                layer_movable.mouse_drag_callbacks.pop()
            for layer_base in layers_base:
                layer_base.opacity = 1
            # Step 3b: Clean up after clicks
            layer_base_points.data = base_points
            layer_movable_points.data = tform.transform(pretransform.inverse_transform(movable_points))
            set_point_size()
            v.layers.selection = prev_selection
            for b in buttons:
                b.enabled = True
        # Step 1: Wait for a click on the base layer
        v.layers.selection = set([layers_base[0]])
        for layer_movable in layers_movable:
            layer_movable.opacity = .1
        for layer_base in layers_base:
            layer_base.mouse_drag_callbacks.append(base_click_callback)
        prev_selection = v.layers.selection
        for b in buttons:
            b.enabled = False
    def remove_point():
        if len(base_points) == 0:
            return
        # The logic to get this to work is out of order, so please read code in the
        # order specified in the comments.
        temp_points = []
        # Step 2: Processe base layer click
        def remove_click_callback(viewer, e):
            if e.type != "mouse_press":
                return
            v.mouse_drag_callbacks.pop()
            # Step 2a: Find and remove the closest point (base or movable) to the click and its corresponding point (movable or base)
            search_point = e.position
            dists_base = np.sum(np.square(np.asarray(base_points) - [search_point]), axis=1)
            dists_movable = np.sum(np.square(np.asarray(tform.transform(pretransform.inverse_transform(movable_points))) - [search_point]), axis=1)
            ind = np.argmin(dists_base) if np.min(dists_base) < np.min(dists_movable) else np.argmin(dists_movable)
            base_points.pop(ind)
            movable_points.pop(ind)
            # Step 2b: Clean up
            if len(base_points) > 0:
                layer_base_points.data = base_points
                layer_movable_points.data = tform.transform(pretransform.inverse_transform(movable_points))
            else:
                layer_base_points.data = []
                layer_movable_points.data = []
            set_point_size()
            for b in buttons:
                b.enabled = True
            for layer_movable in layers_movable:
                layer_movable.opacity = 1
            for layer_base in layers_base:
                layer_base.opacity = 1
        # Step 1: Wait for a click on the base layer
        for layer_movable in layers_movable:
            layer_movable.opacity = .1
        for layer_base in layers_base:
            layer_base.opacity = .1
        for b in buttons:
            b.enabled = False
        v.mouse_drag_callbacks.append(remove_click_callback)
    def apply_transform(*args, transform=None, force=True, **kwargs):
        # kwargs here are extra parameters to pass to the transform.
        nonlocal tform, movable_points, params, _prev_matrix, _prev_translate
        if transform is not None:
            tform = transform
            if is_point_transform:
                layer_movable_points.data = tform.transform(pretransform.inverse_transform(movable_points))
                layer_movable_points.refresh()
        elif is_point_transform:
            if movable_points is not None and len(movable_points) > 0:
                tform = tform_type(points_start=movable_points, points_end=base_points, **params)
                layer_movable_points.data = tform.transform(pretransform.inverse_transform(movable_points))
            else:
                tform = pretransform
                layer_movable_points.data = np.asarray([])
            layer_movable_points.refresh()
        else:
            tform = tform_type(**params)
        for b in buttons: # Disable buttons while applying transform
            b.enabled = False
        for layer_movable,mi in zip(layers_movable,movable_image_img):
            # This if statement is a special case optimisation for
            # AffineTransforms only to avoid rerending the image if only the
            # origin/translation has changed.
            if force or _prev_matrix is None or (not isinstance(tform, AffineTransform)) or (isinstance(tform, AffineTransform) and np.any(_prev_matrix != tform.matrix)):
                tfi = tform.transform_image(mi, output_size=outsize, labels=utils.image_is_label(mi), force_size=False)
                layer_movable.data = tfi
                layer_movable.translate = tform.origin_and_maxpos(mi, output_size=outsize, force_size=False)[0]
            else:
                # This is complicated due to the possibilty of dragging a cropped image out of the crop boundaries
                layer_movable.translate = _prev_translate - tform.shift
            layer_movable.refresh()
        if isinstance(tform, AffineTransform) and (np.any(_prev_matrix != tform.matrix) or force):
            _prev_matrix = tform.matrix
            _prev_translate = tform.origin_and_maxpos(mi, output_size=outsize, force_size=False)[0] + tform.shift
        for b in buttons: # Turn buttons back on when transform is done
            b.enabled = True
    def set_point_size(zoom=None):
        if zoom is None:
            zoom = v.camera.zoom
        if hasattr(zoom, "value"):
            zoom = zoom.value
        layer_base_points.size = 20/zoom
        layer_movable_points.size = 20/zoom
        layer_base_points.selected_data = []
        layer_movable_points.selected_data = []
        layer_base_points.refresh()
        layer_movable_points.refresh()
    v.layers.selection.clear()
    v.layers.selection.add(layers_base[0])
    button_add_point = magicgui.widgets.PushButton(value=True, text='Add new point')
    button_add_point.clicked.connect(select_base_movable)
    button_transform = magicgui.widgets.PushButton(value=True, text='Perform transform')
    button_transform.clicked.connect(apply_transform)
    button_reset = magicgui.widgets.PushButton(value=True, text='Reset transform')
    button_reset.clicked.connect(lambda : apply_transform(transform=pretransform))
    button_delete = magicgui.widgets.PushButton(value=True, text='Remove point')
    button_delete.clicked.connect(remove_point)
    if is_point_transform:
        buttons = [button_add_point, button_transform, button_reset, button_delete]
    else:
        buttons = [button_transform, button_reset]
    widgets = []
    widgets.extend(buttons)
    # For controlling parameters using the mouse
    _MOUSE_DRAG_WIDGETS = [None, None, None] # z, y, and x position widgets
    def mouse_drag_callback(viewer, event):
        if vispy.util.keys.CONTROL not in event.modifiers or vispy.util.keys.SHIFT not in event.modifiers:
            return
        if viewer.dims.ndisplay != 2:
            return
        initial_pos = [w.value if w is not None else 0 for w in _MOUSE_DRAG_WIDGETS]
        dd = event.dims_displayed
        base = event.position
        #wh = event.source.size
        yield
        while event.type == "mouse_move":
            if _MOUSE_DRAG_WIDGETS[dd[0]] is not None:
                _MOUSE_DRAG_WIDGETS[dd[0]].value = event.position[dd[0]] - base[dd[0]] + initial_pos[dd[0]]
            if _MOUSE_DRAG_WIDGETS[dd[1]] is not None:
                _MOUSE_DRAG_WIDGETS[dd[1]].value = event.position[dd[1]] - base[dd[1]] + initial_pos[dd[1]]
            yield
    # Draw parameter spinboxes
    for p,pv in params.items():
        # This currently assumes all parameters are floats or bools
        if isinstance(pv, bool): # Bool
            w = magicgui.widgets.CheckBox(value=pv, label=p+":")
        else: # Float
            w = magicgui.widgets.FloatSpinBox(value=pv, label=p+":", min=-np.inf, max=np.inf)
        def widget_callback(*args,p=p,w=w):
            params[p] = w.value
            if dynamic_update.value:
                apply_transform(force=False)
        w.changed.connect(widget_callback)
        widgets.append(w)
        if p in transform.GUI_DRAG_PARAMETERS:
            _MOUSE_DRAG_WIDGETS[transform.GUI_DRAG_PARAMETERS.index(p)] = w
    dynamic_update = magicgui.widgets.CheckBox(value=False, label="Dynamic update")
    if len(params) > 0:
        widgets.append(dynamic_update)
    if not all(w is None for w in _MOUSE_DRAG_WIDGETS):
        v.mouse_drag_callbacks.append(mouse_drag_callback)
        dynamic_update.value = True
        widgets.insert(-1, magicgui.widgets.Label(value="Ctrl+Shift mouse drag to edit"))
    container_widget = magicgui.widgets.Container(widgets=widgets)
    v.window.add_dock_widget(container_widget, area="left", add_vertical_stretch=False)
    if is_point_transform:
        v.camera.events.zoom.connect(set_point_size)
        set_point_size()
    apply_transform()
    v.show(block=True)
    print(tform)
    return tform

def align_interactive_text(nodes_movable, nodes_fixed, graph=None, transform=None, references=[], start=None):
    if start is not None:
        print("The `start` parameter is deprecated, use `transform` instead")
    if transform is None:
        transform = start
    _TRANSFORMS_FOR_INTERACTIVE = {}
    _queue = Transform.__subclasses__()
    _reserved = "fekudsSqxcw"
    while len(_queue) > 0:
        c = _queue.pop()
        if hasattr(c, "SHORTCUT_KEY") and len(c.SHORTCUT_KEY) != 0:
            assert len(c.SHORTCUT_KEY) == 1, f"Class {c} has a shortcut key '{c.SHORTCUT_KEY}' which is longer than one character"
            assert c.SHORTCUT_KEY not in _TRANSFORMS_FOR_INTERACTIVE.keys(), f"Shortcut keys must be unique, but classes {c} and {_TRANSFORMS_FOR_INTERACTIVE[c.SHORTCUT_KEY]} have shortcut key {c.SHORTCUT_KEY}"
            assert c.SHORTCUT_KEY not in _reserved, f"Shortcut key {c.SHORTCUT_KEY} from transform {c} is reserved, please choose a different one"
            _TRANSFORMS_FOR_INTERACTIVE[c.SHORTCUT_KEY] = c
        _queue.extend(c.__subclasses__())

    # Sort
    _TRANSFORMS_FOR_INTERACTIVE = {k : v for k,v in sorted(_TRANSFORMS_FOR_INTERACTIVE.items(), key=lambda x : x[1].SORT_WEIGHT)}
    # Split into point-based and non-point-based
    _POINT_BASED = {k : v for k,v in _TRANSFORMS_FOR_INTERACTIVE.items() if issubclass(v, PointTransform)}
    _NON_POINT_BASED = {k : v for k,v in _TRANSFORMS_FOR_INTERACTIVE.items() if not issubclass(v, PointTransform)}
    # Generate the strings for printing the help screen
    _PARAMETRIC_NAMES = "\n".join([f"{k}: {v.NAME}" for k,v in _NON_POINT_BASED.items()])
    _POINT_NAMES = "\n".join([f"{k}: {v.NAME}" for k,v in _POINT_BASED.items()])
    _EXTENSION_NAMES = "\n".join([f"x_: Extend previous point-based transform with a point-based transform" for k,v in _POINT_BASED.items()])
    _CONVERSION_NAMES = "\n".join([f"c{k}: Convert previous point-based transform to '{v.NAME}'" for k,v in _POINT_BASED.items()])
    _TEXT = f"""Please choose an option:

Parametric transforms
---------------------
{_PARAMETRIC_NAMES}

Point-based transforms
----------------------
{_POINT_NAMES}

Modify last transform
---------------------
e: edit previous transform
k: remove the previous transform
x_: Extend previous point-based transform with a different point-based transform
c_: Convert previous point-based transform to a different point-based transform
(where _ is the letter key for any point based transform)

Other
-----
v: view
f: flip along z axis
u: revert most recent change
d: toggle references on/off
s: save to graph (but not to disk)
S: save to graph and write to disk
q: quit
"""
    # Ensure we passed lists
    if not isinstance(nodes_movable, (list, tuple)):
        nodes_movable = [nodes_movable]
    if not isinstance(nodes_fixed, (list, tuple)):
        nodes_fixed = [nodes_fixed]
    # Iteratively generate the reference images and transforms
    refs = []
    for r in references:
        if isinstance(r, str) and graph is not None:
            refs.append((graph.get_image(r), graph.get_transform(r, nodes_fixed[0])))
        else:
            assert isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], np.ndarray) and isinstance(r[1], Transform), "Each reference must be a tuple, where the first element is an image as an ndarray and the second is a Transform.  Alternatively, a reference can be the node name in the Graph (if applicable)."
            refs.append(r)
    # Parse the starting transform, falling back to Identity
    if transform is None:
        try: # If we have a graph and there is a link between the nodes
            t = graph.get_transform(nodes_movable[0], nodes_fixed[0])
            print("Using existing transform as a starting place")
        except (AssertionError, NameError, RuntimeError, AttributeError):
            t = Identity()
    elif isinstance(transform, str) and graph is not None:
        t = graph.get_transform(transform, nodes_fixed[0])
        while not isinstance(t, AffineTransform): # Use only the linear portion
            print("Warning: removing nonlinear portion of starting transform.")
            t = t.pretransform()
        #refs.append((g.get_image(start), t))
    elif isinstance(transform, Transform): # start is a transform
        t = transform
    else:
        raise ValueError("Invalid starting transform")
    info = _TEXT
    # Remove save options if we don't have a graph
    if graph is None: 
        info = "\n".join([l for l in info.split("\n") if l[0:3].lower() != "s: "])
    if len(references) == 0:
        info = "\n".join([l for l in info.split("\n") if l[0:3] != "d: "])
    # Put all of the pre-images and post-images into the same space.  Currently only supported for graphs.
    if graph is not None and isinstance(nodes_movable[0], str):
        nodes_movable_img = tuple(graph.get_image(n) if n == nodes_movable[0] else graph.get_transform(n, nodes_movable[0]).transform_image(graph.get_image(n), output_size=graph.get_image(nodes_movable[0]).shape, force_size=True) for n in nodes_movable)
    else:
        nodes_movable_img = tuple(nodes_movable)
    if graph is not None and isinstance(nodes_fixed[0], str):
        nodes_fixed_img = tuple(graph.get_image(n) if n == nodes_fixed[0] else graph.get_transform(n, nodes_fixed[0]).transform_image(graph.get_image(n), output_size=graph.get_image(nodes_fixed[0]).shape, force_size=True) for n in nodes_fixed)
    else:
        nodes_fixed_img = tuple(nodes_fixed)
    t_hist = [] # History of transforms, for undo history
    while True:
        print(f"Current transform is: {t}\n")
        t_hist.append(t)
        print(info)
        resp = input(f"Your choice: ")
        if len(resp) == 0:
            t = t_hist.pop()
            continue
        if resp[0] in _TRANSFORMS_FOR_INTERACTIVE.keys():
            ttype = _TRANSFORMS_FOR_INTERACTIVE[resp]
            t = alignment_gui(nodes_movable, nodes_fixed, transform=t+ttype, references=refs, graph=graph) 
        elif resp[0] == "e":
            t = alignment_gui(nodes_movable, nodes_fixed, transform=t, references=refs, graph=graph) 
        elif resp[0] == "v":
            alignment_gui(nodes_movable, nodes_fixed, transform=t+Identity, references=refs, graph=graph) 
        elif resp[0] in "cx" and len(resp) > 1 and resp[1] in _POINT_BASED.keys():
            if isinstance(t, PointTransform):
                if resp[0] == "x":
                    t = _refine_transform(t, _TRANSFORMS_FOR_INTERACTIVE[resp[1]])
                elif resp[0] == "c":
                    t = _replace_transform(t, _TRANSFORMS_FOR_INTERACTIVE[resp[1]])
                t = alignment_gui(nodes_movable, nodes_fixed, transform=t, references=refs, graph=graph) 
            else:
                print("Previous transform must be a point-based transform")
                t = t_hist.pop()
        elif resp == "f":
            im1 = graph.get_image(nodes_movable[0]) if (graph is not None and isinstance(nodes_movable[0], str)) else nodes_movable[0]
            t = FlipParametric(z=True, zthickness=im1.shape[0]) + t
        elif resp == "d":
            if len(refs) > 0:
                _refs = refs
                refs = []
                print("Refs toggled off")
            else:
                try:
                    refs = _refs
                    print("Refs toggled on")
                except UnboundLocalError:
                    print("No references to toggle")
        elif resp == "u":
            if len(t_hist) > 1:
                t_hist.pop()
            else:
                print("No more history to undo")
            t = t_hist.pop()
        elif resp == "k":
            t = t.pretransform()
        elif resp in "sS" and graph is not None:
            try:
                graph.add_edge(nodes_movable[0], nodes_fixed[0], t)
            except AssertionError:
                print("Edge already exists, overwriting")
                graph.add_edge(nodes_movable[0], nodes_fixed[0], t, update=True)
            if resp == "S":
                if graph.filename is None:
                    print("Graph has no specified filename, please enter one...")
                    filename = input("Filename (eg my_graph): ")
                    graph.filename = filename
                graph.save()
        elif resp == "q":
            break
        else:
            t = t_hist.pop()
            print(f"Invalid choice '{resp}'")
        # Match individual points/cells
    print("Transform is:", t)
    return t

def align_interactive(nodes_movable, nodes_fixed, graph=None, transform=None, references=[], start=None):
    from qtpy import QtWidgets, QtCore

    if start is not None:
        print("The `start` parameter is deprecated, use `transform` instead")
    if transform is None:
        transform = start

    _TRANSFORMS_FOR_INTERACTIVE = {}
    _queue = Transform.__subclasses__()
    _reserved = "fekudsSqxc"
    while len(_queue) > 0:
        c = _queue.pop()
        if hasattr(c, "SHORTCUT_KEY") and len(c.SHORTCUT_KEY) != 0:
            assert len(c.SHORTCUT_KEY) == 1, f"Class {c} has a shortcut key '{c.SHORTCUT_KEY}' which is longer than one character"
            assert c.SHORTCUT_KEY not in _TRANSFORMS_FOR_INTERACTIVE.keys(), f"Shortcut keys must be unique, but classes {c} and {_TRANSFORMS_FOR_INTERACTIVE[c.SHORTCUT_KEY]} have shortcut key {c.SHORTCUT_KEY}"
            assert c.SHORTCUT_KEY not in _reserved, f"Shortcut key {c.SHORTCUT_KEY} from transform {c} is reserved, please choose a different one"
            _TRANSFORMS_FOR_INTERACTIVE[c.SHORTCUT_KEY] = c
        _queue.extend(c.__subclasses__())

    _TRANSFORMS_FOR_INTERACTIVE = {k : v for k,v in sorted(_TRANSFORMS_FOR_INTERACTIVE.items(), key=lambda x : x[1].SORT_WEIGHT)}
    _POINT_BASED = {k : v for k,v in _TRANSFORMS_FOR_INTERACTIVE.items() if issubclass(v, PointTransform)}
    _NON_POINT_BASED = {k : v for k,v in _TRANSFORMS_FOR_INTERACTIVE.items() if not issubclass(v, PointTransform)}

    if not isinstance(nodes_movable, (list, tuple)):
        nodes_movable = [nodes_movable]
    if not isinstance(nodes_fixed, (list, tuple)):
        nodes_fixed = [nodes_fixed]

    refs = []
    for r in references:
        if isinstance(r, str) and graph is not None:
            refs.append((graph.get_image(r), graph.get_transform(r, nodes_fixed[0])))
        else:
            assert isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], np.ndarray) and isinstance(r[1], Transform), "Each reference must be a tuple, where the first element is an image as an ndarray and the second is a Transform.  Alternatively, a reference can be the node name in the Graph (if applicable)."
            refs.append(r)

    if transform is None:
        try:
            t = graph.get_transform(nodes_movable[0], nodes_fixed[0])
            print("Using existing transform as a starting place")
        except (AssertionError, NameError, RuntimeError, AttributeError):
            t = Identity()
    elif isinstance(transform, str) and graph is not None:
        t = graph.get_transform(transform, nodes_fixed[0])
        while not isinstance(t, AffineTransform):
            print("Warning: removing nonlinear portion of starting transform.")
            t = t.pretransform()
    elif isinstance(transform, Transform):
        t = transform
    else:
        raise ValueError("Invalid starting transform")

    app = QtWidgets.QApplication.instance()
    _created_app = False
    if app is None:
        app = QtWidgets.QApplication([])
        _created_app = True

    t_hist = []
    refs_current = list(refs)
    refs_saved = list(refs)
    _pending_prefix = None

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("CASTalign interactive alignment (GUI)")
    dlg.resize(1280, 920)
    root = QtWidgets.QVBoxLayout(dlg)
    root.setContentsMargins(10, 8, 10, 10)
    root.setSpacing(6)

    current_label = QtWidgets.QLabel()
    current_label.setWordWrap(True)
    status_label = QtWidgets.QLabel("")
    status_label.setWordWrap(True)
    status_label.setVisible(False)

    header = QtWidgets.QFrame()
    header.setFrameShape(QtWidgets.QFrame.StyledPanel)
    header_layout = QtWidgets.QVBoxLayout(header)
    header_layout.setContentsMargins(8, 6, 8, 6)
    header_layout.setSpacing(2)
    header_layout.addWidget(current_label)
    header_layout.addWidget(status_label)
    root.addWidget(header)

    group_param = QtWidgets.QGroupBox("Parametric transforms")
    layout_param = QtWidgets.QGridLayout(group_param)
    layout_param.setHorizontalSpacing(8)
    layout_param.setVerticalSpacing(6)
    root.addWidget(group_param)

    group_point = QtWidgets.QGroupBox("Point-based transforms")
    layout_point = QtWidgets.QGridLayout(group_point)
    layout_point.setHorizontalSpacing(8)
    layout_point.setVerticalSpacing(6)
    root.addWidget(group_point)

    group_modify = QtWidgets.QGroupBox("Modify / other actions")
    layout_modify = QtWidgets.QGridLayout(group_modify)
    layout_modify.setHorizontalSpacing(8)
    layout_modify.setVerticalSpacing(6)
    root.addWidget(group_modify)

    group_extend = QtWidgets.QGroupBox("Extend previous point-based transform")
    layout_extend = QtWidgets.QGridLayout(group_extend)
    layout_extend.setHorizontalSpacing(8)
    layout_extend.setVerticalSpacing(6)
    root.addWidget(group_extend)

    group_convert = QtWidgets.QGroupBox("Convert previous point-based transform")
    layout_convert = QtWidgets.QGridLayout(group_convert)
    layout_convert.setHorizontalSpacing(8)
    layout_convert.setVerticalSpacing(6)
    root.addWidget(group_convert)

    quit_button = QtWidgets.QPushButton("Quit")
    root.addWidget(quit_button)

    def _set_status(msg="", level="error"):
        if msg is None or len(str(msg)) == 0:
            status_label.setText("")
            status_label.setVisible(False)
            return
        print(msg)
        status_label.setText(str(msg))
        if level == "warning":
            status_label.setStyleSheet("QLabel { background-color: #fff3cd; color: #7a2e00; border: 1px solid #d6b656; padding: 4px; font-weight: 700; }")
        elif level == "info":
            status_label.setStyleSheet("QLabel { background-color: #d1ecf1; color: #0c5460; border: 1px solid #7fb7c2; padding: 4px; font-weight: 700; }")
        else:
            status_label.setStyleSheet("QLabel { background-color: #f8d7da; color: #7f1d1d; border: 1px solid #d17a84; padding: 4px; font-weight: 700; }")
        status_label.setVisible(True)

    def _push_history():
        t_hist.append(t)

    def _refresh():
        current_label.setText(f"Current transform: {t}")
        in_prefix_mode = _pending_prefix is not None
        is_point = isinstance(t, PointTransform)
        has_refs = len(refs_saved) > 0 or len(refs_current) > 0
        can_save = graph is not None
        for b in all_buttons:
            b.setEnabled(not in_prefix_mode)
        if in_prefix_mode:
            if _pending_prefix == "x":
                for b in extend_buttons:
                    b.setEnabled(True)
            elif _pending_prefix == "c":
                for b in convert_buttons:
                    b.setEnabled(True)
        else:
            for b in point_choice_buttons:
                b.setEnabled(True)
            for b in extend_buttons + convert_buttons:
                b.setEnabled(is_point)
        button_toggle_refs.setEnabled((not in_prefix_mode) and has_refs)
        button_save.setEnabled((not in_prefix_mode) and can_save)
        button_save_disk.setEnabled((not in_prefix_mode) and can_save)
        if in_prefix_mode:
            _set_status("")

    def _run_alignment(align_transform, assign_result=True):
        nonlocal t
        dlg.hide()
        dlg.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        try:
            result = alignment_gui(nodes_movable, nodes_fixed, transform=align_transform, references=refs_current, graph=graph)
            if assign_result:
                t = result
        finally:
            dlg.setEnabled(True)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            QtWidgets.QApplication.processEvents()
        _set_status("")
        _refresh()

    def _run_new_transform(ttype):
        _push_history()
        _run_alignment(t+ttype, assign_result=True)

    def _run_edit():
        _push_history()
        _run_alignment(t, assign_result=True)

    def _run_view():
        _push_history()
        _run_alignment(t+Identity, assign_result=False)

    def _run_remove_previous():
        nonlocal t
        _push_history()
        t = t.pretransform()
        _set_status("")
        _refresh()

    def _run_flip():
        nonlocal t
        _push_history()
        im1 = graph.get_image(nodes_movable[0]) if (graph is not None and isinstance(nodes_movable[0], str)) else nodes_movable[0]
        t = FlipParametric(z=True, zthickness=im1.shape[0]) + t
        _set_status("")
        _refresh()

    def _run_toggle_refs():
        nonlocal refs_current, refs_saved
        _push_history()
        if len(refs_current) > 0:
            refs_saved = list(refs_current)
            refs_current = []
            print("Refs toggled off")
        else:
            if len(refs_saved) > 0:
                refs_current = list(refs_saved)
                print("Refs toggled on")
            else:
                _set_status("No references to toggle", level="warning")
                _refresh()
                return
        _set_status("")
        _refresh()

    def _run_undo():
        nonlocal t
        if len(t_hist) == 0:
            _set_status("No more history to undo", level="warning")
            return
        t = t_hist.pop()
        _set_status("")
        _refresh()

    def _run_save(write_to_disk=False):
        _push_history()
        if graph is None:
            _set_status("No graph provided; cannot save")
            return
        try:
            graph.add_edge(nodes_movable[0], nodes_fixed[0], t)
        except AssertionError:
            _set_status("Edge already exists, overwriting", level="warning")
            graph.add_edge(nodes_movable[0], nodes_fixed[0], t, update=True)
        if write_to_disk:
            if graph.filename is None:
                filename, ok = QtWidgets.QInputDialog.getText(dlg, "Save graph", "Filename (eg my_graph):")
                if not ok or len(filename.strip()) == 0:
                    _set_status("Save to disk cancelled", level="warning")
                    return
                graph.filename = filename.strip()
            graph.save()
            _set_status(f"Saved to graph and disk: {graph.filename}", level="info")
        else:
            _set_status("Saved to graph (not written to disk)", level="info")
        _refresh()

    def _run_save_transform_to_disk():
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(dlg, "Save transform", "", "Transform files (*.tf *.txt);;All files (*)")
        if filename is None or len(filename.strip()) == 0:
            _set_status("Save transform cancelled", level="warning")
            return
        t.save(filename)
        _set_status(f"Saved transform to: {filename}", level="info")
        _refresh()

    def _run_extend_or_convert(mode, key):
        nonlocal _pending_prefix
        _push_history()
        if not isinstance(t, PointTransform):
            _set_status("Previous transform must be a point-based transform")
            _pending_prefix = None
            _refresh()
            return
        if mode == "x":
            t2 = _refine_transform(t, _TRANSFORMS_FOR_INTERACTIVE[key])
        else:
            t2 = _replace_transform(t, _TRANSFORMS_FOR_INTERACTIVE[key])
        _pending_prefix = None
        _run_alignment(t2, assign_result=True)

    def _handle_keypress_char(ch):
        nonlocal _pending_prefix
        if _pending_prefix is not None:
            prefix = _pending_prefix
            if len(ch) == 1 and ch in _POINT_BASED.keys():
                _run_extend_or_convert(prefix, ch)
            else:
                _pending_prefix = None
                _refresh()
            return True
        if len(ch) != 1:
            return False
        if ch in _TRANSFORMS_FOR_INTERACTIVE.keys():
            _run_new_transform(_TRANSFORMS_FOR_INTERACTIVE[ch])
            return True
        if ch == "e":
            _run_edit()
            return True
        if ch == "v":
            _run_view()
            return True
        if ch == "k":
            _run_remove_previous()
            return True
        if ch == "f":
            _run_flip()
            return True
        if ch == "u":
            _run_undo()
            return True
        if ch == "d":
            _run_toggle_refs()
            return True
        if ch == "s":
            _run_save(write_to_disk=False)
            return True
        if ch == "S":
            _run_save(write_to_disk=True)
            return True
        if ch == "w":
            _run_save_transform_to_disk()
            return True
        if ch in "xc":
            _pending_prefix = ch
            _refresh()
            return True
        if ch == "q":
            dlg.accept()
            return True
        return False

    _dlg_keypress_base = dlg.keyPressEvent
    def _dlg_keypress(event):
        nonlocal _pending_prefix
        if _pending_prefix is not None:
            if event.key() in (QtCore.Qt.Key_Shift, QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
                event.accept()
                return
            if event.key() == QtCore.Qt.Key_Escape:
                _pending_prefix = None
                _refresh()
                event.accept()
                return
        if _handle_keypress_char(event.text()):
            event.accept()
            return
        _dlg_keypress_base(event)
    dlg.keyPressEvent = _dlg_keypress

    point_choice_buttons = []
    all_buttons = []
    row = 0
    col = 0
    for k, cls in _NON_POINT_BASED.items():
        b = QtWidgets.QPushButton(f"{cls.NAME} ({k})")
        b.clicked.connect(lambda checked=False, c=cls: _run_new_transform(c))
        layout_param.addWidget(b, row, col)
        all_buttons.append(b)
        col += 1
        if col == 3:
            col = 0
            row += 1

    row = 0
    col = 0
    for k, cls in _POINT_BASED.items():
        b = QtWidgets.QPushButton(f"{cls.NAME} ({k})")
        b.clicked.connect(lambda checked=False, c=cls: _run_new_transform(c))
        layout_point.addWidget(b, row, col)
        point_choice_buttons.append(b)
        all_buttons.append(b)
        col += 1
        if col == 3:
            col = 0
            row += 1

    button_edit = QtWidgets.QPushButton("Edit previous transform (e)")
    button_edit.clicked.connect(_run_edit)
    layout_modify.addWidget(button_edit, 1, 0)
    all_buttons.append(button_edit)

    button_view = QtWidgets.QPushButton("View (v)")
    button_view.clicked.connect(_run_view)
    layout_modify.addWidget(button_view, 0, 0)
    all_buttons.append(button_view)

    button_remove = QtWidgets.QPushButton("Remove previous transform (k)")
    button_remove.clicked.connect(lambda checked=False: _handle_keypress_char("k"))
    layout_modify.addWidget(button_remove, 1, 2)
    all_buttons.append(button_remove)

    button_flip = QtWidgets.QPushButton("Flip along z axis (f)")
    button_flip.clicked.connect(_run_flip)
    layout_modify.addWidget(button_flip, 0, 2)
    all_buttons.append(button_flip)

    button_undo = QtWidgets.QPushButton("Undo (u)")
    button_undo.clicked.connect(_run_undo)
    layout_modify.addWidget(button_undo, 1, 1)
    all_buttons.append(button_undo)

    button_toggle_refs = QtWidgets.QPushButton("Toggle references on/off (d)")
    button_toggle_refs.clicked.connect(_run_toggle_refs)
    layout_modify.addWidget(button_toggle_refs, 0, 1)
    all_buttons.append(button_toggle_refs)

    button_save = QtWidgets.QPushButton("Save to graph (s)")
    button_save.clicked.connect(lambda checked=False: _run_save(write_to_disk=False))
    layout_modify.addWidget(button_save, 2, 0)
    all_buttons.append(button_save)

    button_save_disk = QtWidgets.QPushButton("Save to graph and write to disk (S)")
    button_save_disk.clicked.connect(lambda checked=False: _run_save(write_to_disk=True))
    layout_modify.addWidget(button_save_disk, 2, 1)
    all_buttons.append(button_save_disk)

    button_save_transform = QtWidgets.QPushButton("Save to disk (w)")
    button_save_transform.clicked.connect(_run_save_transform_to_disk)
    layout_modify.addWidget(button_save_transform, 2, 2)
    all_buttons.append(button_save_transform)

    extend_buttons = []
    convert_buttons = []

    row = 0
    col = 0
    for k, cls in _POINT_BASED.items():
        b = QtWidgets.QPushButton(f"Extend with {cls.NAME} (x{k})")
        b.clicked.connect(lambda checked=False, kk=k: _run_extend_or_convert("x", kk))
        layout_extend.addWidget(b, row, col)
        extend_buttons.append(b)
        all_buttons.append(b)
        col += 1
        if col == 3:
            col = 0
            row += 1

    row = 0
    col = 0
    for k, cls in _POINT_BASED.items():
        b = QtWidgets.QPushButton(f"Convert to {cls.NAME} (c{k})")
        b.clicked.connect(lambda checked=False, kk=k: _run_extend_or_convert("c", kk))
        layout_convert.addWidget(b, row, col)
        convert_buttons.append(b)
        all_buttons.append(b)
        col += 1
        if col == 3:
            col = 0
            row += 1

    quit_button.setText("Quit (q)")
    quit_button.clicked.connect(dlg.accept)
    all_buttons.append(quit_button)

    _refresh()
    event_loop = QtCore.QEventLoop()
    dlg.finished.connect(event_loop.quit)
    dlg.show()
    event_loop.exec()
    print("Transform is:", t)

    if _created_app:
        app.quit()

    return t

def _refine_transform(transform, transformtype, **kwargs):
    start = transform.transform(transform.pretransform().invert().transform(transform.points_start))
    end = transform.points_end
    return transform + transformtype(points_start=start, points_end=end, **kwargs)

def _replace_transform(transform, transformtype, **kwargs):
    return transform.pretransform() + transformtype(points_start=transform.points_start, points_end=transform.points_end, **kwargs)
