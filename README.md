# 🍲 SmartRecipe AI — Intelligent Recipe Generator with Smart Ingredient Substitution

A full-stack GenAI web application that generates personalized recipes from the ingredients
you already have, and intelligently substitutes missing ingredients using Gemini 2.5 Flash —
always explaining *why* each swap works.

---

## 📋 Description

SmartRecipe AI lets a user enter a dish they want to cook and the ingredients currently in
their kitchen. The app calls Gemini 2.5 Flash to:

1. Determine what the dish normally needs.
2. Compare that with what the user has.
3. Identify missing ingredients.
4. Suggest a substitution **only from the user's own ingredient list**, based on the
   ingredient's *function* (acidity, fat, moisture, flavor, texture).
5. Explain the reasoning and any taste/texture impact — never claiming two different
   ingredients taste identical.
6. Generate a full, numbered recipe using the (possibly substituted) ingredients.

---

## ✨ Features

- 🔐 Secure signup/signin with hashed passwords (Werkzeug)
- 🍽️ AI recipe generation via Gemini 2.5 Flash, returning structured JSON
- 🔄 Smart, explainable ingredient substitution (function-based, not guesswork)
- 🥕 Ingredient chip/tag input on the generation form
- 📜 Personal recipe history with search
- ❤️ Favorites system
- 📊 Pastel dashboard charts showing recipes / favorites / substitutions
- ⚙️ Settings page and editable profile
- 🎨 Light pastel, glassmorphism-inspired UI, fully responsive
- 🛡️ Session-based auth, per-user data isolation, parameterized SQL queries

---

## 🛠️ Technology Stack

| Layer      | Technology                          |
|------------|--------------------------------------|
| Backend    | Python, Flask                        |
| Database   | SQLite                               |
| Templates  | Jinja2                               |
| AI Model   | Gemini 2.5 Flash (`google-genai` SDK)|
| Frontend   | HTML5, CSS3, vanilla JavaScript      |
| Auth       | Flask sessions + Werkzeug hashing    |

---

## 📁 Project Structure

```
smartrecipe/
│
├── app.py                     # Main Flask app & routes
├── config.py                  # App configuration
├── ai_service.py              # Gemini AI integration module
├── database.db                # SQLite database (auto-created)
├── requirements.txt
├── .env                       # Environment variables (API key, secret key)
├── README.md
│
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── signup.html
│   ├── signin.html
│   ├── dashboard.html
│   ├── generate_recipe.html
│   ├── recipe_detail.html     # Used for both the just-generated result and saved view
│   ├── recipe_history.html
│   ├── favorites.html
│   ├── profile.html
│   ├── settings.html
│   └── 404.html
│
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── images/
│
└── database/
    └── db.py                  # Schema + connection helpers
```

> **Note:** The result page and detail page were consolidated into a single
> `recipe_detail.html` template (used right after generation and when revisiting
> a saved recipe) to keep the codebase clean without duplicating markup.

---

## ⚙️ Installation

### 1. Clone / unzip the project
```bash
cd smartrecipe
```

### 2. Create a virtual environment
```bash
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
The `.env` file is already included with a placeholder structure:
```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
SECRET_KEY=your_flask_secret_key
```
Replace `GEMINI_API_KEY` with your own key from [Google AI Studio](https://aistudio.google.com/) if needed.

### 5. Database setup
No manual step required — `database.db` and all tables are created automatically
the first time you run the app (via `init_db()` in `database/db.py`).

### 6. Run the application
```bash
python app.py
```
Visit **http://127.0.0.1:5000** in your browser.

---

## 🧑‍🍳 How to Use

1. **Sign Up** for an account → **Sign In**.
2. From the **Dashboard**, click **Generate Recipe**.
3. Enter the dish you want (e.g. `Chicken Pakodi`) and add your available ingredients as chips.
4. Toggle the options: use-only-available-ingredients, suggest substitutions, explain substitutions.
5. Click **Generate Recipe with AI** and wait for Gemini to build your recipe.
6. Review ingredients used, smart substitutions (with reasons), any unresolved missing
   ingredients, and step-by-step instructions.
7. **Save to Favorites**, revisit anytime from **History**, or generate another recipe.

### Example

**Dish:** Chicken Pakodi
**Available:** Chicken, Besan, Onion, Ginger, Garlic, Chilli Powder, Lemon, Salt, Oil

The recipe normally needs **Vinegar**, which is missing. The AI substitutes:

> **Vinegar → Lemon Juice** — *"Vinegar provides acidity and tanginess. Lemon juice
> also provides acidity and tanginess, so it can be used as a suitable replacement."*
> Quantity: 1–2 tsp

---

## 🤖 GenAI Workflow

```
User Input (dish + ingredients)
        │
        ▼
ai_service.py builds a structured prompt
        │
        ▼
Gemini 2.5 Flash (JSON-mode response)
        │
        ▼
JSON parsed & validated → missing ingredients & substitutions extracted
        │
        ▼
Recipe + substitutions saved to SQLite (per user)
        │
        ▼
Rendered on the Recipe Result / Detail page
```

---

## 🔒 Security Notes

- Passwords are hashed with `werkzeug.security.generate_password_hash` — never stored in plain text.
- All database queries use parameterized statements to prevent SQL injection.
- Session-based authentication guards every private route (`/dashboard`, `/generate`, `/history`, `/favorites`, `/profile`, `/settings`).
- Users can only view, favorite, or delete their **own** recipes.
- The Gemini API key lives only in `.env` / server-side config — never exposed to the frontend.

---

## 🚀 Future Scope

- 🌐 Multi-language recipe generation (Hindi, Telugu, Tamil)
- 📸 Ingredient detection from an uploaded fridge/pantry photo
- 🛒 "Buy missing ingredients" integration with grocery delivery APIs
- 📱 Progressive Web App (installable, offline recipe cache)
- 🥗 Nutrition breakdown per recipe
- 🗣️ Voice-guided step-by-step cooking mode

---

Built as a GenAI academic project using Flask + Gemini 2.5 Flash. 🍲✨
