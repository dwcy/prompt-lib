---
name: xlsx
description: Use this skill any time a spreadsheet file is the primary input or output — reading, writing, editing, fixing, or converting .xlsx, .xlsm, .csv, or .tsv files.
allowed-tools: Bash, Read, Write, Edit
---

Use this skill any time a spreadsheet file is the primary input or output. This includes:
- Opening, reading, editing, or fixing existing .xlsx, .xlsm, .csv, or .tsv files
- Creating new spreadsheets from scratch or from other data sources
- Converting between tabular file formats
- Cleaning or restructuring messy tabular data into proper spreadsheets

---

## Requirements for Outputs

### All Excel Files

**Professional Font**
- Use consistent, professional fonts (Arial, Times New Roman) unless instructed otherwise

**Zero Formula Errors**
- Deliver with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

**Preserve Existing Templates**
- Match existing format, style, and conventions exactly when modifying files
- Never impose standardized formatting on established patterns

### Financial Models

**Color Coding Standards** (Industry Standard):
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs and scenario-change numbers
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Links from other worksheets in same workbook
- **Red text (RGB: 255,0,0)**: External links to other files
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention

**Number Formatting Standards**:
- **Years**: Format as text strings ("2024" not "2,024")
- **Currency**: Use $#,##0 format; specify units in headers ("Revenue ($mm)")
- **Zeros**: Format all zeros as "-" including percentages
- **Percentages**: Default to 0.0% format (one decimal)
- **Multiples**: Format as 0.0x (e.g., EV/EBITDA)
- **Negative numbers**: Use parentheses (123) not minus -123

**Formula Construction Rules**:
- Place ALL assumptions in separate assumption cells
- Use cell references instead of hardcoded values
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- Ensure consistent formulas across projection periods
- Document hardcodes with source information: "Source: [System/Document], [Date], [Specific Reference], [URL if applicable]"

---

## XLSX Creation, Editing, and Analysis

### Important Requirements

**LibreOffice Required for Formula Recalculation**: LibreOffice is available for recalculating formula values using the `scripts/recalc.py` script located at `C:\Users\Dawid\.claude\skills\xlsx\scripts\recalc.py`.

### Data Analysis with Pandas

```python
import pandas as pd

# Read Excel
df = pd.read_excel('file.xlsx')  # Default: first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

# Analyze
df.head()      # Preview data
df.info()      # Column info
df.describe()  # Statistics

# Write Excel
df.to_excel('output.xlsx', index=False)
```

### CRITICAL: Use Formulas, Not Hardcoded Values

**Always use Excel formulas instead of calculating values in Python and hardcoding them.**

❌ WRONG:
```python
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000
```

✅ CORRECT:
```python
sheet['B10'] = '=SUM(B2:B9)'
```

### Creating New Excel Files

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Add data
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# Add formula
sheet['B2'] = '=SUM(A1:A10)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# Column width
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### Editing Existing Excel Files

```python
from openpyxl import load_workbook

# Load existing file
wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

# Working with multiple sheets
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# Modify cells
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # Insert row at position 2
sheet.delete_cols(3)  # Delete column 3

# Add new sheet
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

### Recalculating Formulas

```bash
python "C:\Users\Dawid\.claude\skills\xlsx\scripts\recalc.py" <excel_file> [timeout_seconds]
```

Example:
```bash
python "C:\Users\Dawid\.claude\skills\xlsx\scripts\recalc.py" output.xlsx 30
```

The script:
- Automatically sets up LibreOffice macro on first run
- Recalculates all formulas in all sheets
- Scans ALL cells for Excel errors
- Returns JSON with detailed error locations and counts

### Formula Verification Checklist

**Essential Verification**:
- Test 2-3 sample references
- Confirm Excel columns match
- Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)

**Common Pitfalls**:
- NaN handling: Check for null values with `pd.notna()`
- Far-right columns: FY data often in columns 50+
- Multiple matches: Search all occurrences
- Division by zero: Check denominators before using `/`
- Wrong references: Verify all cell references point to intended cells
- Cross-sheet references: Use correct format (Sheet1!A1)

### Interpreting scripts/recalc.py Output

```json
{
  "status": "success",           // or "errors_found"
  "total_errors": 0,              // Total error count
  "total_formulas": 42,           // Number of formulas in file
  "error_summary": {              // Only present if errors found
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

---

## Best Practices

**Library Selection**:
- **pandas**: Best for data analysis, bulk operations, and simple data export
- **openpyxl**: Best for complex formatting, formulas, and Excel-specific features

**Working with openpyxl**:
- Cell indices are 1-based (row=1, column=1 refers to cell A1)
- Use `data_only=True` to read calculated values
- Warning: Saving with `data_only=True` replaces formulas with values permanently
- For large files: Use `read_only=True` for reading or `write_only=True` for writing

**Working with pandas**:
- Specify data types: `pd.read_excel('file.xlsx', dtype={'id': str})`
- Read specific columns: `pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- Handle dates properly: `pd.read_excel('file.xlsx', parse_dates=['date_column'])`

**Code Style Guidelines**:
- Write minimal, concise Python code without unnecessary comments
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements
- Add comments to cells with complex formulas or important assumptions
- Document data sources for hardcoded values
