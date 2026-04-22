with open("routes/admin/dashboard.py", "r") as f:
    text = f.read()

# Let's ensure recent_reports is populated with cleaned objects just in case.
new_text = text.replace('recent_reports = list(db.community_price_reports.find().sort("created_at", -1).limit(5))', """
    recent_reports = list(db.community_price_reports.find().sort("created_at", -1).limit(5))
    for r in recent_reports:
        # Convert ObjectId & datetime to strings for template rendering just in case.
        if '_id' in r:
            r['_id'] = str(r['_id'])
        if 'created_at' in r:
            r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r['created_at'], 'strftime') else str(r['created_at'])
""")

with open("routes/admin/dashboard.py", "w") as f:
    f.write(new_text)

