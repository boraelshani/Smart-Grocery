from datetime import datetime
import random

class PricePredictorModel:
    @staticmethod
    def _get_store_multiplier(store_name):
        # Base multipliers indicating typical price level compared to baseline
        # Higher = more expensive, Lower = cheaper
        store = store_name.upper()
        if "HOFER" in store: return 0.90
        if "LIDL" in store: return 0.90
        if "PENNY" in store: return 0.92
        if "SPAR" in store: return 1.05
        if "BILLA" in store: return 1.08
        if "BILLA PLUS" in store: return 1.12
        return 1.0

    @staticmethod
    def estimate_missing_prices(product):
        """
        Takes a product dictionary, examines its active store prices,
        and dynamically estimates missing prices for other major supermarkets
        without modifying or risking the actual database logic.
        """
        # We need a baseline to estimate from.
        if not product.get('stores') or not isinstance(product['stores'], list):
            return product
            
        stores = product.get('stores', [])
        
        # Don't try to predict if there are no prices or already enough prices
        if len(stores) == 0:
            return product
            
        existing_store_names = {s.get('store', '').upper(): s for s in stores if s.get('price')}
        
        # Supermarkets we want to ensure have a price
        target_stores = ["BILLA", "SPAR", "HOFER", "LIDL"]
        missing_stores = []
        for ts in target_stores:
            found = False
            for store_name in existing_store_names:
                if ts in store_name:
                    found = True
                    break
            if not found:
                missing_stores.append(ts)
        
        if not missing_stores:
            return product # We already have prices for major stores
            
        # Calculate a neutral baseline price
        valid_prices = []
        for s in stores:
            try:
                valid_prices.append((float(s.get('price')), s.get('store', '')))
            except (ValueError, TypeError):
                continue
                
        if not valid_prices:
            return product
            
        # Calculate un-biased base price from existing data
        calculated_base_prices = []
        for price, s_name in valid_prices:
            multiplier = PricePredictorModel._get_store_multiplier(s_name)
            base = price / multiplier
            calculated_base_prices.append(base)
            
        avg_base_price = sum(calculated_base_prices) / len(calculated_base_prices)
        
        # We will only generate 1 or 2 missing prices per product to keep it looking realistic.
        num_to_predict = min(len(missing_stores), random.choice([1, 2]))
        stores_to_predict = random.sample(missing_stores, num_to_predict)
        
        extended_product = dict(product)
        extended_product['stores'] = list(stores) # Copy list so we don't mutate DB ref natively
        
        for store_name in stores_to_predict:
            store_mult = PricePredictorModel._get_store_multiplier(store_name)
            predicted_price = avg_base_price * store_mult
            
            # Predict realistic decimal endings like .99, .49, .79
            cents = random.choice([0.49, 0.79, 0.89, 0.99])
            final_predicted = float(int(predicted_price)) + cents
            
            # Form the new store object memory-only
            predicted_store_obj = {
                "store": store_name,
                "price": float(f"{final_predicted:.2f}"),
                "is_estimated": True, # CRITICAL: This lets UI label it as AI Estimated
            }
            extended_product['stores'].append(predicted_store_obj)
            
        # Re-sort list by price if possible
        try:
            extended_product['stores'].sort(key=lambda x: float(x.get('price', 999)))
        except:
            pass
            
        return extended_product

    @staticmethod
    def evaluate_deal(product):
        """
        Determines if the product has a 'Great Deal' relative to historical prices.
        Since we don't have real time-series in this prototype, we simulate a 'Deal'.
        Returns 0-1 score, 1 = amazing deal, or None if no valid metric.
        """
        stores = product.get('stores', [])
        valid_prices = []
        for s in stores:
            try:
                valid_prices.append((float(s.get('price')), s.get('store', '')))
            except:
                pass
        if not valid_prices: return None
        
        # Calculate base average
        calculated_base_prices = []
        for price, s_name in valid_prices:
             calculated_base_prices.append(price / PricePredictorModel._get_store_multiplier(s_name))
             
        avg_base = sum(calculated_base_prices) / len(calculated_base_prices)
        cheapest_p = min([p for p, s in valid_prices])
        
        # If the cheapest is > 10% below the base avg (normalized), it's a great deal.
        if cheapest_p < (avg_base * 0.85):
            return {"is_great_deal": True, "discount_pct": float(f"{(1 - (cheapest_p / avg_base)) * 100:.1f}")}
        return {"is_great_deal": False, "discount_pct": 0.0}
