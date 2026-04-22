with open('templates/base.html', 'r') as f:
    if 'id="priceReportModal"' in f.read():
        print("Success")
    else:
        print("Failed to add modal")
