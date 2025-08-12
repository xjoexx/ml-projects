from __future__ import annotations

from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, jsonify

from .worker import QueueWorker
from . import db

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"), static_folder=str(Path(__file__).parent / "static"))

# Jinja filter to translate status to Russian
_STATUS_RU = {
    "queued": "Новый",
    "running": "Выполняется",
    "paused": "Пауза",
    "completed": "Выполнено",
    "failed": "Ошибка",
    "canceled": "Отменено",
}

@app.template_filter("status_ru")
def status_ru(value: str) -> str:
    return _STATUS_RU.get(value, value)

worker = QueueWorker()

_started = False

def _ensure_started_once() -> None:
    global _started
    if _started:
        return
    db.init_db()
    worker.start()
    _started = True

@app.before_request
def _before_request_setup():
    _ensure_started_once()


@app.route("/")
def root():
    return redirect(url_for("jobs_dashboard"))


@app.route("/programs/", methods=["GET"])
def programs_list_page():
    programs = db.list_programs()
    return render_template("programs.html", programs=programs)


@app.route("/programs/create", methods=["POST"])
def create_program_form():
    name = request.form.get("name", type=str)
    code_text = request.form.get("code_text", type=str)
    estimated = request.form.get("estimated_duration_seconds", type=int)
    existing = db.find_program_by_name(name)
    if existing:
        return ("Program exists", 400)
    db.create_program(name=name, code_text=code_text, estimated_duration_seconds=estimated)
    return redirect(url_for("programs_list_page"))


@app.route("/programs/api", methods=["GET"])
def programs_api_list():
    programs = db.list_programs()
    return jsonify(programs)


@app.route("/programs/<int:program_id>/items", methods=["GET"]) 
def program_items(program_id: int):
    items = db.list_program_items(program_id)
    return jsonify(items)


@app.route("/jobs/", methods=["GET"])
def jobs_dashboard():
    jobs = db.list_active_jobs()
    programs = db.list_programs()
    operators = ["Артемьев", "Корниенков", "Федосеев"]
    cut_types = ["газ", "плазма", "лазер"]
    return render_template("dashboard.html", jobs=jobs, programs=programs, operators=operators, cut_types=cut_types)


@app.route("/jobs/enqueue", methods=["POST"])
def enqueue_job_from_form():
    program_id = request.form.get("program_id", type=int)
    priority = request.form.get("priority", default=100, type=int)
    cut_type = request.form.get("cut_type", type=str)
    thickness = request.form.get("thickness", type=str)
    material = request.form.get("material", type=str)
    if not db.get_program(program_id):
        return ("Program not found", 404)
    db.enqueue_job(
        program_id=program_id,
        priority=priority,
        cut_type=cut_type,
        thickness=thickness,
        material=material,
    )
    return redirect(url_for("jobs_dashboard"))


@app.route("/jobs/api", methods=["GET"]) 
def jobs_api_list():
    jobs = db.list_jobs()
    return jsonify(jobs)


@app.route("/jobs/reorder", methods=["POST"]) 
def jobs_reorder():
    payload = request.get_json(silent=True) or {}
    job_ids = payload.get("job_ids")
    if not isinstance(job_ids, list) or not all(isinstance(x, int) for x in job_ids):
        return jsonify({"ok": False, "error": "job_ids must be a list[int]"}), 400
    db.set_job_priorities(job_ids)
    return jsonify({"ok": True})


@app.route("/jobs/<int:job_id>/heat", methods=["POST"]) 
def update_heat_number(job_id: int):
    payload = request.get_json(silent=True) or {}
    heat_number = payload.get("heat_number")
    if heat_number is not None and not isinstance(heat_number, str):
        return jsonify({"ok": False, "error": "heat_number must be string or null"}), 400
    if not db.get_job(job_id):
        return jsonify({"ok": False, "error": "Job not found"}), 404
    db.update_job_heat_number(job_id, heat_number)
    return jsonify({"ok": True})


@app.route("/jobs/<int:job_id>/operator", methods=["POST"]) 
def update_operator(job_id: int):
    payload = request.get_json(silent=True) or {}
    operator_name = payload.get("operator_name")
    if operator_name is not None and not isinstance(operator_name, str):
        return jsonify({"ok": False, "error": "operator_name must be string or null"}), 400
    if not db.get_job(job_id):
        return jsonify({"ok": False, "error": "Job not found"}), 404
    db.update_job_operator(job_id, operator_name)
    return jsonify({"ok": True})


@app.route("/jobs/<int:job_id>/pause", methods=["POST"]) 
def pause_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return ("Job not found", 404)
    if job["status"] not in ("running", "queued"):
        return ("Invalid state", 400)
    db.update_job_status(job_id, "paused")
    return redirect(url_for("jobs_dashboard"))


@app.route("/jobs/<int:job_id>/resume", methods=["POST"]) 
def resume_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return ("Job not found", 404)
    if job["status"] != "paused":
        return ("Invalid state", 400)
    db.update_job_status(job_id, "queued")
    return redirect(url_for("jobs_dashboard"))


@app.route("/jobs/<int:job_id>/complete", methods=["POST"]) 
def complete_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return ("Job not found", 404)
    if job["status"] in ("completed", "failed", "canceled"):
        return ("Already finished", 400)
    db.update_job_status(job_id, "completed")
    return redirect(url_for("jobs_dashboard"))


@app.route("/jobs/<int:job_id>/duplicate", methods=["POST"]) 
def duplicate_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return ("Job not found", 404)
    new_id = db.enqueue_job(
        program_id=job["program_id"],
        priority=job.get("priority", 100),
        cut_type=job.get("cut_type"),
        thickness=job.get("thickness"),
        material=job.get("material"),
        heat_number=job.get("heat_number"),
        operator_name=job.get("operator_name"),
    )
    return redirect(url_for("jobs_dashboard"))


@app.route("/archive", methods=["GET"]) 
def archive_page():
    q = request.args.get("q", type=str)
    jobs = db.list_completed_jobs(search_program=q)
    operators = ["Артемьев", "Корниенков", "Федосеев"]
    return render_template("archive.html", jobs=jobs, operators=operators, q=q or "")


@app.route("/reports/", methods=["GET"]) 
def reports_page():
    summary = db.summary_counts_and_avg()
    recent = db.recent_jobs(limit=50)
    return render_template("reports.html", summary=summary, recent=recent)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)