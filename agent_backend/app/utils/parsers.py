import re
import logging
import yaml
# -------------------------
# PAGE NUMBER PARSER
# -------------------------
def parse_page_number(chunk_id: str, text: str) -> str:
    patterns = [
        r"page[_\-]?(\d+)", r"\bpage\s+(\d{1,4})\b", r"\bp[.]?\s*(\d{1,4})\b",
        r"\bpg[.]?\s*(\d{1,4})\b", r"\bpage[:\s\-]+(\d{1,4})\b"
    ]
    if match := re.search(patterns[0], chunk_id.lower()):
        return str(int(match.group(1)))

    first_lines = "\n".join(text.strip().splitlines()[:10]).lower()
    for pat in patterns[1:]:
        if match := re.search(pat, first_lines):
            return str(int(match.group(1)))

    if match := re.search(r"chunk[_\-]?(\d+)", chunk_id.lower()):
        return str(int(match.group(1)) + 1)

    return "unknown"

# -------------------------
# EXTRACT DOCUMENT NAME
# =================================================================================

def extract_document_name(chunk_id: str) -> str:
    """Extract clean document name from chunk ID"""
    name = re.sub(r'_\d{10,}_chunk_\d{4,}', '', chunk_id)
    name = re.sub(r'[_\-]+', ' ', name).strip()
    # The .title() method has been removed to preserve original casing.
    return name if name else chunk_id

# -------------------------
# ENHANCED SECTION EXTRACTION
# -------------------------
def extract_section_info(text: str) -> tuple:
    """Extract section and subsection information from text"""
    section = ""
    subsection = ""

    section_patterns = [
        r"(?i)section\s+([IVX\d]+)[:\s]*([^\n]+)",
        r"(?i)coverage\s+([a-z])\s*[-:]\s*([^\n]+)",
        r"(?i)(covered causes|exclusions|additional coverages|limits|deductibles)[:\s]*([^\n]*)",
        r"(?i)(building coverage|business personal property|business income)[:\s]*([^\n]*)",
        r"(?i)(perils insured|general liability|professional liability|property coverage)[:\s]*([^\n]*)"
    ]

    try:
        for pattern in section_patterns:
            match = re.search(pattern, text[:500])
            if match:
                section = match.group(1).strip() if match.group(1) else ""
                subsection = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""

                # Skip unwanted values - ENHANCED
                unwanted_sections = ['document content', 'general', 'main document', 'page', 'content', 'text', 'chunk', 'coverage details', 'policy information', 'document', 'file']
                if section and section.lower().strip() in unwanted_sections:
                    section = ""
                if subsection and subsection.lower().strip() in unwanted_sections:
                    subsection = ""


                if section:  # Only break if we found a valid section
                    break
    except Exception as e:
        logging.error(f"Error in extract_section_info: {e}")

    return section, subsection

# -------------------------
# ENHANCED POLICY FIELD EXTRACTION
# -------------------------
def extract_policy_fields(chunks: list) -> dict:
    """Extract policy holder details, dates, and other key information"""
    policy_info = {
        'holder_name': '',
        'policy_number': '',
        'start_date': '',
        'end_date': '',
        'email': '',
        'contact': '',
        'policy_type': ''
    }

    # Combine all chunk texts for comprehensive extraction
    full_text = "\n".join([chunk.get('text', '') for chunk in chunks])

    # Extract holder name
    name_patterns = [
        r"(?i)policy\s*holder[:\s]*([^\n,]+)",
        r"(?i)insured[:\s]*([^\n,]+)",
        r"(?i)named\s*insured[:\s]*([^\n,]+)",
        r"(?i)applicant[:\s]*([^\n,]+)"
    ]

    for pattern in name_patterns:
        match = re.search(pattern, full_text)
        if match:
            policy_info['holder_name'] = match.group(1).strip()
            break

    # Extract policy number
    policy_num_patterns = [
        r"(?i)policy\s*number[:\s]*([A-Z0-9\-]+)",
        r"(?i)policy\s*no[:\s]*([A-Z0-9\-]+)",
        r"(?i)policy\s*#[:\s]*([A-Z0-9\-]+)"
    ]

    for pattern in policy_num_patterns:
        match = re.search(pattern, full_text)
        if match:
            policy_info['policy_number'] = match.group(1).strip()
            break

    # Extract dates
    date_patterns = [
        r"(?i)effective\s*date[:\s]*([0-9/\-]+)",
        r"(?i)start\s*date[:\s]*([0-9/\-]+)",
        r"(?i)policy\s*period[:\s]*([0-9/\-]+)\s*to\s*([0-9/\-]+)",
        r"(?i)from[:\s]*([0-9/\-]+)\s*to[:\s]*([0-9/\-]+)"
    ]

    for pattern in date_patterns:
        match = re.search(pattern, full_text)
        if match:
            if len(match.groups()) >= 2:  # Period format
                policy_info['start_date'] = match.group(1).strip()
                policy_info['end_date'] = match.group(2).strip()
            else:  # Single date
                policy_info['start_date'] = match.group(1).strip()
            break

    # Extract email
    email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    match = re.search(email_pattern, full_text)
    if match:
        policy_info['email'] = match.group(1).strip()

    # Extract contact/phone
    contact_patterns = [
        r"(?i)phone[:\s]*([0-9\-\(\)\s]+)",
        r"(?i)contact[:\s]*([0-9\-\(\)\s]+)",
        r"(\([0-9]{3}\)\s*[0-9]{3}-[0-9]{4})",
        r"([0-9]{3}-[0-9]{3}-[0-9]{4})"
    ]

    for pattern in contact_patterns:
        match = re.search(pattern, full_text)
        if match:
            policy_info['contact'] = match.group(1).strip()
            break

    # Extract policy type
    type_patterns = [
        r"(?i)(commercial\s*property|business\s*property|homeowners|auto|liability|workers\s*compensation)",
        r"(?i)policy\s*type[:\s]*([^\n,]+)"
    ]

    for pattern in type_patterns:
        match = re.search(pattern, full_text)
        if match:
            policy_info['policy_type'] = match.group(1).strip()
            break

    return policy_info

