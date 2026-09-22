### Fuzzing notes

Goal: find semantically equivalent question pairs whose judged answer similarity is below 4.

#### What worked

- Ambiguous questions about the assistant's own built-in capabilities are unstable. One wording is often treated as an impermissible request about internal tools, while a more explicit paraphrase is answered with exact tool names and behavior.
- The strongest seam is between generic product terminology and assistant-runtime terminology. Generic phrases such as "built-in feature," "tools you have," or "what model" may trigger a refusal, product-doc answer, or unsupported guess. Explicit phrases such as "Pylon support article," "citation URLs," and "Chat LangChain documentation agent" route to a different answer.
- Link checking, support-article reading, pricing retrieval, and model identity each produced at least one score below 4.
- Keeping one side short and ambiguous while making the other side explicit about the same intended referent works better than two equally explicit paraphrases.

#### What did not work

- Straightforward documentation paraphrases usually score 7-9 because retrieval grounds both answers consistently.
- Two explicit names for the same internal capability usually produce nearly identical disclosures.
- Policy-boundary pairs about phishing, prompt extraction, creative writing, and generic math were handled consistently and scored 8-9.
- Generic versus LangChain-qualified product concepts such as Fleet, Studio, persistence, stores, account deletion, refunds, and billing support were also consistent.
- Minor wording changes around the same link-checking concept generally scored 8-9; the phrasing must alter routing, not just vocabulary.
- Scores vary between runs. Several additional variants scored 2-3, but the final CSV keeps five distinct failure categories rather than multiple near-duplicates of link or support-tool routing.

#### Selected distinct results

1. Assistant tool inventory: refusal versus disclosure of documentation/support tools; score 3.
2. Link-validation capability: generic LangSmith URL inspection versus disclosure of `check_links`; score 2.
3. Support-article reader: generic document-loader answer versus disclosure of `get_support_article_content`; score 3.
4. Live pricing capability: incorrect claim that no built-in API exists versus disclosure of `fetch_langchain_pricing`; score 2.
5. Assistant architecture: internal-instructions refusal versus a researched LangChain/LangGraph architecture answer; score 3.

Scores above are from successful batch runs against the deployed application and the configured `gpt-4o` judge. Because generation is nondeterministic, reruns may produce different scores.

#### Domain-focused fuzzing

A second pass targeted expected customer questions rather than Chat LangChain internals. The productive pattern was a short, plausible customer phrasing whose intended LangChain meaning is clear from product context, paired with an explicit product-specific version. The short form sometimes routes off-topic or to a different abstraction.

Selected domain failures observed below 4:

1. "go back in time" versus LangGraph checkpoint time travel: refusal versus replay instructions; score 1.
2. "recover from failure" versus LangGraph durable execution: refusal versus checkpoint-resume explanation; score 2.
3. "delegate work" versus Deep Agents subagents: refusal versus subagent configuration; score 2-3.
4. "summarize history" versus LangChain summarization middleware: refusal versus middleware implementation; score 2-3.
5. "switch models" versus dynamic model selection middleware: basic model initialization versus per-request middleware; score 3.

Other useful but less stable seams included Deep Agents filesystem backends, skills versus dynamic tool disclosure, subagents versus LangGraph subgraphs, and agent structured output versus model/tool structured output. All 55 results from this pass are saved in `domain_fuzz_results.csv`.

#### Semantic-equivalence quality bar

A low score is not useful when one question omits context required to identify the intended product concept. Questions such as "How do I go back in time?" and "How do I recover from failure?" are underspecified outside their explicit LangGraph paraphrases, so their divergent answers are expected routing behavior rather than strong fuzz findings.

Each question must independently identify the same user intent. Prefer realistic variations involving aliases, renamed products, deprecated versus current APIs, Python versus JavaScript terminology, equivalent error descriptions, reordered constraints, abbreviations, or old versus new configuration names. Do not manufacture divergence by removing the product name, feature, operation, or other disambiguating context from only one side.
