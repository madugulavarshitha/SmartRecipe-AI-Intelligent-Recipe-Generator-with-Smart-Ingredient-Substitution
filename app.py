import json
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database.db import init_db, get_connection
from ai_service import generate_recipe, RecipeAIError

app = Flask(__name__)
app.config.from_object(Config)

init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue. 🔐", "warning")
            return redirect(url_for("signin"))
        return view_func(*args, **kwargs)
    return wrapped


def current_user():
    if "user_id" not in session:
        return None
    conn = get_connection()
    user = conn.execute(
        "SELECT id, full_name, username, email, created_at FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


def short_description(steps, limit=110):
    text = " ".join(steps) if steps else "A personalized AI-generated recipe."
    return (text[:limit] + "…") if len(text) > limit else text


@app.context_processor
def inject_user():
    return {"nav_user": current_user() if "user_id" in session else None}


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    flash("⚠️ Something went wrong on our end. Please try again.", "error")
    return render_template("404.html"), 500


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([full_name, username, email, password, confirm_password]):
            flash("⚠️ All fields are required.", "error")
            return render_template("signup.html", form=request.form)

        if "@" not in email or "." not in email.split("@")[-1]:
            flash("⚠️ Please enter a valid email address.", "error")
            return render_template("signup.html", form=request.form)

        if password != confirm_password:
            flash("⚠️ Passwords do not match.", "error")
            return render_template("signup.html", form=request.form)

        if len(password) < 6:
            flash("⚠️ Password must be at least 6 characters long.", "error")
            return render_template("signup.html", form=request.form)

        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()

        if existing:
            conn.close()
            flash("⚠️ Username or email already exists. Please sign in instead.", "error")
            return render_template("signup.html", form=request.form)

        password_hash = generate_password_hash(password)
        try:
            conn.execute(
                "INSERT INTO users (full_name, username, email, password_hash) VALUES (?, ?, ?, ?)",
                (full_name, username, email, password_hash)
            )
            conn.commit()
        except Exception:
            conn.close()
            flash("⚠️ Could not create your account. Please try again.", "error")
            return render_template("signup.html", form=request.form)

        conn.close()
        flash("🎉 Account created successfully! Please sign in.", "success")
        return redirect(url_for("signin"))

    return render_template("signup.html", form={})


@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("⚠️ Please enter both fields.", "error")
            return render_template("signin.html")

        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier)
        ).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("❌ Invalid username/email or password.", "error")
            return render_template("signin.html")

        session["user_id"] = user["id"]
        session["full_name"] = user["full_name"]
        flash(f"👋 Welcome back, {user['full_name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("signin.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("👋 You have been signed out.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Authenticated pages
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    recent = conn.execute(
        "SELECT * FROM recipes WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (session["user_id"],)
    ).fetchall()

    total_recipes = conn.execute(
        "SELECT COUNT(*) c FROM recipes WHERE user_id = ?", (session["user_id"],)
    ).fetchone()["c"]

    total_favorites = conn.execute(
        "SELECT COUNT(*) c FROM favorites WHERE user_id = ?", (session["user_id"],)
    ).fetchone()["c"]

    total_substitutions = 0
    day_counts = {}
    all_recipes = conn.execute(
        "SELECT created_at, substitutions FROM recipes WHERE user_id = ?", (session["user_id"],)
    ).fetchall()
    for r in all_recipes:
        try:
            subs = json.loads(r["substitutions"]) if r["substitutions"] else []
            total_substitutions += len(subs)
        except (json.JSONDecodeError, TypeError):
            pass
        day_key = (r["created_at"] or "")[:10]
        if day_key:
            day_counts[day_key] = day_counts.get(day_key, 0) + 1

    conn.close()

    # Build a 7-day trend (oldest to newest) ending today, for a small chart.
    today = datetime.utcnow().date()
    weekly_trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_str = day.isoformat()
        weekly_trend.append({
            "label": day.strftime("%b %d"),
            "count": day_counts.get(day_str, 0)
        })

    recent_recipes = []
    for r in recent:
        try:
            recipe_data = json.loads(r["generated_recipe"])
            steps = recipe_data.get("recipe", {}).get("steps", [])
        except (json.JSONDecodeError, TypeError):
            steps = []
        recent_recipes.append({
            "id": r["id"],
            "dish_name": r["dish_name"],
            "created_at": r["created_at"],
            "description": short_description(steps)
        })

    donut_total = max(total_recipes + total_favorites + total_substitutions, 1)
    chart_data = {
        "total_recipes": total_recipes,
        "total_favorites": total_favorites,
        "total_substitutions": total_substitutions,
        "recipes_pct": round(total_recipes / donut_total * 100, 1),
        "favorites_pct": round(total_favorites / donut_total * 100, 1),
        "substitutions_pct": round(total_substitutions / donut_total * 100, 1),
    }

    max_weekly = max([d["count"] for d in weekly_trend] + [1])

    return render_template(
        "dashboard.html",
        recent_recipes=recent_recipes,
        chart_data=chart_data,
        weekly_trend=weekly_trend,
        max_weekly=max_weekly
    )


@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    if request.method == "GET":
        return render_template("generate_recipe.html")

    dish_name = request.form.get("dish_name", "").strip()
    ingredients_raw = request.form.get("ingredients", "").strip()
    use_only_available = request.form.get("use_only_available") == "on"
    suggest_substitutions = request.form.get("suggest_substitutions") == "on"
    explain_substitutions = request.form.get("explain_substitutions") == "on"

    ingredients = [i.strip() for i in ingredients_raw.split(",") if i.strip()]

    if not dish_name:
        flash("⚠️ Please tell us what dish you'd like to cook.", "error")
        return render_template("generate_recipe.html", form=request.form)

    if not ingredients:
        flash("⚠️ Please add at least one ingredient you have available.", "error")
        return render_template("generate_recipe.html", form=request.form)

    try:
        recipe_data = generate_recipe(
            dish_name, ingredients, use_only_available,
            suggest_substitutions, explain_substitutions
        )
    except RecipeAIError as exc:
        flash(f"🤖 AI Error: {exc}", "error")
        return render_template("generate_recipe.html", form=request.form)
    except Exception:
        flash("⚠️ An unexpected error occurred while generating your recipe. Please try again.", "error")
        return render_template("generate_recipe.html", form=request.form)

    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO recipes (user_id, dish_name, available_ingredients, generated_recipe, substitutions) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            session["user_id"],
            recipe_data.get("dish_name", dish_name),
            json.dumps(ingredients),
            json.dumps(recipe_data),
            json.dumps(recipe_data.get("substitutions", [])),
        )
    )
    conn.commit()
    recipe_id = cur.lastrowid
    conn.close()

    flash("✅ Your personalized recipe is ready!", "success")
    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


