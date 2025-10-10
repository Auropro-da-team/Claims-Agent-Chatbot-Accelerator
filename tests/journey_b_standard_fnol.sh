#!/bin/bash

# Test Journey: Standard First Notice of Loss (FNOL) for a Car Accident
# This script simulates a user reporting a car accident, providing their policy number,
# and answering questions to file a claim.

SESSION_ID="journey_b_test_$(date +%s)"
BASE_URL="http://localhost:8080/local_test"

echo "--- Starting Test Journey: Standard FNOL ---"
echo "Session ID: $SESSION_ID"
echo ""

# Step 1: User reports a car accident
echo "Step 1: User reports a car accident"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"I need to file a claim, I was in a car accident.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

# Step 2: User provides an incorrect policy number initially
echo "Step 2: User provides an incorrect (renters) policy number"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"My policy number is LP985240156.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

# Step 3: User corrects to the right auto policy number
echo "Step 3: User provides the correct auto policy number"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"Sorry, wrong one. My auto policy is MAI-IL-AUTO-2025-334578.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

# Step 4: User provides the date of the incident
echo "Step 4: User provides the date"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"It happened on October 8th, 2025.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

# Step 5: User provides the location
echo "Step 5: User provides the location"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"On Lake Shore Drive in Chicago.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

# Step 6: User describes what happened
echo "Step 6: User describes the incident"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"I slid on some ice and hit a guardrail. The front bumper is damaged.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

# Step 7: User confirms the details
echo "Step 7: User confirms the summary"
curl -X POST "$BASE_URL" \
-H "Content-Type: application/json" \
-d "{\"query\": \"Yes, that is all correct.\",\"session_id\": \"$SESSION_ID\"}"
echo -e "\n"

echo "--- Test Journey Complete ---"