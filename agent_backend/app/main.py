import functions_framework
import json
import re
import logging
import time
from flask import Flask, request, make_response
from flask_cors import CORS
import os
from dotenv import load_dotenv
load_dotenv()
from config import settings
from app.utils.history_manager import conversation_history, policy_clarification_status
from app.utils.parsers import (
    extract_policy_fields,
    extract_policy_identifier,
    extract_policy_identifier_enhanced,
    is_valid_policy_number
)
from app.utils.reference_builder import generate_detailed_references, add_inline_citations
from app.services.llm_service import llm_model, create_contextual_query
from app.services.analysis_service import (
    analyze_query_intent,
    detect_incident_context_in_history,
    check_insurance_relevance,
    generate_fnol_response,
    determine_policy_requirement
)
from app.services.search_service import (
    get_additional_policies_for_comparison,
    perform_policy_specific_search,
    enhanced_policy_document_search
)
from app.services.document_service import validate_policy_number_in_document_content

# -------------------------
# INITIALIZATION
# -------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(level=logging.INFO)

# -------------------------
# HELPER FUNCTIONS
# -------------------------
def generate_claim_number(policy_number: str) -> str:
    """Generate a realistic claim number based on policy number"""
    import random
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)
    policy_prefix = policy_number[:3] if len(policy_number) >= 3 else "CLM"
    return f"{policy_prefix}-{timestamp % 100000}-{random_suffix}"

def log_policy_search_metrics(found_policy_numbers: list, chunks_found: int, query: str):
    """Log search effectiveness for monitoring"""
    logging.info(f"POLICY SEARCH METRICS:")
    logging.info(f"  Query: {query}")
    logging.info(f"  Policy Numbers Found: {found_policy_numbers}")
    logging.info(f"  Document Chunks Retrieved: {chunks_found}")
    logging.info(f"  Search Success: {'YES' if chunks_found > 0 else 'NO'}")

def debug_policy_search(policy_number: str, chunks: list) -> dict:
    """
    DEBUGGING: Detailed analysis of why a policy number might not be found
    """
    debug_info = {
        'policy_number': policy_number,
        'chunks_searched': len(chunks),
        'potential_matches': [],
        'text_samples': []
    }

    policy_upper = policy_number.upper().strip()
    clean_policy = re.sub(r'[-_\s\.]', '', policy_upper)

    for i, chunk in enumerate(chunks[:5]):  # Check first 5 chunks
        text = chunk.get('text', '')[:500]  # First 500 chars
        debug_info['text_samples'].append(f"Chunk {i}: {text}")

        # Look for partial matches
        policy_parts = re.findall(r'[A-Z]{2,}|\d{4,}', policy_upper)
        for part in policy_parts:
            if part in text.upper():
                debug_info['potential_matches'].append(f"Found '{part}' in chunk {i}")

    return debug_info

def log_search_results(chunks: list, policy_numbers: list, query: str):
    """
    UPDATED: Use comprehensive content-based logging
    """
    log_comprehensive_search_results(chunks, policy_numbers, query)

def debug_clarification_flow(
    found_policy_numbers: list,
    needs_clarification: bool,
    is_follow_up: bool,
    has_context: bool,
    original_incident: str,
    should_ask: bool
) -> None:
    """Helper to log clarification decision making for debugging"""
    logging.info("=" * 60)
    logging.info("CLARIFICATION FLOW DEBUG")
    logging.info("-" * 60)
    logging.info(f"Policy numbers found: {found_policy_numbers}")
    logging.info(f"Policy needs clarification: {needs_clarification}")
    logging.info(f"Is follow-up response: {is_follow_up}")
    logging.info(f"Has conversation context: {has_context}")
    logging.info(f"Original incident detected: {bool(original_incident)}")
    if original_incident:
        logging.info(f"  → Incident text: '{original_incident[:60]}...'")
    logging.info(f"DECISION: Should ask clarification = {should_ask}")
    logging.info("=" * 60)

