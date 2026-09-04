"""
ai_service.py
Dedicated AI service module for SmartRecipe AI.
Handles all communication with Gemini 2.5 Flash via the google-genai SDK.
"""

import json
import re
import time
from google import genai
from google.genai import types
from config import Config


class RecipeAIError(Exception):
    """Raised when the AI service fails to produce a usable recipe."""
    pass


def _get_client():
    if not Config.GEMINI_API_KEY:
        raise RecipeAIError("Gemini API key is not configured. Please set GEMINI_API_KEY in .env")
    return genai.Client(api_key=Config.GEMINI_API_KEY)


def _build_prompt(dish_name, ingredients, use_only_available, suggest_substitutions, explain_substitutions):
    ingredients_list = ", ".join(ingredients)

    rules = f"""
You are an expert culinary AI assistant inside a recipe application called SmartRecipe AI.

TASK:
The user wants to cook: "{dish_name}"
The user's available ingredients are: {ingredients_list}

INSTRUCTIONS:
1. Determine the ingredients normally required to prepare "{dish_name}".
2. Compare the normal requirements with the user's available ingredients.
3. Identify which required ingredients are MISSING from what the user has.
4. For every missing ingredient, look ONLY inside the user's available ingredients list
   for a suitable substitution, based on the FUNCTION of the ingredient
   (acidity, fat, moisture, binding, flavor family, texture, etc).
5. Do NOT invent or assume the user has ingredients that were not listed.
6. {"The user has enabled 'Use Only My Ingredients'. You MUST NOT introduce any ingredient that is not in the user's available list, either in the main recipe or as a substitution. If no suitable substitution exists within the available ingredients, clearly state that the ingredient is unavailable and no suitable replacement was found." if use_only_available else "The user has NOT restricted the recipe to only their ingredients, so you may note ingredients they would ideally need to buy, but still prioritize substitutions from what they already have."}
7. {"Suggest substitutions wherever appropriate." if suggest_substitutions else "Only list missing ingredients, do not suggest substitutions."}
8. {"For every substitution, explain WHY it works based on shared culinary function, and be honest about how it may change taste or texture. Never claim two different ingredients taste exactly the same." if explain_substitutions else "Keep substitution reasons brief."}
9. Preserve the intended identity of the dish as much as possible.
10. Write clear, numbered, step-by-step cooking instructions that use the substituted ingredients naturally.
11. If an ingredient cannot be reasonably substituted from the available list, do NOT force a fake substitution — instead report it under "missing_ingredients" with no matching entry in "substitutions", and mention it in "ai_note".

RESPOND WITH ONLY VALID JSON. Do not include markdown code fences, explanations, or any text outside the JSON object.
Use exactly this structure:

{{
  "dish_name": "string",
  "ingredients_used": [{{"name": "string", "quantity": "string"}}],
  "missing_ingredients": [{{"name": "string", "quantity": "string"}}],
  "substitutions": [
    {{
      "original": "string",
      "replacement": "string",
      "quantity": "string",
      "reason": "string explaining the shared function and any taste/texture difference"
    }}
  ],
  "recipe": {{
    "preparation_time": "string",
    "cooking_time": "string",
    "servings": "string",
    "steps": ["string", "string"]
  }},
  "ai_note": "string summarizing key substitutions and any unresolved missing ingredients"
}}
"""
    return rules


def _extract_json(raw_text):
    """Strip markdown fences / stray text and parse JSON safely."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()

    # If there's still leading/trailing junk, try to isolate the outermost braces
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecipeAIError(f"The AI returned an invalid response format: {exc}")


def generate_recipe(dish_name, ingredients, use_only_available=True,
                     suggest_substitutions=True, explain_substitutions=True):
    """
    Calls Gemini 2.5 Flash and returns a parsed, structured recipe dict.
    Raises RecipeAIError on any failure (network, invalid JSON, empty response).
    """
    if not dish_name or not dish_name.strip():
        raise RecipeAIError("Dish name cannot be empty.")
    if not ingredients:
        raise RecipeAIError("Please provide at least one available ingredient.")

    prompt = _build_prompt(
        dish_name.strip(), ingredients, use_only_available,
        suggest_substitutions, explain_substitutions
    )

    client = _get_client()

    # Try the configured model first, then fall back through known-good model
    # names if Google has retired/renamed the primary one (this happens often
    # as new Gemini versions roll out and older ones are sunset).
    models_to_try = [Config.GEMINI_MODEL] + [
        m for m in Config.GEMINI_MODEL_FALLBACKS if m != Config.GEMINI_MODEL
    ]

    raw_text = None
    last_error = None
    MAX_RETRIES_PER_MODEL = 3
    RETRY_DELAY_SECONDS = 2

    for model_name in models_to_try:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = response.text
                if raw_text:
                    break
            except Exception as exc:
                last_error = exc
                error_text = str(exc)

                # Model retired/renamed -> stop retrying this model, try the next one.
                if "NOT_FOUND" in error_text or "404" in error_text or "not available" in error_text.lower():
                    break

                # Transient overload/rate-limit -> wait briefly and retry the same model.
                is_transient = (
                    "UNAVAILABLE" in error_text or "503" in error_text
                    or "RESOURCE_EXHAUSTED" in error_text or "429" in error_text
                    or "high demand" in error_text.lower()
                )
                if is_transient and attempt < MAX_RETRIES_PER_MODEL:
                    time.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue

                # Anything else (auth errors, bad request, etc.) -> stop entirely.
                if not is_transient:
                    raise RecipeAIError(f"Could not reach Gemini AI service: {exc}")
        if raw_text:
            break

    if not raw_text:
        if last_error:
            raise RecipeAIError(
                f"Gemini's servers are currently overloaded or unavailable ({last_error}). "
                f"We retried automatically — please wait a moment and try generating again."
            )
        raise RecipeAIError("The AI returned an empty response. Please try again.")

    data = _extract_json(raw_text)

    # Basic structural validation with safe fallbacks
    data.setdefault("dish_name", dish_name.strip())
    data.setdefault("ingredients_used", [])
    data.setdefault("missing_ingredients", [])
    data.setdefault("substitutions", [])
    data.setdefault("recipe", {"preparation_time": "N/A", "cooking_time": "N/A", "servings": "N/A", "steps": []})
    data.setdefault("ai_note", "")

    if "steps" not in data["recipe"]:
        data["recipe"]["steps"] = []

    return data
