"""Knowledge base for the chat agent (SPEC M3, decisions 0027-0028).

Sources: FIA Sporting Regulations (current season), Wikipedia season and race articles
(CC BY-SA 4.0), and race summaries generated from our own data. Text is split into
section-aware chunks, embedded with Gemini (if a key is set) and stored in pgvector.
"""
