Transforms
==========

Base classes
~~~~~~~~~~~~

.. autoclass:: castalign.base.Transform
   :members:
   :show-inheritance:
   :exclude-members: NAME, SHORTCUT_KEY, SORT_WEIGHT, DEFAULT_PARAMETERS, GUI_DRAG_PARAMETERS

.. autoclass:: castalign.base.PointTransform
   :show-inheritance:
   :no-members:
   :exclude-members: NAME, SHORTCUT_KEY, SORT_WEIGHT, DEFAULT_PARAMETERS, GUI_DRAG_PARAMETERS

.. autoclass:: castalign.base.AffineTransform
   :show-inheritance:
   :no-members:
   :exclude-members: NAME, SHORTCUT_KEY, SORT_WEIGHT, DEFAULT_PARAMETERS, GUI_DRAG_PARAMETERS

.. autoclass:: castalign.base.PointTransformNoAnalyticInverse
   :no-members:
   :exclude-members: NAME, SHORTCUT_KEY, SORT_WEIGHT, DEFAULT_PARAMETERS, GUI_DRAG_PARAMETERS

Parametric transforms
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: castalign.base.RigidParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.AffineParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.MatrixParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.FlipParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.RescaleParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.TranslateParametric
   :show-inheritance:
   :no-members:

Point-based transforms
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: castalign.base.Identity
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.Translate
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.Rigid
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.Affine
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.PlaneConstrainedAffine
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.Triangulation
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.PlaneConstrainedTriangulation
   :show-inheritance:
   :no-members:

Deprecated transforms
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: castalign.base.TranslateRotate2D
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.Flip
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.TranslateRotateRescaleParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.TranslateRotateRescale2DParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.ShearParametric
   :show-inheritance:
   :no-members:

.. autoclass:: castalign.base.DistanceWeightedAverageGaussian
   :show-inheritance:
   :no-members:
