import re
import logging
from app.services.llm_service import llm_model
from app.utils.history_manager import conversation_history
from app.utils.parsers import extract_policy_identifier

# -------------------------
# ENHANCED QUERY ANALYSIS
# -------------------------
def analyze_query_intent(query: str) -> dict:
    """
    Analyze user query to determine intent using a hybrid regex and LLM approach.
    Combines rich domain patterns + LLM fallback for edge cases.
    """
    query_lower = query.lower()

    # -------- Rich Regex Patterns --------
    patterns = {
        'personal_claim': [
            r'my\s+(floor|roof|car|house|apartment|business|property)',
            r'i\s+have\s+(water\s+damage|fire|theft|accident)',
            r'there\s+is\s+(damage|leak|fire|break)',
            r'something\s+happened\s+to\s+my',
            r'(water|fire|storm|wind)\s+damage\s+(to\s+)?my',
            r'my\s+.+\s+is\s+(leaking|damaged|broken|flooded)',
            r'i\s+need\s+to\s+(file|submit)\s+a\s+claim',
            r'(car|vehicle)\s+(broke\s+down|breakdown)',
            r'it\s+was\s+due\s+to\s+(a\s+)?(crash|accident|collision)',
            r'but\s+it\s+was\s+(due\s+to|because\s+of|from)\s+(a\s+)?(crash|accident|collision)',
            r'(crashed|accident\s+happened|collision\s+occurred)',
            r'due\s+to\s+(crash|accident|collision)'
        ],
        'open_ended': [
            r'show me all', r'list all', r'give me all', r'what do you have',
            r'show all documents', r'all policies', r'everything about'
        ],
        'fnol': [
            r'file.*claim', r'report.*loss', r'start.*claim', r'submit.*claim',
            r'claim.*number', r'register.*loss', r'incident.*report'
        ],
        'policy_info': [
            r'my.*policy', r'policy.*information', r'policy.*details',
            r'coverage.*summary', r'what.*covered.*my', r'policy.*number'
        ],
        'policy_summary': [
            r'what is.*covered', r'policy summary', r'coverage summary',
            r'what does.*policy cover', r'policy details', r'tell me about.*policy',
            r'pull up.*policy', r'.*is covered under', r'show me.*policy',
            r'pull up policy for'
        ],
        'similar_search': [
            r'pull up.*similar', r'find.*similar', r'show.*similar', r'other.*like',
            r'comparable.*policy', r'alternatives', r'similar.*coverage',
            r'most similar.*policy', r'similar.*policy', r'similar.*to'
        ],
        'specific_person': [
            r'what is.*covered under', r'.*policy holder', r'.*insured person',
            r'coverage for.*', r'policy for.*'
        ],
        'comparison': [
            r'compare', r'versus', r'vs', r'difference between', r'which is better',
            r'similar policies', r'alternatives', r'most similar', r'similar.*in.*terms',
            r'renewal.*similar', r'sell.*renewal'  # ENHANCED: Better comparison detection
        ],
        'coverage_check': [
            r'is.*covered', r'does.*cover', r'coverage for', r'covered under',
            r'includes.*', r'excludes.*'
        ],
        'limits_deductibles': [
            r'what are.*limits', r'deductible', r'maximum coverage', r'threshold',
            r'how much.*covered', r'will it cover.*\d+', r'claim exceeds.*coverage'
        ]
    }
    detected_intents = []
    for intent, pattern_list in patterns.items():
        if any(re.search(pattern, query_lower) for pattern in pattern_list):
            detected_intents.append(intent)

    # -------- LLM fallback if no regex match --------
    if not detected_intents:
        logging.info(f"[Intent] No regex match for '{query}'. Using LLM fallback.")
        intent_classifier_prompt = f"""
        You are an expert at classifying insurance-related user queries.
        Classify this query into one of:
        ['policy_summary', 'coverage_check', 'limit_conflict', 'comparison', 'personal_claim', 'open_ended', 'general']

        Examples:
        - "pull up the lemonade renters policy" -> policy_summary
        - "my policy covers 20k but damage is 50k" -> limit_conflict
        - "is flood covered" -> coverage_check
        - "my car was in an accident" -> personal_claim
        - "what can you do?" -> open_ended
        - "that's interesting" -> general

        Query: "{query}"
        Intent:
        """
        try:
            response = llm_model.generate_content(intent_classifier_prompt)
            llm_intent = response.text.strip().replace("'", "").replace('"', '')
            if llm_intent:
                detected_intents.append(llm_intent)
        except Exception as e:
            logging.error(f"LLM intent fallback failed: {e}")
            detected_intents.append('general')

    # -------- Decision Logic --------
    primary_intent = 'general'

    # SCENARIO B: FNOL (First Notice of Loss)
    if 'personal_claim' in detected_intents or 'fnol' in detected_intents:
        primary_intent = 'fnol'
    # SCENARIO A: Policy Information
    elif 'policy_info' in detected_intents or 'policy_summary' in detected_intents or 'specific_person' in detected_intents:
        primary_intent = 'policy_info'
    # SCENARIO C: Complex queries needing tables
    elif 'comparison' in detected_intents or 'similar_search' in detected_intents:
        primary_intent = 'comparison'
    elif detected_intents:
        primary_intent = detected_intents[0]

    format_preference = 'text'
    if primary_intent == 'personal_claim':
        format_preference = 'clarification'
    elif primary_intent in ['comparison', 'policy_summary', 'specific_person', 'limit_conflict']:
        format_preference = 'needs_clarification'  # to ask questions first
    elif primary_intent in ['coverage_check', 'limits_deductibles']:
        format_preference = 'structured'

    return {
        'primary_intent': primary_intent,
        'all_intents': detected_intents,
        'format_preference': format_preference,
        'needs_clarification': primary_intent == 'open_ended' and len(detected_intents) == 1,
        'needs_policyholder_info': primary_intent == 'personal_claim',
        'needs_follow_up': primary_intent in ['policy_summary', 'specific_person']
    }


