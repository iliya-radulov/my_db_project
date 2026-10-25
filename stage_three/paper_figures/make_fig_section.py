"""make_fig_section.py — Figure 3 of paper 3: Fe-Nd-B isothermal section at 1375 K (corrected merge).

Input: stage_three/cache/FENDB_1375K_N200_v3.pkl (default; or give a path) (generator phase_diagram_ternary_v3.py, 24 Oct 2026):
       x1 = x_Fe, x2 = x_Nd per grid point, results[i] = {"phases", "nps", "stable"}.
Fields are shaded by the number of phases; a white line separates fields (grid triangles whose corners
belong to different fields are left unfilled); large fields are labelled directly, small ones by number (key upper left); the inset magnifies the
Fe-rich corner, where Nd2Fe14B lies. Layout is set in inches so the figure prints at \textwidth (6.3 in).
"""
import pickle, sys
from collections import Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "cache" / "FENDB_1375K_N200_v3.pkl"
d = pickle.load(open(SRC, "rb"))
xfe, xnd = np.asarray(d["x1"], float), np.asarray(d["x2"], float)
xb = 1 - xfe - xnd
lab = np.array(["+".join(sorted(r["phases"])) if (r and r.get("stable") and r.get("phases")) else ""
                for r in d["results"]])
S3 = np.sqrt(3) / 2
X, Y = xnd + 0.5 * xfe, S3 * xfe                      # B (0,0), Nd (1,0), Fe (0.5, 0.866)

NAME = {"LIQUID": "L", "FCC_A1": r"$\gamma$-Fe", "BCC_A2": r"$\alpha$-Fe", "FE17ND2": r"Fe$_{17}$Nd$_2$",
        "FE17ND5": r"Fe$_{17}$Nd$_5$", "M2B_C16": r"Fe$_2$B", "MB_B27": "FeB", "ND2B5": r"Nd$_2$B$_5$",
        "NDB4_D1E": r"NdB$_4$", "NDB6_D21": r"NdB$_6$", "NDB66": r"NdB$_{66}$", "BETA_RHOMBO_B": r"$\beta$-B",
        "DHCP": "Nd", "HCP_A3": "hcp"}
ORDER = ["LIQUID", "FCC_A1", "BCC_A2", "FE17ND2", "FE17ND5", "M2B_C16", "MB_B27", "ND2B5", "NDB4_D1E",
         "NDB6_D21", "NDB66", "BETA_RHOMBO_B", "DHCP", "HCP_A3"]
def pretty(a):
    ph = sorted(a.split("+"), key=lambda p: ORDER.index(p) if p in ORDER else 99)
    return " + ".join(NAME.get(p, p) for p in ph)

SHADE = {1: "#e3eefc", 2: "#b7d3f6", 3: "#86b6ef"}    # one hue, light -> dark = 1 -> 3 phases
INK, MUTED, EDGE, FAIL = "#0b0b0b", "#52514e", "#3a3936", "#8a8984"

tri = mtri.Triangulation(X, Y)
t = tri.triangles
same = (lab[t[:, 0]] == lab[t[:, 1]]) & (lab[t[:, 1]] == lab[t[:, 2]]) & (lab[t[:, 0]] != "")
# drop the long triangles qhull adds along the convex hull
L = np.max(np.hypot(X[t] - np.roll(X[t], 1, axis=1), Y[t] - np.roll(Y[t], 1, axis=1)), axis=1)
keep = same & (L < 0.012)
nph = np.array([a.count("+") + 1 if a else 0 for a in lab])
fc = [SHADE[nph[i]] for i in t[keep, 0]]

# label position: grid point of the field farthest from other fields and from the edges of the region
P = np.c_[X, Y]
def pole(a, lo=0.0, hi=1.01):
    m = lab == a
    sel = m & (xfe >= lo) & (xfe < hi)
    dist, _ = cKDTree(P[~m]).query(P[sel])
    edge = np.minimum(np.minimum(xfe[sel] - lo, xnd[sel]), xb[sel]) * S3
    if hi < 1:
        edge = np.minimum(edge, (hi - xfe[sel]) * S3)
    i = int(np.argmax(np.minimum(dist, edge)))
    return X[sel][i], Y[sel][i]

def draw(ax, ms=1.6, clip=None):
    from matplotlib.collections import PolyCollection
    verts = np.stack([np.c_[X[t[keep, k]], Y[t[keep, k]]] for k in range(3)], axis=1)
    pc = PolyCollection(verts, facecolors=fc, edgecolors="none", antialiased=False)
    ax.add_collection(pc)
    f = lab == ""
    if clip is not None:
        f &= xfe >= FE_MIN - 1e-9
    (ln,) = ax.plot(X[f], Y[f], ls="", marker="x", ms=ms, mew=0.5, color=FAIL)
    if clip is not None:
        patch = plt.Polygon(clip, closed=True, transform=ax.transData, fill=False, lw=0)
        ax.add_patch(patch); pc.set_clip_path(patch)
    ax.set_aspect("equal"); ax.axis("off")

