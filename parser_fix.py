import re

def parse_composition_fixed(formula: str) -> dict:
    """
    Properly parse formulas like 'LaFe11.6Si1.4' or 'Lafe11.6si1.4'
    """
    # First, ensure proper capitalization
    # 'Lafe11.6si1.4' → 'LaFe11.6Si1.4'
    
    # List of known two-letter elements (for pattern matching)
    TWO_LETTER = {
        'la', 'ce', 'pr', 'nd', 'pm', 'sm', 'eu', 'gd', 'tb', 'dy', 'ho',
        'er', 'tm', 'yb', 'lu', 'he', 'li', 'be', 'ne', 'na', 'mg', 'al',
        'si', 'cl', 'ar', 'ca', 'sc', 'ti', 'cr', 'mn', 'fe', 'co', 'ni',
        'cu', 'zn', 'ga', 'ge', 'as', 'se', 'br', 'kr', 'rb', 'sr', 'y',
        'zr', 'nb', 'mo', 'tc', 'ru', 'rh', 'pd', 'ag', 'cd', 'in', 'sn',
        'sb', 'te', 'xe', 'cs', 'ba', 'hf', 'ta', 're', 'os', 'ir', 'pt',
        'au', 'hg', 'tl', 'pb', 'bi', 'po', 'at', 'rn', 'fr', 'ra', 'rf',
        'db', 'sg', 'bh', 'hs', 'mt', 'ds', 'rg', 'cn', 'nh', 'fl', 'mc',
        'lv', 'ts', 'og'
    }
    
    # Step 1: Find all element symbols and numbers
    i = 0
    elements = []
    numbers = []
    current_num = ""
    current_elem = ""
    
    while i < len(formula):
        char = formula[i]
        
        if char.isdigit() or char == '.':
            current_num += char
            i += 1
        else:
            # It's a letter
            if current_num:
                numbers.append(float(current_num))
                current_num = ""
            
            # Check for two-letter element
            if i + 1 < len(formula):
                two_letter = formula[i:i+2].lower()
                if two_letter in TWO_LETTER:
                    elements.append(formula[i:i+2].capitalize())
                    i += 2
                    continue
            
            # Single letter element
            if char.isalpha():
                elements.append(char.upper())
                i += 1
    
    # Add last number if exists
    if current_num:
        numbers.append(float(current_num))
    
    # If no numbers, assume 1 for each
    if not numbers:
        numbers = [1.0] * len(elements)
    
    # If more elements than numbers, append 1s
    while len(numbers) < len(elements):
        numbers.append(1.0)
    
    # Build result
    result = {}
    for elem, num in zip(elements, numbers):
        result[elem] = result.get(elem, 0.0) + num
    
    # Normalize to 100%
    total = sum(result.values())
    if total > 0 and abs(total - 100) > 0.01:
        result = {k: v / total * 100 for k, v in result.items()}
    
    return result

# Test
print("Test 1: 'Lafe11.6si1.4' →", parse_composition_fixed('Lafe11.6si1.4'))
print("Test 2: 'LaFe11.6Si1.4' →", parse_composition_fixed('LaFe11.6Si1.4'))
print("Test 3: 'Fe65Nd30Co5' →", parse_composition_fixed('Fe65Nd30Co5'))
print("Test 4: 'fe65nd30co5' →", parse_composition_fixed('fe65nd30co5'))
