import logging
import ast
import re
from google.cloud import aiplatform
from config import settings
from app.services.llm_service import embedding_model
from app.services.document_service import get_text_content_by_id, content_based_policy_filter, validate_policy_number_in_document_content
from app.utils.parsers import extract_document_name, parse_page_number, extract_section_info, extract_policy_names_from_query
from app.services.analysis_service import is_relevant_for_comparison

# -------------------------
# INITIALIZATION
# -------------------------
index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
    index_endpoint_name=f"projects/{settings.PROJECT_ID}/locations/{settings.REGION}/indexEndpoints/{settings.INDEX_ENDPOINT_ID}"
)

# -------------------------
# ENHANCED SEARCH FOR COMPARISONS
# -------------------------
def get_additional_policies_for_comparison(query: str, current_chunks: list) -> list:
    """
    ENHANCED: Better policy retrieval for 10,000+ documents
    """
    comparison_keywords = [
        'compare', 'comparison', 'versus', 'vs', 'different', 'similar', 'best',
        'which', 'other policies', 'pull up', 'show me', 'find', 'alternative',
        'like this', 'similar to', 'closest to', 'renewal'
    ]

    query_lower = query.lower()
    needs_more_policies = any(keyword in query_lower for keyword in comparison_keywords)

    if not needs_more_policies:
        return current_chunks[:8]

    try:
        # ENHANCED: Better search query construction
        # Extract specific policy names mentioned in query
        policy_names = extract_policy_names_from_query(query)

        if policy_names:
            # Search specifically for mentioned policies
            enhanced_query = f"{query} {' '.join(policy_names)} insurance policy coverage"
        else:
            enhanced_query = f"{query} insurance policy coverage business"

        query_vec = embedding_model.get_embeddings([enhanced_query])[0].values

        # INCREASED: Get more neighbors for better coverage
        response = index_endpoint.find_neighbors(
            deployed_index_id=settings.DEPLOYED_INDEX_ID,
            queries=[query_vec],
            num_neighbors=50,  # Increased from 25
            return_full_datapoint=True
        )

        additional_chunks = []
        seen_documents = {chunk['document_name'] for chunk in current_chunks}

        for neighbor in response[0]:
            if len(additional_chunks) >= 8:  # Limit total chunks
                break

            chunk_id = neighbor.id
            doc_name = extract_document_name(chunk_id)

            # ENHANCED: Better filtering for relevant documents
            if (doc_name not in seen_documents and
                is_relevant_for_comparison(doc_name, query, policy_names)):

                text = get_text_content_by_id(chunk_id)
                if text and len(text) > 100:
                    # Process metadata
                    raw_meta = getattr(neighbor, "metadata", {}) or {}
                    if isinstance(raw_meta, str):
                        try:
                            metadata = ast.literal_eval(raw_meta)
                        except Exception:
                            metadata = {}
                    else:
                        metadata = raw_meta

                    page_numbers = metadata.get("page_numbers", [])
                    page = page_numbers[0] if page_numbers else parse_page_number(chunk_id, text)
                    section = metadata.get("section", "")
                    subsection = metadata.get("subsection", "")

                    if not section or section.lower() in ["document content", "general"]:
                        sec, subsec = extract_section_info(text)
                        section = section or sec
                        subsection = subsection or subsec

                    additional_chunks.append({
                        "id": chunk_id,
                        "page": page,
                        "text": text,
                        "document_name": doc_name,
                        "section": section,
                        "subsection": subsection
                    })
                    seen_documents.add(doc_name)

        return (current_chunks + additional_chunks)[:8]

    except Exception as e:
        logging.error(f"Error getting additional policies: {e}")
        return current_chunks[:8]

