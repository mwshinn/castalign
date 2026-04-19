import os

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from PIL import Image

OUT_DIR = "docs/_static/geometries"
FINAL_W, FINAL_H = 508, 358

# Deliberately oversized render + whitespace + downscale pipeline.
RENDER_W, RENDER_H = 4064, 2864
WHITESPACE_CANVAS_W, WHITESPACE_CANVAS_H = 5200, 3800
DOWNSCALE_W, DOWNSCALE_H = 1016, 716
TARGET_MARGIN = 8
EDGE_LINEWIDTH = 16.0

GEOMETRIES = [
    ("geometry_cake.png", (8.0, 7.0, 4.8), "#e3904f"),
    ("geometry_pancake.png", (14.5, 8.5, 1.3), "#5aa3e6"),
    ("geometry_rice_paper.png", (15.5, 9.2, 0.35), "#74c58d"),
]


def render_hires(path, dims, color):
    dx, dy, dz = dims
    fig = plt.figure(figsize=(RENDER_W / 100, RENDER_H / 100), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    ax.bar3d(
        0,
        0,
        0,
        dx,
        dy,
        dz,
        shade=True,
        color=color,
        edgecolor="#1f2937",
        linewidth=EDGE_LINEWIDTH,
    )
    ax.set_xlim(-0.03 * dx, 1.03 * dx)
    ax.set_ylim(-0.03 * dy, 1.03 * dy)
    ax.set_zlim(0, 1.03 * dz)
    ax.set_box_aspect((dx, dy, max(dz, 0.2)))
    ax.view_init(elev=20, azim=-62)
    ax.set_axis_off()
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((1, 1, 1, 0))
    plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(path, transparent=True)
    plt.close(fig)


def postprocess(path):
    im = Image.open(path).convert("RGBA")
    bb = im.split()[-1].getbbox()
    if bb is None:
        return
    obj = im.crop(bb)

    padded = Image.new(
        "RGBA", (WHITESPACE_CANVAS_W, WHITESPACE_CANVAS_H), (255, 255, 255, 0)
    )
    px = (WHITESPACE_CANVAS_W - obj.width) // 2
    py = (WHITESPACE_CANVAS_H - obj.height) // 2
    padded.alpha_composite(obj, (px, py))

    small = padded.resize((DOWNSCALE_W, DOWNSCALE_H), Image.Resampling.LANCZOS)
    bb2 = small.split()[-1].getbbox()
    if bb2 is None:
        return
    obj2 = small.crop(bb2)

    max_w = FINAL_W - 2 * TARGET_MARGIN
    max_h = FINAL_H - 2 * TARGET_MARGIN
    scale = min(max_w / obj2.width, max_h / obj2.height)
    nw = max(1, int(round(obj2.width * scale)))
    nh = max(1, int(round(obj2.height * scale)))
    obj3 = obj2.resize((nw, nh), Image.Resampling.LANCZOS)

    final = Image.new("RGBA", (FINAL_W, FINAL_H), (255, 255, 255, 0))
    fx = (FINAL_W - nw) // 2
    fy = (FINAL_H - nh) // 2
    final.alpha_composite(obj3, (fx, fy))
    final.save(path)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, dims, color in GEOMETRIES:
        path = os.path.join(OUT_DIR, name)
        render_hires(path, dims, color)
        postprocess(path)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
