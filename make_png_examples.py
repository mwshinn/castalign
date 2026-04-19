from PIL import Image, ImageDraw, ImageFont
import math

W, H = 390, 200
BG = (250, 246, 236)
PANEL = (255, 255, 255)
OUTLINE = (42, 50, 70)
GRID = (225, 230, 242)
PURPLE = (150, 120, 245)
BEFORE_FILL = (255, 224, 168)
AFTER_FILL = (255, 198, 170)
AFTER_WARP_FILL = (225, 210, 255)
MARK = (255, 110, 90)

FONT_SMALL = ImageFont.truetype('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf', 13)
FONT_BOLD = ImageFont.truetype('/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf', 15)

TRANSFORMS = [
    ("Identity", "identity"),
    ("Translate", "translate"),
    ("Rigid", "rotate_translate"),
    ("Affine", "affine"),
    ("PlaneConstrainedAffine", "plane_affine"),
    ("RigidParametric", "rotate_translate"),
    ("AffineParametric", "affine"),
    ("MatrixParametric", "matrix"),
    ("FlipParametric", "flip"),
    ("RescaleParametric", "scale"),
    ("TranslateParametric", "translate"),
    ("Triangulation", "triangulation"),
    # Intentionally matching Triangulation look
    ("PlaneConstrainedTriangulation", "triangulation"),
    ("TranslateRotate2D", "rotate2d"),
    ("Flip", "flip"),
    ("TranslateRotateRescaleParametric", "trs"),
    ("TranslateRotateRescale2DParametric", "trs2d"),
    ("ShearParametric", "shear"),
    ("DistanceWeightedAverageGaussian", "gaussian"),
]


def draw_grid(draw, box):
    x0, y0, x1, y1 = box
    step = 14
    for x in range(x0, x1 + 1, step):
        draw.line((x, y0, x, y1), fill=GRID, width=1)
    for y in range(y0, y1 + 1, step):
        draw.line((x0, y, x1, y), fill=GRID, width=1)


def rotate(points, deg):
    ang = math.radians(deg)
    c = math.cos(ang)
    s = math.sin(ang)
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append([dx * c - dy * s + cx, dx * s + dy * c + cy])
    return out


def poly_transform(points, kind):
    pts = [list(p) for p in points]
    if kind == "identity":
        return pts
    if kind == "translate":
        return [[x + 24, y - 18] for x, y in pts]
    if kind in ("rotate_translate", "rotate2d"):
        return [[x + 16, y - 10] for x, y in rotate(pts, 46)]
    if kind == "scale":
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        return [[cx + (x - cx) * 1.42, cy + (y - cy) * 0.56] for x, y in pts]
    if kind == "flip":
        cx = sum(x for x, _ in pts) / len(pts)
        return [[2 * cx - x, y] for x, y in pts]
    if kind == "shear":
        cy = sum(y for _, y in pts) / len(pts)
        return [[x + 0.72 * (y - cy), y] for x, y in pts]
    if kind in ("affine", "matrix", "plane_affine"):
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        out = []
        for x, y in pts:
            dx, dy = x - cx, y - cy
            nx = 1.34 * dx + 0.5 * dy
            ny = -0.32 * dx + 0.66 * dy
            if kind == "plane_affine":
                ny *= 0.5
            out.append([nx + cx + 8, ny + cy - 8])
        return out
    if kind in ("triangulation", "gaussian"):
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        out = []
        for x, y in pts:
            dx, dy = x - cx, y - cy
            wobble = 13 * math.sin((x + 2 * y) / 18) + 8 * math.cos((2 * x - y) / 24)
            nx = x + 0.26 * dy + wobble * 0.34
            ny = y - 0.18 * dx + wobble * 0.2
            if kind == "gaussian":
                nx += 17 * math.exp(-((dx * dx + dy * dy) / (2 * 1200)))
                ny -= 9 * math.exp(-((dx * dx + dy * dy) / (2 * 1600)))
            out.append([nx, ny])
        return out
    if kind in ("trs", "trs2d"):
        step = poly_transform(pts, "translate")
        step = poly_transform(step, "rotate2d")
        step = poly_transform(step, "scale")
        return step
    return pts


def ixy(points):
    return [(int(round(x)), int(round(y))) for x, y in points]


def center_points(points):
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    return [[x - cx, y - cy] for x, y in points]


def shift_points(points, dx, dy):
    return [[x + dx, y + dy] for x, y in points]


