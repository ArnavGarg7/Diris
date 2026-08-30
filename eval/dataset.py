"""A small hand-labeled evaluation dataset.

CHUNKS are the "documents"; each QUERY is a paraphrase whose answer lives in
exactly one chunk (the gold index). OUT_OF_SCOPE questions have no answer in the
corpus — used to measure hallucination resistance.
"""
from __future__ import annotations

CHUNKS: list[str] = [
    "Neil Armstrong was the first person to walk on the Moon, in 1969.",          # 0
    "The Saturn V rocket propelled the Apollo missions into Earth orbit.",        # 1
    "Marie Curie discovered the elements radium and polonium.",                   # 2
    "Photosynthesis converts sunlight into chemical energy inside plant leaves.", # 3
    "The Great Wall of China stretches for over thirteen thousand miles.",        # 4
    "Mount Everest is the tallest mountain above sea level on Earth.",            # 5
]

# (query, gold chunk index) — deliberately paraphrased (little lexical overlap).
QUERIES: list[tuple[str, int]] = [
    ("Who stepped onto the lunar surface first?", 0),
    ("Which launch vehicle carried the Apollo spacecraft?", 1),
    ("Who found the element radium?", 2),
    ("How do plants turn light into energy?", 3),
    ("How long is the Great Wall?", 4),
    ("What is the highest peak on the planet?", 5),
]

OUT_OF_SCOPE: list[str] = [
    "What is the capital of France?",
    "Who wrote the novel Pride and Prejudice?",
]