def enhanced_policy_document_search(policy_numbers: list) -> list:
    """
    NEW FUNCTION: Comprehensive search across entire vector index for policy documents
    Searches through document content, not metadata
    """
    if not policy_numbers:
        return []

    try:
        # PHASE 1: Cast a wide net with semantic search
        broad_search_terms = [
            "insurance policy coverage inclusions exclusions limits",
            "policy holder insured coverage details",
            "insurance policy number coverage information",
            "policy coverage limits deductibles inclusions",
            "insurance policy documents coverage details"
        ]

        all_candidate_chunks = []
        seen_chunk_ids = set()

        # Perform broad searches to get potential policy documents
        for search_term in broad_search_terms:
            try:
                query_vec = embedding_model.get_embeddings([search_term])[0].values

                response = index_endpoint.find_neighbors(
                    deployed_index_id=settings.DEPLOYED_INDEX_ID,
                    queries=[query_vec],
                    num_neighbors=200,  # Large search to ensure we don't miss documents
                    return_full_datapoint=True
                )

                if response and response[0]:
                    for neighbor in response[0]:
                        chunk_id = neighbor.id
                        if chunk_id not in seen_chunk_ids:
                            # Get the actual document content
                            text = get_text_content_by_id(chunk_id)

                            if text and len(text) > 10:


                                raw_meta = getattr(neighbor, "metadata", {}) or {}
                                metadata = {}
                                if isinstance(raw_meta, str):
                                    try:
                                        metadata = ast.literal_eval(raw_meta)
                                    except Exception:
                                        pass
                                elif isinstance(raw_meta, dict):
                                    metadata = raw_meta

                                page_numbers = metadata.get("page_numbers", [])
                                page = page_numbers[0] if page_numbers else parse_page_number(chunk_id, text)

                                all_candidate_chunks.append({
                                    "id": chunk_id,
                                    "page": page,
                                    "text": text,
                                    "document_name": extract_document_name(chunk_id),
                                    "section": metadata.get("section", "Policy Information"),
                                    "subsection": metadata.get("subsection", "")
                                })

                                seen_chunk_ids.add(chunk_id)

                                # Limit total candidates to prevent memory issues
                                if len(all_candidate_chunks) >= 500:
                                    break

                if len(all_candidate_chunks) >= 500:
                    break

            except Exception as e:
                logging.error(f"Broad search failed: {e}")
                continue

        logging.info(f"PHASE 1: Found {len(all_candidate_chunks)} candidate documents")

        # PHASE 2: Filter candidates by actual policy number content
        policy_documents = content_based_policy_filter(all_candidate_chunks, policy_numbers)

        if policy_documents:
            logging.info(f"PHASE 2: Found {len(policy_documents)} documents containing policy numbers")
            return policy_documents
        else:
            logging.warning(f"PHASE 2: No documents found containing policy numbers: {policy_numbers}")
            return []

    except Exception as e:
        logging.error(f"Enhanced policy document search failed: {e}")
        return []


def strict_policy_document_filter(chunks: list, policy_numbers: list) -> list:
    """
    UPDATED: Now uses content-based filtering instead of metadata
    """
    return content_based_policy_filter(chunks, policy_numbers)

# -------------------------
# This function now searches through document content, not metadata