@app.route("/recipe/<int:recipe_id>")
@login_required
def recipe_detail(recipe_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recipes WHERE id = ? AND user_id = ?",
        (recipe_id, session["user_id"])
    ).fetchone()

    if row is None:
        conn.close()
        flash("⚠️ Recipe not found.", "error")
        return redirect(url_for("history"))

    is_favorite = conn.execute(
        "SELECT id FROM favorites WHERE user_id = ? AND recipe_id = ?",
        (session["user_id"], recipe_id)
    ).fetchone() is not None
    conn.close()

    try:
        recipe_data = json.loads(row["generated_recipe"])
    except (json.JSONDecodeError, TypeError):
        flash("⚠️ This recipe could not be loaded correctly.", "error")
        return redirect(url_for("history"))

    return render_template(
        "recipe_detail.html",
        recipe=recipe_data,
        row=row,
        is_favorite=is_favorite,
        is_result_view=False
    )


@app.route("/history")
@login_required
def history():
    query = request.args.get("q", "").strip()
    conn = get_connection()
    if query:
        rows = conn.execute(
            "SELECT * FROM recipes WHERE user_id = ? AND dish_name LIKE ? ORDER BY created_at DESC",
            (session["user_id"], f"%{query}%")
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM recipes WHERE user_id = ? ORDER BY created_at DESC",
            (session["user_id"],)
        ).fetchall()

    favorite_ids = {
        row["recipe_id"] for row in conn.execute(
            "SELECT recipe_id FROM favorites WHERE user_id = ?", (session["user_id"],)
        ).fetchall()
    }
    conn.close()

    recipes = []
    for r in rows:
        try:
            recipe_data = json.loads(r["generated_recipe"])
            steps = recipe_data.get("recipe", {}).get("steps", [])
        except (json.JSONDecodeError, TypeError):
            steps = []
        recipes.append({
            "id": r["id"],
            "dish_name": r["dish_name"],
            "created_at": r["created_at"],
            "description": short_description(steps),
            "is_favorite": r["id"] in favorite_ids
        })

    return render_template("recipe_history.html", recipes=recipes, query=query)


