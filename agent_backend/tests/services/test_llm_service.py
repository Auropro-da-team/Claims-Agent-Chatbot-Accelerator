from app.services.llm_service import create_contextual_query

def test_create_contextual_query_rewrites_short_query(mock_llm_model):
    """
    GIVEN a short, ambiguous query and conversation history.
    WHEN `create_contextual_query` is called.
    THEN it should call the LLM to rewrite the query.
    """
    # ARRANGE
    query = "what about for a crash?"
    context = "User previously asked: Tell me about my Lemonade Renters Policy"
    expected_rewritten_query = "What coverage does Lemonade Renters Policy provide for a car crash?"
    
    mock_llm_model.generate_content.return_value.text = expected_rewritten_query
    
    # ACT
    result = create_contextual_query(query, context)
    
    # ASSERT
    assert result == expected_rewritten_query
    mock_llm_model.generate_content.assert_called_once()

def test_create_contextual_query_skips_long_query(mock_llm_model):
    """
    GIVEN a long, specific query.
    WHEN `create_contextual_query` is called.
    THEN it should NOT call the LLM and should return the original query.
    """
    # ARRANGE
    query = "I need to know the specific coverage limits for personal property in my policy number ABC-123."
    context = "Some previous conversation."
    
    # ACT
    result = create_contextual_query(query, context)
    
    # ASSERT
    assert result == query
    mock_llm_model.generate_content.assert_not_called()