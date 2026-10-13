import os
import sqlite3
from pathlib import Path
from datetime import date

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort
)
from flask_wtf.csrf import CSRFProtect

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "todo.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-only-change-this-secret"
)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

CSRFProtect(app)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'Medium'
                    CHECK(priority IN ('Low', 'Medium', 'High')),
                due_date TEXT DEFAULT NULL,
                completed INTEGER NOT NULL DEFAULT 0
                    CHECK(completed IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT
                    (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
            )
        """)


def get_task(task_id):
    with get_db() as db:
        task = db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

    if task is None:
        abort(404)

    return task


def validate_task_form():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    priority = request.form.get("priority", "Medium")
    due_date = request.form.get("due_date", "").strip() or None

    if not title or len(title) > 120:
        flash("Title is required and must be at most 120 characters.", "error")
        return None

    if len(description) > 2000:
        flash("Description must be at most 2000 characters.", "error")
        return None

    if priority not in ("Low", "Medium", "High"):
        flash("Please select a valid priority.", "error")
        return None

    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            flash("Please enter a valid due date.", "error")
            return None

    return title, description, priority, due_date


@app.route("/")
def index():
    search = request.args.get("q", "").strip()[:120]
    status = request.args.get("status", "all")
    priority_filter = request.args.get("priority", "all")
    sort = request.args.get("sort", "newest")

    if status not in ("all", "pending", "completed"):
        status = "all"

    if priority_filter not in ("all", "Low", "Medium", "High"):
        priority_filter = "all"

    sort_options = {
        "newest": "created_at DESC, id DESC",
        "oldest": "created_at ASC, id ASC",
        "due_date": "due_date IS NULL, due_date ASC, id DESC",
        "priority": (
            "CASE priority WHEN 'High' THEN 1 "
            "WHEN 'Medium' THEN 2 ELSE 3 END, created_at DESC"
        ),
    }
    order_by = sort_options.get(sort, sort_options["newest"])

    conditions = []
    params = []

    if search:
        conditions.append("(title LIKE ? OR description LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    if status == "pending":
        conditions.append("completed = 0")
    elif status == "completed":
        conditions.append("completed = 1")

    if priority_filter != "all":
        conditions.append("priority = ?")
        params.append(priority_filter)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    with get_db() as db:
        tasks = db.execute(
            f"SELECT * FROM tasks{where} ORDER BY {order_by}",
            params
        ).fetchall()

        stats = db.execute("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END), 0)
                    AS pending,
                COALESCE(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END), 0)
                    AS completed
            FROM tasks
        """).fetchone()

    return render_template(
        "index.html",
        tasks=tasks,
        stats=stats,
        search=search,
        status=status,
        priority_filter=priority_filter,
        sort=sort,
        today=date.today().isoformat(),
    )


@app.route("/add", methods=["POST"])
def add_task():
    values = validate_task_form()
    if values is None:
        return redirect(url_for("index"))

    title, description, priority, due_date = values

    with get_db() as db:
        db.execute("""
            INSERT INTO tasks (title, description, priority, due_date)
            VALUES (?, ?, ?, ?)
        """, (title, description, priority, due_date))

    flash("Task added successfully!", "success")
    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    task = get_task(task_id)

    if request.method == "POST":
        values = validate_task_form()
        if values is None:
            return redirect(url_for("edit_task", task_id=task_id))

        title, description, priority, due_date = values

        with get_db() as db:
            db.execute("""
                UPDATE tasks
                SET title = ?, description = ?, priority = ?, due_date = ?
                WHERE id = ?
            """, (title, description, priority, due_date, task_id))

        flash("Task updated successfully!", "success")
        return redirect(url_for("index"))

    return render_template("edit.html", task=task)


@app.route("/toggle/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    task = get_task(task_id)

    with get_db() as db:
        db.execute(
            "UPDATE tasks SET completed = ? WHERE id = ?",
            (0 if task["completed"] else 1, task_id)
        )

    flash("Task status updated.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    get_task(task_id)

    with get_db() as db:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    flash("Task deleted.", "success")
    return redirect(url_for("index"))


@app.route("/clear-completed", methods=["POST"])
def clear_completed():
    with get_db() as db:
        db.execute("DELETE FROM tasks WHERE completed = 1")

    flash("Completed tasks cleared.", "success")
    return redirect(url_for("index"))


@app.errorhandler(413)
def too_large(_error):
    return "Request too large.", 413


init_db()

if __name__ == "__main__":
    app.run(debug=True)