@app.route("/recipe/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM recipes WHERE id = ? AND user_id = ?",
        (recipe_id, session["user_id"])
    ).fetchone()
    if row is None:
        conn.close()
        flash("⚠️ Recipe not found.", "error")
        return redirect(url_for("history"))

    conn.execute("DELETE FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("🗑️ Recipe deleted.", "success")
    return redirect(request.referrer or url_for("history"))


@app.route("/favorites")
@login_required
def favorites():
    conn = get_connection()
    rows = conn.execute("""
        SELECT recipes.* FROM recipes
        JOIN favorites ON favorites.recipe_id = recipes.id
        WHERE favorites.user_id = ?
        ORDER BY favorites.created_at DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    recipes = []
    for r in rows:
        try:
            recipe_data = json.loads(r["generated_recipe"])
            steps = recipe_data.get("recipe", {}).get("steps", [])
        except (json.JSONDecodeError, TypeError):
            steps = []
        recipes.append({
            "id": r["id"],
            "dish_name": r["dish_name"],
            "created_at": r["created_at"],
            "description": short_description(steps)
        })

    return render_template("favorites.html", recipes=recipes)


@app.route("/favorites/toggle/<int:recipe_id>", methods=["POST"])
@login_required
def toggle_favorite(recipe_id):
    conn = get_connection()
    owned = conn.execute(
        "SELECT id FROM recipes WHERE id = ? AND user_id = ?",
        (recipe_id, session["user_id"])
    ).fetchone()

    if owned is None:
        conn.close()
        flash("⚠️ Recipe not found.", "error")
        return redirect(url_for("history"))

    existing = conn.execute(
        "SELECT id FROM favorites WHERE user_id = ? AND recipe_id = ?",
        (session["user_id"], recipe_id)
    ).fetchone()

    if existing:
        conn.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
        conn.commit()
        flash("💔 Removed from favorites.", "success")
    else:
        conn.execute(
            "INSERT INTO favorites (user_id, recipe_id) VALUES (?, ?)",
            (session["user_id"], recipe_id)
        )
        conn.commit()
        flash("❤️ Added to favorites!", "success")

    conn.close()
    return redirect(request.referrer or url_for("recipe_detail", recipe_id=recipe_id))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_connection()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not full_name or not email:
            flash("⚠️ Name and email cannot be empty.", "error")
        elif "@" not in email or "." not in email.split("@")[-1]:
            flash("⚠️ Please enter a valid email address.", "error")
        else:
            duplicate = conn.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (email, session["user_id"])
            ).fetchone()
            if duplicate:
                flash("⚠️ That email is already used by another account.", "error")
            else:
                conn.execute(
                    "UPDATE users SET full_name = ?, email = ? WHERE id = ?",
                    (full_name, email, session["user_id"])
                )
                conn.commit()
                session["full_name"] = full_name
                flash("✅ Profile updated successfully!", "success")

    user = conn.execute(
        "SELECT id, full_name, username, email, created_at FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()

    return render_template("profile.html", user=user)


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
