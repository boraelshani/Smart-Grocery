# Smart Import AI - Enhanced Features

## Introduction

This specification outlines comprehensive enhancements to the Smart Import AI feature to improve usability, accuracy, and functionality. The improvements include better discount detection, automatic category selection, similar product detection, and a redesigned user interface.

## Glossary

- **Smart Import**: AI-powered feature that extracts product data from store URLs
- **Quantity Discount**: Promotional pricing based on purchasing multiple units (e.g., "ab 24 Stück €0.99")
- **Similar Product**: Products with matching or highly similar names, brands, or barcodes
- **Category Path**: Full hierarchical category structure (e.g., "Food > Dairy > Milk")
- **Duplicate Product**: Exact same product already in the database

## Requirements

### Requirement 1: Enhanced Discount Detection for Billa

**User Story**: As an admin importing Billa products, I want quantity-based discounts to be automatically detected and displayed, so that I can see promotional pricing like "ab 24 Stück €0.99 from €1.59".

#### Acceptance Criteria

1. WHERE the product URL is from Billa AND contains quantity-based discount information (e.g., "ab 24 Stück"), THE system SHALL extract both the regular price and the promotional price
2. WHERE a quantity discount is detected, THE system SHALL populate the "Promo Price" field with the discounted price
3. WHERE a quantity discount is detected, THE system SHALL populate the "Offer Details" field with the full offer description (e.g., "ab 24 Stück €0.99")
4. WHERE both regular and promotional prices are found, THE system SHALL display the discount percentage in the offer details
5. WHERE the offer details field shows only "AKTION" without specifics, THE system SHALL attempt to extract more detailed offer information from the page content

#### Correctness Properties

1. **Property**: Promotional price is always lower than regular price
   - Test: For any product with both prices, `promo_price < base_price`
2. **Property**: Quantity discount patterns are correctly identified
   - Test: Text containing "ab 24 Stück €0.99" extracts promo_price="0.99"
3. **Property**: Offer details are non-empty when promotional pricing exists
   - Test: If `promo_price` is set, `offer_details` must not be empty or just "AKTION"

### Requirement 2: Automatic Category Selection

**User Story**: As an admin importing products, I want the system to automatically select the best matching category with full path, so that I don't have to manually search through categories.

#### Acceptance Criteria

1. WHERE a product is extracted from a store URL, THE system SHALL analyze the product name, description, and store category path
2. WHERE the analysis is complete, THE system SHALL automatically select the most appropriate category from the internal taxonomy
3. WHERE a category is selected, THE system SHALL display the full category path (e.g., "Food > Dairy > Milk > Organic")
4. WHERE the confidence score is below 70%, THE system SHALL highlight the category selection in yellow as "Low Confidence - Please Review"
5. WHERE no suitable category is found, THE system SHALL leave the category unselected and show a warning message

#### Correctness Properties

1. **Property**: Category selection is deterministic for identical inputs
   - Test: Same product name/description always maps to same category
2. **Property**: Selected category exists in the database
   - Test: All auto-selected category IDs must exist in the categories table
3. **Property**: Category path is complete and valid
   - Test: Full path from root to leaf category is displayed

### Requirement 3: Similar Product Detection

**User Story**: As an admin importing products, I want to see if similar or duplicate products already exist in the database, so that I can avoid duplicates and link products from different stores.

#### Acceptance Criteria

1. WHERE a product is extracted, THE system SHALL search for similar products based on name similarity (>80%), brand match, and barcode match
2. WHERE similar products are found, THE system SHALL display them in a "Similar Products Found" section below the form
3. WHERE each similar product is displayed, THE system SHALL show: product name, brand, stores where it's available, last update date, and a similarity score
4. WHERE a similar product is an exact match (100% similarity), THE system SHALL highlight it as "Possible Duplicate" with a red badge
5. WHERE the user clicks "Link to Existing Product", THE system SHALL create an offer for the existing product instead of creating a new product
6. WHERE the user clicks "Update Existing Product", THE system SHALL update the existing product's information with the newly extracted data
7. WHERE the user clicks "Create as New Product", THE system SHALL proceed with creating a new product entry

#### Correctness Properties

1. **Property**: Similarity score is between 0 and 100
   - Test: All similarity scores satisfy `0 <= score <= 100`
2. **Property**: Exact name and brand match results in 100% similarity
   - Test: Products with identical name_de and brand have similarity = 100
3. **Property**: Similar products are sorted by similarity score descending
   - Test: List is ordered from highest to lowest similarity

### Requirement 4: Enhanced UI Design

**User Story**: As an admin using the Smart Import feature, I want a modern, well-organized interface with clear visual hierarchy, so that the import process is intuitive and efficient.

#### Acceptance Criteria

1. WHERE the Smart Import page loads, THE system SHALL display a clean, modern interface with proper spacing and visual hierarchy
2. WHERE action buttons are displayed, THE system SHALL use styled buttons with icons, hover effects, and clear labels
3. WHERE the "Save Product" button is displayed, THE system SHALL use a prominent primary button style (indigo background, white text, with save icon)
4. WHERE the "Start Over" button is displayed, THE system SHALL use a secondary button style (gray background, with back arrow icon)
5. WHERE similar products are found, THE system SHALL display them in an organized card layout with clear visual separation
6. WHERE form fields are displayed, THE system SHALL group related fields together with section headers
7. WHERE the extraction is in progress, THE system SHALL show an animated loading state with progress indicator

#### Correctness Properties

1. **Property**: All buttons have consistent styling
   - Test: Primary buttons use indigo-600, secondary buttons use gray-200
2. **Property**: Form is responsive on all screen sizes
   - Test: Layout adapts correctly on mobile (320px), tablet (768px), and desktop (1024px+)
3. **Property**: Loading states prevent duplicate submissions
   - Test: Submit button is disabled while extraction is in progress

### Requirement 5: Product Update Tracking

**User Story**: As an admin managing products, I want to see when products were last updated and track price changes, so that I can keep product information current.

#### Acceptance Criteria

1. WHERE a similar product is displayed, THE system SHALL show the last update timestamp in a human-readable format (e.g., "Updated 2 days ago")
2. WHERE a product has multiple offers from different stores, THE system SHALL display all stores with their respective prices
3. WHERE the user chooses to update an existing product, THE system SHALL record the update in the product's history
4. WHERE price changes are detected, THE system SHALL highlight the price difference (e.g., "Was €1.99, now €1.79")
5. WHERE the user links a new store offer to an existing product, THE system SHALL create a new offer entry while preserving existing offers

#### Correctness Properties

1. **Property**: Update timestamps are monotonically increasing
   - Test: For any product, `updated_at >= created_at`
2. **Property**: Price history is preserved
   - Test: Old prices remain in price_history table after updates
3. **Property**: Multiple offers per product are supported
   - Test: A product can have offers from multiple stores simultaneously

## Success Criteria

1. Billa quantity discounts are detected with >95% accuracy
2. Category auto-selection has >85% accuracy (correct category or parent category)
3. Similar product detection identifies duplicates with >90% precision
4. UI redesign receives positive feedback from admin users
5. Product update workflow reduces duplicate entries by >70%

## Out of Scope

- Automatic product merging (requires manual review)
- Bulk import of multiple products simultaneously
- AI-powered image recognition for product matching
- Real-time price monitoring and alerts
- Integration with external product databases (e.g., Open Food Facts)