FE_MIN = 0.70                                           # inset: x_Fe >= FE_MIN
MAIN_NAMED = ["LIQUID+MB_B27+ND2B5", "LIQUID+ND2B5", "LIQUID+M2B_C16", "LIQUID+M2B_C16+MB_B27",
              "LIQUID", "LIQUID+MB_B27"]            # L + Fe17Nd2: too narrow below the dashed line, named in the inset
NUMBERED = ["MB_B27+ND2B5+NDB4_D1E", "MB_B27+NDB4_D1E+NDB6_D21", "MB_B27+NDB6_D21",
            "MB_B27+NDB66+NDB6_D21", "BETA_RHOMBO_B+MB_B27+NDB66"]
INSET_NAMED = ["FE17ND2+LIQUID", "LIQUID+M2B_C16", "FCC_A1+LIQUID+M2B_C16", "FCC_A1+FE17ND2+LIQUID"]
INSET_NUMBERED = ["FE17ND2+LIQUID+M2B_C16", "FCC_A1+LIQUID"]
FS, FS_KEY, FS_TICK = 7.5, 7.2, 6.5

def split(txt, n_first):
    parts = txt.split(" + ")
    return " + ".join(parts[:n_first]) + " +\n" + " + ".join(parts[n_first:]) if len(parts) > n_first else txt

# ---- layout in inches: main triangle (B vertex at (BX, BY), SM in/unit), inset (SI in/unit)
W, H = 6.3, 5.0
SM, BX, BY = 4.2, 0.35, 0.42
SI = 8.4
fig = plt.figure(figsize=(W, H))
def axes_at(x0, y0, s, xlim, ylim):                      # axes whose data unit is s inches, data (0,0) at (x0,y0) in
    r = [(x0 + s * xlim[0]) / W, (y0 + s * ylim[0]) / H, s * (xlim[1] - xlim[0]) / W, s * (ylim[1] - ylim[0]) / H]
    a = fig.add_axes(r); a.set_xlim(*xlim); a.set_ylim(*ylim); return a

ax = axes_at(BX, BY, SM, (-0.08, 1.08), (-0.10, S3 + 0.06))
draw(ax)
ax.plot([0, 1, 0.5, 0], [0, 0, S3, 0], color=EDGE, lw=0.9)
for a in MAIN_NAMED:
    x, y = pole(a)
    txt = pretty(a)
    ax.text(x, y, split(txt, 2) if txt.count("+") == 2 else txt, fontsize=FS, color=INK,
            ha="center", va="center", linespacing=1.1)
for k, a in enumerate(NUMBERED, 1):
    x, y = pole(a)
    ax.text(x, y, str(k), fontsize=FS, color=INK, ha="center", va="center", fontweight="bold")

ax.text(0.5, S3 + 0.025, "Fe", ha="center", va="bottom", fontsize=9.5, color=INK, fontweight="bold")
ax.text(-0.015, -0.015, "B", ha="right", va="top", fontsize=9.5, color=INK, fontweight="bold")
ax.text(1.015, -0.015, "Nd", ha="left", va="top", fontsize=9.5, color=INK, fontweight="bold")
for v_ in np.arange(0.2, 1.0, 0.2):
    ax.plot([v_, v_], [0, -0.012], color=EDGE, lw=0.6)
    ax.text(v_, -0.022, f"{v_:.1f}", ha="center", va="top", fontsize=FS_TICK, color=MUTED)
    xr, yr = 1 - 0.5 * v_, S3 * v_                     # right edge: x_Fe = v
    ax.plot([xr, xr + 0.0104], [yr, yr + 0.006], color=EDGE, lw=0.6)
    ax.text(xr + 0.016, yr + 0.009, f"{v_:.1f}", ha="left", va="center", fontsize=FS_TICK, color=MUTED)
    xl, yl = 0.5 * (1 - v_), S3 * (1 - v_)             # left edge: x_B = v
    ax.plot([xl, xl - 0.0104], [yl, yl + 0.006], color=EDGE, lw=0.6)
    ax.text(xl - 0.016, yl + 0.009, f"{v_:.1f}", ha="right", va="center", fontsize=FS_TICK, color=MUTED)
