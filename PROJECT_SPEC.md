# RAG-Based Customer Policy Chatbot

## 1. Project Overview

This project builds a Retrieval-Augmented Generation (RAG) customer support chatbot for online sellers and small businesses.

Sellers provide their own business policies and customer-support documents, such as:

* Return and refund policies
* Product warranty policies
* Shipping policies
* Customer care procedures
* Product insurance policies
* Exchange conditions
* Payment policies
* Order cancellation policies
* Frequently asked questions
* Other seller-defined rules and support documents

Customers can then ask questions in natural language.

The system retrieves the most relevant information from the seller's policy knowledge base and uses a Large Language Model (LLM) to generate a natural, concise, and customer-friendly answer.

The system must not invent policies or make unsupported assumptions.

If the available documents do not contain sufficient evidence to answer a question, the chatbot must explicitly tell the customer that the case is not clearly covered by the existing policies and recommend contacting the seller directly.

---

# 2. Problem Statement

Customers often need answers to questions such as:

* Can I return this product after 10 days?
* Who pays the shipping fee for an exchanged product?
* Is accidental damage covered by warranty?
* Can I cancel an order after it has been shipped?
* How long does a refund take?
* What happens if my package is lost?
* Does the warranty cover water damage?

For small and medium sellers, answering these questions manually is repetitive and time-consuming.

Traditional FAQ systems have several limitations:

* They require customers to use predefined questions.
* They cannot handle different ways of phrasing the same question.
* They are difficult to maintain when policies change.
* They cannot easily combine information from multiple policy documents.

General-purpose LLM chatbots introduce another risk: they may generate plausible but incorrect answers.

This project addresses the problem by grounding every answer in seller-provided documents using Retrieval-Augmented Generation.

---

# 3. Product Principle

The core principle of the system is:

> The chatbot may rephrase and explain seller policies, but it must never create new policies.

The priority order is:

1. Correctness
2. Grounding in seller-provided evidence
3. Safe abstention when evidence is insufficient
4. Clear and natural communication
5. Response speed

A graceful refusal is considered better than an unsupported answer.

---

# 4. Target Users

## 4.1 Seller / Administrator

The seller manages the knowledge base used by the chatbot.

The seller should be able to:

* Upload policy documents
* Add textual policies manually
* Update existing documents
* Remove outdated documents
* Trigger or automatically perform re-indexing
* View indexed documents
* Inspect questions the chatbot could not answer
* Review chatbot answers and retrieved evidence

## 4.2 Customer

The customer interacts with the chatbot.

The customer should be able to:

* Ask questions using natural language
* Receive concise policy-based answers
* See which policy or document supports the answer
* Receive a clear fallback message when no reliable answer exists

---

# 5. Primary Use Cases

## UC-01: Ask a covered policy question

Customer:

> Can I return a product after 7 days?

The system retrieves a relevant return-policy section.

Example response:

> Yes. Products may be returned within 14 days of delivery, provided they remain unused and in their original packaging.

Source:

> Return Policy — Section 2

---

## UC-02: Ask the same question using different wording

Customer:

> I received my order last week. Can I send it back?

The system should understand the semantic similarity to the return policy and retrieve the correct evidence.

---

## UC-03: Ask a question requiring multiple pieces of evidence

Customer:

> If my product is defective, can I exchange it and who pays the shipping fee?

The system may need evidence from:

* Exchange policy
* Shipping policy

The answer must combine only information supported by those sources.

---

## UC-04: Ask a question not covered by policy

Customer:

> Can I get a refund because I simply changed my mind after 45 days?

If no policy clearly defines this situation, the chatbot must not infer the answer.

Expected response:

> This situation is not clearly covered by the available store policies. Please contact the seller directly for confirmation.

---

## UC-05: Ask an unrelated question

Customer:

> What laptop should I buy for machine learning?

If the seller knowledge base contains no relevant information, the chatbot should not use its general LLM knowledge to answer.

Expected behavior:

* Detect lack of relevant evidence.
* Abstain.
* Explain that the chatbot only answers questions based on seller-provided information.

---

## UC-06: Seller updates a policy

The seller replaces:

> Returns allowed within 14 days.

with:

> Returns allowed within 30 days.

The previous content must no longer influence future responses after the update and re-indexing process completes.

---

# 6. Core Functional Requirements

## FR-01: Document ingestion

The system must support ingesting seller-provided content.

Initial supported formats:

* PDF
* Markdown
* TXT
* Direct text input

Optional future formats:

* DOCX
* Web pages
* Google Docs

---

## FR-02: Document parsing

The ingestion pipeline must extract readable text while preserving useful metadata.

Metadata should include where available:

* seller_id
* document_id
* document_name
* policy_type
* section
* page
* version
* created_at
* updated_at

---

## FR-03: Chunking

Documents must be divided into retrieval units.

