import os
import re

with open('utils/recipe_ai.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the single fallback item with the full fallback dictionary array
text = text.replace(
'''    except Exception as e:
        print(f"Error connecting to Gemini API for budget meals: {e}")
        return [{"name": "Budget Pasta", "time": "15 mins"}]''',
'''    except Exception as e:
        print(f"Error connecting to Gemini API for budget meals: {e}")
        
        all_options = {
            "vegetarian": [
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Cheese Quesadillas", "time": "10 mins", "ingredients_range": "2-4"},
                {"name": "Veggie Stir Fry", "time": "15 mins", "ingredients_range": "6-9"},
                {"name": "Potato Gnocchi", "time": "20 mins", "ingredients_range": "4-5"},
                {"name": "Eggplant Parm", "time": "45 mins", "ingredients_range": "5-8"},
                {"name": "Mushroom Risotto", "time": "40 mins", "ingredients_range": "6-8"},
                {"name": "Zucchini Fritters", "time": "25 mins", "ingredients_range": "5-7"},
                {"name": "Tomato Basil Soup", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Sweet Potato Noodles", "time": "20 mins", "ingredients_range": "3-5"}
            ],
            "vegan": [
                {"name": "Chickpea Curry", "time": "25 mins", "ingredients_range": "6-9"},
                {"name": "Black Bean Tacos", "time": "15 mins", "ingredients_range": "5-7"},
                {"name": "Tomato Rice", "time": "20 mins", "ingredients_range": "3-5"},
                {"name": "Tofu Scramble", "time": "12 mins", "ingredients_range": "4-6"},
                {"name": "Lentil Pasta", "time": "15 mins", "ingredients_range": "2-4"},
                {"name": "Vegan Chili", "time": "35 mins", "ingredients_range": "8-12"},
                {"name": "Peanut Stew", "time": "30 mins", "ingredients_range": "6-8"},
                {"name": "Avocado Salad", "time": "10 mins", "ingredients_range": "3-5"},
                {"name": "Mushroom Tacos", "time": "20 mins", "ingredients_range": "4-6"}
            ],
            "any": [
                {"name": "Tomato Pasta", "time": "15 mins", "ingredients_range": "3-5"}, 
                {"name": "Fried Rice with Eggs", "time": "10 mins", "ingredients_range": "4-7"}, 
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6"}, 
                {"name": "Potato Bake", "time": "50 mins", "ingredients_range": "3-5"}, 
                {"name": "Oatmeal", "time": "5 mins", "ingredients_range": "2-4"}, 
                {"name": "Bean Burritos", "time": "10 mins", "ingredients_range": "4-6"},
                {"name": "Roast Chicken Thighs", "time": "45 mins", "ingredients_range": "3-5"},
                {"name": "Pork Chops & Apples", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Sausage and Peppers", "time": "25 mins", "ingredients_range": "3-5"}
            ]
        }
        return all_options.get(preference, all_options["any"])'''
)

with open('utils/recipe_ai.py', 'w', encoding='utf-8') as f:
    f.write(text)