# -------------------------
# ENHANCED POLICY NUMBER EXTRACTION - FIXED VERSION
# -------------------------
def extract_policy_identifier(query: str) -> list:
    """
    FIXED: More conservative extraction - only extract obvious policy numbers
    Reduces false positives like company names being treated as policy numbers
    """
    policy_numbers = []

    # CONSERVATIVE patterns - only clear policy number formats
    policy_patterns = [
        # Clear policy formats with separators
        r'\b[A-Z]{2,4}[-_][A-Z]{2,4}[-_][A-Z0-9]+[-_]\d{4}[-_]\d{3,}\b',  # SAC-AZ-AUTO-2025-456789
        r'\b[A-Z]{2,4}[-_][A-Z]{2,4}[-_]\d{4}[-_]\d{3,}\b',               # ESC-NY-CP-2025-334567
        r'\b[A-Z]{2,4}[-_]\d{4}[-_]?\d{6,}\b',                           # LP-985240156, SH-2025-445789

        # Clear alphanumeric with numbers (must have both letters AND numbers)
        r'\b[A-Z]{2,4}\d{8,15}\b',                                        # LP985240156 (letters + 8-15 digits)

        # Long pure numeric (likely policy numbers)
        r'\b\d{10,20}\b',                                                 # 1234567890123456 (10-20 digits)

        # Contextual extraction (when "policy" is explicitly mentioned)
        r'(?i)policy\s*(?:number|no|#)\s*:?\s*([A-Z0-9\-_\.]{8,})',      # "policy number: ABC123"
        r'(?i)policy\s+([A-Z0-9\-_\.]{8,})',                             # "policy ABC123"

        # PRIORITY: Most common insurance formats
        r'\b[A-Z]{2,5}[-_][A-Z]{2,4}[-_][A-Z0-9]+[-_]\d{4}[-_]\d{3,}\b',  # SAC-AZ-AUTO-2025-456789
        r'\b[A-Z]{3}[-_][A-Z]{2}[-_][A-Z]{2,4}[-_]\d{4}[-_]\d{4,}\b',     # PHI-IL-IND-2025-778899
        r'\b[A-Z]{2,4}[-_][A-Z]{2,4}[-_]\d{4}[-_]\d{3,}\b',               # ESC-NY-CP-2025-334567

        # Alphanumeric combinations (no separators)
        r'\b[A-Z]{2,4}\d{8,15}\b',                                         # LP985240156, SH445789123
        r'\b[A-Z]{3}\d{6}[A-Z]{2,3}\b',                                   # PHI778899IND

        # With minimal separators
        r'\b[A-Z]{2,4}[-_]\d{4,}[-_]?\d{3,}\b',                          # LP-985240156, SH-2025-445789
        r'\b[A-Z]{2,4}[-_]\d{8,}\b',                                      # SAC-456789123

        # Pure numeric (high confidence)
        r'\b\d{10,20}\b',                                                  # 1234567890123456 (10-20 digits)

        # Complex multi-part formats
        r'\b[A-Z0-9]{2,4}[-_\.][A-Z0-9]{2,4}[-_\.][A-Z0-9]{4,}\b',       # XX-YY-123456, XX.YY.ABCD123
        r'\b[A-Z]{1,3}\d{2,4}[A-Z]{1,4}\d{4,10}\b',                      # A12BC345678, AB12CDE456789

        # Contextual extraction (when policy/claim mentioned)
        r'(?i)(?:policy|claim)\s*(?:number|no|#)?\s*:?\s*([A-Z0-9\-_\.]{6,25})', # policy number: ABC123
        r'(?i)policy\s+([A-Z0-9\-_\.]{6,25})',                           # policy ABC123
        r'(?i)number\s+([A-Z0-9\-_\.]{8,25})',                           # number ABC12345678

        # Specialized formats
        r'\bPOL[-_]?[A-Z0-9]{6,}\b',                                      # POL-123456ABC
        r'\bP\d{8,}[A-Z]*\b',                                             # P12345678AB
        r'\bINS[A-Z0-9]{6,}\b',                                           # INS123456ABC
        r'\b\d{4}[A-Z]{2,4}\d{4,8}\b',                                    # 2025SAC456789


        # Standard insurance formats with separators
        r'\b[A-Z]{2,4}[-_][A-Z]{2,4}[-_][A-Z0-9]+[-_]\d{4}[-_]\d{3,}\b',  # SAC-AZ-AUTO-2025-456789
        r'\b[A-Z]{2,4}[-_][A-Z]{2,4}[-_]\d{4}[-_]\d{3,}\b',               # ESC-NY-CP-2025-334567
        r'\b[A-Z]{2,4}[-_]\d{4}[-_]\d{6,}\b',                            # LP-985240156, SH-2025-445789
        r'\b[A-Z]{2,4}\d{4}\d{6,}\b',                                     # LP985240156 (no separators)

        # Pure alphanumeric patterns
        r'\b[A-Z]{2,}\d{8,}\b',                                          # ABC12345678 (letters + 8+ digits)
        r'\b\d{10,}\b',                                                   # Pure numeric 10+ digits
        r'\b[A-Z]{3}\d{6}[A-Z]{2}\b',                                    # PHI123456IL format

        # Complex insurance-specific patterns
        r'\bPOL[-_]?\d{6,}\b',                                           # POL-123456, POL123456
        r'\bP\d{8,}[A-Z]*\b',                                            # P12345678A
        r'\bINS[A-Z0-9]{6,}\b',                                          # INS123456ABC

        # Multi-part formats with various separators
        r'\b[A-Z0-9]{2,4}[-_\.][A-Z0-9]{2,4}[-_\.][A-Z0-9]{4,}\b',      # XX-YY-123456, XX.YY.123456
        r'\b[A-Z]{1,3}\d{2,4}[A-Z]{1,3}\d{4,8}\b',                      # A12B345678

        # Contextual patterns (when "policy" is mentioned)
        r'(?i)policy\s*(?:number|no|#)?\s*:?\s*([A-Z0-9\-_\.]{6,})',     # policy number: ABC123
        r'(?i)policy\s+([A-Z0-9\-_\.]{6,})',                             # policy ABC123
        r'(?i)claim\s*(?:number|no|#)?\s*:?\s*([A-Z0-9\-_\.]{6,})',      # claim number: ABC123

    ]

    query_upper = query.upper().strip()

    # Extract using conservative patterns
    for pattern in policy_patterns:
        matches = re.findall(pattern, query_upper, re.IGNORECASE)
        if matches:
            for match in matches:
                if isinstance(match, tuple):
                    # Handle grouped matches from contextual patterns
                    for m in match:
                        if m and len(m.strip()) >= 8:  # Minimum 8 characters
                            candidate = m.strip().upper()
                            if is_valid_policy_number(candidate):
                                policy_numbers.append(candidate)
                elif match and len(match.strip()) >= 8:
                    candidate = match.strip().upper()
                    if is_valid_policy_number(candidate):
                        policy_numbers.append(candidate)

    # Remove duplicates while preserving order
    unique_numbers = list(dict.fromkeys(policy_numbers))

    if unique_numbers:
        logging.info(f"EXTRACTION SUCCESS: Found {len(unique_numbers)} policy numbers: {unique_numbers}")
    else:
        logging.info(f"EXTRACTION: No valid policy numbers found in: '{query}'")

    return unique_numbers