def detect_incident_context_in_history(session_id: str, conversation_history: dict) -> str:
    """
    Intelligently detect if user mentioned an incident/claim in recent conversation.
    Returns the original incident description or empty string.

    Uses LLM for intelligent detection without hardcoded keywords.
    """
    if session_id not in conversation_history or not conversation_history[session_id]:
        return ""

    # Look at last 3 interactions
    recent_history = conversation_history[session_id][-8:]

    for interaction in recent_history:
        # Check if bot asked for policy number (indicating previous claim mention)
        if interaction.get('query_type') == 'policy_required':
            user_query = interaction.get('query', '').strip()

            if not user_query or len(user_query) < 5:
                continue

            # Use LLM to detect incident intelligently
            detection_prompt = f"""
            Analyze the user's query to determine if it describes a real event that has already happened (like an accident, damage, or breakdown).
            - "my car broke down" -> YES
            - "is water damage covered?" -> NO
            - "there was a fire in my kitchen" -> YES
            - "what if there is a fire?" -> NO
            Query: "{user_query}"
            Does this describe a real event that already happened? Answer with only YES or NO.
            """

            try:
                response = llm_model.generate_content(
                    detection_prompt,
                    generation_config={'temperature': 0.0, 'max_output_tokens': 10}
                )

                answer = response.text.strip().upper()

                if "YES" in answer:
                    logging.info(f"✅ LLM DETECTED INCIDENT: '{user_query}'")
                    return user_query
                else:
                    logging.info(f"ℹ️  LLM: No incident in '{user_query[:50]}'")

            except Exception as e:
                logging.error(f"Incident detection LLM error: {e}")
                # Fallback: Use minimal pattern matching for obvious cases
                obvious_patterns = [
                    r'\bmy\s+\w+\s+(broke|crashed|damaged|failed|stopped)',
                    r'\b(accident|collision|theft|fire|flood|leak|burst)\b',
                    r'\bthere\s+(is|was)\s+damage\b'
                ]

                if any(re.search(p, user_query.lower()) for p in obvious_patterns):
                    logging.info(f"⚠️  FALLBACK: Pattern matched '{user_query}'")
                    return user_query

    return ""

