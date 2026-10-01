"""
app.py — Stage 3 Synthesis Advisor (Flask)

Runs on port 5001 (stage 2 app uses 5000).

Usage (from project root with venv active):
    python stage_three/advisor_app/app.py

Or from inside advisor_app/:
    flask run --port 5001
"""

import io
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from calphad_query import run_equilibrium
from overlay import make_overlay
from sweep_chart import make_sweep_chart

STAGE3_DIR = Path(__file__).resolve().parent.parent   # stage_three/

app = Flask(__name__)


@app.route("/")
def advisor():
    return render_template("advisor.html", active="advisor")


@app.route("/explorer")
def explorer():
    return render_template("explorer.html", active="explorer")


# ── Image serving ──────────────────────────────────────────────────────────────
# PNGs live in stage_three/plots/.
# Change IMG_DIR here if you reorganise the folder layout.
IMG_DIR = STAGE3_DIR / "plots"

@app.route("/images/<filename>")
def serve_image(filename):
    """Serve pre-computed PNG phase diagrams from IMG_DIR."""
    return send_from_directory(str(IMG_DIR), filename)


@app.route("/api/ternary_overlay")
def ternary_overlay():
    """
    Return a ternary PNG with a composition dot overlaid.
    Query params: x_nd, x_fe, x_b (mole fractions), T (temperature in K).
    """
    try:
        x_nd = float(request.args.get("x_nd", 0))
        x_fe = float(request.args.get("x_fe", 0))
        x_b  = float(request.args.get("x_b",  0))
        T    = int(request.args.get("T", 1375))
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid params: {e}"}), 400

    try:
        png_bytes = make_overlay(T, x_nd, x_fe, x_b, img_dir=IMG_DIR)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return send_file(io.BytesIO(png_bytes), mimetype="image/png")


@app.route("/api/phase_sweep")
def phase_sweep():
    """
    Return a PNG chart of phase fractions vs temperature.
    Query params: x_nd, x_fe, x_b (mole fractions).
    """
    try:
        x_nd = float(request.args.get("x_nd", 0))
        x_fe = float(request.args.get("x_fe", 0))
        x_b  = float(request.args.get("x_b",  0))
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid params: {e}"}), 400

    try:
        png_bytes = make_sweep_chart(x_nd, x_fe, x_b)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return send_file(io.BytesIO(png_bytes), mimetype="image/png")


@app.route("/api/equilibrium", methods=["POST"])
def equilibrium_api():
    data = request.get_json(force=True)
    try:
        x_nd = float(data.get("x_nd", 0))
        x_fe = float(data.get("x_fe", 0))
        x_b  = float(data.get("x_b",  0))
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    result = run_equilibrium(x_nd, x_fe, x_b)
    return jsonify(result)


if __name__ == "__main__":
    # Threaded=False: pycalphad is not thread-safe; one request at a time is fine
    app.run(debug=True, port=5001, threaded=False)
