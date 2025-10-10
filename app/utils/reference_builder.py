import re

def is_document_mentioned_in_answer(doc_name: str, answer: str) -> bool:
    """
    PRECISE matching - only match if document appears in markdown table
    """
    if not doc_name or not answer:
        return False

    # Only match if document name appears in a table row like:
    # | Mountain West Commercial Insurance Policy | ... | ... |
    escaped_name = re.escape(doc_name)
    table_pattern = rf'\|\s*[^|]*{escaped_name}[^|]*\s*\|'

    return bool(re.search(table_pattern, answer, re.IGNORECASE))

# -------------------------
# ENHANCED REFERENCE GENERATOR
# -------------------------
def generate_detailed_references(chunks: list, answer: str) -> tuple:
    """
    FIXED: Only reference documents that ACTUALLY appear in the answer
    """

    if not chunks:
        return [], {}

    # Skip references for questions/clarification requests
    if (answer.endswith('?') or
        any(phrase in answer.lower() for phrase in [
            "could you please", "i need", "provide your", "to check your specific",
            "not specified in the provided documents"
        ])):
        return [], {}

    references = []
    source_mapping = {}
    reference_counter = 1

    # CRITICAL FIX: Only include documents that appear in the answer
    for chunk in chunks:
        doc_name = chunk.get('document_name', 'Unknown Document')
        page = chunk.get('page', 'unknown')

        # Check if this document is actually mentioned in the answer
        if is_document_mentioned_in_answer(doc_name, answer):

            # Check if we already have this document
            existing_ref = None
            for ref in references:
                if doc_name in ref:
                    existing_ref = ref
                    break

            if existing_ref:
                # Update existing reference with additional pages
                if page != 'unknown' and str(page) not in existing_ref:
                    old_ref = existing_ref
                    if "Pages" in old_ref:
                        pages_match = re.search(r'Pages? ([0-9, -]+)', old_ref)
                        if pages_match:
                            current_pages = pages_match.group(1)
                            new_ref = old_ref.replace(current_pages, f"{current_pages}, {page}")
                            references[references.index(old_ref)] = new_ref
                    else:
                        new_ref = old_ref.replace(f"Page {page}", f"Pages {page}")
                        references[references.index(old_ref)] = new_ref
            else:
                # Add new reference
                page_str = f"Page {page}" if page != 'unknown' else "Document Content"
                source_mapping[doc_name] = reference_counter
                references.append(f"[{reference_counter}] {doc_name} : {page_str}")
                reference_counter += 1

    return ["-"] + references if references else [], source_mapping


def add_inline_citations(answer: str, chunks: list, source_mapping: dict) -> str:
    """
    SCALABLE CITATION INSERTION
    Pattern-based matching works regardless of document count
    """
    if not source_mapping:
        return answer

    modified_answer = answer

    for doc_name, ref_num in source_mapping.items():
        # Strategy 1: Table format (most common)
        table_patterns = [
            (rf'(\|\s*)({re.escape(doc_name)})(\s*\|)', rf'\1\2 [{ref_num}]\3'),  # | Doc Name |
            (rf'({re.escape(doc_name)})(\s*\|)', rf'\1 [{ref_num}]\2'),           # Doc Name |
        ]

        citation_added = False
        for pattern, replacement in table_patterns:
            if re.search(pattern, modified_answer, re.IGNORECASE):
                modified_answer = re.sub(pattern, replacement, modified_answer, count=1, flags=re.IGNORECASE)
                citation_added = True
                break

        # Strategy 2: First mention fallback
        if not citation_added:
            first_word = doc_name.split()[0]
            pattern = rf'\b{re.escape(first_word)}\b(?!\s*\[\d+\])'
            replacement = f'{first_word} [{ref_num}]'
            modified_answer = re.sub(pattern, replacement, modified_answer, count=1, flags=re.IGNORECASE)

    return modified_answer