def perform_policy_specific_search(policy_numbers: list, base_query: str) -> list:
    """
    CONTENT-BASED SEARCH: Search through document text content for policy numbers
    Since policy numbers are in document content, not metadata
    """
    if not policy_numbers:
        return []

    try:
        all_policy_chunks = []
        seen_chunk_ids = set()

        # STRATEGY 1: Broad semantic search first, then content filtering
        search_queries = []


        for pnum in policy_numbers:
            # Create multiple search variations for each policy number
            clean_pnum = re.sub(r'[-_]', '', pnum)
            spaced_pnum = re.sub(r'[-_]', ' ', pnum)

            search_queries.extend([
                f"policy number {pnum}",
                f"{pnum} insurance policy coverage",
                f"{clean_pnum} policy holder coverage",
                f"policy {spaced_pnum} inclusions exclusions",
                f"insurance policy {pnum} details",
                f"{pnum} coverage limits deductibles"
            ])

        # Also include general insurance terms to cast a wider net
        search_queries.extend([
            "insurance policy coverage inclusions exclusions",
            "policy holder coverage details insurance",
            "insurance policy limits deductibles coverage"
        ])

        # Execute searches with larger neighbor count to ensure we don't miss documents
        for search_query in search_queries[:15]:  # Limit to prevent timeout
            if len(all_policy_chunks) >= 100:  # Cast wide net initially
                break

            try:
                query_vec = embedding_model.get_embeddings([search_query])[0].values

                response = index_endpoint.find_neighbors(
                    deployed_index_id=settings.DEPLOYED_INDEX_ID,
                    queries=[query_vec],
                    num_neighbors=200,  # Larger search to find policy documents
                    return_full_datapoint=True
                )

                if response and response[0]:
                    for neighbor in response[0]:
                        chunk_id = neighbor.id
                        if chunk_id in seen_chunk_ids:
                            continue

                        # Fetch the actual document content from GCS
                        text = get_text_content_by_id(chunk_id)
                        if not text or len(text) < 30:
                            continue

                        # Process metadata for page/section info
                        raw_meta = getattr(neighbor, "metadata", {}) or {}
                        metadata = {}
                        if isinstance(raw_meta, str):
                            try:
                                metadata = ast.literal_eval(raw_meta)
                            except Exception:
                                pass
                        elif isinstance(raw_meta, dict):
                            metadata = raw_meta

                        page_numbers = metadata.get("page_numbers", [])
                        page = page_numbers[0] if page_numbers else parse_page_number(chunk_id, text)

                        all_policy_chunks.append({
                            "id": chunk_id,
                            "page": page,
                            "text": text,
                            "document_name": extract_document_name(chunk_id),
                            "section": metadata.get("section", "Policy Information"),
                            "subsection": metadata.get("subsection", "")
                        })

                        seen_chunk_ids.add(chunk_id)

            except Exception as search_error:
                logging.error(f"Search failed for query '{search_query}': {search_error}")
                continue

        # STRATEGY 2: Content-based filtering - find chunks containing policy numbers
        logging.info(f"Content filtering {len(all_policy_chunks)} chunks for policy numbers: {policy_numbers}")
        policy_specific_chunks = content_based_policy_filter(all_policy_chunks, policy_numbers)

        if policy_specific_chunks:
            # Sort by relevance - prioritize earlier pages and longer content
            policy_specific_chunks.sort(key=lambda x: (
                int(x['page']) if str(x['page']).isdigit() else 999,
                -len(x['text'])
            ))

            logging.info(f"✅ CONTENT SEARCH SUCCESS: Found {len(policy_specific_chunks)} chunks containing policy numbers")
            return policy_specific_chunks[:30]  # Return top 30 most relevant
        else:
            logging.warning(f"❌ CONTENT SEARCH FAILED: No chunks contain policy numbers {policy_numbers}")
            return []

    except Exception as e:
        logging.error(f"Critical error in content-based policy search: {e}")
        return []

