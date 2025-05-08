# Auto-install required packages if not present
import subprocess
import sys

required = {
    "flask": "2.3.3"
}

for pkg, ver in required.items():
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", f"{pkg}=={ver}"])

import os
import subprocess
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from pathlib import Path

app = Flask(__name__)
state = {}
KUBECONFIG_PATH = "/tmp/kubeconfig.yaml"
os.environ["KUBECONFIG"] = KUBECONFIG_PATH

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        kubeconfig_content = request.form["kubeconfig"]
        with open(KUBECONFIG_PATH, "w") as f:
            f.write(kubeconfig_content)
        os.chmod(KUBECONFIG_PATH, 0o600)
        return redirect(url_for("browser"))
    return render_template("upload_kubeconfig.html")

@app.route("/browser")
def browser():
    return render_template("browser.html")

@app.route("/api/root")
def api_root():
    return jsonify([{"id": "/", "text": "/", "children": True}])

@app.route("/api/children")
def api_children():
    pod = request.args.get("pod")
    ns = request.args.get("namespace")
    path = request.args.get("path", "/")
    if not all([pod, ns]):
        return jsonify([])

    cmd = ["kubectl", "exec", "-n", ns, pod, "--", "ls", "-p", path]
    try:
        entries = subprocess.check_output(cmd, text=True).splitlines()
    except subprocess.CalledProcessError:
        return jsonify([])

    result = []
    for entry in entries:
        is_dir = entry.endswith('/')
        name = entry.rstrip('/')
        full_path = os.path.join(path, name)
        result.append({
            "id": full_path,
            "text": name,
            "children": is_dir
        })
    return jsonify(result)

@app.route("/download")
def download():
    pod = request.args.get("pod")
    ns = request.args.get("namespace")
    path = request.args.get("path")
    if not all([pod, ns, path]):
        return "Missing parameters", 400

    local_dir = f"/tmp/logs-{pod}-{path.replace('/', '_')}"
    os.makedirs(local_dir, exist_ok=True)
    try:
        subprocess.check_call(["kubectl", "cp", f"{ns}/{pod}:{path}", local_dir])
        zip_path = f"{local_dir}.zip"
        subprocess.check_call(["zip", "-r", zip_path, local_dir])
        return send_file(zip_path, as_attachment=True)
    except subprocess.CalledProcessError as e:
        return f"Error copying files: {e}", 500

if __name__ == "__main__":
    app.run(debug=True)
