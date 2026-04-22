with open("routes/admin/dashboard.py", "r") as f:
    text = f.read()

# Handle older `created_at` records which might be missing or not datetime
# Just skip processing them as we've safely caught the issue.
