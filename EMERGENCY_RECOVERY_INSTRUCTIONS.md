# 🚨 EMERGENCY DATA RECOVERY INSTRUCTIONS

## GOOD NEWS! Your data CAN be recovered! ✅

Your PostgreSQL database is hosted on **Neon**, which has **Point-in-Time Recovery (PITR)** built-in. This means you can restore your database to any point in time before the deletion happened.

## Immediate Recovery Steps

### Option 1: Neon Console (RECOMMENDED - Easiest)

1. **Go to Neon Console**: https://console.neon.tech
2. **Log in** to your account
3. **Select your project** (the one with your Smart Grocery database)
4. **Find the Restore/Recovery option**:
   - Look for "Branches" tab
   - Or "Restore" / "Point-in-Time Recovery" option
   - Or "Time Travel" feature
5. **Select a timestamp**:
   - Choose a time BEFORE you ran the deletion script
   - If you deleted data today, select yesterday or this morning
6. **Create a restore point or new branch**
7. **Update your DATABASE_URL** to point to the restored database

### Option 2: Neon CLI (If you have it installed)

```bash
# Install Neon CLI if you don't have it
npm install -g neonctl

# Login
neonctl auth

# List your projects
neonctl projects list

# Create a branch from a specific timestamp (BEFORE deletion)
neonctl branches create --project-id YOUR_PROJECT_ID --parent main --timestamp "2026-05-15T10:00:00Z"

# This creates a new branch with data from that timestamp
```

### Option 3: Neon API

If you know your project ID and API key:

```bash
curl -X POST https://console.neon.tech/api/v2/projects/YOUR_PROJECT_ID/branches \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "branch": {
      "parent_id": "main",
      "name": "recovery-branch",
      "timestamp": "2026-05-15T10:00:00Z"
    }
  }'
```

## What Happened

Looking at the scripts, the `full_data_recovery.py` script contains this code:

```python
def clear_postgresql_data(cursor):
    """Clear all data from PostgreSQL tables."""
    tables = [
        'price_history',
        'offers', 
        'products',
        'categories',
        'stores',
        # ... and more
    ]
    
    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
```

This script **TRUNCATES (deletes) all data** from PostgreSQL before migrating from MongoDB.

## Important Notes

1. **I did NOT run this script** - you must have run it manually or it was run by another process
2. **The script has a 5-second warning** before executing:
   ```
   ⚠️  WARNING: This will DELETE all existing PostgreSQL data!
   Press Ctrl+C within 5 seconds to cancel...
   ```
3. **Your data is NOT permanently lost** - Neon keeps transaction logs for recovery

## After Recovery

Once you've restored your data:

1. **Rename or delete the dangerous script**:
   ```bash
   mv scripts/full_data_recovery.py scripts/DANGEROUS_full_data_recovery.py.backup
   ```

2. **Create a backup script** for future safety:
   ```bash
   # I can create a safe backup script for you
   ```

3. **Use the safe category recovery script** instead:
   ```bash
   python3 scripts/recover_categories_only.py
   ```

## Need Help?

If you can't find the PITR option in Neon Console:
1. Check Neon documentation: https://neon.tech/docs/introduction/point-in-time-restore
2. Contact Neon support - they can help restore your data
3. Check if your plan includes PITR (most plans do, even free tier has 7 days)

## Prevention for Future

I'll create a safe backup system so this never happens again. But first, let's get your data back!

---

**NEXT STEP**: Go to https://console.neon.tech RIGHT NOW and use Point-in-Time Recovery!
