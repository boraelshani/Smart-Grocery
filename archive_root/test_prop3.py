
import os, sys;
sys.path.append(os.getcwd());
from utils.recipe_matcher import calculate_proportion_message as prop;
print(prop('20ml oil', '500ml', 10.99))
print(prop('50g cheese', '250g', 2.99))
print(prop('1.5 kg tomatoes', '500g pack', 1.99))