def debug_policy_search_in_content(policy_numbers: list, sample_chunks: list) -> dict:
    """
    NEW FUNCTION: Debug why policy numbers might not be found in document content
    """
    debug_info = {
        'policy_numbers': policy_numbers,
        'chunks_analyzed': len(sample_chunks),
        'content_samples': [],
        'search_patterns_tried': [],
        'partial_matches': []
    }

    for i, chunk in enumerate(sample_chunks[:5]):
        text = chunk.get('text', '')
        doc_name = chunk.get('document_name', 'Unknown')

        # Sample content for debugging
        debug_info['content_samples'].append({
            'chunk_index': i,
            'document_name': doc_name,
            'text_sample': text[:300],
            'text_length': len(text),
            'contains_policy_keywords': any(word in text.lower() for word in ['policy', 'coverage', 'insurance', 'holder'])
        })

        # Check for partial matches
        for pnum in policy_numbers:
            policy_parts = re.findall(r'[A-Z]{2,}|\d{4,}', pnum.upper())
            matches_found = []

            for part in policy_parts:
                if part in text.upper():
                    matches_found.append(part)

            if matches_found:
                debug_info['partial_matches'].append({
                    'policy_number': pnum,
                    'document': doc_name,
                    'parts_found': matches_found,
                    'parts_total': len(policy_parts)
                })

    logging.info(f"DEBUGGING: Policy search debug info: {debug_info}")
    return debug_info


def log_comprehensive_search_results(chunks: list, policy_numbers: list, query: str):
    """
    NEW FUNCTION: Enhanced logging for content-based search
    """
    logging.info(f"=== CONTENT-BASED SEARCH RESULTS ===")
    logging.info(f"Query: {query}")
    logging.info(f"Policy Numbers Searched: {policy_numbers}")
    logging.info(f"Total Chunks Found: {len(chunks)}")

    if chunks:
        # Log document distribution
        doc_distribution = {}
        for chunk in chunks:
            doc_name = chunk.get('document_name', 'Unknown')
            doc_distribution[doc_name] = doc_distribution.get(doc_name, 0) + 1

        logging.info(f"Document Distribution: {doc_distribution}")

        # Log sample content
        for i, chunk in enumerate(chunks[:3]):
            text_sample = chunk.get('text', '')[:200]
            logging.info(f"Sample Chunk {i}: {chunk.get('document_name')} - {text_sample}...")

            # Check which policy numbers were found in this chunk
            found_policies = []
            for pnum in policy_numbers:
                if validate_policy_number_in_document_content(pnum, chunk.get('text', '')):
                    found_policies.append(pnum)

            if found_policies:
                logging.info(f"  ✅ Contains policy numbers: {found_policies}")
            else:
                logging.info(f"  ❌ No policy numbers found in this chunk")
    else:
        logging.warning(f"❌ NO DOCUMENTS FOUND containing policy numbers: {policy_numbers}")

        # If no results, try debugging
        debug_info = debug_policy_search_in_content(policy_numbers, [])
        logging.info(f"Debug suggestions: Check if policy numbers exist in document content")

    logging.info(f"=== END SEARCH RESULTS ===")

