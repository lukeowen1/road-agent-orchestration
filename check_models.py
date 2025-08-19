#!/usr/bin/env python3
"""
Check which OpenAI models you have access to
"""

import os
from openai import OpenAI

# Make sure your API key is set
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Please set OPENAI_API_KEY environment variable")
    exit(1)

client = OpenAI(api_key=api_key)

print("Checking available models...")

# Common models to test
models_to_test = [
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "gpt-4",
    "gpt-4-turbo-preview",
    "gpt-4-1106-preview",
    "gpt-4-0125-preview",
    "gpt-4o",
    "gpt-4o-mini",
]

available_models = []

for model in models_to_test:
    try:
        # Try a minimal completion
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1
        )
        print(f"{model}: Available")
        available_models.append(model)
    except Exception as e:
        if "model_not_found" in str(e):
            print(f"{model}: Not available")
        else:
            print(f"{model}: Error - {str(e)[:50]}")

print("\n" + "="*50)
print(f"You have access to {len(available_models)} model(s):")
for model in available_models:
    print(f"   - {model}")

if available_models:
    print(f"Recommended: Use '{available_models[0]}' for the evaluator")
    print(f"Run with: python run_evaluator.py ./your-project {available_models[0]}")
else:
    print("No models available. Please check your API key and billing.")