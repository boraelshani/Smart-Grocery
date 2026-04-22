import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# Replace the two "mt-auto" nested divs that are weird, and close flex-grow-1 correctly.
pattern = re.compile(
    r'<div class="mt-auto pt-3">\s*<div class="mt-auto">',
    re.DOTALL
)

replacement = r'</div><!-- close flex-grow-1 -->\n\n<div class="mt-auto pt-3">'
text, count = pattern.subn(replacement, text)
print(f"Replaced {count} instances.")

# Check if maybe we also need to close 'card-body' and 'card' and 'col-custom'.
# We have 5 closing divs at the bottom:
#                 </div> <!-- closes d-flex flex-column gap-2 -->
#               </div> <!-- used to be mt-auto inner -->
#             </div> <!-- used to be mt-auto pt-3 -->
#           </div> <!-- card-body -->
#         </div> <!-- card -->
#       </div> <!-- col-custom -->

with open('templates/compare_prices.html', 'w') as f:
    f.write(text)