ax.text(0.5, -0.065, r"$x_\mathrm{Nd}$", ha="center", va="top", fontsize=FS_TICK + 0.5, color=MUTED)
ax.text(0.79, 0.43, r"$x_\mathrm{Fe}$", ha="center", va="center", fontsize=FS_TICK + 0.5, color=MUTED, rotation=-60)
ax.text(0.21, 0.43, r"$x_\mathrm{B}$", ha="center", va="center", fontsize=FS_TICK + 0.5, color=MUTED, rotation=60)
fy = S3 * FE_MIN
ax.plot([0.5 * FE_MIN, 1 - 0.5 * FE_MIN], [fy, fy], color=EDGE, lw=0.7, ls=(0, (3, 2)))
sx, sy = 2 / 17 + 0.5 * 14 / 17, S3 * 14 / 17           # Nd2Fe14B: x_Nd = 2/17, x_Fe = 14/17
ax.plot(sx, sy, marker="*", ms=7, color=INK, mec="white", mew=0.5, zorder=5)

# ---- inset: Fe-rich corner; its B-side corner sits right of the main triangle's right edge
IB = 2.55                                               # inset base height, in
xfe_at = (IB - BY) / (S3 * SM)
x_main_edge = BX + SM * (1 - 0.5 * xfe_at)
ix0 = x_main_edge + 0.14 - SI * 0.5 * FE_MIN            # inches of inset data X = 0
iy0 = IB - SI * fy
ai = axes_at(ix0, iy0, SI, (0.5 * FE_MIN - 0.02, 1 - 0.5 * FE_MIN + 0.10), (fy - 0.03, S3 + 0.03))
corner = [(0.5 * FE_MIN, fy), (1 - 0.5 * FE_MIN, fy), (0.5, S3)]
draw(ai, ms=2.6, clip=corner)
ai.add_patch(plt.Polygon(corner, closed=True, fill=False, ec=EDGE, lw=0.9))
NUDGE = {"FCC_A1+FE17ND2+LIQUID": (0.003, 0.0)}
for a in INSET_NAMED:
    x, y = pole(a, lo=FE_MIN)
    x, y = x + NUDGE.get(a, (0, 0))[0], y + NUDGE.get(a, (0, 0))[1]
    txt = pretty(a)
    ai.text(x, y, split(txt, 2) if txt.count("+") == 2 else txt, fontsize=FS - 0.5, color=INK,
            ha="center", va="center", linespacing=1.1)
for k, a in enumerate(INSET_NUMBERED, len(NUMBERED) + 1):
    x, y = pole(a, lo=FE_MIN)
    ai.text(x, y, str(k), fontsize=FS, color=INK, ha="center", va="center", fontweight="bold",
            bbox=dict(boxstyle="circle,pad=0.12", fc="white", ec="none") if a == "FCC_A1+LIQUID" else None)
ai.plot(sx, sy, marker="*", ms=10, color=INK, mec="white", mew=0.6, zorder=5)
xe = 1 - 0.5 * 14 / 17                                  # right edge at the height of the star
ai.annotate(r"Nd$_2$Fe$_{14}$B", xy=(sx, sy), xytext=(xe + 0.025, sy + 0.012), fontsize=FS, color=INK,
            ha="left", va="center", arrowprops=dict(arrowstyle="-", color=INK, lw=0.6, shrinkA=1, shrinkB=4))
ai.text(0.5, S3 + 0.008, "Fe", ha="center", va="bottom", fontsize=9.5, color=INK, fontweight="bold")
ai.text(0.5, fy - 0.008, rf"$x_\mathrm{{Fe}} \geq {FE_MIN:.2f}$", ha="center", va="top", fontsize=FS_TICK + 0.5, color=MUTED)

# ---- key of numbered fields and shading (upper left)
key = "\n".join(f"{k}  {pretty(a)}" for k, a in enumerate(NUMBERED + INSET_NUMBERED, 1))
fig.text(0.08 / W, 1 - 0.08 / H, key, ha="left", va="top", fontsize=FS_KEY, color=INK, linespacing=1.4)
from matplotlib.patches import Patch
hs = [Patch(facecolor=SHADE[n], edgecolor=MUTED, lw=0.3, label=f"{n}-phase field") for n in (1, 2, 3)]
hs.append(plt.Line2D([], [], ls="", marker="x", ms=3.5, mew=0.6, color=FAIL, label="not converged"))
hs.append(plt.Line2D([], [], ls="", marker="*", ms=7, color=INK, label=r"Nd$_2$Fe$_{14}$B"))
fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.08 / W, 1 - 1.45 / H), fontsize=FS_KEY,
           frameon=False, handlelength=1.3, borderaxespad=0, labelspacing=0.45)

fig.savefig(HERE / "FENDB_section_1375K.pdf")
fig.savefig(HERE / "FENDB_section_1375K.png", dpi=200)
print("saved")