Each chunk should preserve:

* chunk text
* document identifier
* section information
* source metadata
* chunk position

Chunking strategy must be configurable so different strategies can be evaluated.

---

## FR-04: Embedding and indexing

Each chunk must be converted into a vector representation using an embedding model.

The vectors and corresponding metadata must be stored in a vector database.

The index must isolate data between sellers.

A customer interacting with Seller A must never retrieve documents belonging to Seller B.

---

## FR-05: Retrieval

Given a customer query, the system must retrieve the most relevant policy chunks.

The baseline implementation should use dense vector retrieval.

Advanced retrieval strategies may later include:

* Hybrid search
* BM25
* Query rewriting
* Metadata filtering
* Reranking
* Parent-child retrieval

These are explicitly excluded from the initial baseline unless evaluation shows they are necessary.

---

# 7. Answer Generation

The LLM must receive:

* Customer question
* Retrieved evidence
* Relevant source metadata
* Generation instructions

The model must:

* Answer only from retrieved evidence
* Avoid unsupported assumptions
* Preserve important policy conditions
* Produce customer-friendly language
* Prefer concise answers
* Mention uncertainty when evidence is incomplete

The model must not use external or general knowledge to create seller-specific policy information.

---

# 8. Grounding Rules

Every factual policy claim in an answer must be supported by retrieved context.

The system must not:

* Invent return periods
* Invent refund conditions
* Invent warranty coverage
* Invent fees
* Invent exceptions
* Infer seller intent
* Resolve ambiguous policies without evidence

Example:

Context:

> Warranty covers manufacturing defects for 12 months.

Question:

> Does the warranty cover accidental water damage?

The system must not answer:

> No, water damage is excluded.

unless such exclusion is explicitly supported by the seller's documents.

A valid response would instead be:

> The available warranty policy only states that manufacturing defects are covered for 12 months. It does not clearly specify whether accidental water damage is covered. Please contact the seller for confirmation.

---

# 9. Abstention and Fallback

Safe abstention is a core system feature.

The chatbot should abstain when:

* No relevant document is retrieved
* Retrieval relevance is below the configured threshold
* Retrieved documents do not contain enough information
* Retrieved policies contradict each other
* The question falls outside the seller's knowledge base
* The system cannot confidently ground the generated answer

Default fallback message:

> This situation is not clearly covered by the available store policies. Please contact the seller directly for confirmation.

The exact wording may be adjusted for the seller's brand voice, but the meaning must remain unchanged.

---

# 10. Citation Requirements

Answers should provide references to the supporting policies.

Minimum citation information:

* Document name
* Section or page where available

Example:

> Products can be returned within 14 days if they remain unused and in their original packaging.

Source: `Return Policy`, Section 2.

Citation correctness is considered part of answer quality.

---

# 11. Seller Knowledge Base Management

The seller should be able to:

* Add a document
* Delete a document
* Replace a document
* View document processing status
* View indexed policy documents
* Rebuild the index when required

Document lifecycle:

```text
Upload
  ↓
Parse
  ↓
Clean
  ↓
Chunk
  ↓
Embed
  ↓
Index
  ↓
Available for retrieval
```

Updating or deleting documents must ensure stale chunks no longer affect retrieval.

---

# 12. Policy Gap Analytics

Questions that cannot be reliably answered should be logged as unresolved questions.

Example:

```json
{
  "query": "Can I return a discounted item?",
  "reason": "insufficient_evidence",
  "retrieval_score": 0.31
}
```

The seller should eventually be able to inspect frequent unresolved questions.

This can help identify missing or ambiguous policies.

Example output:

```text
Most frequent unresolved topics

1. Return conditions for discounted items
2. International shipping refunds
3. Water damage warranty
4. Late delivery compensation
```

This feature is not required for the first baseline but is an important planned extension.

---

# 13. Multi-Tenant Isolation

The system is designed to support multiple sellers.

Each seller owns an independent knowledge base.

All document and retrieval operations must be scoped by:

```text
seller_id
```

Conceptually:

```text
Seller A
 ├── return-policy.pdf
 ├── warranty.pdf
 └── shipping.pdf

Seller B
 ├── refund-policy.pdf
 └── customer-care.pdf
```

Queries sent to Seller A's chatbot must never retrieve Seller B's documents.

Tenant isolation is a correctness and security requirement.

---

# 14. High-Level System Architecture

```text
                    SELLER

                      │
              Upload policies
                      │
                      ▼
              ┌──────────────┐
              │  Ingestion   │
              └──────┬───────┘
                     │
                     ▼
              Parsing / Cleaning
                     │
                     ▼
                  Chunking
                     │
                     ▼
                 Embedding
                     │
                     ▼
              ┌──────────────┐
              │ Vector Store │
              └──────┬───────┘
                     │
                     │
CUSTOMER             │
   │                 │
   │ question        │
   ▼                 │
Query Processing     │
   │                 │
   ▼                 │
Retriever ───────────┘
   │
   ▼
Relevant Evidence
   │
   ▼
Evidence Validation
   │
   ├── insufficient evidence
   │           │
   │           ▼
   │       Abstention
   │
   ▼
LLM Generation
   │
   ▼
Grounding Validation
   │
   ▼
Answer + Citations
```

