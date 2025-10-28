import re
import logging
from google.cloud import storage
from config import settings
from app.utils.parsers import extract_document_name

# -------------------------
# INITIALIZATION
# -------------------------
storage_client = storage.Client()

# -------------------------
# FETCH TEXT FROM GCS
# -------------------------
def get_text_content_by_id(chunk_id: str) -> str:
    try:
        # Try both possible paths
        paths = [
            f"extracted/{chunk_id}.txt",
            f"text-chunks/{extract_document_name(chunk_id).replace(' ', '_')}/{chunk_id}.txt"
        ]

        for path in paths:
            blob = storage_client.bucket(settings.BUCKET_NAME).blob(path)
            if blob.exists():
                return blob.download_as_text()
        return ""
    except Exception as e:
        logging.error(f"Error fetching chunk {chunk_id}: {e}")
        return ""

def validate_policy_number_in_corpus(policy_number: str, chunks: list) -> bool:
    """
    CONTENT-BASED VALIDATION: Search through actual document content from GCS
    No longer relies on metadata - searches through document text
    """
    if not policy_number or not chunks:
        return False

    for chunk in chunks:
        text = chunk.get('text', '')
        if text and validate_policy_number_in_document_content(policy_number, text):
            return True

    return False

def content_based_policy_filter(chunks: list, policy_numbers: list) -> list:
    """
    NEW FUNCTION: Filter chunks based on actual document content containing policy numbers
    This is the key function that searches through GCS document content
    """
    if not policy_numbers or not chunks:
        return []

    validated_chunks = []

    for chunk in chunks:
        text = chunk.get('text', '')
        if not text:
            continue

        # Check if this chunk contains any of the policy numbers
        contains_policy = False
        for pnum in policy_numbers:
            if validate_policy_number_in_document_content(pnum, text):
                contains_policy = True
                logging.info(f"✅ Found policy {pnum} in document: {chunk.get('document_name', 'Unknown')}")
                break

        if contains_policy:
            validated_chunks.append(chunk)

    logging.info(f"CONTENT FILTER: {len(validated_chunks)}/{len(chunks)} chunks contain policy numbers")
    return validated_chunks


# =================================================================================
# Making sure it doesn't fail for minor OCR differences
# Normalizes both strings
# before comparing, making the match reliable.
# =================================================================================
# =================================================================================
# =================================================================================
def validate_policy_number_in_document_content(policy_number: str, text: str) -> bool:
    """
    ROBUST FUNCTION: Validates policy number exists in document text content,
    ignoring differences in spacing, dashes, or other separators.
    This is critical for handling OCR inconsistencies.
    """
    # --- SANITY CHECK ---
    logging.info(f"--- RUNNING NEW ROBUST VALIDATION for policy: '{policy_number}' ---")
    # --- END SANITY CHECK ---

    if not policy_number or not text:
        return False

    # Create a "normalized" version by removing all common separators and making it uppercase.
    def _normalize_for_match(s: str) -> str:
        return re.sub(r'[\s_\-\.—–:/]', '', s).upper()

    normalized_policy = _normalize_for_match(policy_number)
    normalized_text = _normalize_for_match(text)

    # Log the normalized strings so we can see exactly what is being compared
    logging.info(f"Comparing normalized policy '{normalized_policy}' with first 300 chars of normalized text.")

    if normalized_policy in normalized_text:
        if normalized_policy.isalpha() and len(normalized_policy) < 10:
            if normalized_text.count(normalized_policy) > 5:
                logging.info(f"Rejecting likely company name '{normalized_policy}' found multiple times.")
                return False
        # If we find a match, log it!
        logging.info(f"✅ SUCCESS: Found '{normalized_policy}' in document chunk.")
        return True

    return False