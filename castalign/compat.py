import re

CURRENT_FILE_FORMAT_VERSION = 2

LEGACY_CLASS_NAME_REMAPPINGS = {
    "PointTransformNoInverse": "PointTransformNoAnalyticInverse",
    "TranslateRotate": "Rigid",
    "TranslateRotate2D": "Rigid",
    "TranslateRotateRescaleByPlane": "LaminarAffine",
    "TranslateRotateRescale": "Affine",
    "FlipFixed": "FlipParametric",
    "TranslateFixed": "TranslateParametric",
    "TranslateRotateFixed": "RigidParametric",
    "TranslateRotateRescaleFixed": "AffineParametric",
    "TranslateRotateRescale2DFixed": "_legacy_trr2d_parametric",
    "ShearFixed": "_legacy_shear_parametric",
    "MatrixFixed": "MatrixParametric",
    "Rescale": "RescaleParametric",
    "Triangulation2D": "LaminarTriangulation",
    "AffineFixed": "AffineParametric",
    "TranslateRotateRescaleParametric": "AffineParametric",
    "TranslateRotateRescale2DParametric": "_legacy_trr2d_parametric",
    "ShearParametric": "_legacy_shear_parametric",
    "Shear": "_legacy_shear_parametric",
}


def _legacy_trr2d_parametric_factory(base_globals):
    affine_parametric = base_globals["AffineParametric"]

    def _legacy_trr2d_parametric(**kwargs):
        y = kwargs.pop("y", 0.0)
        x = kwargs.pop("x", 0.0)
        rotate = kwargs.pop("rotate", 0.0)
        scale = kwargs.pop("scale", 1.0)
        invert = kwargs.pop("invert", False)
        z = kwargs.pop("z", 0.0)
        return affine_parametric(
            z=z,
            y=y,
            x=x,
            zrotate=rotate,
            yrotate=0.0,
            xrotate=0.0,
            zscale=1.0,
            yscale=scale,
            xscale=scale,
            yzshear=0.0,
            xzshear=0.0,
            xyshear=0.0,
            invert=invert,
        )

    return _legacy_trr2d_parametric


def _legacy_shear_parametric_factory(base_globals):
    affine_parametric = base_globals["AffineParametric"]

    def _legacy_shear_parametric(**kwargs):
        z = kwargs.pop("zshift", kwargs.pop("z", 0.0))
        y = kwargs.pop("yshift", kwargs.pop("y", 0.0))
        x = kwargs.pop("xshift", kwargs.pop("x", 0.0))
        yzshear = kwargs.pop("yzshear", 0.0)
        xzshear = kwargs.pop("xzshear", 0.0)
        xyshear = kwargs.pop("xyshear", 0.0)
        invert = kwargs.pop("invert", False)
        return affine_parametric(
            z=z,
            y=y,
            x=x,
            zrotate=0.0,
            yrotate=0.0,
            xrotate=0.0,
            zscale=1.0,
            yscale=1.0,
            xscale=1.0,
            yzshear=yzshear,
            xzshear=xzshear,
            xyshear=xyshear,
            invert=invert,
        )

    return _legacy_shear_parametric


def get_legacy_eval_namespace(base_globals):
    return {
        "_legacy_trr2d_parametric": _legacy_trr2d_parametric_factory(base_globals),
        "_legacy_shear_parametric": _legacy_shear_parametric_factory(base_globals),
    }


def apply_legacy_class_remappings(text):
    remapped = text
    for old, new in sorted(LEGACY_CLASS_NAME_REMAPPINGS.items(), key=lambda kv: -len(kv[0])):
        remapped = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, remapped)
    return remapped