---

# 15. Baseline RAG Pipeline

The first version must remain deliberately simple.

```text
Documents
    ↓
Parser
    ↓
Fixed / recursive chunking
    ↓
Embedding model
    ↓
Vector database
    ↓
Dense similarity search
    ↓
Top-K chunks
    ↓
Evidence threshold
    ↓
LLM
    ↓
Answer + citation
```

The baseline must be measurable before advanced retrieval techniques are introduced.

---

# 16. Non-Goals for Initial Version

The initial implementation will NOT include:

* Agentic RAG
* GraphRAG
* Knowledge graphs
* Fine-tuning an LLM
* Fine-tuning embedding models
* Voice chatbot
* Image understanding
* OCR-heavy document processing
* Autonomous customer actions
* Automatic refunds
* Automatic order cancellation
* Integration with payment systems
* Complex workflow automation
* Personalized recommendations
* Web search
* General-purpose question answering

These features may only be considered after the baseline is evaluated.

---

# 17. Evaluation Strategy

The project must be evaluation-driven.

A fixed evaluation dataset must be created before optimization.

Each evaluation case should contain:

```json
{
  "query": "Can I return an unused product after seven days?",
  "expected_sources": [
    "return_policy"
  ],
  "expected_answer_points": [
    "return period",
    "unused condition"
  ],
  "answerable": true
}
```

For unanswerable questions:

```json
{
  "query": "Does warranty cover water damage?",
  "expected_sources": [],
  "answerable": false
}
```

---

# 18. Retrieval Metrics

The retrieval layer should initially be evaluated using:

## Recall@K

Measures whether the relevant evidence appears among the top-K retrieved chunks.

Primary metric:

```text
Recall@5
```

## Mean Reciprocal Rank

Measures how highly the first relevant result appears.

Primary metric:

```text
MRR@10
```

Additional metrics may later include:

* Precision@K
* nDCG
* Hit Rate

---

# 19. Generation Metrics

The answer generation layer should evaluate:

## Faithfulness

Are claims in the generated answer supported by retrieved evidence?

## Answer Relevance

Does the response directly address the customer's question?

## Citation Correctness

Do the provided citations actually support the answer?

## Completeness

Does the answer contain the important conditions required by the policy?

---

# 20. Abstention Metrics

Because refusal is a major feature, it must be evaluated explicitly.

The evaluation dataset should contain both:

* answerable questions
* unanswerable questions

Metrics should include:

```text
Abstention Precision
Abstention Recall
False Answer Rate
```

A particularly important failure is:

> The system gives a confident answer to a question that should have been rejected.

This should be treated as a high-severity error.

---

# 21. System Metrics

The system should also measure:

* End-to-end latency
* Retrieval latency
* LLM latency
* Token usage
* Cost per query
* Error rate

These metrics will be used to evaluate engineering trade-offs.

---

# 22. Initial Evaluation Dataset

The first evaluation dataset should contain approximately:

```text
30–50 questions
```

Suggested distribution:

```text
40% simple answerable questions
20% paraphrased questions
15% multi-policy questions
15% unanswerable questions
10% ambiguous / adversarial questions
```

The dataset should gradually expand as the system develops.

---

# 23. Experiment Policy

All meaningful RAG modifications must be evaluated against the existing baseline.

Examples:

* Changing chunk size
* Changing embedding model
* Adding reranking
* Adding hybrid retrieval
* Changing top-K
* Changing prompts
* Adding query rewriting

An experiment should record:

```text
Experiment ID
Change
Hypothesis
Baseline metrics
New metrics
Latency impact
Cost impact
Conclusion
```

An improvement should not be accepted solely because a few manually tested examples look better.

---

# 24. Regression Protection

Previously passing evaluation cases should remain passing unless the specification changes.

Whenever retrieval or generation logic changes:

```text
Unit tests
    ↓
Integration tests
    ↓
Retrieval evaluation
    ↓
Generation evaluation
    ↓
Abstention evaluation
    ↓
Regression comparison
```

The agent or developer must inspect failures before declaring the task complete.

---

# 25. Definition of Done

A feature is considered complete only when:

1. Implementation matches the specification.
2. Relevant unit tests pass.
3. Relevant integration tests pass.
4. Evaluation suite runs successfully.
5. No unacceptable regression is introduced.
6. New behavior has appropriate evaluation cases.
7. Documentation is updated when required.

Manual inspection alone is not sufficient.

