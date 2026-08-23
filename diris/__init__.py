"""DIRIS — Data Injection and Retrieval Intelligence System.

A knowledge-graph-based document intelligence platform (MVP vertical slice).

Pipeline:  ingest documents -> extract entities & relationships with an LLM
           -> build a knowledge graph + vector index -> answer questions with
           hybrid (graph + vector + keyword) retrieval and cited, explainable answers.
"""

__version__ = "0.1.0"
