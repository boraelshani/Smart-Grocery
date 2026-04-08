import re

with open("templates/recipe_planner.html", "r") as f:
    text = f.read()

btn_html = r"""
                            <ul class="list-group list-group-flush mb-4">
                                ${ingredientsList}
                            </ul>
                            <!-- COMPARE INGREDIENTS BUTTON -->
                            <button class="btn btn-primary w-100 rounded-pill fw-bold py-3 mb-4 shadow" style="background: linear-gradient(135deg, #7c3aed, #0ea5a3); border: none; font-size: 1.1rem;" onclick="compareIngredients('${encodeURIComponent(JSON.stringify(Object.keys(recipe.ingredients || {})))}')">
                                <i class="bi bi-search me-2"></i> Compare Prices for Ingredients
                            </button>
"""

# replace the <ul> rendering block
text = re.sub(r'<ul class="list-group list-group-flush mb-4">[^<]*\$\{ingredientsList\}[^<]*<\/ul>', btn_html, text)

js_addition = """
function compareIngredients(jsonKeys) {
    try {
        const keys = JSON.parse(decodeURIComponent(jsonKeys));
        if (!keys || keys.length === 0) return;
        // In a real multi-search, we might route to a specialized bulk compare page.
        // For now, we will add them to the query or redirect to search for the first few.
        const query = keys.slice(0, 3).join(' | '); // simple approximation
        window.location.href = "/compare-prices?search=" + encodeURIComponent(query);
    } catch(err) {
        console.error(err);
    }
}
</script>
"""

text = text.replace("</script>", js_addition)

with open("templates/recipe_planner.html", "w") as f:
    f.write(text)
