"""
Evaluation Dataset — Benchmark Test Documents and Ground Truth Query Cases

Gold-standard labeled evaluation dataset testing:
1. Single-fact precise retrieval
2. Quantitative/numerical precision
3. Multi-hop synthesis
4. Adversarial/Negative out-of-domain queries (hallucination/refusal test)
"""

BENCHMARK_CASES = [
    # ── SaaS Contract Domain ────────────────────────────────────────────────
    {
        "id": "case_01_liability_cap",
        "doc_key": "saas_msa",
        "question": "What is the maximum aggregate liability dollar cap under the contract?",
        "ground_truth_answer": "The aggregate liability is strictly capped at the total fees paid or payable by the customer in the 12 months immediately preceding the claim, not to exceed $500,000.",
        "required_keywords": ["$500,000", "twelve (12) months", "aggregate liability"],
        "category": "single_fact",
        "is_negative": False,
    },
    {
        "id": "case_02_uptime_sla",
        "doc_key": "saas_msa",
        "question": "What monthly uptime percentage is guaranteed and what credit applies if uptime is 96%?",
        "ground_truth_answer": "The guaranteed monthly uptime is at least 99.9%. For uptime between 95.0% and 98.99%, a 25% credit of monthly fees is applied.",
        "required_keywords": ["99.9%", "25%", "service credits"],
        "category": "single_fact",
        "is_negative": False,
    },
    {
        "id": "case_03_termination_notice",
        "doc_key": "saas_msa",
        "question": "What are the notice requirements for termination for convenience versus material breach?",
        "ground_truth_answer": "Termination for convenience requires 60 days written notice, while termination for material breach is effective immediately if uncured within 30 days of written notice.",
        "required_keywords": ["60 days", "30 days", "material breach", "convenience"],
        "category": "multi_hop",
        "is_negative": False,
    },
    {
        "id": "case_04_rpo_rto",
        "doc_key": "saas_msa",
        "question": "What are the disaster recovery RPO and RTO commitments and where is the secondary region?",
        "ground_truth_answer": "Recovery Point Objective (RPO) is 1 hour, Recovery Time Objective (RTO) is 4 hours, and production backups are replicated to Frankfurt.",
        "required_keywords": ["rpo of 1 hour", "rto of 4 hours", "frankfurt"],
        "category": "multi_hop",
        "is_negative": False,
    },

    # ── Technical Architecture Domain ────────────────────────────────────────
    {
        "id": "case_05_raft_election",
        "doc_key": "quantum_db",
        "question": "What are QuantumDB's Raft heartbeat intervals and randomized election timeouts?",
        "ground_truth_answer": "The Raft heartbeat interval is 50ms, and randomized election timeouts are between 150ms and 300ms.",
        "required_keywords": ["50ms", "150ms", "300ms", "election timeout"],
        "category": "single_fact",
        "is_negative": False,
    },
    {
        "id": "case_06_quorum_writes",
        "doc_key": "quantum_db",
        "question": "How are write consistency and quorum configured in QuantumDB?",
        "ground_truth_answer": "Write consistency uses Quorum Write W=2, R=2, with replication factor N=3, guaranteeing strong consistency (linearizability) under network partitions.",
        "required_keywords": ["w=2", "r=2", "n=3", "linearizability", "quorum write"],
        "category": "single_fact",
        "is_negative": False,
    },
    {
        "id": "case_07_tombstone_compaction",
        "doc_key": "quantum_db",
        "question": "How does QuantumDB handle deleted keys during compaction to prevent ghost keys?",
        "ground_truth_answer": "Deletions append a tombstone entry to the MemTable. During tiered leveled compaction, tombstones are dropped only when the key does not exist in any older SSTable level.",
        "required_keywords": ["tombstone", "compaction", "sstable", "ghost keys"],
        "category": "multi_hop",
        "is_negative": False,
    },
    {
        "id": "case_08_bloom_filters",
        "doc_key": "quantum_db",
        "question": "What Bloom filter configuration is used and what is the target read amplification?",
        "ground_truth_answer": "Block-level Bloom filters use 10 bits per key, reducing point lookup read amplification to under 1.2 I/O operations per query.",
        "required_keywords": ["10 bits per key", "1.2 i/o", "bloom filter"],
        "category": "single_fact",
        "is_negative": False,
    },

    # ── Financial Performance Domain ─────────────────────────────────────────
    {
        "id": "case_09_q4_revenue_growth",
        "doc_key": "apex_financial",
        "question": "What was ApexGlobal's Q4 revenue and year-over-year growth percentage?",
        "ground_truth_answer": "ApexGlobal generated $142.4 million in Q4 revenue, representing an 18.2% year-over-year growth.",
        "required_keywords": ["$142.4 million", "18.2%"],
        "category": "single_fact",
        "is_negative": False,
    },
    {
        "id": "case_10_gross_margin",
        "doc_key": "apex_financial",
        "question": "What was the GAAP gross margin and how many basis points did it expand?",
        "ground_truth_answer": "GAAP Gross Margin reached 74.2%, expanding 180 basis points year-over-year.",
        "required_keywords": ["74.2%", "180 basis points"],
        "category": "single_fact",
        "is_negative": False,
    },
    {
        "id": "case_11_cash_flow_debt",
        "doc_key": "apex_financial",
        "question": "What was the Q4 free cash flow and what is the total long-term debt?",
        "ground_truth_answer": "Free Cash Flow for Q4 was $28.3 million, with zero outstanding long-term debt.",
        "required_keywords": ["$28.3 million", "zero outstanding long-term debt", "free cash flow"],
        "category": "multi_hop",
        "is_negative": False,
    },
    {
        "id": "case_12_forward_guidance",
        "doc_key": "apex_financial",
        "question": "What is the projected full-year revenue range in the forward guidance?",
        "ground_truth_answer": "Management projected total revenue between $620.0 million and $635.0 million (21% to 24% annual growth).",
        "required_keywords": ["$620.0 million", "$635.0 million", "21% to 24%"],
        "category": "single_fact",
        "is_negative": False,
    },

    # ── Adversarial / Negative Cases (Hallucination Resistance & Refusal) ─────
    {
        "id": "case_13_negative_crypto",
        "doc_key": "apex_financial",
        "question": "How much Bitcoin and Ethereum does ApexGlobal hold on its balance sheet?",
        "ground_truth_answer": "This information is not found in the document.",
        "required_keywords": [],
        "category": "adversarial_negative",
        "is_negative": True,
    },
    {
        "id": "case_14_negative_kubernetes",
        "doc_key": "quantum_db",
        "question": "What Kubernetes Helm chart values are required for QuantumDB node autoscaling?",
        "ground_truth_answer": "This information is not found in the document.",
        "required_keywords": [],
        "category": "adversarial_negative",
        "is_negative": True,
    },
    {
        "id": "case_15_negative_governing_law",
        "doc_key": "saas_msa",
        "question": "What are the specific California Civil Code arbitration rules mentioned in the contract?",
        "ground_truth_answer": "This information is not found in the document.",
        "required_keywords": [],
        "category": "adversarial_negative",
        "is_negative": True,
    }
]
