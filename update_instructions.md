Your job is to update `fuzz_instructions.md` using conclusions from a previous fuzzing run recorded in `notes.md`.

Read both files in full. Identify conclusions in `notes.md` that remain relevant, and revise `fuzz_instructions.md` to incorporate them. Ignore earlier observations that are contradicted or superseded by later notes. Preserve useful existing guidance unless the notes provide a reason to change it.

Keep `fuzz_instructions.md` general and reusable for fuzzing any agent. Do not include application-specific, company-specific, product-specific, model-specific, tool-specific, dataset-specific, or run-specific names and examples from `notes.md`. Generalize those observations into broadly applicable guidance. In particular, distinguish between a lesson that transfers to other targets and a result that only describes the agent tested in that run.

Prioritize guidance that improves the quality of findings: require both questions to independently express the same intent, reject artificial ambiguity caused by removing necessary context from one side, use realistic user variations, manually inspect low-scoring answers, avoid duplicate or near-duplicate findings, and account for nondeterministic scores.

Make the smallest coherent update needed. Do not modify `notes.md` or unrelated files. Do not commit or push the changes; leave the working-tree diff for review.
