from . import base as transform
import numpy as np
from .compat import CURRENT_FILE_FORMAT_VERSION, apply_legacy_class_remappings, get_legacy_eval_namespace
from . import ndarray_shifted as ndarray_shifted
from . import utils
import os
import tempfile
import sqlite3
import shutil 


class Graph:
    """Store 3D image nodes and transforms between node spaces.

    Nodes can store image data directly or reference another node's image.
    Edges store transforms between node coordinate systems.
    """

    def __init__(self, name=""):
        """Create an empty graph.

        Parameters
        ----------
        name : str, optional
            Graph name.
        """
        # NOTE: If you change the constructor or internal data structure, you also need to change the load and save methods.
        self.name = name
        self.nodes = [] # List of node names
        self.edges = {} # Dictionary of dictonaries, edges[node1][node2] = transform
        
        # node_images is a cache. It can contain:
        # - an ndarray if the image is loaded.
        # - None if the image exists in the DB but is not loaded.
        # - a 'ref:other_node' string if it's a reference to another node.
        # Keys are all nodes that have an associated image.
        self.node_images = {} 

        # compressed_node_images stores "dirty" images that need to be saved to the database.
        # Format: {node_name: (compressed_data, info)} for image data
        #      or {node_name: (ref_node_name, [])} for a reference
        self.compressed_node_images = {}
        
        self.filename = None
        self.metadata = None
        self.node_metadata = {}

    def __eq__(self, other):
        """Compare graph structure and image-node membership.

        Parameters
        ----------
        other : object
            Object to compare.

        Returns
        -------
        bool
            ``True`` if name, nodes, edges, and image-node keys match.

        Notes
        -----
        Image array contents are intentionally not compared.
        """
        # NOTE: This equality check does not compare image data for performance reasons.
        # It only checks if the same nodes have images.
        return (isinstance(other, Graph) and
                self.name == other.name and
                set(self.nodes) == set(other.nodes) and
                self.edges == other.edges and
                set(self.node_images.keys()) == set(other.node_images.keys()))
    def __getitem__(self, item):
        """Get an image or transform using indexing syntax.

        This is shorthand for calling g.get_image() or g.get_transform().

        Parameters
        ----------
        item : str or slice
            - ``str``: node name, returns image for that node.
            - ``slice`` ``"from":"to"``: returns transform from from->to.

        Returns
        -------
        ndarray or transform.Transform
            Node image or composed transform.

        Examples
        --------
        >>> g["session1"] # Returns the image
        >>> g["session1":"session2"] # Return a transform from session1 to session2
        """
        if isinstance(item, str) and item in self.nodes:
            return self.get_image(item)
        if isinstance(item, slice) and isinstance(item.start, str) and isinstance(item.stop, str) and item.step is None and item.start in self.nodes and item.stop in self.nodes:
            return self.get_transform(item.start, item.stop)
        raise ValueError(f"Graph does not have the node '{item}'")
    def __setitem__(self, name, value):
        """Set node image or edge transform using indexing syntax.

        This is shorthand for calling add_node or add_edge.

        Parameters
        ----------
        name : str or slice
            - ``str``: node name to add.
            - ``slice`` ``"from":"to"``: edge to set.
        value : ndarray, str, or transform.Transform
            Node image/reference for node assignment, or transform for edge
            assignment.

        Examples
        --------
        >>> g["session2"] = vol # Creates a new node with image data vol
        >>> g["session1":"session2"] = tform # Creates an edge from "session1" to "session2"
        """
        if isinstance(name, str):
            return self.add_node(name, image=value)
        if isinstance(name, slice) and isinstance(name.start, str) and isinstance(name.stop, str) and name.step is None:
            return self.add_edge(name.start, name.stop, value)
        raise ValueError(f"A graph cannot assign the item '{item}'")
    def __delitem__(self, name):
        """Delete a node or edge using indexing syntax.

        Parameters
        ----------
        name : str or slice
            - ``str``: node to remove.
            - ``slice`` ``"from":"to"``: edge to remove.

        Returns
        -------
        None

        Examples
        --------
        >>> del g["session1"] # Remove the node session1
        >>> del g["session1":"session2"] # Remove the edge from session1 to session2
        """
        if isinstance(name, str):
            return self.remove_node(name)
        if isinstance(name, slice) and isinstance(name.start, str) and isinstance(name.stop, str) and name.step is None:
            return self.remove_edge(name.start, name.stop)
        
    def __contains__(self, item):
        """Check whether a node or edge exists.

        Parameters
        ----------
        item : str or tuple/list of length 2
            Node name, or edge endpoints ``(from_node, to_node)``.

        Returns
        -------
        bool
            ``True`` when the node/edge exists.

        Examples
        --------
        >>> "session1" in g # Returns True if "session1" is a node in the graph
        >>> ("session1", "session2") in g # Returns True if "session1" and "session2" are directly connected by an edge
        """
        if isinstance(item, str):
            return item in self.nodes
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            return item[0] in self.edges.keys() and item[1] in self.edges[item[0]].keys()
        raise ValueError(f"A graph cannot contain the item '{item}'")

    def save(self, filename=None):
        """Save the graph.

        Parameters
        ----------
        filename : str or path-like or None, optional
            Output path. If omitted, uses ``self.filename``.

        Returns
        -------
        None

        Notes
        -----
        If no extension is provided, ``.db`` is appended.
        """
        assert filename is None or not os.path.isfile(filename), "Save path already exists"
        if filename and self.filename and os.path.isfile(self.filename):
            shutil.copy(self.filename, filename)
        if not filename:
            filename = self.filename
        if not filename:
            raise ValueError("Filename must be provided to save.")
        filename = str(filename)
        if filename.endswith(".npz"):
            raise ValueError("Saving in npz format is no longer supported")
        if "." not in filename:
            filename = filename+".db"

        self.filename = filename
        
        con = sqlite3.connect(filename)
        cur = con.cursor()

        cur.execute("PRAGMA foreign_keys = ON;")

        cur.execute('''
            CREATE TABLE IF NOT EXISTS graph_properties (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                name TEXT PRIMARY KEY
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS node_images (
                node_name TEXT PRIMARY KEY,
                data BLOB,
                info TEXT,
                ref_node TEXT,
                FOREIGN KEY(node_name) REFERENCES nodes(name) ON DELETE CASCADE
            )
        ''')

        cur.execute("BEGIN")
        try:
            properties = {
                'name': self.name,
                'file_format_version': str(CURRENT_FILE_FORMAT_VERSION),
                'edges': repr(self.edges),
                'metadata': repr(self.metadata),
                'node_metadata': repr(self.node_metadata),
            }
            cur.executemany("INSERT OR REPLACE INTO graph_properties VALUES (?, ?)", properties.items())

            cur.execute("SELECT name FROM nodes")
            db_nodes = {row[0] for row in cur.fetchall()}
            current_nodes = set(self.nodes)

            nodes_to_delete = db_nodes - current_nodes
            if nodes_to_delete:
                cur.executemany("DELETE FROM nodes WHERE name = ?", [(n,) for n in nodes_to_delete])

            nodes_to_add = current_nodes - db_nodes
            if nodes_to_add:
                cur.executemany("INSERT OR IGNORE INTO nodes (name) VALUES (?)", [(n,) for n in nodes_to_add])

            cur.execute("SELECT node_name FROM node_images")
            db_image_nodes = {row[0] for row in cur.fetchall()}
            current_image_nodes = set(self.node_images.keys())
            
            image_entries_to_delete = db_image_nodes - current_image_nodes
            if image_entries_to_delete:
                 cur.executemany("DELETE FROM node_images WHERE node_name = ?", [(n,) for n in image_entries_to_delete])

            for node_name, compressed_value in self.compressed_node_images.items():
                if isinstance(compressed_value[0], str) and compressed_value[1] == []: # Reference node
                    ref_node = compressed_value[0]
                    cur.execute(
                        "INSERT OR REPLACE INTO node_images (node_name, data, info, ref_node) VALUES (?, NULL, NULL, ?)",
                        (node_name, ref_node)
                    )
                else:  # Actual image data
                    data, info = compressed_value
                    cur.execute(
                        "INSERT OR REPLACE INTO node_images (node_name, data, info, ref_node) VALUES (?, ?, ?, NULL)",
                        (node_name, data, str(info))
                    )
            
            con.commit()
            self.compressed_node_images.clear()

        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @classmethod
    def load(cls, filename):
        """Load a graph.

        Parameters
        ----------
        filename : str or path-like
            Input graph file.

        Returns
        -------
        Graph
            Loaded graph.
        """
        filename = str(filename)
        if not os.path.exists(filename):
            raise FileNotFoundError(f"No such file or directory: '{filename}'")
        if filename.endswith(".npz"):
            return cls._load_npz(filename)
        return cls._load_sqlite(filename)
    @classmethod
    def _load_sqlite(cls, filename):
        """Load graph data from SQLite.

        Do not call directly, use load() instead.

        Parameters
        ----------
        filename : str or path-like
            SQLite graph file.

        Returns
        -------
        Graph
            Loaded graph with lazy image placeholders.
        """
        con = sqlite3.connect(f'file:{filename}?mode=ro', uri=True)
        cur = con.cursor()
        try:
            cur.execute("SELECT value FROM graph_properties WHERE key = 'name'")
            name = cur.fetchone()[0]
            g = cls(name)
            g.filename = filename

            cur.execute("SELECT key, value FROM graph_properties")
            props = dict(cur.fetchall())

            try:
                version = int(props.get("file_format_version", "1"))
            except Exception:
                version = 1
            edges_text = props['edges']
            if version < CURRENT_FILE_FORMAT_VERSION:
                print(
                    f"Loading legacy graph format version {version}. "
                    f"It will be saved as version {CURRENT_FILE_FORMAT_VERSION} when you save it."
                )
            if version == 1:
                edges_text = apply_legacy_class_remappings(edges_text)
            eval_namespace = dict(transform.__dict__)
            eval_namespace.update(get_legacy_eval_namespace(eval_namespace))
            g.edges = eval(edges_text, eval_namespace, eval_namespace)
            g.metadata = eval(props.get('metadata', 'None'))
            g.node_metadata = eval(props.get('node_metadata', '{}'))

            cur.execute("SELECT name FROM nodes")
            g.nodes = list(sorted([row[0] for row in cur.fetchall()]))

            cur.execute("SELECT node_name, ref_node FROM node_images")
            for node_name, ref_node in cur.fetchall():
                if ref_node is not None:
                    g.node_images[node_name] = f"ref:{ref_node}"
                else:
                    g.node_images[node_name] = None
        finally:
            con.close()
        return g

    @classmethod
    def _load_npz(cls, filename):
        """Load graph data from legacy NPZ format.

        Do not call directly, use load() instead.

        Parameters
        ----------
        filename : str or path-like
            Legacy NPZ graph file.

        Returns
        -------
        Graph
            Loaded graph. ``filename`` is rewritten to the matching ``.db``
            path for subsequent saves.
        """
        print(
            f"Loading legacy NPZ file: {filename}. "
            f"It will be converted to graph format version {CURRENT_FILE_FORMAT_VERSION} when you save it."
        )
        f = np.load(filename, allow_pickle=True)
        g = cls(str(f['name']))

        g.nodes = list(map(str, f['nodes']))
        edges_text = apply_legacy_class_remappings(str(f['edges']))
        eval_namespace = dict(transform.__dict__)
        eval_namespace.update(get_legacy_eval_namespace(eval_namespace))
        g.edges = eval(edges_text, eval_namespace, eval_namespace)
        if "metadata" in f.keys():
            g.metadata = eval(str(f['metadata']))
        if "notes" in f.keys():
            g.node_metadata = eval(str(f['notes']))
        else:
            g.node_metadata = {}

        node_image_keys = f.get('nodeimage_keys', [])
        for i, n_bytes in enumerate(node_image_keys):
            n = str(n_bytes)
            compressed_value = (f[f'nodeimage_{i}'], f[f'nodeimageinfo_{i}'])

            info_obj = compressed_value[1]
            try:
                # Handle old format where string reference info was an empty ndarray
                is_ref = info_obj.size == 0
            except AttributeError:
                is_ref = False

            if is_ref:
                ref_node_name = str(compressed_value[0])
                g.compressed_node_images[n] = (ref_node_name, [])
                g.node_images[n] = f"ref:{ref_node_name}"
            else:
                data = compressed_value[0]
                info = list(compressed_value[1])
                g.compressed_node_images[n] = (data, [i.item() for i in info]) # Avoid numpy printing datatypes
                g.node_images[n] = None

        g.filename = os.path.splitext(filename)[0] + '.db'
        return g
    
    def add_node(self, name, image=None, compression="normal", metadata=None):
        """Add a node, optionally with image data or an image reference.

        Setting the image to be a reference (the name of another node with image
        data) can be used if the image data for this node can be computed from
        that of another node.  For instance, one node might be identical to
        another node but have a different voxel size (see example).

        Parameters
        ----------
        name : str
            New node name.
        image : ndarray or str or None, optional
            - ``ndarray``: 2D or 3D image (2D is interpreted as ``(1, Y, X)``).
            - ``str``: name of another existing node with an image.
            - ``None``: no image attached.
        compression : {'low', 'normal', 'high', 'label'}, optional
            Compression level for stored ndarray image data.
        metadata : object, optional
            Per-node metadata.

        Returns
        -------
        None

        Examples
        --------
        >>> g.add_node("session1", image=session1_vol)
        >>> g.add_node("session1_1umvoxels", image="session1")
        >>> g.add_edge("session1", "session1_1umvoxels", RescaleParametric(z=1, x=.3, y=.3))

        """
        # Image can either be a 3-dimensional ndarray or a string of another node
        assert name not in self.nodes, f"Node '{name}' already exists"
        if image is not None:
            if isinstance(image, str):
                assert image in self.nodes, f"Referenced node '{image}' for new node '{name}' does not exist"
                self.compressed_node_images[name] = (image, [])
                self.node_images[name] = f"ref:{image}"
            else:
                if image.ndim == 2:
                    image = image[None]
                compressed = utils.compress_image(image, level=compression)
                self.compressed_node_images[name] = compressed
                self.node_images[name] = image
        if metadata is not None:
            self.node_metadata[name] = metadata
        self.nodes.append(name)
        self.edges[name] = {}
        # TODO this doesn't handle the case where other node images refer to the given node
    
    def remove_node(self, name):
        """Remove a node and all incident edges.

        Parameters
        ----------
        name : str
            Node name to remove.

        Returns
        -------
        None
        """
        if name in self.compressed_node_images:
            del self.compressed_node_images[name]
        if name in self.node_images:
            del self.node_images[name]
        if name in self.node_metadata:
            del self.node_metadata[name]
        del self.edges[name]
        for n in self.nodes:
            if n in self.edges and name in self.edges[n]:
                del self.edges[n][name]
        self.nodes.remove(name)

    def replace_node_image(self, name, image=None, compression="normal"):
        """Replace or remove a node image without changing graph connections.

        Parameters
        ----------
        name : str
            Node name.
        image : ndarray or str or None, optional
            New image volume, reference node name, or ``None`` to remove image.
            2D input is promoted to ``(1, Y, X)``.
        compression : {'low', 'normal', 'high', 'label'}, optional
            Compression level for stored ndarray image data.

        Returns
        -------
        None
        """
        assert name in self.nodes, f"Node '{name}' doesn't exist"

        if image is None:
            if name in self.node_images:
                del self.node_images[name]
            if name in self.compressed_node_images:
                del self.compressed_node_images[name]
            return
        
        if isinstance(image, str):
            assert image in self.nodes, f"Referenced node '{image}' for node '{name}' does not exist"
            self.compressed_node_images[name] = (image, [])
            self.node_images[name] = f"ref:{image}"
        else:
            if image.ndim == 2:
                image = image[None]
            compressed = utils.compress_image(image, level=compression)
            self.compressed_node_images[name] = compressed
            self.node_images[name] = image

    def add_edge(self, frm, to, transform, update=False):
        """Add or update a transform edge between two nodes.

        Parameters
        ----------
        frm : str
            Source node.
        to : str
            Destination node.
        transform : transform.Transform
            Transform from ``frm`` to ``to``.
        update : bool, optional
            If ``False``, edge must not exist yet.
            If ``True``, edge must already exist and is replaced.

        Returns
        -------
        None
        """
        assert frm in self.nodes, f"Node '{frm}' doesn't exist"
        assert to in self.nodes, f"Node '{to}' doesn't exist"
        if update is False:
            assert to not in self.edges[frm].keys(), "Edge already exists"
        else:
            assert to in self.edges[frm].keys(), "Edge doesn't exist"
        self.edges[frm][to] = transform
        # At some point in the future we can support directed graphs, i.e.,
        # graphs with non-invertible transforms.
        inv = transform.invert()
        self.edges[to][frm] = inv
        cycle = self._is_acyclic()
        if cycle is not True:
            print("Warning: graph contains a cycle: " + " -> ".join(cycle))

    def remove_edge(self, frm, to):
        """Remove an edge and its reverse edge if present.

        Parameters
        ----------
        frm : str
            Source node.
        to : str
            Destination node.

        Returns
        -------
        None
        """
        assert frm in self.nodes, f"Node '{frm}' doesn't exist"
        assert to in self.nodes, f"Node '{to}' doesn't exist"
        assert to in self.edges[frm].keys(), "Edge doesn't exist"
        del self.edges[frm][to]
        if frm in self.edges[to].keys():
            del self.edges[to][frm]

    def _is_acyclic(self):
        """Return ``True`` if acyclic, otherwise return the first cycle found.

        Returns
        -------
        bool or list[str]
            ``True`` when acyclic, else a cycle as node names with the start
            node repeated at the end (for example ``["a", "b", "c", "a"]``).
        """
        visited = set()
        path = []
        path_index = {}

        def _dfs(node, parent):
            visited.add(node)
            path_index[node] = len(path)
            path.append(node)

            for neighbor in self.edges.get(node, {}):
                # Undirected traversal: skip the edge we came from.
                if neighbor == parent:
                    continue
                # Back-edge to an active node in this DFS path => cycle.
                if neighbor in path_index:
                    return path[path_index[neighbor]:] + [neighbor]
                if neighbor not in visited:
                    cycle = _dfs(neighbor, node)
                    if cycle is not True:
                        return cycle

            path.pop()
            del path_index[node]
            return True

        for node in self.nodes:
            if node not in visited:
                cycle = _dfs(node, None)
                if cycle is not True:
                    return cycle

        return True

    def connected_components(self):
        """Find connected components in the graph.

        This does not yet support directed graphs, i.e., graphs which contain
        non-invertable transforms.

        Returns
        -------
        list of set[str]
            One set per connected component.
        """
        components = []
        for n in self.nodes:
            # Make sure n isn't accounted for already
            if any([n in c for c in components]):
                continue
            # Find all nodes reachable from n and add to current_component.
            # Only search through those that haven't been searched through yet.
            current_component = set([n])
            to_search = [n]
            while len(to_search) > 0:
                node = to_search.pop()
                connected = list(self.edges[node].keys())
                to_search.extend([c for c in connected if c not in current_component])
                current_component = current_component.union(set(connected))
            components.append(current_component)
        return components

    def unload(self):
        """Clear memory by unloading the node images, keeping only the compressed forms.

        Returns
        -------
        None
        """
        # Before deleting nodes from node_images, make sure that this isn't
        # unsaved.
        nodes_to_unload = [
            node for node, image in self.node_images.items()
            if isinstance(image, np.ndarray) and node not in self.compressed_node_images
        ]
        if not nodes_to_unload:
            return
        # Re-fetch the correct placeholders from the database.
        con = sqlite3.connect(f'file:{self.filename}?mode=ro', uri=True)
        cur = con.cursor()
        try:
            placeholders = ','.join('?' * len(nodes_to_unload))
            cur.execute(f"SELECT node_name, ref_node FROM node_images WHERE node_name IN ({placeholders})", nodes_to_unload)
            for node_name, ref_node in cur.fetchall():
                if ref_node is not None:
                    self.node_images[node_name] = f"ref:{ref_node}"
                else:
                    self.node_images[node_name] = None
        finally:
            con.close()

    def get_chain(self, frm, to):
        """Return a node path from ``frm`` to ``to``.

        This returns the node chain used to compose transforms between nodes.
        The returned values are node names (not transforms).

        Parameters
        ----------
        frm : str
            Start node.
        to : str
            End node.

        Returns
        -------
        list[str]
            Path nodes excluding ``frm`` and ending at ``to``.
            Returns ``[]`` when ``frm == to``.

        Raises
        ------
        RuntimeError
            If no path exists between the two nodes.
        """
        assert frm in self.nodes, f"Node {frm} not found"
        assert to in self.nodes, f"Node {to} not found"
        if frm == to:
            return []
        candidates = list(map(lambda x : (x,) if isinstance(x, str) else tuple(x), self.edges[frm].keys()))
        seen = [frm]
        while len(candidates) > 0:
            if to in [l[-1] for l in candidates]:
                chain = next(l for l in candidates if to == l[-1])
                return chain
            c0 = candidates.pop(0)
            seen.append(c0[-1])
            to_append = [tuple(list(c0)+[n]) for n in self.edges[c0[-1]] if n not in seen]
            candidates.extend(to_append)
        raise RuntimeError(f"Path from '{frm}' to '{to}' not found")
    def get_transform(self, frm, to):
        """Return a transform from ``frm`` to ``to``.

        The transform is composed along the shortest path from ``frm`` to ``to``
        (returned by :meth:`get_chain`), applying each edge transform in path
        order.

        Parameters
        ----------
        frm : str
            Source node.
        to : str
            Destination node.

        Returns
        -------
        transform.Transform
            Composed transform from ``frm`` to ``to``.
            Returns ``Identity()`` when ``frm == to``.
        """
        if frm == to:
            return transform.Identity()
        def _get_transform_from_chain(chain):
            cur = frm
            tform = None
            for c in chain:
                tform = self.edges[cur][c] if tform is None else tform + self.edges[cur][c]
                cur = c
            return tform
        chain = self.get_chain(frm, to)
        return _get_transform_from_chain(chain)
    def has_transform(self, frm, to):
        """Check whether a transform path exists between two nodes.

        This is equivalent to determining whether :meth:`get_transform` raises
        an error.

        Parameters
        ----------
        frm : str
            Source node.
        to : str
            Destination node.

        Returns
        -------
        bool
            ``True`` if a transform can be composed.
        """
        try:
            self.get_transform(frm, to)
        except RuntimeError:
            return False
        return True
    def get_image(self, node):
        """Get image data for a node.

        Parameters
        ----------
        node : str
            Node name.

        Returns
        -------
        ndarray
            Node image data.

        Notes
        -----
        If the node image is a reference (``"ref:other_node"``), the referenced
        image is transformed into this node's space and returned.
        """
        if node not in self.nodes:
            raise KeyError(f"Node '{node}' does not exist.")
        if node not in self.node_images:
            raise KeyError(f"Node '{node}' does not have an associated image.")

        # First try to load it from the cache
        cached_value = self.node_images[node]
        if isinstance(cached_value, np.ndarray):
            return cached_value
        if isinstance(cached_value, str) and cached_value.startswith('ref:'):
            imnode = cached_value.split(':', 1)[1]
            transformed_image = self.get_transform(imnode, node).transform_image(self.get_image(imnode))
            self.node_images[node] = transformed_image
            return transformed_image
        # If it is not cached, we will need to decompress.
        if cached_value is None:
            # Look for the compressed image in the dirty images, and if you
            # can't find it there, then go to the db file on the disk.
            if node in self.compressed_node_images.keys():
                compressed_image = self.compressed_node_images[node]
            else:
                if not self.filename or not os.path.exists(self.filename):
                    raise RuntimeError("Graph has no associated database file to load image from.")

                con = sqlite3.connect(f'file:{self.filename}?mode=ro', uri=True)
                cur = con.cursor()
                try:
                    cur.execute("SELECT data, info FROM node_images WHERE node_name = ? AND ref_node IS NULL", (node,))
                    row = cur.fetchone()
                    if row is None:
                        raise RuntimeError(f"Image for node '{node}' not found in database '{self.filename}'.")
                    compressed_image = (row[0], eval(row[1]))
                finally:
                    con.close()
            data_bytes, info = compressed_image
            np_data = np.frombuffer(data_bytes, dtype=np.uint8)
            image = utils.decompress_image(np_data, info)
            self.node_images[node] = image
            return image
        raise RuntimeError(f"Internal error in get_image for node '{node}'. Invalid cache state: {cached_value}")

    def visualise(self, filename=None, nearby=None):
        """Render a Graphviz visualization of the graph.

        Parameters
        ----------
        filename : str or path-like or None, optional
            Output filename stem. If ``None``, a temporary file is used.
        nearby : str or None, optional
            If provided, only draw edges connected to this node.

        Returns
        -------
        None

        Notes
        -----
        This requires the "graphviz" package to be installed.
        """
        try:
            import graphviz
        except ImportError:
            raise ImportError("Please install graphviz package to visualise")
        fn = filename
        if fn is None:
            fn = tempfile.mkstemp()[1]
        g = graphviz.Digraph(self.name, filename=fn, engine="sfdp", strict=True)
        g.attr(overlap="prism", sep="+12", K="1.2", repulsiveforce="1.2", splines="true", forcelabels="true") 
        g.attr('edge', fontsize='10')
        # Find all nodes that have an Identity edge and choose one as the 'base" node
        ur_node = {}
        ur_node_names = {}
        for e1 in self.edges.keys():
            found = False
            ident_edges = [e2 for e2 in self.edges[e1] if self.edges[e1][e2].__class__.__name__ == "Identity"]
            for e2 in ident_edges:
                if e2 in ur_node.keys() and ur_node[e2] == e2:
                    ur_node[e1] = e2
                    ur_node_names[e2] += "\n"+e1
                    found = True
                    break
            if not found:
                ur_node[e1] = e1
                ur_node_names[e1] = e1
        ur_nodes_used = set()
        for e1 in self.edges.keys():
            for e2 in self.edges[e1].keys():
                if nearby is not None and e1 != nearby and e2 != nearby:
                    continue
                if e1 in self.edges[e2].keys() and self.edges[e1][e2].__class__.__name__ == self.edges[e2][e1].__class__.__name__:
                    if e1 > e2 and (self.edges[e1][e2].__class__.__name__ != "Identity" or ur_node[e1] != ur_node[e2]):
                        g.edge(ur_node[e1], ur_node[e2], label=self.edges[e1][e2].NAME, dir="both")
                        ur_nodes_used.add(ur_node[e1])
                        ur_nodes_used.add(ur_node[e2])
                else:
                    g.edge(ur_node[e1], ur_node[e2], label=self.edges[e1][e2].NAME)
                    ur_nodes_used.add(ur_node[e1])
                    ur_nodes_used.add(ur_node[e2])
        for n in sorted(ur_nodes_used):
            g.node(n, label=ur_node_names[n])
        g.view()
        if filename is None: # Temporary file
            os.unlink(fn)

# We put this file here to avoid circular imports
def load(fn, version=None):
    """Load a Graph or Transform from file.

    Parameters
    ----------
    fn : str or path-like
        Input file path.
    version : int or None, optional
        Transform file format version, used only when ``fn`` is a transform
        text file.

    Returns
    -------
    Graph or transform.Transform
        Loaded object.

    Examples
    --------
    >>> g = load("my_graph.db") # Loads a graph
    >>> t = load("my_transform.txt") # Loads a transform
    """
    try:
        return Graph.load(fn)
    except sqlite3.DatabaseError:
        pass
    try:
        return transform.Transform.load(fn, version=version)
    except:
        raise IOError("Invalid file type, can only load Transforms or Graphs.")

TransformGraph = Graph # Backward compatibility
