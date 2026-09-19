"""
Demo Service — Instant Zero-Friction Public Demo Access

Provides pre-seeded, high-quality benchmark documents for portfolio visitors,
recruiters, and interviewers to experience DocuMind without registration friction.
"""
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.models import Document, DocumentStatus, User, UserRole
from app.services.document_processor import chunk_text
from app.services.rag_service import build_document_index

logger = get_logger(__name__)

DEMO_EMAIL = "demo@documind.app"

DEMO_DOCUMENTS = [
    {
        "filename": "SaaS_Master_Services_Agreement_2025.txt",
        "file_type": "txt",
        "summary": "Master Services Agreement establishing enterprise cloud terms between CloudScale Systems and enterprise customers. Details 99.9% uptime SLA service credits, liability capped at 12 months fees ($500,000 max), mutual indemnification for IP infringement, and 30-day termination for cause under Delaware jurisdiction.",
        "entities": {
            "organizations": ["CloudScale Systems Inc.", "Customer Enterprise Corp", "Delaware Chancery Court"],
            "persons": ["Marcus Vance", "Elena Rostova"],
            "dates": ["January 15, 2025", "30 days notice", "12 months preceding"],
            "monetary_values": ["$500,000", "$120,000 annual fee"],
            "technologies": ["CloudScale Platform", "REST API", "SOC-2 Type II", "TLS 1.3"],
            "locations": ["Delaware", "United States", "Frankfurt data center"],
            "other": ["IP Infringement", "Service Level Agreement", "Force Majeure"]
        },
        "keywords": ["uptime SLA", "liability limitation", "indemnification", "termination", "governing law", "confidentiality"],
        "sentiment": {
            "label": "Neutral",
            "score": 0.52,
            "confidence": 0.95,
            "tone": "formal",
            "explanation": "Standard binding legal contract drafted with rigorous, formal legal precision."
        },
        "content": """MASTER SERVICES AGREEMENT (MSA)
Effective Date: January 15, 2025
Parties: CloudScale Systems Inc. ("Provider") and Enterprise Customer ("Customer")
Jurisdiction: State of Delaware, United States

1. SCOPE OF SERVICES & SUBSCRIPTION
Provider provides Customer non-exclusive, world-wide access to the CloudScale Platform via authenticated API and Web Console. Services include hosted document processing, semantic indexing, and analytics services as specified in each executed Order Form.

2. SERVICE LEVEL AGREEMENT (SLA) & UPTIME COMMITMENT
Provider guarantees a Monthly Uptime Percentage of at least 99.9% during each billing cycle, excluding scheduled maintenance windows announced at least 72 hours in advance.
If Provider fails to meet 99.9% uptime, Customer is eligible for Service Credits calculated as follows:
- 99.0% to 99.89% uptime: 10% credit of monthly fees.
- 95.0% to 98.99% uptime: 25% credit of monthly fees.
- Less than 95.0% uptime: 50% credit of monthly fees.
Service Credits must be requested within 30 days of incident occurrence and are applied against future invoice payments.

3. LIMITATION OF LIABILITY
EXCEPT FOR WILLFUL MISCONDUCT, GROSS NEGLIGENCE, OR INDEMNIFICATION OBLIGATIONS UNDER SECTION 5, NEITHER PARTY SHALL BE LIABLE FOR INDIRECT, SPECIAL, INCIDENTAL, PUNITIVE, OR CONSEQUENTIAL DAMAGES, INCLUDING LOSS OF PROFITS, DATA, OR REVENUE.
THE AGGREGATE LIABILITY OF EITHER PARTY ARISING OUT OF OR RELATED TO THIS AGREEMENT SHALL BE STRICTLY CAPPED AT THE TOTAL FEES PAID OR PAYABLE BY CUSTOMER IN THE TWELVE (12) MONTHS IMMEDIATELY PRECEDING THE CLAIM, NOT TO EXCEED $500,000.

4. DATA SECURITY & COMPLIANCE
Provider maintains SOC-2 Type II certification, encrypts all Customer data at rest using AES-256 and in transit using TLS 1.3. Production backups are replicated to a secondary region (Frankfurt) with Recovery Point Objective (RPO) of 1 hour and Recovery Time Objective (RTO) of 4 hours.

5. INDEMNIFICATION
Provider shall defend, indemnify, and hold harmless Customer against any third-party claims, suits, or actions alleging that the CloudScale Platform infringes or misappropriates any copyright, patent, or trade secret, provided Customer gives prompt written notice and control of defense to Provider.

6. TERMINATION & DISPUTE RESOLUTION
Either party may terminate this Agreement for convenience with 60 days written notice, or immediately for material breach if uncured within 30 days of written notice. This Agreement is governed by Delaware law without regard to conflict of law principles. Any dispute shall be resolved through binding arbitration in Wilmington, Delaware."""
    },
    {
        "filename": "QuantumDB_Distributed_Architecture_Spec.txt",
        "file_type": "txt",
        "summary": "Technical architecture specification for QuantumDB, an LSM-tree based distributed key-value store. Details the Raft multi-group consensus protocol, tunable quorum reads and writes (R=2, W=2 on replication factor 3), SSTable tiered compaction, and distributed tombstone garbage collection.",
        "entities": {
            "technologies": ["QuantumDB", "Raft Consensus", "LSM-Tree", "SSTables", "Bloom Filters", "Write-Ahead Log (WAL)", "gRPC"],
            "persons": ["Dr. Aris Thorne", "Dr. Mei Lin"],
            "dates": ["Q3 2025", "50ms heartbeat", "100ms election timeout"],
            "monetary_values": [],
            "locations": ["Multi-datacenter", "us-east-1", "eu-central-1"],
            "organizations": ["Quantum Systems Lab", "ACM SIGMOD"],
            "other": ["Quorum Consensus", "Linearizable Consistency", "Tombstone GC"]
        },
        "keywords": ["Raft consensus", "quorum write", "LSM-tree", "SSTable compaction", "tombstones", "replication factor"],
        "sentiment": {
            "label": "Positive",
            "score": 0.82,
            "confidence": 0.94,
            "tone": "technical",
            "explanation": "Authoritative engineering architecture specification with high structural rigor."
        },
        "content": """QUANTUMDB DISTRIBUTED ARCHITECTURE SPECIFICATION
Version: 3.4-RC
Author: Distributed Systems Core Team

1. SYSTEM OVERVIEW & ARCHITECTURAL TOPOLOGY
QuantumDB is a horizontally scalable, linearly scalable distributed storage engine engineered for mission-critical write-heavy workloads. The architecture combines Log-Structured Merge-trees (LSM-trees) on individual storage nodes with a multi-group Raft consensus layer for distributed state machine replication.

2. CONSENSUS & REPLICATION PROTOCOL
Replication factor N is configured to 3 across distinct availability zones. Leader election uses the Raft algorithm with randomized election timeouts between 150ms and 300ms, and heartbeat intervals of 50ms.
Write Consistency:
- Quorum Write (W=2, R=2, N=3) guarantees strong consistency (linearizability) under network partitions not exceeding minority quorum.
- When a client issues a PUT request, the Raft leader appends the entry to its local Write-Ahead Log (WAL), replicates to followers via gRPC, and acknowledges the client only after at least one follower confirms disk persistence.

3. LOCAL STORAGE ENGINE (LSM-TREE)
Each storage node executes a tiered LSM-tree engine:
- MemTable: In-memory skiplist storing updates up to 64MB before freezing and flushing.
- Immutable MemTable: Read-only memory buffer queued for disk flush.
- Level 0 (L0) to Level 4 (L4) SSTables: Immutable sorted string tables stored on NVMe storage.
- Bloom Filters: Block-level Bloom filters with 10 bits per key reduce point lookup read amplification to under 1.2 I/O operations per query.

4. COMPACTION & TOMBSTONE CLEANUP
Deletions are recorded by appending a tombstone entry to the MemTable. To prevent disk bloat from deleted keys:
- Tiered Leveled Compaction periodically merges overlapping SSTable key ranges from L(i) into L(i+1).
- Tombstones are dropped during compaction only when the key does not exist in any older SSTable level, preventing resurrected ghost keys.

5. PARTITIONING & FAILOVER
Key-space is partitioned into 256 virtual ranges using MurmurHash3 consistent hashing. During leader failure, followers trigger election within 300ms, with zero data loss for acknowledged transactions."""
    },
    {
        "filename": "ApexGlobal_Q4_Financial_Performance.txt",
        "file_type": "txt",
        "summary": "ApexGlobal Financial and Operational Summary for Q4 and Full Fiscal Year. Highlights $142M in quarterly revenue (18% YoY growth), 74% gross margins, $28M free cash flow, and guidance projecting $620M-$635M for the upcoming fiscal year.",
        "entities": {
            "organizations": ["ApexGlobal Inc.", "Goldman Sachs", "Morgan Stanley"],
            "persons": ["Sarah Jenkins (CFO)", "David Morales (CEO)"],
            "dates": ["Q4 2024", "Fiscal Year 2025", "December 31, 2024"],
            "monetary_values": ["$142.4M", "$512.8M full year", "$28.3M free cash flow", "$620M-$635M guidance"],
            "locations": ["New York", "London", "Singapore"],
            "technologies": ["Cloud Infrastructure", "Enterprise SaaS", "DocuMind AI Platform"],
            "other": ["GAAP Net Income", "Net Dollar Retention", "EBITDA Margin"]
        },
        "keywords": ["quarterly revenue", "gross margin", "free cash flow", "net retention", "EBITDA", "financial guidance"],
        "sentiment": {
            "label": "Positive",
            "score": 0.88,
            "confidence": 0.98,
            "tone": "optimistic",
            "explanation": "Strong quarterly financial results demonstrating profitable growth and robust expansion."
        },
        "content": """APEXGLOBAL INC. FOURTH QUARTER & FULL YEAR EARNINGS REPORT
Date: February 20, 2025
Audited GAAP & Non-GAAP Financial Highlights

1. REVENUE & TOP-LINE PERFORMANCE
ApexGlobal generated $142.4 million in revenue for Q4, representing an 18.2% year-over-year growth compared to $120.5 million in Q4 of the prior year. Full fiscal year revenue reached $512.8 million, up 22.4% year-over-year.
- Subscription Revenue: $128.2 million (90.0% of total revenue).
- Professional Services & Support: $14.2 million (10.0% of total revenue).
Net Dollar Retention (NDR) stood at 122% across enterprise accounts, reflecting strong seat expansion and cross-sell of AI intelligence modules.

2. MARGINS & PROFITABILITY
- GAAP Gross Margin expanded 180 basis points year-over-year to 74.2%, driven by platform optimization and reduced third-party cloud compute unit costs.
- Non-GAAP Operating Income was $24.8 million (17.4% operating margin), compared to $16.1 million (13.4% margin) in Q4 of the prior year.
- Adjusted EBITDA reached $31.6 million (22.2% EBITDA margin).

3. BALANCE SHEET & CASH FLOW
ApexGlobal generated $28.3 million in Free Cash Flow (FCF) for Q4 (19.9% FCF margin), bringing full-year operating cash flow to $98.5 million.
As of December 31, cash, cash equivalents, and marketable securities totaled $214.6 million with zero outstanding long-term debt.

4. FISCAL YEAR FORWARD GUIDANCE
For the upcoming Fiscal Year, management projects:
- Total Revenue between $620.0 million and $635.0 million (representing 21% to 24% annual growth).
- Non-GAAP Operating Margin expanding to 19.0% - 20.5%.
- Free Cash Flow conversion exceeding 22% of revenue.
Key investment priorities include global multi-region datacenter expansion and automated cross-document intelligence capabilities."""
    }
]


