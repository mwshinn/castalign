import re

CURRENT_FILE_FORMAT_VERSION = 2

LEGACY_CLASS_NAME_REMAPPINGS = {
    "PointTransformNoInverse": "PointTransformNoAnalyticInverse",
    "TranslateRotate": "Rigid",
    "TranslateRotateRescaleByPlane": "PlaneConstrainedAffine",
    "TranslateRotateRescale": "Affine",
    "FlipFixed": "FlipParametric",
    "TranslateFixed": "TranslateParametric",
    "TranslateRotateFixed": "RigidParametric",
    "TranslateRotateRescaleFixed": "TranslateRotateRescaleParametric",
    "TranslateRotateRescale2DFixed": "TranslateRotateRescale2DParametric",
    "ShearFixed": "ShearParametric",
    "MatrixFixed": "MatrixParametric",
    "Rescale": "RescaleParametric",
    "Triangulation2D": "PlaneConstrainedTriangulation",
    "AffineFixed": "AffineParametric",
}


def apply_legacy_class_remappings(text):
    remapped = text
    for old, new in sorted(LEGACY_CLASS_NAME_REMAPPINGS.items(), key=lambda kv: -len(kv[0])):
        remapped = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, remapped)
    return remapped
