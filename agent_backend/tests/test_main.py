import json

# The `client` and `mock_llm_model` fixtures are automatically injected from conftest.py

def test_greeting_journey(client, mock_llm_model):
    """
    GIVEN a user sends a simple greeting.
    WHEN they post to the `/local_test` endpoint.
    THEN the system should provide a standard greeting response WITHOUT calling any LLMs.
    """
    # ACT
    response = client.post(
        '/local_test',
        data=json.dumps({'query': 'hello', 'session_id': 'greeting_test_01'}),
        content_type='application/json'
    )
    
    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert "Hello!" in response_data['answer']
    assert response_data['query_type'] == 'greeting'
    mock_llm_model.assert_not_called()

def test_fnol_journey_requires_policy_number(client, mock_llm_model):
    """
    GIVEN a user starts a claim journey.
    WHEN they post their initial claim report.
    THEN the system should identify the 'fnol' intent and respond by asking for a policy number.
    """
    # ARRANGE
    user_query = "I was in a car accident."
    expected_bot_response = "I am sorry to hear about the accident. What is your policy number?"
    mock_llm_model.generate_content.return_value.text = expected_bot_response
    
    # ACT
    response = client.post(
        '/local_test',
        data=json.dumps({'query': user_query, 'session_id': 'integration_test_01'}),
        content_type='application/json'
    )
    
    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['answer'] == expected_bot_response
    assert response_data['query_type'] == 'policy_required'
    mock_llm_model.generate_content.assert_called_once()

# ADD THIS TEST TO THE END of test_main.py

def test_full_query_journey_happy_path(client, mocker, mock_llm_model, mock_embedding_model, mock_index_endpoint, mock_storage_client):
    """
    INTEGRATION TEST (HAPPY PATH)
    GIVEN a user asks a question with a valid policy number.
    WHEN they post to the `/local_test` endpoint.
    THEN the system should perform a full pipeline execution:
      1. Analyze intent (regex).
      2. Extract policy number.
      3. Perform a (mocked) vector search.
      4. Fetch (mocked) document content.
      5. Build a context.
      6. Call the LLM (mocked) to generate a final answer.
      7. Return a complete and correct JSON response.
    """
    # ARRANGE
    user_query = "What is the personal property limit for policy AEG-NJ-2025-338921?"
    session_id = "happy_path_01"
    
    # --- Mock the entire external dependency chain ---
    # 1. Mock Vector Search to return a chunk ID
    mock_neighbor = MagicMock()
    mock_neighbor.id = "Aegis_Policy_chunk_001"
    mock_index_endpoint.find_neighbors.return_value = [[mock_neighbor]]
    
    # 2. Mock GCS to return the content for that chunk ID
    mock_storage_client.bucket.return_value.blob.return_value.exists.return_value = True
    mock_storage_client.bucket.return_value.blob.return_value.download_as_text.return_value = "Your Personal Property limit is $35,000."
    
    # 3. Mock the final LLM call to generate the answer
    expected_final_answer = "Based on your policy, the Personal Property limit is $35,000."
    # We configure the mock to respond only when the final, complex prompt is received.
    # The `side_effect` allows us to have different return values for different calls.
    mock_llm_model.generate_content.side_effect = [
        # The first call might be for relevance, etc. We ignore it.
        MagicMock(text="YES"), 
        # The second call is the one we care about, the final answer generation.
        MagicMock(text=expected_final_answer)
    ]

    # ACT
    response = client.post(
        '/local_test',
        data=json.dumps({'query': user_query, 'session_id': session_id}),
        content_type='application/json'
    )
    
    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['answer'] == expected_final_answer
    assert response_data['query_type'] == 'policy_info'
    
    # Assert that our key dependencies were called
    mock_index_endpoint.find_neighbors.assert_called_once()
    mock_storage_client.bucket.return_value.blob.return_value.download_as_text.assert_called_once()
    # Assert that the LLM was called (at least once for the final answer)
    assert mock_llm_model.generate_content.call_count > 0