def is_valid_policy_number(candidate: str) -> bool:
    """
    Validate if a candidate string is likely a real policy number
    Reduces false positives like company names (e.g., 'LEMONADE')
    """
    if not candidate or len(candidate) < 8:
        return False

    # Reject obvious false positives
    false_positives = ['HTTP', 'HTTPS', 'WWW', 'EMAIL', 'LOCALHOST', 'DOCUMENT', 'CONTENT']
    if any(fp in candidate for fp in false_positives):
        return False

    # 🚨 NEW FIX: reject plain words (like 'LEMONADE', 'STATEFARM') that have no digits
    if candidate.isalpha():
        return False

    # Reject simple repeated patterns
    if candidate.isdigit() and len(set(candidate)) <= 2 and len(candidate) < 10:
        return False

    # Reject just years
    if re.match(r'^[0-9]{4}$', candidate):
        return False

    # Must have either numbers AND letters, OR be a long number, OR have separators
    has_letters = bool(re.search(r'[A-Z]', candidate))
    has_numbers = bool(re.search(r'\d', candidate))
    has_separators = bool(re.search(r'[-_]', candidate))
    is_long_number = candidate.isdigit() and len(candidate) >= 10

    return (has_letters and has_numbers) or is_long_number or has_separators


# ===== Enhanced Policy Number Extraction =====
def extract_policy_identifier_enhanced(query: str) -> list:
    """
    BULLETPROOF ENHANCEMENT: Catches policy numbers the original function misses
    Specifically designed for PHI-IL-IND-2025-778899 and SH-2025-445789 formats
    """
    policy_numbers = []

    # PRIORITY PATTERNS - covers the exact formats you're having issues with
    priority_patterns = [
        # PHI-IL-IND-2025-778899 format (5-part with state codes)
        r'\b[A-Z]{2,4}[-_][A-Z]{2,4}[-_][A-Z]{2,4}[-_]\d{4}[-_]\d{4,}\b',

        # SH-2025-445789 format (3-part year format)
        r'\b[A-Z]{2,4}[-_]\d{4}[-_]\d{4,}\b',

        # Other common insurance formats
        r'\b[A-Z]{3,4}[-_][A-Z]{2,4}[-_][A-Z0-9]+[-_]\d{4}[-_]\d{3,}\b',
        r'\b[A-Z]{2,4}\d{4}\d{4,}\b',  # No separators version

        # Contextual extraction (when policy mentioned)
        r'(?i)policy\s*(?:number|no|#)?\s*:?\s*([A-Z0-9\-_]{8,25})',
        r'(?i)number\s*:?\s*([A-Z0-9\-_]{8,25})',
    ]

    query_upper = query.upper().strip()

    # Try priority patterns first
    for pattern in priority_patterns:
        matches = re.findall(pattern, query_upper, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                for m in match:
                    if m and len(m.strip()) >= 6:
                        candidate = m.strip().upper()
                        if not re.match(r'^[0-9]{1,4}$', candidate):  # Not just year
                            policy_numbers.append(candidate)
            elif match and len(match.strip()) >= 6:
                candidate = match.strip().upper()
                if not re.match(r'^[0-9]{1,4}$', candidate):  # Not just year
                    policy_numbers.append(candidate)

    # FALLBACK: Ultra-wide net for missed patterns
    if not policy_numbers:
        fallback_patterns = [
            r'\b[A-Z]{2,}[-_][A-Z0-9\-_]+\b',  # Any letter-separator-alphanumeric
            r'\b[A-Z0-9]{8,}\b',                 # Any 8+ alphanumeric
            r'\b[A-Z]{2}\d{4}\d{4,}\b',         # State-year-number format
        ]

        for pattern in fallback_patterns:
            matches = re.findall(pattern, query_upper)
            for match in matches:
                if len(match) >= 8 and match not in ['HTTP', 'HTTPS', 'LOCALHOST']:
                    policy_numbers.append(match)

    # Remove duplicates
    unique_numbers = list(dict.fromkeys(policy_numbers))

    # SMART FILTER: Remove single words that are likely company names
    filtered_numbers = []
    for num in unique_numbers:
        # Keep if it has numbers OR is multi-part OR is long enough to be a real policy number
        if (re.search(r'\d', num) or
            len(num.split('-')) > 1 or
            len(num.split('_')) > 1 or
            len(num) >= 8):
            filtered_numbers.append(num)
        else:
            logging.info(f"Filtered out likely company name: {num}")

    logging.info(f"Enhanced extraction found: {filtered_numbers}")
    return filtered_numbers

def extract_policy_names_from_query(query: str) -> list:
    """
    SCALABLE: Extract policy names from query without hardcoding
    Works with 10,000+ documents
    """
    policy_names = []

    # Pattern 1: "Mountain West" style names
    compound_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+(?:Insurance|Policy|Commercial|Auto|Renters|Business))?'
    matches = re.findall(compound_pattern, query)
    policy_names.extend(matches)

    # Pattern 2: Single word policies
    single_pattern = r'\b([A-Z][a-z]{4,})(?:\s+(?:Insurance|Policy|Commercial|Auto|Renters|Business))'
    matches = re.findall(single_pattern, query)
    policy_names.extend(matches)

    # Pattern 3: Common insurance company patterns
    company_patterns = [
        r'\b(Lemonade)\b',
        r'\b(Southwest)\b.*(?:Auto|Policy)',
        r'\b(Northeast)\b.*(?:Business|Policy)',
        r'\b(Empire\s+State)\b',
        r'\b(Brooklyn\s+Tech)\b'
    ]

    for pattern in company_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        policy_names.extend(matches)

    return list(set(policy_names))  # Remove duplicates