# -------------------------
# MAIN HANDLER - ENHANCED VERSION
# -------------------------
@functions_framework.http
def query_documents(request):
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type'
    }

    try:
        # STEP 1: PARSE REQUEST
        request_json = request.get_json(silent=True)
        user_query = request_json["query"].strip()
        session_id = request_json.get("session_id", f"session_{int(time.time())}")

        # Initialize conversation history
        if session_id not in conversation_history:
            conversation_history[session_id] = []

        # STEP 2: HANDLE GREETINGS
        if len(user_query.split()) <= 5:
            greeting_patterns = [
                r'\b(hi|hello|hey|good morning|good afternoon|good evening)\b',
                r'\b(how are you|what can you do|help me|assist me)\b',
                r'\b(thanks|thank you|bye|goodbye)\b'
            ]
            if any(re.search(pattern, user_query.lower()) for pattern in greeting_patterns):
                return json.dumps({
                    "answer": "Hello! I'm here to help you understand your insurance coverage. What questions do you have about your policies?",
                    "query_type": "greeting",
                    "references": [],
                    "session_id": session_id
                }), 200, headers

        # STEP 3: ANALYZE INTENT (WITH CONTEXT)
        query_analysis = analyze_query_intent(user_query)
        logging.info(f"Initial query analysis result: {query_analysis}")

        # --- CONTEXT RESTORATION LOGIC ---
        # If the bot's last action was to ask for a policy number, the user's current
        # message is likely providing it. The TRUE intent is from the user's
        # query BEFORE the bot's interruption.
        if session_id in conversation_history and conversation_history[session_id]:
            last_interaction = conversation_history[session_id][-1]
            if last_interaction.get('query_type') == 'policy_required':
                # The original user query is the one that triggered the policy request.
                original_user_query = last_interaction.get('query')
                if original_user_query:
                    # Re-run analysis on the original query to restore the true intent.
                    original_query_analysis = analyze_query_intent(original_user_query)
                    query_analysis = original_query_analysis
                    logging.info(f"CONTEXT RESTORED: Re-evaluating based on original query '{original_user_query}'. New analysis: {query_analysis}")
        # --- END CONTEXT RESTORATION LOGIC ---

        # STEP 4: BUILD CONVERSATION CONTEXT
        conversation_context = ""
        is_follow_up_with_details = False

        # Use dedicated function to detect incident context
        original_claim_context = detect_incident_context_in_history(session_id, conversation_history)

        if session_id in conversation_history and conversation_history[session_id]:
            recent_history = conversation_history[session_id][-8:]

            # Check if last interaction was asking for clarification
            if recent_history and recent_history[-1].get('query_type') == 'needs_more_context':
                is_follow_up_with_details = True
                logging.info("✓ Detected follow-up with user details")

            # Build conversational context
            context_parts = []
            for h in recent_history:
                context_parts.append(f"User previously asked: {h['query']}")
                prev_answer = h['answer'][:400]
                if "policy" in prev_answer.lower() or "|" in prev_answer:
                    context_parts.append(f"Assistant previously provided: {prev_answer}")
            conversation_context = "\n".join(context_parts)

        # Log context analysis
        logging.info(f"=== CONTEXT ANALYSIS ===")
        logging.info(f"  Conversation context: {bool(conversation_context)}")
        logging.info(f"  Is follow-up: {is_follow_up_with_details}")
        logging.info(f"  Original incident: '{original_claim_context[:50] if original_claim_context else 'None'}'")
        logging.info(f"========================")

        # STEP 5: EXTRACT POLICY NUMBERS - ENHANCED
        # Combine original claim context if present
        if original_claim_context and original_claim_context not in user_query:
            contextual_query = create_contextual_query(f"{original_claim_context} {user_query}", conversation_context)
        else:
            contextual_query = create_contextual_query(user_query, conversation_context)
        # Enhanced policy number extraction - use both methods
        found_policy_numbers = extract_policy_identifier(contextual_query)
        enhanced_policy_numbers = extract_policy_identifier_enhanced(contextual_query)

        # Merge results, prioritizing enhanced results
        # Merge results, prioritizing enhanced results, then validate
        all_found_policies = enhanced_policy_numbers + found_policy_numbers
        all_found_policies = list(dict.fromkeys(all_found_policies))  # Remove duplicates first

        # 🚨 Validate candidates so that brand names (like LEMONADE) are rejected
        found_policy_numbers = [p for p in all_found_policies if is_valid_policy_number(p)]


        logging.info(f"COMBINED EXTRACTION: Found {len(found_policy_numbers)} total: {found_policy_numbers}")


        # Also check conversation context for policy numbers
        if conversation_context:
            context_policy_numbers = extract_policy_identifier(conversation_context)
            found_policy_numbers.extend(context_policy_numbers)
            found_policy_numbers = list(dict.fromkeys(found_policy_numbers))  # Remove duplicates



        # ENHANCED: Extract policy numbers from conversation history for context continuity
        if session_id in conversation_history and not found_policy_numbers:
            for interaction in conversation_history[session_id]:
                hist_query = interaction.get('query', '')
                hist_answer = interaction.get('answer', '')

                # Look for policy numbers in previous queries
                hist_policies = extract_policy_identifier(hist_query)
                found_policy_numbers.extend(hist_policies)

                # Also check successful policy responses (tables with policy info)
                if ('|' in hist_answer and
                    'Policy' in hist_answer and
                    any(keyword in hist_answer for keyword in ['SAC-', 'ESC-', 'PHI-', 'LP-'])):
                    table_policies = extract_policy_identifier(hist_answer)
                    found_policy_numbers.extend(table_policies)

            # Remove duplicates while preserving order
            found_policy_numbers = list(dict.fromkeys(found_policy_numbers))


        logging.info(f"POLICY EXTRACTION RESULT: Found {len(found_policy_numbers)} policy numbers: {found_policy_numbers}")

        # STEP 6: CHECK IF WE NEED TO ASK FOR POLICY NUMBERS - CRITICAL DECISION POINT
        # ENHANCED: Include session context for policy continuity