# -------------------------
# ENHANCED RELEVANCE CHECKER
# -------------------------
def check_insurance_relevance(query: str, chunks: list, conversation_context: str = "") -> tuple:
    # Check for greeting patterns
    greeting_patterns = [
        r'\b(hi|hello|hey|good morning|good afternoon|good evening)\b',
        r'\b(how are you|what can you do|help me|assist me)\b',
        r'\b(thanks|thank you|bye|goodbye)\b'
    ]

    query_lower = query.lower()
    is_greeting = any(re.search(pattern, query_lower) for pattern in greeting_patterns)

    if is_greeting and len(query.split()) <= 5:
        return "greeting", []

    # Check for insurance relevance
    insurance_keywords = [
        'insurance', 'policy', 'coverage', 'claim', 'deductible', 'premium', 'liability',
        'fire', 'flood', 'damage', 'theft', 'accident', 'property', 'business', 'personal',
        'covered', 'excluded', 'limit', 'repair', 'replacement', 'loss', 'renewal', 'similar'
    ]

    is_insurance_related = any(keyword in query_lower for keyword in insurance_keywords)

    if not is_insurance_related:
        relevance_prompt = f"""
        Analyze if this query is related to insurance, claims, policy coverage, or situations that might need insurance coverage.
        Query: "{query}"
        Previous conversation context: {conversation_context}
        Respond with only "YES" or "NO".
        """

        relevance_response = llm_model.generate_content(relevance_prompt)
        is_insurance_related = "YES" in relevance_response.text.strip().upper()

    if not is_insurance_related:
        return "non_insurance", []

    # TRUST VECTOR SEARCH - minimal filtering only
    if not chunks:
        return "insurance", []

        # TRUST vector search - minimal filtering only
    filtered_chunks = []
    for chunk in chunks[:20]:  # Take more chunks
        text = chunk.get('text', '')
        if text and len(text) > 30:  # Much lower threshold
            filtered_chunks.append(chunk)

    if len(filtered_chunks) >= 15:  # Allow more chunks through
        filtered_chunks = filtered_chunks[:15]

    return "insurance", filtered_chunks

def generate_fnol_response(user_query: str, policy_info: dict, conversation_history: list) -> dict:
    """
    Generate appropriate FNOL (First Notice of Loss) response based on conversation stage
    """
    stages = {
        'initial_loss_report': 1,
        'policy_verification': 2,
        'loss_type_validation': 3,
        'incident_details': 4,
        'confirmation': 5,
        'claim_number_issued': 6
    }

    # Determine current stage from conversation
    current_stage = 'initial_loss_report'

    if conversation_history:
        last_interaction = conversation_history[-1]
        last_query_type = last_interaction.get('query_type', '')

        if 'policy_required' in last_query_type:
            current_stage = 'policy_verification'
        elif 'loss_validated' in last_query_type:
            current_stage = 'incident_details'
        elif 'details_collected' in last_query_type:
            current_stage = 'confirmation'
        elif 'confirmed' in user_query.lower():
            current_stage = 'claim_number_issued'

    return {
        'stage': current_stage,
        'needs_policy': current_stage in ['initial_loss_report', 'policy_verification'],
        'needs_details': current_stage == 'incident_details',
        'ready_for_confirmation': current_stage == 'confirmation'
    }

def is_relevant_for_comparison(doc_name: str, query: str, mentioned_policies: list) -> bool:
    """
    SCALABLE: Check if document is relevant for comparison
    No hardcoding - works with any number of documents
    """
    doc_lower = doc_name.lower()
    query_lower = query.lower()

    # Check if document name appears in query
    if any(name.lower() in doc_lower for name in mentioned_policies):
        return True

    # Check for insurance-related terms
    insurance_terms = ['insurance', 'policy', 'coverage', 'commercial', 'business', 'auto', 'renters']
    if any(term in doc_lower for term in insurance_terms):
        return True

    # Check for geographic/business type relevance
    if any(word in query_lower for word in doc_lower.split()[:2]):  # Check first 2 words
        return True

    return False

