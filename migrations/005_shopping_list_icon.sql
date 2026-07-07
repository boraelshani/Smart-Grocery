-- Add icon column to shopping_lists (user-selectable list icon)
ALTER TABLE shopping_lists ADD COLUMN IF NOT EXISTS icon TEXT DEFAULT 'basket';
