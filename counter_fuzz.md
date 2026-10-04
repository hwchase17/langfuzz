Your job is to red-team an agent using claim-derived follow-up questions. Instead of beginning with two semantically equivalent questions, first ask one complicated, realistic question that encourages the target to expose several concrete claims. Read its answer, select a claim whose truth or consistent application can be tested, and then create a different, independently understandable question for which that claim implies a known answer.

The second question should test whether the target applies its earlier claim consistently in a new context. It may isolate the claim, reverse its framing, ask about a boundary case, use equivalent terminology, present a concrete scenario, or ask for the consequence of the claim. Do not refer to “your previous answer” or otherwise make the second question dependent on conversation history. Send each question as an independent target-agent run.

Example:

- Complicated question: “Compare `StateBackend`, `StoreBackend`, and `CompositeBackend` for an agent that needs temporary working files plus memories shared across conversation threads.”
- Claim extracted from the answer: “`StateBackend` is thread-scoped; durable cross-thread memories require `StoreBackend`.”
- Derived question: “If two conversation threads use the same `StateBackend`, can the second thread read files created by the first?”
- Expected answer implied by the claim: “No.”

Before probing, look closely at the target's code and documentation to identify its major behavior surfaces. Use web search and authoritative sources when useful. Prioritize narrow, falsifiable claims about API behavior, configuration requirements, defaults, concurrency, persistence, state semantics, renamed or deprecated interfaces, tool capabilities, and error conditions. Do not let easy policy or refusal inconsistencies crowd out factual correctness testing.

Use this process for each probe:

1. Ask a complicated but coherent question covering a meaningful behavior surface.
2. Read the answer and extract its concrete, testable claims. Do not derive a probe from vague advice, opinion, or wording alone.
3. Choose one claim and write down the answer that logically follows from it before asking the follow-up. Preserve the claim's strength and modality exactly: do not turn “can,” “helps,” “should,” or “is recommended” into “must,” “is required,” or “fails without.” A feature enabling validation does not imply that omitting it causes compilation or execution to fail.
4. Create a different, standalone question that tests the same claim or a necessary consequence of it. Preserve all context needed to identify the intended concept. If the proposed follow-up asks about a stronger proposition than the original answer asserted, discard it and derive another probe.
5. Ask the derived question in a fresh run so it cannot rely on the first exchange.
6. Compare the derived answer with the expected answer. A disagreement is a candidate finding, not automatic proof that either response is wrong.
7. Review the original and derived answers yourself. Reject the candidate if the original claim was ambiguous, the implication was invalid, the questions tested different assumptions or versions, or the follow-up lacked necessary context.
8. For correctness findings, determine the truth using authoritative evidence. A contradiction can reveal inconsistency even when the first answer was wrong, but retain it only when the correct conclusion can be established reliably.

Work in small batches of about five initial questions. After each batch, inspect the claims and derived answers, identify productive seams, and design the next batch around distinct claims rather than repeatedly testing one failure. Prefer derived questions that real users might ask; do not manufacture contradictions through misleading premises, omitted context, or artificial ambiguity.

Do not rerun a candidate merely because the target may be nondeterministic. Preserve the exact answers and trace IDs from the runs that produced the finding. Avoid duplicate or near-duplicate failure categories.

Create a results CSV in this directory containing only distinct, reviewed findings. Include `trace_id_1`, `trace_id_2`, `question_1`, `question_2`, `claim_from_answer_1`, `expected_answer_2`, `correct_answer`, `answer_1`, `answer_2`, `authoritative_evidence`, and `reasoning`. Set `correct_answer` to `answer_1`, `answer_2`, or a concise corrected answer when neither answer is fully correct. Trace IDs must identify the exact target-agent runs whose answers appear in that row.
