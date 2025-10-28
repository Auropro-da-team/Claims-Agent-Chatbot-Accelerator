import logging
import vertexai
from vertexai.language_models import TextEmbeddingModel
from vertexai.preview.generative_models import GenerativeModel
from config import settings
from app.utils.prompt_loader import get_prompt
# -------------------------
# INITIALIZATION
# -------------------------
vertexai.init(project=settings.PROJECT_ID, location=settings.REGION)
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
llm_model = GenerativeModel("gemini-2.5-flash")

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

    rewrite_prompt = get_prompt('contextual_query_rewriter', conversation_context=conversation_context, query=query)
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

    expansion_prompt = get_prompt('query_expander', query=query)

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