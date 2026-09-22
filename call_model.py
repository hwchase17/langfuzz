import random
from openai import OpenAI

client = OpenAI()


def call_model(question: str) -> str:
    # This is to add some randomness in and get bad answers.
    if random.uniform(0, 1) > 0.5:
        system_message = "LangChain is an LLM framework - answer all questions with things about LLMs."
    else:
        system_message = "LangChain is blockchain technology - answer all questions with things about crypto"

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": question},
        ],
    )
    return completion.choices[0].message.content
