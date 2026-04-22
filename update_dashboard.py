with open("routes/admin/dashboard.py", "r") as f:
    text = f.read()

# I will add `reports` to `collections`, `stats` and `recent_reports`.
import re
new_text = text.replace('collections = ["stores", "brands", "categories", "products", "users", "feedback"]', 'collections = ["stores", "brands", "categories", "products", "users", "feedback", "community_price_reports"]')
new_text = new_text.replace('"pending_feedback": db.feedback.count_documents({"resolved": {"$ne": True}}),', '"pending_feedback": db.feedback.count_documents({"resolved": {"$ne": True}}),\n        "total_reports": counts.get("community_price_reports", 0),')
new_text = new_text.replace('recent_feedback = list(db.feedback.find().sort("timestamp", -1).limit(5))', 'recent_feedback = list(db.feedback.find().sort("timestamp", -1).limit(5))\n    recent_reports = list(db.community_price_reports.find().sort("created_at", -1).limit(5))')
new_text = new_text.replace('return {"stats": stats, "recent_feedback": recent_feedback, "counts": counts}', 'return {"stats": stats, "recent_feedback": recent_feedback, "recent_reports": recent_reports, "counts": counts}')

with open("routes/admin/dashboard.py", "w") as f:
    f.write(new_text)