# =================================================================================

        # STEP 6: DETERMINE IF A POLICY NUMBER IS REQUIRED AND ENFORCE IT
        policy_requirement = determine_policy_requirement(query_analysis, user_query)

        # This is the MANDATORY GATE.
        # If the rules say a policy is required AND we don't have one, we STOP here.
        if policy_requirement['required'] and not found_policy_numbers:
            logging.info(f"ACTION: Policy number is required for intent '{query_analysis['primary_intent']}' but none was found. Asking user.")

            ask_message = policy_requirement.get('ask_message') or "To provide accurate information, I need a policy number. Please provide the policy number you're asking about."

            conversation_history[session_id].append({
                "query": user_query,
                "answer": ask_message,
                "timestamp": int(time.time()),
                "query_type": "policy_required"
            })

            # Immediately return the question to the user. Do not proceed to search.
            return json.dumps({
                "answer": ask_message,
                "query_type": "policy_required",
                "format_used": "clarification",
                "references": [],
                "session_id": session_id,
                "needs_clarification": False,
                "needs_policyholder_info": True,
                "missing_policy_numbers": True
            }, ensure_ascii=False), 200, headers

        # STEP 7: HANDLE OPEN-ENDED QUERIES (if we passed the policy gate)
        # This code only runs if a policy number was not required, or if we already have one.
        # The complex check for 'is_followup_after_policy_request' is no longer needed.
        if query_analysis['needs_clarification'] and not conversation_context:
            logging.info(f"ACTION: Asking for clarification for broad query '{user_query}'")

            clarification_prompt = f"""
            The user asked "{user_query}" which is too broad. Ask 1-3 clarifying questions to help them narrow their search.
            """
            try:
                llm_response = llm_model.generate_content(clarification_prompt)
                answer = llm_response.text.strip()
            except Exception:
                answer = "I can help with that. Could you be more specific? For example, are you looking for coverage details, exclusions, or comparing policies?"

            conversation_history[session_id].append({"query": user_query, "answer": answer, "timestamp": int(time.time()), "query_type": "open_ended"})

            return json.dumps({
                "answer": answer,
                "query_type": "open_ended",
                "references": [],
                "session_id": session_id,
            }, ensure_ascii=False), 200, headers

        # STEP 7.5: INTELLIGENT CLARIFICATION FOR POLICY-SPECIFIC QUERIES
        # Ask clarifying questions before providing detailed coverage information
        if (found_policy_numbers and
            query_analysis['format_preference'] in ['clarification', 'needs_clarification'] and
            query_analysis['primary_intent'] not in ['greeting', 'open_ended', 'comparison', 'fnol']):

            # Initialize tracking if needed
            if session_id not in policy_clarification_status:
                policy_clarification_status[session_id] = {}

            # Check if we've already clarified for this policy in this session
            needs_clarification = False
            for pnum in found_policy_numbers:
                if pnum not in policy_clarification_status[session_id]:
                    needs_clarification = True
                    break

            # Determine if we should ask clarifying questions
            # Priority: If user mentioned an incident before providing policy, ALWAYS ask for details
            # Determine if we should ask clarifying questions.
            # This is TRUE if we have policy numbers, the intent requires clarification,
            # and we haven't already asked these questions for this policy.
            # Determine if we should ask clarifying questions.
            # This is TRUE if we have policy numbers, the intent requires clarification,
            # and we haven't already asked these questions for this policy.
            should_ask_clarification = (
                found_policy_numbers and
                query_analysis['primary_intent'] in ['personal_claim', 'policy_summary', 'coverage_check'] and
                needs_clarification
            )
            logging.info(f"=== CLARIFICATION DECISION ===")
            logging.info(f"  Needs clarification: {needs_clarification}")
            logging.info(f"  Not follow-up: {not is_follow_up_with_details}")
            logging.info(f"  Has incident context: {bool(original_claim_context)}")
            logging.info(f"  RESULT: {should_ask_clarification}")
            logging.info(f"===============================")

            debug_clarification_flow(
                found_policy_numbers=found_policy_numbers,
                needs_clarification=needs_clarification,
                is_follow_up=is_follow_up_with_details,
                has_context=bool(conversation_context),
                original_incident=original_claim_context,
                should_ask=should_ask_clarification
            )

            if should_ask_clarification:
                logging.info(f"🎯 ASKING CLARIFICATION for policy {found_policy_numbers}")

                # Generate intelligent, context-aware clarifying questions using LLM
                # Build context-aware situation description
                if original_claim_context:
                    situation_description = (
                        f"ORIGINAL INCIDENT: The user said '{original_claim_context}'\n"
                        f"POLICY PROVIDED: {', '.join(found_policy_numbers)}\n"
                        f"CURRENT QUERY: {user_query}"
                    )
                    logging.info(f"📋 Using incident context: '{original_claim_context}'")
                else:
                    situation_description = (
                        f"USER QUERY: {user_query}\n"
                        f"POLICY NUMBER: {', '.join(found_policy_numbers)}"
                    )
                    logging.info(f"📋 No incident context - general inquiry")

                clarification_prompt = f"""You are an experienced insurance claims specialist.

{situation_description}

YOUR TASK: Ask 2-3 specific, targeted questions to understand their situation before checking coverage.

CRITICAL RULES:
- Be conversational and natural - NOT robotic
- NEVER use: "I'm here to help", "I'd be happy to", "I'm glad to assist"
- Get straight to the questions
- Be direct and professional

FOCUS YOUR QUESTIONS ON:
1. When the incident occurred (or if it's about future coverage)
2. Specific details about what happened
3. Extent/severity and any other parties involved

EXAMPLES OF GOOD QUESTIONS:
❌ BAD: "I'm here to help! To provide accurate coverage details, I need to know when this happened."
✅ GOOD: "To check your coverage: When did this happen? What specifically broke down? Have you had it diagnosed?"

❌ BAD: "I'd be happy to look that up for you. Let me ask a few questions first."
✅ GOOD: "To pull up your exact coverage: When did the accident occur? Were there injuries? Was another vehicle involved?"

NOW RESPOND with your 2-3 questions for this situation. Be natural and conversational.

Critical rules:
- Sound like a real person, NOT a chatbot
- NEVER use phrases like: "I'm here to help", "I can help with that", "I'm happy to assist", "I'd be glad to"
- Get straight to the questions naturally
- Be direct, professional, and conversational
- Avoid robotic politeness

Good examples:
❌ BAD: "I'm here to help! To provide accurate coverage details, I need to know..."
✅ GOOD: "To check what's covered for the pipe burst, I need a few details: When did this happen? Which rooms were affected? How extensive is the water damage?"

❌ BAD: "I'd be happy to look that up for you. To give you the most relevant information..."
✅ GOOD: "Got it. To pull up your exact coverage: When did the accident occur? Was there any injury involved? Have you already filed a police report?"

❌ BAD: "I can help with that. Let me ask you a few questions..."
✅ GOOD: "To give you accurate information about your coverage: What specific situation are you asking about? Is this something that already happened or are you checking coverage for future scenarios?"

Now respond to: "{user_query}"
Be natural and conversational. Ask your 2-3 questions directly without robotic pleasantries.
"""

                try:
                    llm_response = llm_model.generate_content(
                        clarification_prompt,
                        generation_config={'temperature': 0.4}
                    )
                    clarification_message = llm_response.text.strip()
                except Exception as e:
                    logging.error(f"Clarification generation failed: {e}")
                    # Fallback message - natural and direct
                    clarification_message = (
                        f"To check your coverage under policy {found_policy_numbers[0]}, I need a few details:\n\n"
                        "• When did this happen (or is this about future coverage)?\n"
                        "• Which area or property section are you asking about?\n"
                        "• What's your specific concern with the coverage?"
                    )

                # Mark that we've asked for clarification (but not yet received answer)
                for pnum in found_policy_numbers:
                    policy_clarification_status[session_id][pnum] = False

                # Save to conversation history
                conversation_history[session_id].append({
                    "query": user_query,
                    "answer": clarification_message,
                    "timestamp": int(time.time()),
                    "query_type": "needs_more_context"
                })

                return json.dumps({
                    "answer": clarification_message,
                    "query_type": "needs_clarification",
                    "format_used": "clarification",
                    "references": [],
                    "session_id": session_id,
                    "policy_numbers_found": found_policy_numbers,
                    "awaiting_user_details": True
                }, ensure_ascii=False), 200, headers

        # If we've reached this point, it means we have any required policy numbers and can safely proceed.
        logging.info("Policy requirements met. Proceeding to document search...")

        # STEP 8: PERFORM DOCUMENT SEARCH
        #PERFORM CONTENT-BASED POLICY DOCUMENT SEARCH
        logging.info(f"ACTION: Searching document content for policy numbers: {found_policy_numbers}")

        chunks = []

        if found_policy_numbers:
            # STRATEGY 1: Try targeted policy search first
            logging.info(f"Attempting targeted search for policies: {found_policy_numbers}")
            chunks = perform_policy_specific_search(found_policy_numbers, contextual_query)

            # STRATEGY 2: If targeted search fails, try comprehensive search
            if not chunks:
                logging.warning(f"Targeted search failed. Attempting comprehensive document search...")
                chunks = enhanced_policy_document_search(found_policy_numbers)

            # VALIDATION: Ensure we found documents containing the policy numbers
            if not chunks:
                logging.error(f"SEARCH FAILURE: No documents found containing policy numbers: {found_policy_numbers}")

                # Generate detailed error message
                policies_str = "**, **".join(found_policy_numbers)
                error_msg = (f"Please provide the correct policy number(s): **{policies_str}**.\n\n"
                        f"This could mean:\n"
                        f"• The policy number might be incorrect or contain typos\n"
                        f"• The policy documents haven't been uploaded to the system yet\n"
                        f"• The policy number format might be different\n\n"
                        f"Please:\n"
                        f"• Double-check the policy number on your documents\n"
                        f"• Try without dashes or spaces: `{found_policy_numbers[0].replace('-', '').replace('_', '')}`\n"
                        f"• Contact your agent if the issue persists")

                conversation_history[session_id].append({
                    "query": user_query,
                    "answer": error_msg,
                    "timestamp": int(time.time()),
                    "query_type": "policy_not_found_in_content"
                })

                return json.dumps({
                    "answer": error_msg,
                    "query_type": "policy_not_found",
                    "format_used": "error",
                    "references": [],
                    "session_id": session_id,
                    "policy_numbers_searched": found_policy_numbers,
                    "search_type": "content_based",
                    "documents_searched": "all_available"
                }, ensure_ascii=False), 200, headers

            # SUCCESS: Found documents containing policy numbers
            logging.info(f"✅ SEARCH SUCCESS: Found {len(chunks)} documents containing policy numbers")

            # Additional content validation to ensure quality
            validated_chunks = []
            for chunk in chunks:
                text = chunk.get('text', '')
                # Ensure chunk has substantial policy-related content
                if (len(text) > 100 and
                    any(term in text.lower() for term in ['policy', 'coverage', 'insurance', 'holder', 'insured'])):
                    validated_chunks.append(chunk)

            chunks = validated_chunks or chunks  # Use validated or fall back to original
            logging.info(f"Content validation: {len(chunks)} chunks passed quality check")

        else:
            # This should never happen due to earlier checks
            logging.error(f"CRITICAL ERROR: No policy numbers for insurance query")
            return json.dumps({
                "answer": "I need your policy number to provide accurate information. Please provide your policy number.",
                "query_type": "policy_required",
                "format_used": "error",
                "references": [],
                "session_id": session_id
            }, ensure_ascii=False), 200, headers


        # Use this after finding chunks:
        log_search_results(chunks, found_policy_numbers, user_query)


        # STEP 9: CHECK RELEVANCE AND FILTER CHUNKS
        relevance_type, filtered_chunks = check_insurance_relevance(contextual_query, chunks, conversation_context)

        # Handle non-insurance queries
        if relevance_type == "non_insurance":
            return json.dumps({
                "answer": "I specialize in helping with insurance and claims questions. Is there anything about your policies or coverage that I can help you with?",
                "query_type": "non_insurance",
                "references": [],
                "session_id": session_id
            }), 200, headers

        # STEP 10: ENHANCE FOR COMPARISONS IF NEEDED
        if query_analysis['primary_intent'] in ['comparison', 'similar_search'] and len(found_policy_numbers) >= 2:
            logging.info(f"ACTION: Enhancing search results for comparison intent.")
            filtered_chunks = get_additional_policies_for_comparison(contextual_query, filtered_chunks)

        # STEP 11: EXTRACT POLICY FIELDS IF NEEDED
        policy_fields = {}
        if query_analysis['primary_intent'] in ['policy_summary', 'specific_person']:
            policy_fields = extract_policy_fields(filtered_chunks)

        # STEP 12: BUILD CONTEXT FOR LLM
        if filtered_chunks:
            context_parts = []
            seen_sources = set()

            for chunk in filtered_chunks:
                section = chunk.get('section', '') or ''
                subsection = chunk.get('subsection', '') or ''

                # Filter unwanted values
                unwanted_values = ['document content', 'general', 'main document', 'page', 'content', 'text', 'chunk']
                if section and section.lower() in unwanted_values:
                    section = ''
                if subsection and subsection.lower() in unwanted_values:
                    subsection = ''

                section_info = section if section else "Policy Information"
                source_key = f"{chunk['document_name']}:{section_info}:{chunk['page']}"

                if source_key not in seen_sources:
                    context_parts.append(
                        f"Source Reference: [{chunk['document_name']} : {section_info} : Page {chunk['page']}]\n"
                        f"Content:\n{chunk['text']}"
                    )
                    seen_sources.add(source_key)

            context = "\n\n".join(context_parts)

            # Add policy number context
            if found_policy_numbers:
                policy_context = f"\n\nPOLICY NUMBERS IN SCOPE: {', '.join(found_policy_numbers)}"
                context += policy_context
        else:
            context = "No relevant policy documents found for this query."

        # Add policy fields to context if available
        if policy_fields and any(policy_fields.values()):
            policy_context = f"""
            Policy Information Found:
            - Policy Holder: {policy_fields.get('holder_name', 'Not specified')}
            - Policy Number: {policy_fields.get('policy_number', 'Not specified')}
            - Coverage Period: {policy_fields.get('start_date', 'Not specified')} to {policy_fields.get('end_date', 'Not specified')}
            """
            context += f"\n\n{policy_context}"

        # Add conversation history
        if conversation_context:
            context += f"\n\nPrevious conversation context:\n{conversation_context}"



        # STEP 13: GENERATE LLM RESPONSE
        # Check for special follow-up scenario
        is_personal_claim_followup = False
        last_interaction = conversation_history.get(session_id, [])[-1] if conversation_history.get(session_id) else None

        # Enhanced follow-up detection
        if last_interaction:
            last_query_type = last_interaction.get('query_type', '')

            # Check if user is responding to our clarification request
            if last_query_type == 'needs_more_context' or is_follow_up_with_details:
                is_personal_claim_followup = True
                query_analysis['needs_policyholder_info'] = True
                logging.info("User provided clarification details - proceeding with full response")

            # Original follow-up logic
            elif (conversation_context and
                ('broke down' in conversation_context.lower() or 'breakdown' in conversation_context.lower()) and
                ('crash' in user_query.lower() or 'accident' in user_query.lower())):
                is_personal_claim_followup = True
                query_analysis['needs_policyholder_info'] = True

        # SCENARIO-BASED PROMPT GENERATION
        if query_analysis['primary_intent'] == 'fnol':
            # SCENARIO B: FNOL handling
            fnol_state = generate_fnol_response(user_query, {}, conversation_history.get(session_id, []))

            enhanced_prompt = f"""
            {settings.SYSTEM_GUIDANCE}

            SCENARIO: First Notice of Loss (FNOL) - Claim Reporting
            Current Stage: {fnol_state['stage']}

            User's message: "{user_query}"
            Previous conversation: {conversation_context}

            YOUR TASK:
            - Acknowledge their loss naturally and empathetically
            - Guide them conversationally through the claim process
            - Collect required information step by step
            - Validate loss type matches their policy
            - Confirm details before issuing claim number

            Context from documents: {context}

            Respond conversationally without bullet points.
            """
        # FNOL-specific: Generate claim number if confirmation detected
        if query_analysis['primary_intent'] == 'fnol':
            fnol_state = generate_fnol_response(user_query, {}, conversation_history.get(session_id, []))

            # Check if user confirmed and we should issue claim number
            if fnol_state['stage'] == 'claim_number_issued' and found_policy_numbers:
                claim_number = generate_claim_number(found_policy_numbers[0])

                # Append claim number to answer
                if not any(phrase in answer.lower() for phrase in ['claim number', 'claim #', 'claim id']):
                    answer += f"\n\nYour claim number is **{claim_number}**. We'll be in touch within 24-48 hours to proceed with your claim."
        elif query_analysis['primary_intent'] == 'policy_info':
            # SCENARIO A: Policy information request
            enhanced_prompt = f"""
            {settings.SYSTEM_GUIDANCE}

            SCENARIO: Policy Information Request

            User's question: "{user_query}"
            Policy context: {conversation_context}

            YOUR TASK:
            - If no policy number: Ask for it conversationally
            - After getting policy number: Provide high-level summary (name, number, product, dates)
            - Follow up: "What else would you like to know?"
            - Answer specific questions naturally in flowing sentences

            Context from documents: {context}

            Respond conversationally. NO bullet points unless it's a complex table scenario.
            """

        elif query_analysis['primary_intent'] == 'comparison':
            # SCENARIO C: Complex comparison requiring table
            enhanced_prompt = f"""
            {settings.SYSTEM_GUIDANCE}

            SCENARIO: Policy Comparison (Table Required)

            User's request: "{user_query}"

            YOUR TASK:
            - Use the markdown table format for side-by-side comparison
            - Include only the most relevant coverage details
            - Keep it organized and scannable

            Context from documents: {context}

            Use the table format from SCENARIO C guidelines.
            """

        else:
            # Default conversational response
            enhanced_prompt = f"""
            {settings.SYSTEM_GUIDANCE}

            User's question: "{user_query}"
            Context: {context}

            Respond conversationally in natural flowing sentences. No bullet points.
            """


        # Generate response
        llm_response = llm_model.generate_content(enhanced_prompt, generation_config={'temperature': 0.2})
        answer = llm_response.text.strip()

        # Post-process: Remove bullet points if not a table response
        if query_analysis['primary_intent'] not in ['comparison', 'similar_search']:
            # Count bullet points - only convert if there are 5 or fewer (simple lists)
            bullet_count = answer.count('•') + answer.count('\n- ') + answer.count('\n* ')

            # Convert bullet points to conversational text for simple responses
            if 0 < bullet_count <= 5:  # Only small lists - preserve complex structures
                conversion_prompt = f"""
                Convert this response to natural conversational flowing text without bullet points.
                Keep the same information but write it as flowing sentences.

                {answer}

                Output only the conversational version.
                """
                try:
                    converted = llm_model.generate_content(conversion_prompt, generation_config={'temperature': 0.1})
                    answer = converted.text.strip()
                    logging.info("✅ Converted bullet points to conversational text")
                except Exception as e:
                    logging.warning(f"Bullet point conversion failed: {e}")
                    pass  # Keep original if conversion fails

        if not answer:
            answer = "I couldn't find specific information about that in your policy documents. Could you provide more details?"

        # STEP 14: GENERATE REFERENCES AND ADD CITATIONS
        references, source_mapping = generate_detailed_references(filtered_chunks, answer)
        answer = add_inline_citations(answer, filtered_chunks, source_mapping)

        # STEP 15: UPDATE CONVERSATION HISTORY
        conversation_history[session_id].append({
            "query": user_query,
            "answer": answer,
            "timestamp": int(time.time()),
            "query_type": query_analysis['primary_intent']
        })

        # Mark policies as clarified after providing detailed answer
        if found_policy_numbers and session_id in policy_clarification_status:
            for pnum in found_policy_numbers:
                policy_clarification_status[session_id][pnum] = True
                logging.info(f"Marked policy {pnum} as clarified for session {session_id}")

        # Keep only recent history
        if len(conversation_history[session_id]) > 15:
            conversation_history[session_id] = conversation_history[session_id][-15:]

        # STEP 16: RETURN RESPONSE
        return json.dumps({
            "answer": answer,
            "query_type": query_analysis['primary_intent'],
            "format_used": query_analysis['format_preference'],
            "references": references,
            "session_id": session_id,
            "needs_clarification": False,
            "needs_policyholder_info": query_analysis.get('needs_policyholder_info', False),
            "is_personal_claim": query_analysis['primary_intent'] == 'personal_claim'
        }, ensure_ascii=False), 200, headers

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        return json.dumps({
            "error": "Technical difficulties. Please try again.",
            "details": str(e)
        }), 500, headers

# -------------------------
# LOCAL TESTING ENDPOINT
# -------------------------
@app.route('/local_test', methods=['POST', 'OPTIONS'])
def local_test():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 200
    return query_documents(request)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)