def fit_points_to_box(points, box, margin=10):
    x0, y0, x1, y1 = box
    minx = min(x for x, _ in points)
    maxx = max(x for x, _ in points)
    miny = min(y for _, y in points)
    maxy = max(y for _, y in points)
    pw = maxx - minx
    ph = maxy - miny
    bw = (x1 - x0) - 2 * margin
    bh = (y1 - y0) - 2 * margin
    s = min(1.0, bw / max(pw, 1e-6), bh / max(ph, 1e-6))
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    boxcx = (x0 + x1) / 2
    boxcy = (y0 + y1) / 2
    out = []
    for x, y in points:
        out.append([(x - cx) * s + boxcx, (y - cy) * s + boxcy])
    return out


def build_complex_shape():
    pts = [(-48, -28), (-20, -50), (0, -36), (22, -54), (50, -22), (40, 2)]
    cx, cy, r = 8, 10, 44
    for deg in range(20, 170, 18):
        a = math.radians(deg)
        pts.append([cx + r * math.cos(a), cy + 0.72 * r * math.sin(a)])
    pts.extend([(-30, 26), (-44, 44), (-58, 28), (-54, 8)])
    return pts


def build_direction_marker():
    return [(-30, -5), (12, -5), (12, -15), (38, 0), (12, 15), (12, 5), (-30, 5)]


def draw_scene(kind, name):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    left = (16, 38, 176, 184)
    right = (214, 38, 374, 184)
    for box in (left, right):
        d.rounded_rectangle(box, radius=11, fill=PANEL, outline=OUTLINE, width=3)
        draw_grid(d, (box[0] + 6, box[1] + 6, box[2] - 6, box[3] - 6))

    # Middle arrow with head clearly ahead of shaft
    d.line((184, 112, 204, 112), fill=OUTLINE, width=5)
    d.polygon([(212, 112), (202, 105), (202, 119)], fill=OUTLINE)

    base = build_complex_shape()
    marker = build_direction_marker()

    left_center = ((left[0] + left[2]) / 2, (left[1] + left[3]) / 2)
    before = shift_points(base, left_center[0], left_center[1])
    before_marker = shift_points(marker, left_center[0], left_center[1])
    before = fit_points_to_box(before, left, margin=12)
    before_marker = fit_points_to_box(before_marker, left, margin=24)

    d.polygon(ixy(before), fill=BEFORE_FILL, outline=OUTLINE, width=3)
    d.polygon(ixy(before_marker), fill=MARK, outline=OUTLINE, width=2)
    d.text((60, 45), "before", fill=OUTLINE, font=FONT_SMALL)

    after_local = center_points(poly_transform(base, kind))
    marker_local = center_points(poly_transform(marker, kind))
    right_center = ((right[0] + right[2]) / 2, (right[1] + right[3]) / 2)
    after = shift_points(after_local, right_center[0], right_center[1])
    after_marker = shift_points(marker_local, right_center[0], right_center[1])
    after = fit_points_to_box(after, right, margin=12)
    after_marker = fit_points_to_box(after_marker, right, margin=24)

    # Translation is visually subtle if we center-fit the output; keep an explicit panel-space shift.
    if kind == "translate":
        after = shift_points(after, 26, -20)
        after_marker = shift_points(after_marker, 26, -20)

    fill = AFTER_WARP_FILL if kind in ("triangulation", "gaussian") else AFTER_FILL
    d.polygon(ixy(after), fill=fill, outline=OUTLINE, width=3)
    d.polygon(ixy(after_marker), fill=MARK, outline=OUTLINE, width=2)
    d.text((260, 45), "after", fill=OUTLINE, font=FONT_SMALL)

    if kind == "flip":
        d.text((236, 170), "mirror", fill=PURPLE, font=FONT_SMALL)
    elif kind in ("shear", "affine", "matrix", "plane_affine"):
        d.text((224, 170), "skew+stretch", fill=PURPLE, font=FONT_SMALL)
    elif kind == "triangulation":
        d.text((218, 170), "nonlinear warp", fill=PURPLE, font=FONT_SMALL)
    elif kind == "gaussian":
        d.text((224, 170), "smooth field", fill=PURPLE, font=FONT_SMALL)
    elif kind in ("trs", "trs2d"):
        d.text((218, 170), "move+turn+scale", fill=PURPLE, font=FONT_SMALL)
    elif kind == "translate":
        d.text((232, 170), "shift", fill=PURPLE, font=FONT_SMALL)

    d.rounded_rectangle((14, 8, 376, 32), radius=10, fill=(255, 255, 255), outline=OUTLINE, width=2)
    d.text((22, 13), name, fill=OUTLINE, font=FONT_BOLD)
    return img


def main():
    for name, kind in TRANSFORMS:
        draw_scene(kind, name).save(f"transform_{name}.png")
    print(f"Wrote {len(TRANSFORMS)} transform PNGs")


if __name__ == "__main__":
    main()