def handle_policy_not_found_with_retry(policy_numbers: list, user_query: str) -> tuple:
    """
    CRITICAL: Retry mechanism when policies aren't found on first attempt
    """
    logging.warning(f"RETRY MECHANISM: Attempting fallback search for {policy_numbers}")

    # FALLBACK 1: Broader search without strict policy validation
    fallback_searches = []
    for pnum in policy_numbers:
        # Extract just the core components
        components = re.findall(r'[A-Z]{2,}|\d{4,}', pnum)
        if components:
            fallback_searches.extend([
                f"insurance policy {components[0]}",
                f"coverage {' '.join(components[:2])}",
                f"policy holder {components[-1]}" if components[-1].isdigit() else f"policy {components[-1]}"
            ])

    # FALLBACK 2: Generic insurance search with user context
    insurance_keywords = ['coverage', 'policy', 'insurance', 'claims', 'liability', 'property']
    contextual_search = f"{user_query} insurance policy coverage"

    all_fallback_searches = fallback_searches + [contextual_search]

    fallback_chunks = []
    for search_query in all_fallback_searches[:5]:  # Limit to 5 searches
        try:
            query_vec = embedding_model.get_embeddings([search_query])[0].values
            response = index_endpoint.find_neighbors(
                deployed_index_id=settings.DEPLOYED_INDEX_ID,
                queries=[query_vec],
                num_neighbors=30,
                return_full_datapoint=True
            )

            if response and response[0]:
                for neighbor in response[0][:10]:  # Top 10 per search
                    chunk_id = neighbor.id
                    text = get_text_content_by_id(chunk_id)
                    if text and len(text) > 50:
                        fallback_chunks.append({
                            "id": chunk_id,
                            "page": parse_page_number(chunk_id, text),
                            "text": text,
                            "document_name": extract_document_name(chunk_id),
                            "section": "Policy Information",
                            "subsection": ""
                        })

                        if len(fallback_chunks) >= 15:
                            break

            if len(fallback_chunks) >= 15:
                break

        except Exception as e:
            logging.error(f"Fallback search failed: {e}")
            continue

    if fallback_chunks:
        logging.info(f"✓ FALLBACK SUCCESS: Found {len(fallback_chunks)} insurance documents")
        return fallback_chunks, None
    else:
        error_msg = (f"I searched extensively but couldn't locate documents for policy number(s): "
                   f"**{', '.join(policy_numbers)}**.\n\n"
                   f"Please verify:\n"
                   f"• Policy number is exactly as shown on your documents\n"
                   f"• Policy is currently active\n"
                   f"• Try removing dashes/spaces (e.g., '{policy_numbers[0].replace('-', '')}' instead of '{policy_numbers[0]}')\n\n"
                   f"Or describe your coverage question and I'll help find relevant policies.")
        return [], error_msg



def perform_enhanced_vector_search(query: str, policy_numbers: list = None) -> list:
    """
    ENHANCED: Dynamic neighbor count based on corpus size and query complexity
    """
    # Determine optimal neighbor count
    base_neighbors = 80  # Increased from 50
    if policy_numbers:
        # Policy-specific searches need more neighbors due to specificity
        neighbor_count = min(150, base_neighbors * len(policy_numbers))
    else:
        neighbor_count = base_neighbors

    try:
        query_vec = embedding_model.get_embeddings([query])[0].values

        response = index_endpoint.find_neighbors(
            deployed_index_id=settings.DEPLOYED_INDEX_ID,
            queries=[query_vec],
            num_neighbors=neighbor_count,
            return_full_datapoint=True
        )

        chunks = []
        if response and response[0]:
            for neighbor in response[0]:
                chunk_id = neighbor.id
                text = get_text_content_by_id(chunk_id)
                if text and len(text) > 30:  # Lowered threshold
                    raw_meta = getattr(neighbor, "metadata", {}) or {}
                    if isinstance(raw_meta, str):
                        try:
                            metadata = ast.literal_eval(raw_meta)
                        except Exception:
                            metadata = {}
                    else:
                        metadata = raw_meta

                    page_numbers = metadata.get("page_numbers", [])
                    page = page_numbers[0] if page_numbers else parse_page_number(chunk_id, text)
                    section = metadata.get("section", "")
                    subsection = metadata.get("subsection", "")

                    if not section or section.lower() in ["document content", "general"]:
                        sec, subsec = extract_section_info(text)
                        section = section or sec
                        subsection = subsection or subsec

                    chunks.append({
                        "id": chunk_id,
                        "page": page,
                        "text": text,
                        "document_name": extract_document_name(chunk_id),
                        "section": section,
                        "subsection": subsection
                    })

        logging.info(f"Vector search returned {len(chunks)} chunks with {neighbor_count} neighbors")
        return chunks

    except Exception as e:
        logging.error(f"Enhanced vector search failed: {e}")
        return []