def determine_policy_requirement(query_analysis: dict, user_query: str = "") -> dict:
    """
    FIXED: Now properly requires policy numbers for ALL policy-related queries
    with empathetic, LLM-generated clarification messages when needed.
    """
    intent = query_analysis['primary_intent']

    requirements = {
        'min_policies': 1,  # FIXED: Default to requiring 1 policy number
        'max_policies': 1,
        'required': True,   # FIXED: Default to requiring policy numbers
        'ask_message': None
    }

    # Only override for specific cases
    if intent == 'fnol':
        # FNOL requires policy number after acknowledging loss
        requirements.update({
            'min_policies': 1,
            'max_policies': 1,
            'required': True,
            'ask_message': None  # Will be generated contextually
        })
    elif intent in ['policy_info', 'policy_summary', 'specific_person']:
    # Policy info always needs the policy number
        requirements.update({
            'min_policies': 1,
            'max_policies': 1,
            'required': True,
            'ask_message': "What's your policy number? You can find it on your policy documents."
        })
    elif intent in ['comparison', 'similar_search']:
        requirements.update({
            'min_policies': 2,
            'max_policies': 3,
            'required': True,
            'ask_message': "To compare policies, I'll need at least 2 policy numbers."
        })
    elif intent in ['open_ended', 'general', 'greeting']:
        # ONLY these intents don't require policy numbers
        requirements.update({
            'min_policies': 0,
            'max_policies': 0,
            'required': False,
            'ask_message': ""
        })

    # === Empathetic message finalizer ===
    if requirements['required'] and not requirements['ask_message']:
        try:
            # Detect if user_query has loss/claim-related keywords
            loss_keywords = ["leak", "burst", "damage", "fire", "accident", "stolen", "injury", "broken", "loss"]
            is_loss_event = any(kw in user_query.lower() for kw in loss_keywords)

            if is_loss_event:
                llm_prompt = (
                    f"The user said: '{user_query}'.\n\n"
                    "You are an empathetic insurance claims assistant.\n"
                    "1) Acknowledge their situation naturally (e.g., 'I’m sorry to hear about the water damage').\n"
                    "2) Make it clear that the policy number is REQUIRED before you can check any coverage or details.\n"
                    "3) Politely ask them to provide their policy number from their declarations page or policy document.\n"
                    "Be supportive, concise, and professional."
                )
            else:
                llm_prompt = (
                    f"The user said: '{user_query}'.\n\n"
                    "You are a professional insurance assistant.\n"
                    "1) Do not add empathy since this is not a loss/damage situation.\n"
                    "2) Clearly state that the policy number is REQUIRED before you can check coverage or details.\n"
                    "3) Politely ask them to provide their policy number from their declarations page or policy document.\n"
                    "Keep tone polite and concise."
                )

            requirements['ask_message'] = llm_model.generate_content(
                llm_prompt, generation_config={'temperature': 0.3}
            ).text.strip()

        except Exception as e:
            logging.warning(f"LLM clarification generation failed in determine_policy_requirement: {e}")
            requirements['ask_message'] = (
                "I want to help, but before I can look up coverage details, I’ll need your policy number. "
                "Providing the policy number is mandatory. Please share it from your declarations page or policy document."
            )

    return requirements



def should_ask_for_policy_numbers(query_analysis: dict, found_policy_numbers: list, conversation_context: str, session_id: str = None) -> str:
    """
    FIXED: Central decision function - now ALWAYS asks for policy numbers when none found
    Returns None if no request needed, or message string if policy numbers needed
    """

    # MEMORY: Check session history for previously used policy numbers
    if session_id and session_id in conversation_history:
        for interaction in conversation_history[session_id][-3:]:  # Check last 3 interactions
            hist_answer = interaction.get('answer', '')
            # If we see a successful policy table response, extract policy numbers from it
            if '|' in hist_answer and 'Policy' in hist_answer:
                table_policies = extract_policy_identifier(hist_answer)
                if table_policies:
                    found_policy_numbers.extend(table_policies)

        # Remove duplicates
        found_policy_numbers[:] = list(dict.fromkeys(found_policy_numbers))

    requirements = determine_policy_requirement(query_analysis)

    # CRITICAL FIX 1: If policy numbers aren't required for this intent, don't ask
    if not requirements['required']:
        return None

    # CRITICAL FIX 2: For ANY insurance query requiring policy info, we MUST have a policy number
    if len(found_policy_numbers) == 0:
        return "To provide accurate information about your coverage, I need your specific policy number. Please provide your policy number (found on your policy documents or declarations page)."

    # Check if we have sufficient policy numbers for comparison queries
    if requirements['min_policies'] > 1 and len(found_policy_numbers) < requirements['min_policies']:
        if len(found_policy_numbers) == 1:
            return f"I found policy number **{found_policy_numbers[0]}**. To complete the comparison, I need one more policy number. Please provide the second policy number."
        else:
            return f"I found {len(found_policy_numbers)} policy number(s) but need at least {requirements['min_policies']} for this request. Please provide the additional policy number(s)."

    # We have sufficient policy numbers
    return None