---

# 26. Harness Engineering Requirements

The repository should be designed so AI coding agents can work safely and predictably.

The development harness should provide:

* Clear repository instructions
* Explicit project scope
* Task state tracking
* Repeatable setup commands
* Repeatable test commands
* Repeatable evaluation commands
* Machine-readable evaluation results
* Clear Definition of Done
* Session handoff information
* Regression checks

Agents must not determine task success only from their own judgment.

Success should be verified through external signals such as:

```text
tests
metrics
evaluation datasets
acceptance criteria
```

---

# 27. Recommended Repository Structure

```text
rag-policy-chatbot/
│
├── README.md
├── PROJECT_SPEC.md
├── ARCHITECTURE.md
├── AGENTS.md
├── feature_list.json
├── progress.md
├── session-handoff.md
│
├── src/
│   ├── ingestion/
│   ├── parsing/
│   ├── chunking/
│   ├── embeddings/
│   ├── retrieval/
│   ├── generation/
│   ├── evaluation/
│   └── api/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
│
├── evals/
│   ├── datasets/
│   ├── retrieval/
│   ├── generation/
│   └── reports/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── scripts/
│   ├── ingest
│   ├── test
│   ├── evaluate
│   └── benchmark
│
└── docs/
    ├── architecture/
    └── experiments/
```

---

# 28. Initial Development Milestones

## Phase 0 — Project Foundation

Deliverables:

* PROJECT_SPEC.md
* ARCHITECTURE.md
* AGENTS.md
* Development harness
* Repository structure

---

## Phase 1 — Evaluation Dataset

Deliverables:

* Initial policy documents
* 30–50 evaluation questions
* Answerable/unanswerable labels
* Expected evidence annotations

No optimization should begin before a basic evaluation set exists.

---

## Phase 2 — Baseline Retrieval

Implement:

```text
Document
→ parse
→ chunk
→ embed
→ vector store
→ retrieve
```

Measure:

* Recall@5
* MRR@10

No LLM generation optimization is required yet.

---

## Phase 3 — Baseline Generation

Implement:

```text
Query
→ retrieval
→ evidence
→ LLM
→ answer
→ citation
```

Evaluate:

* Faithfulness
* Relevance
* Citation correctness

---

## Phase 4 — Safe Abstention

Implement explicit detection for insufficient evidence.

Evaluate:

* Correct refusal
* Incorrect refusal
* False confident answers

---

## Phase 5 — Seller Knowledge Management

Implement:

* Upload
* Delete
* Replace
* Re-index
* Tenant isolation

---

## Phase 6 — Retrieval Improvements

Only after establishing the baseline, experiment with:

* Chunking strategies
* Hybrid retrieval
* Reranking
* Query rewriting
* Metadata filters

Each technique must demonstrate measurable benefit.

---

## Phase 7 — Observability

Add monitoring for:

* Retrieval results
* Retrieval scores
* LLM responses
* Citations
* Latency
* Token usage
* Abstentions
* Errors

---

## Phase 8 — Policy Gap Analytics

Analyze unanswered questions to identify missing policies.

Provide sellers with summaries such as:

```text
Frequently unanswered customer questions
```

This becomes a feedback loop for improving the seller knowledge base.

---

## Phase 9 — Deployment

Expose the system through:

* Backend API
* Seller administration interface
* Customer chat interface

Possible deployment architecture:

```text
Frontend
   ↓
Backend API
   ↓
RAG Service
   ├── Vector DB
   ├── Metadata DB
   └── LLM Provider
```

---

# 29. MVP Success Criteria

The MVP is considered successful when:

* Seller documents can be ingested and indexed.
* Customer questions retrieve seller-specific evidence.
* The chatbot answers using only retrieved policy information.
* Answers contain source references.
* Unsupported questions trigger abstention.
* Seller data remains isolated.
* Retrieval quality can be measured automatically.
* Generation quality can be evaluated.
* Changes can be regression-tested.
* The complete system can be run through documented commands.

---

# 30. Long-Term Extensions

Potential future improvements include:

* Hybrid retrieval
* Cross-encoder reranking
* Query decomposition
* Multi-query retrieval
* Contextual retrieval
* Conversation memory
* Multilingual support
* Vietnamese policy optimization
* Policy versioning
* Seller analytics dashboard
* Automatic policy-gap clustering
* Human escalation
* E-commerce platform integrations
* Customer conversation analytics
* LLM-based document consistency checking

These features are future extensions and are not requirements for the initial implementation.

---

# 31. Core Engineering Objective

The primary objective of this project is not simply to demonstrate that an LLM can answer questions from documents.

The project should demonstrate the ability to engineer a RAG system that is:

* measurable
* grounded
* testable
* observable
* safe against unsupported answers
* maintainable
* multi-tenant aware
* suitable for iterative improvement through controlled experiments
