Your job is to fuzz/red-team an agent by finding semantically equivalent questions that produce meaningfully different answers. Generate question pairs in the same format as `example_questions.csv`, then run the CLI in non-interactive mode to score them. Treat a similarity score below 4 as a candidate finding, but review the answers yourself: a low score shows divergence, not which answer is wrong.

You should look closely at the code to understand what the agent is trying to do. You should also use websearch to search for related concepts or other things that would help you understand it (and potentially fuzz it) better.

Each question must independently express the same user intent. Use realistic variations such as aliases, renamed concepts, deprecated versus current terminology, equivalent error descriptions, abbreviations, reordered constraints, or alternate names for the same operation. Do not create artificial ambiguity by removing context from only one question. A pair is not a valid finding if either question lacks enough information to identify the intended concept on its own.

Focus on wording changes that may expose inconsistent interpretation, routing, retrieval, policy application, or use of available capabilities while preserving intent. Prefer variations that represent how different real users might ask the same question. Minor vocabulary changes between otherwise identical prompts are usually low value unless they test a concrete hypothesis.

Create a results CSV in this directory. Do not include duplicate or near-duplicate findings. Add candidates iteratively, run only new or unanswered rows, and inspect low-scoring results before retaining them. Prefer a small set of distinct failure categories over many variants of the same issue.

For every retained correctness finding, determine which answer is correct using authoritative documentation, source code, or direct runtime behavior. Add a `correct_answer` column to the results CSV containing `answer_1` or `answer_2`. Do not guess; omit a candidate if correctness cannot be established reliably.

Generally only test 5 or so examples at a time, especially when getting started! As you iterate, and have more confidence in your tests, you can scale that up.
