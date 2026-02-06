# Bike World Purchase Order Extraction Prompt

## Document Format Description
This format is a traditional two-column purchase order layout with tab-delimited header sections, followed by a structured line items section with embedded specifications. The document uses clear section headers and consistent field labeling patterns.

## Extraction Instructions

### Document Identification
- **document_type**: Always "purchase_order" (indicated by "# PURCHASE ORDER" header)
- **retailer**: Extract from "FROM:" section - first line after "FROM:" label ("Bike World")
- **po_number**: Extract from "Order #:" label - value after colon ("PO-2024-0005")
- **order_date**: Extract from "Date:" label - full timestamp after colon ("2024-10-31 11:18:29.916722")

### Customer Information
Located in "TO:" section (right column of header):
- **name**: First line after "TO:" label ("Helen Davis")
- **email**: Second line after "TO:" label ("helen.davis@customer.tstdata")
- **address**: Fourth line after "TO:" label ("9467 Valley Rd, Seattle, WA 98194")

### Vendor Information
Located in "FROM:" section (left column of header):
- **name**: First line after "FROM:" label ("Bike World")
- **address**: Second line after "FROM:" label ("456 Oak Ave, Seattle, WA 98101")
- **phone**: Third line after "FROM:" label ("555-3495")

### Line Items
Located under "Items Ordered" section header.

**Structure**: Each item spans exactly 2 lines:
- Line 1: SKU, Product Name, Quantity with price information
- Line 2: Pipe-delimited specifications with unit price

**Line 1 Pattern**: `[SKU]\t[Product Name]\tQty: [number]\t$[total]`
**Line 2 Pattern**: `[Specifications separated by " I "]\t@ $[unit_price]`

For each line item:
- **sku**: First token on Line 1 before first tab (e.g., "AB-EB-002")
- **product_name**: Second token on Line 1 between first and second tabs (e.g., "E-Mountain")
- **description**: Combine product_name with key specifications from Line 2
- **quantity**: Extract number after "Qty: " on Line 1 (e.g., "3")
- **unit_price**: Extract dollar amount after "@ $" on Line 2 (e.g., "1749.99")
- **line_total**: Extract dollar amount at end of Line 1 after "$" (e.g., "5249.97")

**Product Specifications (Line 2):**
Pipe-delimited format: `[spec1] I [spec2] I [spec3]`
Each specification follows pattern: `[attribute]: [value]`

- **colors**: Extract value after "Colors: " (e.g., "gr5432")
- **sizes**: Extract value after "Sizes: " (e.g., "M", "12\"", "S")
- **battery**: Extract value after "Battery: " if present (e.g., "48V 17.5Ah")
- **range**: Extract value after "Range: " if present, append "miles" (e.g., "50 miles")
- **speeds**: Extract value after "Speeds: " if present (e.g., "11")
- **wheel_size**: Same as sizes for wheel-related items
- **weight**: Extract value after "Weight: " if present
- **certification**: Extract value after "Certification: " if present

**Additional Options Mapping:**
- Adjustable_Seat → Custom field
- Wireless → Custom field  
- Travel → Custom field
- Adjustable → Custom field
- Tire_Clearance → Custom field

### Totals
Located after line items section:
- **order_total**: Extract dollar amount after "TOTAL: $" label (e.g., "12844.83")

### Validation Rules
1. SKU must follow pattern "AB-XX-NNN" where XX are letters and NNN are digits
2. Each line item must have exactly 2 lines
3. Quantity × unit_price should equal line_total (within rounding)
4. Sum of all line_totals should equal order_total (within rounding)
5. All monetary values must be positive numbers

## Extraction Algorithm

Step-by-step process for this specific format:

1. **Identify Header Section**: Look for "FROM:" and "TO:" labels in tab-delimited layout
2. **Extract Basic Info**: 
   - Retailer from first line after "FROM:"
   - PO number from line containing "Order #:"
   - Date from line containing "Date:"
   - Customer info from lines after "TO:"
3. **Locate Items Section**: Find "Items Ordered" header
4. **Process Line Items**: 
   - Read pairs of lines (item data + specifications)
   - Parse Line 1 for SKU, name, quantity, total using tab delimiters
   - Parse Line 2 for specifications using " I " delimiter and unit price
   - Split specifications on " I " and parse each as "attribute: value"
5. **Extract Total**: Find line starting with "TOTAL: $"
6. **Validate**: Check SKU patterns, calculate totals, verify structure

## Edge Cases for This Format

1. **Multi-word Product Names**: Product names may contain spaces (e.g., "Balance Bike", "Fitness Pro")
2. **Specification Variations**: Not all items have all specification types (battery, range only for e-bikes)
3. **Color/Size Codes**: Values may be alphanumeric codes (e.g., "gr5432", "bk1798") rather than descriptive names
4. **Unit Specifications**: Sizes may include units (e.g., "12\"", "100mm")
5. **Boolean Specifications**: Some specs are yes/no values (e.g., "Adjustable: yes", "Wireless: yes")
6. **Missing Specifications**: Some items may have fewer specification lines
7. **Decimal Precision**: Prices use standard USD formatting with 2 decimal places

## Template Classification
- **template_type**: "traditional" (based on two-column header layout and structured line items)