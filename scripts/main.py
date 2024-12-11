from typing import Dict, List
from autogen import ConversableAgent
import sys
import os
from math import sqrt

def fetch_restaurant_data(restaurant_name: str) -> Dict[str, List[str]]:
    # TODO
    # This function takes in a restaurant name and returns the reviews for that restaurant. 
    # The output should be a dictionary with the key being the restaurant name and the value being a list of reviews for that restaurant.
    # The "data fetch agent" should have access to this function signature, and it should be able to suggest this as a function call. 
    # Example:
    # > fetch_restaurant_data("Applebee's")
    # {"Applebee's": ["The food at Applebee's was average, with nothing particularly standing out.", ...]}
    restaurant_reviews = []
    try:
        with open("restaurant-data.txt", "r") as f:
            for line in f:
                # Split the line into restaurant name and review
                if ". " in line:
                    name, review = line.split(". ", 1)
                    if name.replace("-", " ").strip().lower() == restaurant_name.replace("-", " ").strip().lower():
                        restaurant_reviews.append(review.strip())
    except FileNotFoundError:
        print("Error: 'restaurant-data.txt' not found.")
    except Exception as e:
        print(f"Error while fetching data: {e}")
    return {restaurant_name: restaurant_reviews}

def calculate_overall_score(restaurant_name: str, food_scores: List[int], customer_service_scores: List[int]) -> Dict[str, float]:
    # TODO
    # This function takes in a restaurant name, a list of food scores from 1-5, and a list of customer service scores from 1-5
    # The output should be a score between 0 and 10, which is computed as the following:
    # SUM(sqrt(food_scores[i]**2 * customer_service_scores[i]) * 1/(N * sqrt(125)) * 10
    # The above formula is a geometric mean of the scores, which penalizes food quality more than customer service. 
    # Example:
    # > calculate_overall_score("Applebee's", [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    # {"Applebee's": 5.048}
    # NOTE: be sure to that the score includes AT LEAST 3  decimal places. The public tests will only read scores that have 
    # at least 3 decimal places.
    N = len(food_scores)
    if N == 0 or N != len(customer_service_scores):
        return {restaurant_name: 0.000}
    total_score = 0
    for i in range(N):
        score = sqrt(food_scores[i]**2 * customer_service_scores[i])
        total_score += score  * (10 /(N * sqrt(125)))
    total_score = f"{total_score:.3f}"
    return {restaurant_name: total_score}

def get_entrypoint_system_message() -> str:
    """Returns the system message for the entry point agent."""
    return (
        "You are a restaurant review analysis assistant. Your role is to:"
        "\n1. Extract restaurant names from user queries"
        "\n2. Coordinate with other agents to fetch and analyze restaurant reviews"
        "\n3. Ensure proper handling of the data flow between agents"
        "\nWhen analyzing queries, focus on identifying the restaurant name regardless of case sensitivity."
    )

def get_data_fetch_agent_prompt(restaurant_query: str) -> str:
    """Generate prompt for the data fetch agent."""
    return (
        f"Please analyze this query: '{restaurant_query}' and extract the restaurant name. "
        "Then call the fetch_restaurant_data function with the extracted restaurant name. "
        "The query might contain phrases like 'How good is' or 'What would you rate' - "
        "ignore these and focus on the restaurant name itself. "
        "For example, from 'How good is Subway as a restaurant', extract just 'Subway'. "
        "Handle case variations (like 'subway' or 'SUBWAY') appropriately."
    )

def get_review_analyzer_system_message() -> str:
    """Generate prompt for review analyzer agent."""
    review_analyzer_system_message = (
        "You are a review analysis agent specialized in extracting scores from restaurant reviews."
        "Your task is CRITICAL: you must extract EXACTLY one food score AND one service score for EACH review."
        "For each review, you must identify two specific scores:"
        "1. food_score (1-5): Based on food quality keywords"
        "2. customer_service_score (1-5): Based on service quality keywords"
        "YOUR TOP PRIORITY IS TO ENSURE YOU EXTRACT EXACTLY ONE FOOD SCORE AND ONE CUSTOMER SERVICE SCORE PER REVIEW."
        "Score mapping:"
        "- Score 1/5: awful, horrible, disgusting"
        "- Score 2/5: bad, unpleasant, offensive"
        "- Score 3/5: average, uninspiring, forgettable"
        "- Score 4/5: good, enjoyable, satisfying"
        "- Score 5/5: awesome, incredible, amazing"
        "CRITICAL RULES:"
        "1. You MUST find EXACTLY ONE food keyword and ONE service keyword in each review"
        "2. ALWAYS output both scores for every review - no exceptions"
        "3. Double-check that your food_scores and customer_service_scores lists have IDENTICAL lengths"
        "Format your response exactly like this:"
        "RESTAURANT_NAME: [name]"
        "SCORES:"
        "["
        "{'food_score': N, 'customer_service_score': N },"
        "{'food_score': N, 'customer_service_score': N },"
        "...continue for each review"
        "]"
        "For each review, provide both scores in this exact JSON-like format."
        "Rules:"
        "1. EVERY review MUST have exactly ONE food score and ONE service score."
        "2. Use ONLY the exact keywords provided to determine scores."
        "3. Do not skip any reviews."
        "4. Use numbers for scores (not text)."
        "5. Keep this exact format."
    )
    return review_analyzer_system_message

