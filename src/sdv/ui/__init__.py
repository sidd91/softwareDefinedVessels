"""The ArgOS screen: a FastAPI app serving one page with its views (Operations with the constraint-ledger
drill-down, Mission compare, Admission review, the profile and rule builder, Reference) and a /ws stream of
{snapshot, records} per tick.

    uv run sdv demo            (or: uv run python -m sdv.ui.server)
"""
