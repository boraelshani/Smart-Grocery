"""
MODULE 5 - Category Normalization
"""
import re

class CategoryMapper:
    def __init__(self):
        self.unified_categories = {
            "Chocolate": ["schokolade", "süßwaren", "chocolate", "candy"],
            "Dairy": ["milch", "käse", "dairy", "milk", "cheese", "molkerei"],
            "Produce": ["obst", "gemüse", "produce", "fruits", "vegetables"],
            "Beverages": ["getränke", "beverages", "drinks", "saft", "wasser"]
        }

    def map_category(self, store_category_path):
        """Maps store category path to unified global category using keywords."""
        if not store_category_path:
            return "Other"
            
        full_path_str = " ".join(store_category_path).lower()
        
        # Keyword matching
        for canonical, keywords in self.unified_categories.items():
            for kw in keywords:
                if kw in full_path_str:
                    return canonical
                    
        return self._ai_fallback_prediction(full_path_str)

    def _ai_fallback_prediction(self, text):
        """Fallback AI-based predictor using Mock/Embeddings heuristic."""
        # Future implementation map for LLM/Embeddings
        return "Miscellaneous" 