def get_review_analyzer_prompt(data_fetch_summary: str) -> str:
    """Generates prompt for the review analyzer agent using the summary from data fetch agent."""
    try:
        data = eval(data_fetch_summary["carryover"][0])
        restaurant_name = list(data.keys())[0]
        reviews = data[restaurant_name]
        return (
            f"Please analyze the following reviews for {restaurant_name}."
            "For each review, identify the keywords related to food quality and customer service, then assign appropriate scores (1-5)."
            "Remember to look for exact matches of the scoring keywords."
            "Reviews to analyze:"
            f"{chr(10).join(f'Review {i+1}: {review}' for i, review in enumerate(reviews))}"
            "Please analyze each review and provide the food_score and customer_service_score based on the keywords found."
            "Before submitting:"
            "Verify you found TWO scores for EACH review"
            "Count total food scores and service scores - they MUST be equal"
        )
    except Exception as e:
        return f"Error processing summary: {e}. Please ensure the summary contains valid restaurant review data."
    
def get_scoring_agent_system_message() -> str:
    """Returns the system message for the scoring agent."""
    system_message =  (
        "You are a scoring analysis agent that calculates final restaurant scores."
        "You will receive review analysis in this format:"
        "RESTAURANT_NAME: [name]"
        "SCORES:"
        "["
        "{'food_score': N, 'customer_service_score': N},"
        "{'food_score': N, 'customer_service_score': N},"
        "..."
        "]"
        "Your task is to:"
        "1. Extract the restaurant name from between 'RESTAURANT_NAME:' and 'REVIEW_SCORES:'"
        "2. Extract all scores from the section between 'REVIEW_SCORES:' and 'END_SCORES'"
        "3. Create two equal-length lists:"
            "- food_scores: all food scores in order"
            "- customer_service_scores: all service scores in order"
        "4. Make exactly ONE call to calculate_overall_score with:"
            "- restaurant_name"
            "- food_scores list"
            "- customer_service_scores list"
    )
    return system_message

def get_scoring_agent_prompt(review_analysis_summary: str) -> str:
    """Generates prompt for the scoring agent using the review analysis summary."""
    system_prompt =  (
        "Please extract scores from this analysis and calculate the final restaurant score:"
        f"{review_analysis_summary}"
        "Steps:"
        "1. Find the restaurant name after 'RESTAURANT_NAME:'"
        "2. Parse ALL scores between 'REVIEW_SCORES:' and 'END_SCORES'"
        "3. Create two lists of equal length:"
            "- food_scores = [score1, score2, ...]"
            "- customer_service_scores = [score1, score2, ...]"
        "4. Call calculate_overall_score(restaurant_name, food_scores, customer_service_scores)"

        "IMPORTANT:"
        "- Make only ONE function call"
        "- Ensure both score lists have the same length"
        "- Verify all scores are numbers between 1 and 5"
        "- Include ALL scores from ALL reviews"
        "- Return the exact result without modification"
    )
    return system_prompt
    
# TODO: feel free to write as many additional functions as you'd like.

# Do not modify the signature of the "main" function.
def main(user_query: str):
    entrypoint_agent_system_message = get_entrypoint_system_message() # TODO
    # example LLM config for the entrypoint agent
    llm_config = {"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY"), "temperature": 0.1}]}
    # the main entrypoint/supervisor agent
    entrypoint_agent = ConversableAgent("entrypoint_agent", 
                                        system_message=entrypoint_agent_system_message, 
                                        llm_config=llm_config,
                                        human_input_mode="NEVER")

    # Define the query for the data fetch agent
    restaurant_query = user_query.strip()
    data_fetch_prompt = get_data_fetch_agent_prompt(restaurant_query)

    data_fetch_agent = ConversableAgent(
        name="data_fetch_agent",
        system_message=("You are a data fetch agent specialized in analyzing restaurant queries. "
            "Your task is to extract the restaurant name from queries and use the fetch_restaurant_data function "
            "to retrieve reviews. For example, from 'How good is Subway' you should extract 'Subway' and fetch its data."
            "In the end add the word Good bye to the list of reviews aftre fetching reviews."
            ),
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
    )
    data_fetch_agent.register_for_llm(name="fetch_restaurant_data", description="Fetches the reviews for a specific restaurant.")(fetch_restaurant_data)
    entrypoint_agent.register_for_execution(name="fetch_restaurant_data")(fetch_restaurant_data)

    review_analyzer_agent = ConversableAgent(
        name="review_analyzer_agent",
        system_message=get_review_analyzer_system_message(),
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    scoring_agent = ConversableAgent(
        name="scoring_agent",
        system_message=get_scoring_agent_system_message(),
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
    )
    scoring_agent.register_for_llm(
        name="calculate_overall_score",
        description="Calculates the overall score for a restaurant based on food and service scores."
    )(calculate_overall_score)
    entrypoint_agent.register_for_execution(
        name="calculate_overall_score"
    )(calculate_overall_score)

    # Initiate chat with the entry point agent
    result = entrypoint_agent.initiate_chats([
        {
            "message": data_fetch_prompt, 
            "recipient": data_fetch_agent, 
            "max_turns": 2, 
            "summary_method": "last_msg"
        },
        {
            "recipient": review_analyzer_agent,
            "max_turns": 1,
            "message": lambda sender, recipient, last_summary: get_review_analyzer_prompt(last_summary),
            "summary_method": "last_msg"
        },
        {
            "recipient": scoring_agent,
            "max_turns": 2,
            "message": lambda sender, recipient, last_summary: get_scoring_agent_prompt(last_summary),
            "summary_method": "last_msg"
        }
    ])
    print(result)
    
    # TODO
    # Fill in the argument to `initiate_chats` below, calling the correct agents sequentially.
    # If you decide to use another conversation pattern, feel free to disregard this code.
    
    # Uncomment once you initiate the chat with at least one agent.
    #result = entrypoint_agent.initiate_chats([{}])
    
# DO NOT modify this code below.
if __name__ == "__main__":
    assert len(sys.argv) > 1, "Please ensure you include a query for some restaurant when executing main."
    main(sys.argv[1])