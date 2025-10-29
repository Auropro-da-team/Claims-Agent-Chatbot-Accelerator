import pytest
from app.utils.parsers import (
    extract_policy_identifier_enhanced,
    parse_page_number,
    extract_document_name
)

# === Test Suite for `extract_policy_identifier_enhanced` ===
# We define our test cases as a list of `pytest.param` objects.
# This makes the test highly readable and allows for clear reporting using the `id`.
POLICY_ID_TEST_CASES = [
    pytest.param("My policy is PHI-IL-IND-2025-778899.", ["PHI-IL-IND-2025-778899"], id="Complex 5-Part ID"),
    pytest.param("Please look up SH-2025-445789 for me.", ["SH-2025-445789"], id="Standard 3-Part Year ID"),
    pytest.param("Compare policies ESC-NY-CP-2025-334567 and GS-FL-HO3-445789.", ["ESC-NY-CP-2025-334567", "GS-FL-HO3-445789"], id="Two IDs in one query"),
    pytest.param("The policy is LP985240156.", ["LP985240156"], id="Alphanumeric No Separators"),
    pytest.param("What is covered for water damage?", [], id="Negative Case: No policy ID"),
    pytest.param("Tell me about my LEMONADE policy.", [], id="Negative Case: Company name only"),
    pytest.param("", [], id="Negative Case: Empty query string"),
]

@pytest.mark.parametrize("query, expected", [p.values[0:2] for p in POLICY_ID_TEST_CASES], ids=[p.id for p in POLICY_ID_TEST_CASES])
def test_extract_policy_identifier_enhanced(query, expected):
    """
    GIVEN a user query string.
    WHEN the `extract_policy_identifier_enhanced` function is called.
    THEN it should return a list containing only the correctly formatted policy numbers.
    """
    result = extract_policy_identifier_enhanced(query)
    assert set(result) == set(expected)


# === Test Suite for `parse_page_number` ===
PAGE_NUMBER_TEST_CASES = [
    pytest.param("doc_name_page_12_chunk_001.txt", "Some text", "12", id="Page in chunk_id"),
    pytest.param("doc_name_chunk_005.txt", "Page: 3\nSome text", "3", id="Page in text (overrides chunk)"),
    pytest.param("doc_name_chunk_005.txt", "Some text", "6", id="Fallback to chunk number + 1"),
    pytest.param("doc_name.txt", "Some text", "unknown", id="No page info available"),
]

@pytest.mark.parametrize("chunk_id, text, expected", PAGE_NUMBER_TEST_CASES)
def test_parse_page_number(chunk_id, text, expected):
    """
    GIVEN a chunk ID and its text content.
    WHEN `parse_page_number` is called.
    THEN it should correctly extract the page number based on a hierarchy of patterns.
    """
    result = parse_page_number(chunk_id, text)
    assert result == expected


# === Test Suite for `extract_document_name` ===
DOC_NAME_TEST_CASES = [
    pytest.param("Aegis_NJ_Renter_Coverage_1634567890_chunk_0001", "Aegis NJ Renter Coverage", id="Standard chunk ID"),
    pytest.param("Simple-Document-Name_1634567890_chunk_0002", "Simple Document Name", id="Hyphens in name"),
]

@pytest.mark.parametrize("chunk_id, expected", DOC_NAME_TEST_CASES)
def test_extract_document_name(chunk_id, expected):
    """
    GIVEN a complex chunk ID.
    WHEN `extract_document_name` is called.
    THEN it should return the clean, human-readable document name.
    """
    result = extract_document_name(chunk_id)
    assert result == expected