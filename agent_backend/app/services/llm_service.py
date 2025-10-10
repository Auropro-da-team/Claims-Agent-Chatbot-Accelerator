import logging
import vertexai
from vertexai.language_models import TextEmbeddingModel
from vertexai.preview.generative_models import GenerativeModel
from config import settings

# -------------------------
# INITIALIZATION
# -------------------------
vertexai.init(project=settings.PROJECT_ID, location=settings.REGION)
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
llm_model = GenerativeModel("gemini-1.5-flash")

# -------------------------
# CONTEXTUAL QUERY REWRITING
# -------------------------
def create_contextual_query(query: str, conversation_context: str) -> str:
    """
    Rewrites a user's follow-up query to be a self-contained query
    by injecting context from the conversation history.
    """
    # If there's no history or the query is long/specific, the original query is likely fine.
    if not conversation_context or len(query.split()) > 10:
        return query

    rewrite_prompt = f"""
    You are a query rewriting expert. Your task is to take a conversation history and a new user question,
    and rewrite the user question into a single, self-contained, and specific search query.

    - If the new question is a follow-up (e.g., "what about for a crash?", "is that covered?"), incorporate key entities (like policy names, policy numbers, or specific topics) from the previous turns into the new query.
    - If the new question is completely unrelated or already specific, just use the new question as the query.
    - The output MUST be only the rewritten search query and nothing else.

    --- CONVERSATION HISTORY ---
    {conversation_context}

    --- NEW USER QUESTION ---
    "{query}"

    --- REWRITTEN SEARCH QUERY ---
    """
    try:
        response = llm_model.generate_content(rewrite_prompt, generation_config={'temperature': 0.0})
        rewritten_query = response.text.strip().replace('"', '')
        logging.info(f"Original Query: '{query}' | Rewritten Query: '{rewritten_query}'")
        return rewritten_query
    except Exception as e:
        logging.error(f"Error during query rewriting: {e}")
        return query # Fallback to the original query on error


def expand_query_for_better_search(query: str, conversation_context: str = "") -> str:
    """
    Uses an LLM to expand a query with relevant, synonymous insurance terms
    for a more robust vector search, especially for ambiguous queries.
    """
    # For very specific queries (like with a policy number), don't expand.
    from app.utils.parsers import extract_policy_identifier
    if extract_policy_identifier(query):
        return query

    expansion_prompt = f"""
    You are a search query expansion expert for the insurance industry.
    Your task is to take a user's query and expand it with 3 to 5 additional, highly relevant keywords or phrases that will improve vector search results.
    Focus on synonyms and related concepts. Do not change the original query.
    
    Example 1:
    Query: "for a customer with Mountain West Commercial Insurance policy what policy can i sell for renewal"
    Expanded Query: for a customer with Mountain West Commercial Insurance policy what policy can i sell for renewal similar alternative business coverage comparison

    Example 2:
    Query: "what is covered for water damage"
    Expanded Query: what is covered for water damage pipe burst flood leak coverage inclusions exclusions
    
    Now, expand this query:
    Query: "{query}"
    Expanded Query:
    """
    try:
        response = llm_model.generate_content(expansion_prompt)
        expanded_query = response.text.strip()
        logging.info(f"Expanded search query: '{expanded_query}'")
        return expanded_query
    except Exception as e:
        logging.error(f"LLM query expansion failed: {e}")
        return query # Fallback to original query on error

def get_format_instruction(format_preference):
    if format_preference == 'table':
        return """
        MANDATORY TABLE FORMATTING:
        | Policy Name | Inclusions | Exclusions |
        |-------------|------------|------------|
        | [Policy Name] | • Item 1<br>• Item 2 | • Exclusion 1<br>• Exclusion 2 |
        """
    elif format_preference == 'structured':
        return "Use clear sections with bullet points"
    else:
        return "Use natural paragraph format"


def get_intent_instruction(primary_intent):
    if primary_intent == 'policy_summary':
        return "Provide comprehensive policy summaries with holder details"
    elif primary_intent == 'comparison':
        return "Use professional comparison tables with key differentiators"
    else:
        return "Provide direct, clear answers with supporting details"