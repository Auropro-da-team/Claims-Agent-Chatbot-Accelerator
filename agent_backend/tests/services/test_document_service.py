import pytest
from app.services.document_service import get_text_content_by_id, content_based_policy_filter

# The `mock_storage_client` fixture is injected from conftest.py
def test_get_text_content_by_id_tries_multiple_paths(mock_storage_client):
    """
    GIVEN a chunk ID.
    WHEN `get_text_content_by_id` is called.
    THEN it should attempt to find the file in multiple GCS paths and return the content
         of the first one that exists.
    """
    # ARRANGE: We program our mock GCS client.
    chunk_id = "Aegis_NJ_Renter_Coverage_12345_chunk_0001"
    expected_text = "This is the policy content."
    
    # Simulate that the first path does NOT exist.
    mock_storage_client.bucket.return_value.blob.return_value.exists.side_effect = [False, True]
    # Simulate that the second path DOES exist and contains our text.
    mock_storage_client.bucket.return_value.blob.return_value.download_as_text.return_value = expected_text
    
    # ACT: Call the function.
    result = get_text_content_by_id(chunk_id)
    
    # ASSERT: Check that the correct text was returned.
    assert result == expected_text
    
    # ASSERT: Verify that the `blob` method was called twice, once for each path.
    assert mock_storage_client.bucket.return_value.blob.call_count == 2

def test_get_text_content_by_id_returns_empty_if_not_found(mock_storage_client):
    """
    GIVEN a chunk ID for a file that does not exist.
    WHEN `get_text_content_by_id` is called.
    THEN it should return an empty string after checking all possible paths.
    """
    # ARRANGE: Simulate that NO paths exist.
    mock_storage_client.bucket.return_value.blob.return_value.exists.return_value = False
    
    # ACT
    result = get_text_content_by_id("non_existent_chunk")
    
    # ASSERT
    assert result == ""
    assert mock_storage_client.bucket.return_value.blob.call_count > 0

def test_content_based_policy_filter():
    """
    GIVEN a list of document chunks and a list of policy numbers.
    WHEN `content_based_policy_filter` is called.
    THEN it should return only the chunks that contain one of the policy numbers in their text.
    """
    # ARRANGE
    chunks = [
        {'document_name': 'Doc A', 'text': 'This chunk contains policy number ABC-123.'},
        {'document_name': 'Doc B', 'text': 'This chunk has no policy number.'},
        {'document_name': 'Doc C', 'text': 'Policy XYZ-789 is mentioned here.'},
        {'document_name': 'Doc D', 'text': 'This chunk also has ABC-123.'},
    ]
    policy_numbers = ["ABC-123", "LMN-456"]
    
    # ACT
    result = content_based_policy_filter(chunks, policy_numbers)
    
    # ASSERT
    assert len(result) == 2
    assert result[0]['document_name'] == 'Doc A'
    assert result[1]['document_name'] == 'Doc D'