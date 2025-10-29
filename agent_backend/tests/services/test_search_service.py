from app.services.search_service import perform_policy_specific_search

def test_perform_policy_specific_search(mocker, mock_embedding_model, mock_index_endpoint):
    """
    GIVEN a list of policy numbers and a query.
    WHEN `perform_policy_specific_search` is called.
    THEN it should generate embeddings, query the vector index, fetch content from GCS,
         and filter the results.
    """
    # ARRANGE
    policy_numbers = ["ABC-123"]
    base_query = "water damage"
    
    # Mock the embedding model to return a fake vector
    mock_embedding_model.get_embeddings.return_value = [MagicMock(values=[0.1, 0.2, 0.3])]
    
    # Mock the vector search response
    mock_neighbor = MagicMock()
    mock_neighbor.id = "doc_A_chunk_1"
    mock_index_endpoint.find_neighbors.return_value = [[mock_neighbor]]
    
    # Mock the GCS call that happens inside the search function
    mock_get_text = mocker.patch('app.services.search_service.get_text_content_by_id')
    mock_get_text.return_value = "This is the text content for doc_A_chunk_1 which contains policy ABC-123."
    
    # ACT
    result = perform_policy_specific_search(policy_numbers, base_query)
    
    # ASSERT
    # Verify the core logic: that a chunk was found and returned.
    assert len(result) == 1
    assert result[0]['id'] == "doc_A_chunk_1"
    
    # Verify that all our mocks were called, proving the orchestration worked.
    mock_embedding_model.get_embeddings.assert_called()
    mock_index_endpoint.find_neighbors.assert_called()
    mock_get_text.assert_called_with("doc_A_chunk_1")