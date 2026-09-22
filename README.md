
# LangFuzz: Red Teaming for Language Models
LangFuzz is a command line tool designed to perform red teaming on language model applications and add any points of interest to a [LangSmith Dataset](https://docs.smith.langchain.com/). It generates pairs of similar questions and compares the responses to identify potential failure modes in chatbots or other language model-based systems. For those coming from a software engineering background: this similar to a particular type of [fuzz testing](https://www.blackduck.com/glossary/what-is-fuzz-testing.html#:~:text=Definition,as%20crashes%20or%20information%20leakage.) called [metamorphic testing](https://arxiv.org/abs/2002.12543).

## Installation
To install LangFuzz, use pip:

```
pip install langfuzz
```

## Usage

### Step 1: define a model file
First, define a model file that calls your model. This file should expose a sync OR async function called `call_model` that takes in a string and returns a string. An example file is found in [call_model.py](call_model.py). Example model file:

```python
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

```

### Step 2: define a configuration file

Next, you need to define a configuration file. 

The `config.yaml` file should contain the following keys:
- `chatbot_description`: A description of the chatbot being tested.
- `model_file`: Path to the Python file containing the call_model function

Example config.yaml:
```
chatbot_description: "Chat over LangChain Docs"
model_file: "call_model.py"
```

It may optionally contain other keys (see [Options](#options) and [Additional Configuration](#additional-configuration) below).

### Step 3: set any environment variables

This requires several environment variables to run:

- `OPENAI_API_KEY`: required for accessing OpenAI model
- [OPTIONAL] `LANGSMITH_API_KEY`: required for sending generated data to a LangSmith dataset.

```
export OPENAI_API_KEY=...
export LANGSMITH_API_KEY=...
```

### Step 4: run the red teaming

To run the red teaming process, use the following command:
```
langfuzz config.yaml [options]
```

### Step 5: curate datapoints

As the redteaming is run, pairs of datapoints will be shown to you in the command line. From there, you can choose to add both, one, or neither to a LangSmith dataset.

- **Enter**: To add both inputs to the dataset, just press enter
- **`1`**: If you want to add only the first input to the dataset, enter `1`
- **`2`**: If you want to add only the second input to the dataset, enter `2`
- **`3`**: If you don't want to add either input to the dataset, enter `3`
- **`q`**: To quit, enter `q`

If you add a datapoint to a LangSmith dataset, it will be added with a single input key `question` and no output key.

## Options

- `--dataset_id`: ID of the dataset to use (optional)
- `--n`: Number of questions to generate (default: 10)
- `--max_concurrency`: Maximum number of concurrent requests to the model (default: 10)
- `--n_prefill_questions`: Number of questions to prefill the dataset with (default: 10)
- `--max_similarity`: Maximum similarity score to accept (default: 10)
- `-p`, `--persistence-path`: Path to the persistence file (optional)

These options can additionally be provided as part of the configuration file.

## Use question pairs from a CSV

To score existing question pairs instead of generating them, create a CSV with `question_1` and `question_2` columns:

```csv
question_1,question_2
What is LangChain?,Can you explain LangChain?
```

Then run:

```
langfuzz-csv config.yaml example_questions.csv [options]
```

This runs both questions through the configured `call_model`, scores the answer similarity, and presents qualifying pairs for the same interactive LangSmith curation flow. Rows with populated `answer` or both `answer_1` and `answer_2` columns are skipped by default; pass `--rerun` to run every row. It supports `--dataset_id`, `--max_concurrency`, and `--max_similarity`; `input_1` and `input_2` are also accepted as CSV column names.

Add every qualifying scored pair directly to the dataset without prompting:

```
langfuzz-csv config.yaml example_questions.csv --non-interactive
```

Each dataset example contains both questions as inputs and both answers, the similarity score, and the judge reasoning as outputs. Use `--rows` to run selected 1-based data rows (the header is not counted); comma-separated rows and inclusive ranges can be combined:

```
langfuzz-csv config.yaml example_questions.csv --non-interactive --rows 1,3-5
```

## Additional Configuration

You can also configure more aspects of the redteaming agent.

- `judge_model`: the model to use to judge whether two pairs are similar
- `question_gen_model`: the model to use to generate pairs of questions
- `judge_prompt`: the prompt to use to judge whether two pairs are similar
- `question_gent_prompt`: the prompt to use to generate pairs of questions

## How It Works

The tool generates pairs of similar questions based on the provided chatbot description.
It sends these questions to the chatbot and compares the responses.
A judge model evaluates the similarity of the responses on a scale of 1-10.
Results with similarity scores below the max_similarity threshold are presented for review.
Users can choose to add the questions to a dataset for further analysis or training.
Persistence
If a persistence path is provided, the tool will save generated questions and dataset information between runs. This allows for continuous red teaming sessions without duplicating questions.

## Use without LangSmith

You can also use this redteaming agent without LangSmith and dump all the results to a local file. To do this, use the following command:

```
langfuzz-dump config.yaml results.json [options]
```