async def ensure_demo_user(db: AsyncSession) -> User:
    """
    Finds or creates the demo user and pre-seeds the 3 benchmark documents
    with pre-calculated pgvector embeddings for instant portfolio exploration.
    """
    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=DEMO_EMAIL,
            hashed_password=hash_password("DemoPassword123!"),
            full_name="DocuMind Demo Guest",
            role=UserRole.premium,
            subscription_tier="pro",
            subscription_status="active",
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        logger.info("demo_user_created", user_id=str(user.id))
    else:
        if user.subscription_tier != "pro":
            user.subscription_tier = "pro"
            user.subscription_status = "active"
            await db.flush()

    # Check if demo documents exist
    doc_res = await db.execute(select(Document).where(Document.user_id == user.id))
    existing_docs = doc_res.scalars().all()

    if not existing_docs:
        logger.info("seeding_demo_documents", user_id=str(user.id))
        for doc_data in DEMO_DOCUMENTS:
            doc_id = uuid4()
            raw_text = doc_data["content"]
            chunks = chunk_text(raw_text)

            doc = Document(
                id=doc_id,
                user_id=user.id,
                filename=doc_data["filename"],
                original_filename=doc_data["filename"],
                file_type=doc_data["file_type"],
                file_size_bytes=len(raw_text.encode("utf-8")),
                storage_path=f"demo/{doc_id}/{doc_data['filename']}",
                status=DocumentStatus.ready,
                raw_text=raw_text,
                chunk_count=len(chunks),
                token_count=sum(c["token_count"] for c in chunks),
                page_count=1,
                summary=doc_data["summary"],
                entities=doc_data["entities"],
                keywords=doc_data["keywords"],
                sentiment=doc_data["sentiment"],
                language="en",
            )
            db.add(doc)
            await db.flush()

            # Store chunks and vector embeddings directly in pgvector
            await build_document_index(db, doc.id, chunks)

        await db.commit()
        logger.info("demo_documents_seeded_successfully", count=len(DEMO_DOCUMENTS))

    return user
