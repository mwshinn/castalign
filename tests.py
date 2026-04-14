import tempfile
import unittest
from pathlib import Path
import os
import shutil

import numpy as np

import castalign as ca
from castalign import *


TEST_SLOW_TRANSFORMS = False


class TestTransforms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        np.random.seed(0)

        cls._fixed_transforms = [
            TranslateRotateFixed,
            TranslateRotateFixed,
            TranslateFixed,
            Identity,
            Rescale,
            ShearFixed,
            FlipFixed,
            TranslateRotateRescaleFixed,
        ]
        cls._fixed_transforms_params = [
            dict(z=3.2, y=5, x=-24, zrotate=3.4, yrotate=10, xrotate=20),
            dict(z=3.2, y=0, x=-24, zrotate=3.4, yrotate=10, xrotate=25),
            dict(z=-10, y=0.3, x=4),
            dict(),
            dict(z=2, y=4, x=3),
            dict(yzshear=0.3, xzshear=-0.2, xyshear=0.1, xshift=4, yshift=-5, zshift=2),
            dict(z=True, zthickness=30),
            dict(
                xscale=1.2,
                yscale=0.9,
                zscale=1.4,
                xrotate=3,
                yrotate=2,
                zrotate=10,
                x=10,
                y=-8,
                z=5,
            ),
        ]
        cls.fixed_transforms = [
            t(**tp) for t, tp in zip(cls._fixed_transforms, cls._fixed_transforms_params)
        ]

        cls._point_transforms = [
            TranslateRotate,
            Translate,
            TranslateRotate2D,
            TranslateRotateRescale,
            Triangulation,
        ]
        cls._point_transforms_2d = [Triangulation2D, TranslateRotateRescaleByPlane]
        cls._point_transforms_slow = [DistanceWeightedAverage] if TEST_SLOW_TRANSFORMS else []

        points_pre_flat = np.random.rand(20, 3)
        points_pre_flat[:, 1:3] *= 150
        points_pre_flat[:, 0] *= 10
        points_post_flat = points_pre_flat @ rotation_matrix(2, 3, -2) - 4
        cls.point_transforms_2d = [
            t(points_pre_flat, points_post_flat) for t in cls._point_transforms_2d
        ]

        cls.points_pre = np.random.randn(50, 3)
        cls.points_post = cls.points_pre @ rotation_matrix(4, 6, 2) - 9
        cls.point_transforms = [
            t(cls.points_pre, cls.points_post) for t in cls._point_transforms
        ] + cls.point_transforms_2d
        cls.point_transforms_slow = [
            t(cls.points_pre, cls.points_post) for t in cls._point_transforms_slow
        ]

        cls.all_transforms = cls.fixed_transforms + cls.point_transforms
        cls.new_points = np.random.randn(10, 3).astype("float32")
        cls.new_points_big = np.random.randn(30, 3).astype("float32")

        cls.checkerboard = np.asarray(
            [
                [
                    [
                        float(((i // 10) + (j // 10) + (k // 10)) % 2)
                        for i in range(0, 150)
                    ]
                    for j in range(0, 300)
                ]
                for k in range(0, 30)
            ]
        )

    @staticmethod
    def close(x, y):
        return np.allclose(x, y, atol=1e-3, rtol=1e-3)

    def test_all_transforms_invertible(self):
        for t in self.all_transforms + self.point_transforms_slow:
            self.assertTrue(
                self.close(t.inverse_transform(t.transform(self.new_points)), self.new_points),
                msg=f"Transform {t} can not be inverted",
            )

    def test_invert_all_transforms(self):
        for t in self.all_transforms:
            self.assertTrue(
                self.close(t.transform(t.invert().transform(self.new_points)), self.new_points),
                msg=f"Error with inverse of transform {t}",
            )

    def test_all_compositions_invertible(self):
        for t1 in self.all_transforms:
            for t2 in self.all_transforms:
                t = t1 + t2
                self.assertTrue(
                    self.close(t.inverse_transform(t.transform(self.new_points)), self.new_points),
                    msg=f"Transform {t} can not be inverted",
                )

    def test_double_compositions_invertible(self):
        for t1 in self.all_transforms[0:2]:
            for t2 in self.all_transforms:
                for t3 in self.all_transforms + self.point_transforms_slow:
                    t = t1 + t2 + t3
                    self.assertTrue(
                        self.close(
                            t.inverse_transform(t.transform(self.new_points)),
                            self.new_points,
                        ),
                        msg=f"Transform {t} can not be inverted",
                    )

    def test_invert_all_compositions(self):
        for t1 in self.all_transforms + self.point_transforms_slow:
            for t2 in self.all_transforms:
                t = t1 + t2
                self.assertTrue(
                    self.close(
                        t.transform(t.invert().transform(self.new_points)),
                        self.new_points,
                    ),
                    msg=f"Error with inverse of transform {t}",
                )

    def test_compositionality(self):
        for t1 in self.all_transforms:
            for t2 in self.all_transforms + self.point_transforms_slow:
                t = t1 + t2
                self.assertTrue(
                    self.close(
                        t2.transform(t1.transform(self.new_points)),
                        t.transform(self.new_points),
                    ),
                    msg=f"Transform {t} did not compose",
                )

    def test_distance_weighted_average_behavior(self):
        for t in self.point_transforms_slow:
            self.assertTrue(
                np.all(
                    t.invert().transform(self.new_points_big)[0:5]
                    == t.invert().transform(self.new_points_big[0:5])
                )
            )

    def test_partial_compositions_invertible(self):
        for t1 in self.all_transforms:
            for t2 in self._point_transforms:
                _t = t1 + t2
                t = _t(self.points_pre, self.points_post)
                self.assertTrue(
                    self.close(t.inverse_transform(t.transform(self.new_points)), self.new_points),
                    msg=f"Transform {t} was not close",
                )
            for t2, t2p in zip(self._fixed_transforms, self._fixed_transforms_params):
                _t = t1 + t2
                t = _t(**t2p)
                self.assertTrue(
                    self.close(t.inverse_transform(t.transform(self.new_points)), self.new_points),
                    msg=f"Transform {t} was not close",
                )

    def test_partial_compositions_compositionality(self):
        for t1 in self.all_transforms:
            for t2 in self._point_transforms:
                _t = t1 + t2
                t = _t(self.points_pre, self.points_post)
                self.assertTrue(
                    self.close(
                        t.transform(self.new_points),
                        t2(self.points_pre, self.points_post).transform(
                            t1.transform(self.new_points)
                        ),
                    ),
                    msg=f"Transform {t} was not close",
                )
            for t2, t2p in zip(self._fixed_transforms, self._fixed_transforms_params):
                _t = t1 + t2
                t = _t(**t2p)
                self.assertTrue(
                    self.close(
                        t.transform(self.new_points),
                        t2(**t2p).transform(t1.transform(self.new_points)),
                    ),
                    msg=f"Transform {t} was not close",
                )

    def test_compositions_transforming_images(self):
        for t in self.all_transforms + self.point_transforms_slow:
            image_transformed_once = t.transform_image(
                self.checkerboard, output_size=self.checkerboard.shape
            )
            image_transformed_twice = t.transform_image(
                image_transformed_once, output_size=self.checkerboard.shape
            )
            image_transformed_sum = (t + t).transform_image(
                self.checkerboard, output_size=self.checkerboard.shape
            )
            sim = np.mean(
                image_transformed_twice.flatten() == image_transformed_sum.flatten()
            )
            self.assertGreater(
                sim,
                0.9,
                msg=f"Correlation for composition of {t} was too low, it was {sim}",
            )

    def test_exact_answers_for_some_transforms(self):
        self.assertTrue(
            self.close(
                TranslateFixed(z=5, y=4, x=7).transform(self.points_pre),
                self.points_pre + [5, 4, 7],
            )
        )
        self.assertTrue(self.close(Identity().transform(self.points_pre), self.points_pre))
        self.assertTrue(
            self.close(
                TranslateRotateFixed(
                    z=3, y=8, x=-3, zrotate=8, yrotate=-9, xrotate=2
                ).transform(self.points_pre),
                self.points_pre @ rotation_matrix(8, -9, 2) + [3, 8, -3],
            )
        )
        self.assertTrue(
            self.close(
                Translate(self.points_pre, self.points_pre + [5, 4, 3]).transform(
                    self.points_pre
                ),
                self.points_pre + [5, 4, 3],
            )
        )
        self.assertTrue(
            self.close(
                TranslateRotate(
                    self.points_pre,
                    (self.points_pre + [-4, 2, 1]) @ rotation_matrix(6, 1, -3),
                ).transform(self.points_pre),
                (self.points_pre + [-4, 2, 1]) @ rotation_matrix(6, 1, -3),
            )
        )
        self.assertTrue(
            self.close(
                TranslateRotate2D(
                    self.points_pre,
                    (self.points_pre + [0, 2, 1]) @ rotation_matrix(30, 0, 0),
                ).transform(self.points_pre),
                (self.points_pre + [0, 2, 1]) @ rotation_matrix(30, 0, 0),
            )
        )
        self.assertTrue(
            self.close(
                Rescale(z=3, y=1, x=0.5).transform(self.points_pre),
                self.points_pre * [3, 1, 0.5],
            )
        )


class TestSpotTransforms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        np.random.seed(1)
        cls.spot = np.zeros((80, 90, 100))
        cls.spotpos = (51, 65, 53)
        cls.spot[cls.spotpos] = 1

        cls._fixed_transforms_spot = [TranslateRotateFixed, TranslateFixed, Identity]
        cls._fixed_transforms_params_spot = [
            dict(z=3.2, y=5, x=-24, zrotate=3.4, yrotate=5, xrotate=10),
            dict(z=-10, y=0.3, x=4),
            dict(),
        ]
        cls.fixed_transforms_spot = [
            t(**tp)
            for t, tp in zip(cls._fixed_transforms_spot, cls._fixed_transforms_params_spot)
        ]
        cls._point_transforms_spot = [TranslateRotate2D, Translate, TranslateRotate]
        cls._point_transforms_spot_slow = [Triangulation]

        cls.points_pre = np.random.randn(100, 3) + 50
        cls.points_post = (cls.points_pre @ rotation_matrix(1, 2, 3)) - 9
        cls.point_transforms_spot = [
            t(cls.points_pre, cls.points_post) for t in cls._point_transforms_spot
        ]
        cls.point_transforms_spot_slow = [
            t(cls.points_pre, cls.points_post) for t in cls._point_transforms_spot_slow
        ]

        cls.all_transforms_spot = cls.fixed_transforms_spot + cls.point_transforms_spot

    def test_image_transforms_absolute_and_relative(self):
        for t in self.all_transforms_spot + self.point_transforms_spot_slow:
            spot_rel = np.mean(np.where(t.transform_image(self.spot) > 0.1), axis=1)
            self.assertLess(
                np.max(spot_rel - (t.transform([self.spotpos]) - t.origin_and_maxpos(self.spot)[0])),
                1,
            )
            spot_abs = np.mean(
                np.where(t.transform_image(self.spot, output_size=self.spot.shape) > 0.1),
                axis=1,
            )
            self.assertLess(np.max(spot_abs - t.transform([self.spotpos])), 1)

    def test_compositions_absolute_and_relative(self):
        for t1 in self.all_transforms_spot:
            for t2 in self.all_transforms_spot:
                t = t1 + t2
                spot_rel = np.mean(np.where(t.transform_image(self.spot) > 0.1), axis=1)
                self.assertLess(
                    np.max(
                        spot_rel - (t.transform([self.spotpos]) - t.origin_and_maxpos(self.spot)[0])
                    ),
                    1,
                )
                spot_abs = np.mean(
                    np.where(t.transform_image(self.spot, output_size=self.spot.shape) > 0.1),
                    axis=1,
                )
                self.assertLess(np.max(spot_abs - t.transform([self.spotpos])), 1)


class TestNonRigidTransforms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        np.random.seed(2)
        cls.points_pre = np.random.randn(100, 3) + 50
        cls.points_post = (cls.points_pre @ rotation_matrix(1, 2, 3)) - 9
        cls.checkerboard = np.asarray(
            [
                [
                    [
                        float(((i // 10) + (j // 10) + (k // 10)) % 2)
                        for i in range(0, 150)
                    ]
                    for j in range(0, 300)
                ]
                for k in range(0, 30)
            ]
        )

    def test_nonrigid_transform_image_consistency(self):
        class _TranslateComplicated(Translate):
            """Should be identical to Translate, included for testing only."""

            def transform_image(self, *args, **kwargs):
                return Transform.transform_image(self, *args, **kwargs)

        class _TranslateRotateComplicated(TranslateRotate):
            """Should be identical to TranslateRotate, included for testing only."""

            def transform_image(self, *args, **kwargs):
                return Transform.transform_image(self, *args, **kwargs)

        for simple, complicated in [
            (Translate, _TranslateComplicated),
            (TranslateRotate, _TranslateRotateComplicated),
        ]:
            im1 = complicated(self.points_pre, self.points_post).transform_image(
                self.checkerboard, output_size=self.checkerboard.shape
            )
            im2 = simple(self.points_pre, self.points_post).transform_image(
                self.checkerboard, output_size=self.checkerboard.shape
            )
            corr = np.corrcoef(im1.flatten(), im2.flatten())[0, 1]
            self.assertGreater(
                corr,
                0.95,
                msg=(
                    f"Correlation for normal and complicated version of {simple} "
                    f"was too low, it was {corr}"
                ),
            )


class TestGraphs(unittest.TestCase):
    def test_graphs(self):
        np.random.seed(3)
        fixed_transforms = [
            TranslateRotateFixed,
            TranslateRotateFixed,
            TranslateFixed,
            Identity,
            Rescale,
            ShearFixed,
            FlipFixed,
            TranslateRotateRescaleFixed,
        ]
        fixed_transforms_params = [
            dict(z=3.2, y=5, x=-24, zrotate=3.4, yrotate=10, xrotate=20),
            dict(z=3.2, y=0, x=-24, zrotate=3.4, yrotate=10, xrotate=25),
            dict(z=-10, y=0.3, x=4),
            dict(),
            dict(z=2, y=4, x=3),
            dict(yzshear=0.3, xzshear=-0.2, xyshear=0.1, xshift=4, yshift=-5, zshift=2),
            dict(z=True, zthickness=30),
            dict(
                xscale=1.2,
                yscale=0.9,
                zscale=1.4,
                xrotate=3,
                yrotate=2,
                zrotate=10,
                x=10,
                y=-8,
                z=5,
            ),
        ]
        all_transforms = [t(**tp) for t, tp in zip(fixed_transforms, fixed_transforms_params)]
        new_points = np.random.randn(10, 3).astype("float32")

        g = Graph("mygraph")
        g.add_node("a")
        g.add_node("c", image=np.random.randn(2, 3, 4))
        g.add_node("bx")
        g.add_node("d")
        g.add_edge("a", "bx", all_transforms[0])
        g.add_edge("a", "c", all_transforms[1])
        g.add_edge("c", "d", all_transforms[2])

        self.assertTrue(
            np.allclose(
                g.get_transform("bx", "d").transform(
                    g.get_transform("d", "bx").transform(new_points)
                ),
                new_points,
                atol=1e-3,
                rtol=1e-3,
            )
        )
        self.assertEqual(g.get_image("c").shape, (2, 3, 4))
        self.assertEqual(g, g, "Self-equality failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            fn = Path(tmpdir).joinpath("file.db")
            g.save(fn)
            g2 = Graph.load(fn)
            self.assertEqual(g, g2)


class InvertibleError(PointTransformNoInverse):
    DEFAULT_PARAMETERS = {"extent": 1, "invert": False}
    def _transform(self, points, points_start, points_end):
        return points

class TestGraph(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_graph.sqlite3")
        self.npz_path = os.path.join(self.test_dir, "old_graph.npz")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _create_sample_image(self, value=1, shape=(1, 10, 10)):
        """Helper to create a simple numpy array image."""
        return np.full(shape, value, dtype=np.uint8)

    def test_01_initialization(self):
        """Test basic graph initialization."""
        g = Graph("MyTestGraph")
        self.assertEqual(g.name, "MyTestGraph")
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.edges, {})
        self.assertEqual(g.node_images, {})

    def test_02_add_and_remove_node(self):
        """Test adding and removing nodes."""
        g = Graph("NodeTest")
        img1 = self._create_sample_image(1)
        
        # Add a node with an image
        g.add_node("node1", image=img1, metadata="This is node 1.")
        self.assertIn("node1", g.nodes)
        self.assertIn("node1", g.edges)
        self.assertIn("node1", g.node_images)
        self.assertIn("node1", g.compressed_node_images) # Should be dirty
        self.assertEqual(g.node_metadata["node1"], "This is node 1.")
        np.testing.assert_array_equal(g.get_image("node1"), img1)

        # Add a node without an image
        g.add_node("node2")
        self.assertIn("node2", g.nodes)
        self.assertNotIn("node2", g.node_images)
        with self.assertRaises(KeyError):
            g.get_image("node2")
            
        # Add a node that references another
        g.add_node("node1_ref", image="node1")
        self.assertIn("node1_ref", g.node_images)
        self.assertEqual(g.node_images['node1_ref'], 'ref:node1')

        # Remove the node
        g.remove_node("node1")
        self.assertNotIn("node1", g.nodes)
        self.assertNotIn("node1", g.edges)
        self.assertNotIn("node1", g.node_images)
        self.assertNotIn("node1", g.compressed_node_images)
        self.assertNotIn("node1", g.node_metadata)

    def test_03_add_and_remove_edge(self):
        """Test adding and removing edges."""
        g = Graph("EdgeTest")
        g.add_node("A")
        g.add_node("B")
        g.add_node("C")

        # Add an invertible edge
        t_ab = TranslateFixed(x=10)
        g.add_edge("A", "B", t_ab)
        self.assertIn("B", g.edges["A"])
        self.assertIs(g.edges["A"]["B"], t_ab)
        # Check for automatic inverse
        self.assertIn("A", g.edges["B"])
        self.assertIsInstance(g.edges["B"]["A"], TranslateFixed)

        # Add a non-invertible edge
        t_ac = InvertibleError()
        g.add_edge("A", "C", t_ac)
        self.assertIn("C", g.edges["A"])

        # Remove edge
        g.remove_edge("A", "B")
        self.assertNotIn("B", g.edges["A"])
        self.assertNotIn("A", g.edges["B"])

    def test_04_save_and_load_sqlite(self):
        """Test saving to and loading from a SQLite database."""
        g_orig = Graph("DBSaveLoadTest")
        img1 = self._create_sample_image(10)
        img2 = self._create_sample_image(20)

        g_orig.add_node("n1", image=img1, metadata="Note for n1")
        g_orig.add_node("n2", image=img2)
        g_orig.add_node("n3", image="n1") # Reference node
        g_orig.add_node("n4")
        g_orig.add_edge("n1", "n2", TranslateFixed(x=5))
        g_orig.metadata = {"author": "tester"}

        g_orig.save(self.db_path)
        self.assertTrue(os.path.exists(self.db_path))

        # Load into a new graph object
        g_loaded = Graph.load(self.db_path)

        self.assertEqual(g_orig.name, g_loaded.name)
        self.assertEqual(sorted(g_orig.nodes), sorted(g_loaded.nodes))
        self.assertEqual(g_orig.node_metadata, g_loaded.node_metadata)
        self.assertEqual(g_orig.metadata, g_loaded.metadata)
        self.assertEqual(repr(g_orig.edges), repr(g_loaded.edges))
        
        # Test dynamic image loading
        self.assertIsNone(g_loaded.node_images["n1"]) # Should not be loaded yet
        np.testing.assert_array_equal(g_loaded.get_image("n1"), img1)
        self.assertIsNotNone(g_loaded.node_images["n1"]) # Should be cached now
        
        np.testing.assert_array_equal(g_loaded.get_image("n2"), img2)
        
        # Test loading of a referenced image
        self.assertEqual(g_loaded.node_images["n3"], "ref:n1")
        # get_image should calculate the transformed image
        transformed_img = TranslateFixed(x=0).transform_image(img1) # Bogus transform, just for check
        # With our mocks, the path n1->n3 is empty, so there will be an error
        with self.assertRaises(RuntimeError):
            g_loaded.get_image("n3")

    def test_05_selective_image_saving(self):
        """Test that only modified images are saved."""
        g = Graph("SelectiveSave")
        img1 = self._create_sample_image(1)
        img2 = self._create_sample_image(2)

        g.add_node("node1", image=img1)
        g.add_node("node2", image=img2)
        
        # Initial save, all images are dirty
        self.assertIn("node1", g.compressed_node_images)
        self.assertIn("node2", g.compressed_node_images)
        g.save(self.db_path)
        self.assertEqual(g.compressed_node_images, {}) # Dirty dict should be cleared

        # Load, modify one image, and resave
        g_loaded = Graph.load(self.db_path)
        self.assertEqual(g_loaded.compressed_node_images, {})

        new_img2 = self._create_sample_image(99)
        g_loaded.replace_node_image("node2", new_img2)
        
        # Now only node2 should be dirty
        self.assertNotIn("node1", g_loaded.compressed_node_images)
        self.assertIn("node2", g_loaded.compressed_node_images)

        g_loaded.save() # Resave to the same path
        self.assertEqual(g_loaded.compressed_node_images, {})

        # Load again and verify changes
        g_final = Graph.load(self.db_path)
        np.testing.assert_array_equal(g_final.get_image("node1"), img1)
        np.testing.assert_array_equal(g_final.get_image("node2"), new_img2)

    def test_06_npz_backward_compatibility(self):
        """Test loading an old .npz file and converting it."""
        # Create a fake old .npz file
        name = "OldNPZ"
        nodes = ["A", "B"]
        edges = repr({'A': {'B': TranslateFixed(x=1)}, 'B': {'A': TranslateFixed(x=1)}})
        node_images_keys = ["A"]
        # Use our mock compression to get the right format
        img_a_data, img_a_info = utils.compress_image(self._create_sample_image(50))

        np.savez_compressed(
            self.npz_path, 
            name=name, 
            nodes=nodes, 
            edges=edges, 
            nodeimage_keys=node_images_keys, 
            nodeimage_0=img_a_data, 
            nodeimageinfo_0=img_a_info
        )

        # Load the .npz file
        g = Graph.load(self.npz_path)
        
        # Check data integrity
        self.assertEqual(g.name, name)
        self.assertEqual(sorted(g.nodes), sorted(nodes))
        np.testing.assert_array_equal(g.get_image("A"), self._create_sample_image(50))

    def test_07_get_transform(self):
        """Test pathfinding for transforms."""
        g = Graph("PathTest")
        g.add_node("A")
        g.add_node("B")
        g.add_node("C")
        g.add_node("D") # Disconnected
        
        g.add_edge("A", "B", TranslateFixed(x=10))
        g.add_edge("B", "C", TranslateFixed(x=5))

        # Direct transform
        t_ab = g.get_transform("A", "B")
        self.assertIsInstance(t_ab, TranslateFixed)
        self.assertEqual(t_ab, TranslateFixed(x=10))

        # Chained transform
        t_ac = g.get_transform("A", "C")
        self.assertTrue(np.all(t_ac.transform([1, 2, 3]) == ca.TranslateFixed(x=15).transform([1, 2, 3])))
        
        # Identity transform
        t_aa = g.get_transform("A", "A")
        self.assertIsInstance(t_aa, Identity)

        # Path not found
        with self.assertRaises(RuntimeError):
            g.get_transform("A", "D")

    def test_08_unload(self):
        """Test unloading images from the cache."""
        g = Graph("UnloadTest")
        img1 = self._create_sample_image(1)
        g.add_node("node1", image=img1)
        g.save(self.db_path)

        g_loaded = Graph.load(self.db_path)
        # Load image into cache
        g_loaded.get_image("node1")
        self.assertIsInstance(g_loaded.node_images["node1"], np.ndarray)

        # Unload
        g_loaded.unload()
        self.assertIsNone(g_loaded.node_images["node1"])

        # Getting it again should reload from DB
        np.testing.assert_array_equal(g_loaded.get_image("node1"), img1)
    
    def test_09_remove_node_with_image_from_db(self):
        """Test that removing a node also removes its image on save."""
        g = Graph("RemoveFromDB")
        g.add_node("n1", image=self._create_sample_image(1))
        g.add_node("n2", image=self._create_sample_image(2))
        g.save(self.db_path)
        
        # Load, remove a node, and save again
        g_loaded = Graph.load(self.db_path)
        g_loaded.remove_node("n1")
        self.assertNotIn("n1", g_loaded.nodes)
        g_loaded.save()
        
        # Load final version and check
        g_final = Graph.load(self.db_path)
        self.assertIn("n2", g_final.nodes)
        self.assertNotIn("n1", g_final.nodes)
        self.assertNotIn("n1", g_final.node_images)
        with self.assertRaises(KeyError):
            g_final.get_image("n1")
        
        # Verify the image for n2 is still there
        np.testing.assert_array_equal(g_final.get_image("n2"), self._create_sample_image(2))
    def test_10_new_filename(self):
        """Test renaming a graph file by saving under a new name"""
        g = Graph("RemoveFromDB")
        img1 = self._create_sample_image(1)
        g.add_node("n1", image=img1)
        img2 = self._create_sample_image(2)
        g.add_node("n2", image=img2)
        g.save(self.db_path)
        img1_new = self._create_sample_image(3)
        img3 = self._create_sample_image(4)
        g.replace_node_image("n1", image=img1_new)
        g.add_node("n3", image=img3)
        g.save(self.db_path+".new")
        g_loaded = Graph.load(self.db_path+".new")
        self.assertIn("n1", g_loaded.nodes)
        self.assertIn("n1", g_loaded.node_images)
        self.assertIn("n3", g_loaded.nodes)
        self.assertIn("n3", g_loaded.node_images)
        np.testing.assert_array_equal(g_loaded.get_image("n1"), img1_new)
        np.testing.assert_array_equal(g_loaded.get_image("n3"), img3)
        


if __name__ == "__main__":
    unittest.main()
