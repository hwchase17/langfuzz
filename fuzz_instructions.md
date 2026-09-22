Your job is to fuzz/redteam an agent. You do this by generating questions in the required format (same as example_questions.csv) and then running the CLI in non-interactive model to assign a score to them.

You should suggest pairs that ask the same question in slightly different ways, and then the CLI will score whether the answers are semantically the same or not. If they are not - you know one is wrong, you just don't know which one, but this is a great place to start!

Create a csv of results in this directory. It should not contain duplicates. You should add rows iteratively, and when using the CLI to run over them you shou