from src.local_llm import extract_actions_with_llm

transcript = """
Meera will prepare the website content by October 16.
Arjun will test the website by October 17.
"""

try:
    actions = extract_actions_with_llm(transcript)
    print("\nExtracted action items:")
    for action in actions:
        print(action)
except Exception as error:
    print(f"Test failed: {error}")