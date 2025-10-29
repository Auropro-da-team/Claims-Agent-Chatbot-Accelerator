import pytest
from app.services.analysis_service import analyze_query_intent, determine_policy_requirement

# By including `mock_llm_model` in the test function's arguments, pytest automatically
# finds and injects the fixture from conftest.py. This is a core feature of pytest.

def test_analyze_query_intent_with_regex_match(mock_llm_model):
    """
    GIVEN a query that matches a predefined regex pattern (e.g., for a 'personal_claim').
    WHEN `analyze_query_intent` is called.
    THEN the correct intent should be identified using the fast regex path,
         AND the expensive external LLM call should be completely avoided.
    """
    # ARRANGE
    query = "I was in a car accident and need to file a claim."
    
    # ACT
    result = analyze_query_intent(query)
    
    # ASSERT
    assert result['primary_intent'] == 'fnol'
    assert 'personal_claim' in result['all_intents']
    mock_llm_model.generate_content.assert_not_called()

def test_analyze_query_intent_with_llm_fallback(mock_llm_model):
    """
    GIVEN a query that does NOT match any regex patterns.
    WHEN `analyze_query_intent` is called.
    THEN the function should fall back to using the LLM, and the LLM's mocked response
         should be correctly processed to determine the intent.
    """
    # ARRANGE
    query = "something bad happened to my shipment"
    mock_llm_model.generate_content.return_value.text = 'personal_claim'
    
    # ACT
    result = analyze_query_intent(query)
    
    # ASSERT
    assert result['primary_intent'] == 'fnol'
    assert 'personal_claim' in result['all_intents']
    mock_llm_model.generate_content.assert_called_once()

@pytest.mark.parametrize("intent, user_query, expected_prompt_key", [
    pytest.param("fnol", "My house had a fire", "empathetic_clarification_generator", id="FNOL with loss keyword"),
    pytest.param("fnol", "I need to start a claim", "standard_clarification_generator", id="FNOL without loss keyword"),
])
def test_determine_policy_requirement_chooses_correct_prompt(mocker, intent, user_query, expected_prompt_key):
    """
    GIVEN a specific intent and user query.
    WHEN `determine_policy_requirement` is called.
    THEN it should select the correct prompt (empathetic vs. standard) based on keywords.
    
    This test uses a spy to ensure the right prompt key is requested from our loader.
    """
    # ARRANGE
    query_analysis = {'primary_intent': intent}
    # We need to spy on `get_prompt` to see what it's called with.
    mock_get_prompt = mocker.patch('app.services.analysis_service.get_prompt')
    # We also need to mock the final LLM call, as it's still part of the function.
    mocker.patch('app.services.analysis_service.llm_model.generate_content')

    # ACT
    determine_policy_requirement(query_analysis, user_query)
    
    # ASSERT
    # We check that our `get_prompt` spy was called with the correct prompt key.
    mock_get_prompt.assert_any_call(expected_prompt_key, user_query=user_query)


from app.services.analysis_service import (
    detect_incident_context_in_history,
    check_insurance_relevance,
    generate_fnol_response
)

def test_detect_incident_context_in_history_finds_incident(mock_llm_model):
    """
    GIVEN a conversation history where the user previously reported an incident.
    WHEN `detect_incident_context_in_history` is called.
    THEN it should use the LLM to identify the original incident description.
    """
    # ARRANGE
    session_id = "test_session"
    incident_query = "My car broke down on the highway."
    conversation_history = {
        session_id: [
            {"query": incident_query, "query_type": "policy_required"}
        ]
    }
    # Program the mock LLM to confirm this is a real event.
    mock_llm_model.generate_content.return_value.text = "YES"
    
    # ACT
    result = detect_incident_context_in_history(session_id, conversation_history)
    
    # ASSERT
    assert result == incident_query
    mock_llm_model.generate_content.assert_called_once()

def test_check_insurance_relevance_with_keyword():
    """
    GIVEN a query containing an obvious insurance keyword.
    WHEN `check_insurance_relevance` is called.
    THEN it should immediately identify it as relevant without calling the LLM.
    """
    # This test does not need a mock because the LLM should not be called.
    query = "What is my policy deductible?"
    result_type, _ = check_insurance_relevance(query, [], "")
    assert result_type == "insurance"

def test_check_insurance_relevance_with_llm_fallback(mock_llm_model):
    """
    GIVEN a query without obvious keywords.
    WHEN `check_insurance_relevance` is called.
    THEN it should use the LLM to determine relevance.
    """
    # ARRANGE
    query = "I had a problem with my property."
    mock_llm_model.generate_content.return_value.text = "YES"
    
    # ACT
    result_type, _ = check_insurance_relevance(query, [], "")
    
    # ASSERT
    assert result_type == "insurance"
    mock_llm_model.generate_content.assert_called_once()

@pytest.mark.parametrize("last_query_type, user_query, expected_stage", [
    ("initial_loss_report", "I was in an accident", "initial_loss_report"),
    ("policy_required", "My policy is ABC-123", "policy_verification"),
    ("details_collected", "Yes, that's correct", "confirmation"),
    ("confirmation", "confirmed", "claim_number_issued"),
])
def test_generate_fnol_response_state_machine(last_query_type, user_query, expected_stage):
    """
    GIVEN a conversation history representing a certain stage in the FNOL process.
    WHEN `generate_fnol_response` is called.
    THEN it should correctly identify the current stage.
    """
    # ARRANGE
    history = [{"query_type": last_query_type}]
    
    # ACT
    result = generate_fnol_response(user_query, {}, history)
    
    # ASSERT
    assert result['stage'] == expected_stage