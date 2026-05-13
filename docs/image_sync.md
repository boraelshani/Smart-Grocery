# Automated Image Sync and Archiving System

## Purpose
This system handles the reliable extraction, downloading, and local saving of product images from external store URLs, specifically focused on Billa integrations. It ensures products loaded from our catalog contain high-quality, locally-served images (`/static/products/images/prod_{id}.{ext}`). 

A core secondary function of this script is maintaining database hygiene. If an existing `product_url` is no longer available on the target store (e.g., returns a `404 Not Found`), the script safely archives the associated offers.

## Safety Features
- **Database Integrity**: The script strictly utilizes `is_available = False` for 404 cases. It does not perform hard deletions on any records to preserve historically linked data and prevent foreign key cascading errors.
- **Transactional Row-by-Row Operations**: Execution commits per product. If an individual image fails to download or save, its specific transaction is rolled back independently without corrupting the broader batch.
- **Corrupted File Prevention**: Failed or incomplete image downloads are automatically deleted from the filesystem locally before moving on.
- **Redundancy Skipping**: Checks the filesystem (`glob` pattern matching) beforehand. If a product already possesses a valid image locally, the network request is skipped to conserve bandwidth and time.
- **Rate Limiting**: Incorporates polite thread-sleeping (`time.sleep(1)`) to avoid anti-bot flagging or IP blacklisting by the origin servers.
- **Search Fallback Immunity**: Excludes URL strings containing `search?q=` to prevent parsing invalid list pages.

## Rollback Mechanism
Before running the main image execution process, manual database snapshots are created via `scripts/backup_and_rollback.py`.
It drops and recreates `products_backup` and `offers_backup` mirrors to capture the exact database state before any alterations.

If a catastrophic failure occurs, you can run:
```bash
$env:PYTHONPATH="."; .\venv\Scripts\python.exe scripts/backup_and_rollback.py --rollback
```
This safely truncates the active primary tables and re-inserts the data from the backups seamlessly.

## Verification Queries

To assert the validity of the process after execution, you can use the following queries:

**Check successfully downloaded images:**
```sql
SELECT id, name_de, default_image_url 
FROM products 
WHERE default_image_url LIKE '/static/products/images/%';
```

**Check successfully archived 404 offers:**
```sql
SELECT p.id, p.name_de, o.product_url, o.is_available 
FROM offers o
JOIN products p ON o.product_id = p.id
WHERE o.is_available = False;
```

**Monitor execution logs:**
The system provides verbose details during execution:
```bash
tail -n 50 image_download.log
```

## What To Do When It Finishes
1. **Review the Log Footer**: Open `image_download.log` and verify the final line showing `Completed! Successes: X, Failures: Y`. 
2. **Run the Verification Queries**: Ensure the database accurately reflects the new `default_image_url` paths and deactivated offers.
3. **Verify Frontend Display**: Boot up the Flask app (`python app.py`) and browse the product catalog on the UI to ensure the images render locally with no 404 errors.
4. **Cleanup Options**: If everything looks perfect, the `images/` folder is populated, and the database is healthy, you can optionally drop the backup tables (`products_backup`, `offers_backup`) to free up database storage.

## Troubleshooting

| **Issue** | **Likely Cause** | **Solution** |
| :--- | :--- | :--- |
| **Consistent `Read timed out` Errors** | Origin server is rate-limiting your IP address or throttling requests. | Edit `time.sleep(1)` to `time.sleep(2)` or `3` inside the loop to delay requests. |
| **All requests return `404 Not Found`** | Truncated/Changed URL formatting by the vendor, or bad seed data. | Run the verification query for archived 404 offers to debug if the URL scheme fundamentally changed. |
| **Images not loading on UI** | Missing Flask static path mapping or corrupted download. | Verify the image files physically exist in `static/products/images/`. Clear browser cache. |
| **Out of Space / Disk Errors** | Too many large images clogging local storage. | Compress the image outputs (e.g., using Pillow in Python) during the saving process, or check server disk space. |