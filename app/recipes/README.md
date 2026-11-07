# Offline Recipe Pack

`pack.json` holds 100 built-in recipes across 10 categories: Lighting, Robotics, Garden, Home & Desk, Storage, Sound, Play, Outdoor, Workshop, and Science. Each recipe plays offline in its own sandbox with its own parts, so every one works on stage with no API key and no wifi.

Each recipe is a basic build with an `extend` line, the next upgrade shown when you complete the build.

## Recipe shape

Same shape the AI idea generator returns, plus a few pack fields:

| Field | Meaning |
|-------|---------|
| `id` | Unique slug, e.g. `jar_lantern` |
| `title`, `pitch` | Name and one-sentence description |
| `category`, `difficulty` | Catalog filter and label (`Easy`, `Medium`, `Hard`) |
| `rawMaterials` | `{id, name, qty}` parts the sandbox starts with |
| `recipes` | Merges: `a` + `b` makes `result_id` (`result_name`, `result_short`) |
| `final_requires` | `{id, qty}` items needed to press Build |
| `assembly_steps` | 2 to 8 steps shown in the assembly guide |
| `extend` | The next upgrade, shown on completion |

A merge input is a raw part id or a `result_id` from an earlier merge in the same recipe.

## Add or edit a recipe

1. Edit `pack.json`.
2. Run `python3 app/recipes/validate.py`. The validator checks every merge uses real parts, no pair repeats, every part gets used, and the raw counts cover the build.
3. Run `python3 app/tests/pack_test.py <your_recipe_id>` to build the recipe in a headless browser.
4. Reload the app. The recipe shows in the catalog under its category.
