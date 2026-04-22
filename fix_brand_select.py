with open("templates/admin_products.html", "r") as f:
    text = f.read()

text = text.replace('<select class="form-select border-0 border-start bg-transparent text-muted" name="brand" style="width: auto; max-width: 180px; box-shadow: none;" onchange="this.form.submit()">', '<select class="form-select border-0 border-start bg-transparent text-muted" name="brand" style="width: auto; max-width: 180px; box-shadow: none;">')

with open("templates/admin_products.html", "w") as f:
    f.write(text)
