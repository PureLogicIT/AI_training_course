"""
schemas.py — Pydantic models for Exercise 2.

Complete each TODO to define the three extraction schemas.
Each field must have a Field(description="...") so the parser
can generate accurate format instructions for the LLM.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# TODO A — JobPosting schema
# ---------------------------------------------------------------------------
# Fields required:
#   job_title       : str           — the role name
#   company         : str           — organisation name
#   location        : str           — city/country or "Remote"
#   salary_range    : Optional[str] — e.g. "$80k-$100k", or None
#   required_skills : list[str]     — list of technologies or skills
#   experience_years: Optional[int] — minimum years required, or None
#
# All Optional fields must default to None.
# ---------------------------------------------------------------------------

class JobPosting(BaseModel):
    """Structured representation of a job posting."""

    # YOUR CODE HERE — add the six fields with Field(description="...") on each
    pass


# ---------------------------------------------------------------------------
# TODO B — ProductDescription schema
# ---------------------------------------------------------------------------
# Fields required:
#   product_name : str           — the product's marketing name
#   brand        : str           — manufacturer or brand
#   price        : Optional[str] — price as a string, or None
#   key_features : list[str]     — up to five bullet-point features
#   category     : str           — product category (e.g. "Electronics")
#   in_stock     : Optional[bool]— availability, or None if not mentioned
# ---------------------------------------------------------------------------

class ProductDescription(BaseModel):
    """Structured representation of a product description."""

    # YOUR CODE HERE
    pass


# ---------------------------------------------------------------------------
# TODO C — EventAnnouncement schema
# ---------------------------------------------------------------------------
# Fields required:
#   event_name       : str           — full name of the event
#   organiser        : str           — person or organisation running it
#   date             : str           — date as a string
#   location         : str           — venue and/or city, or "Online"
#   topics           : list[str]     — themes, topics, or speaker names
#   registration_url : Optional[str] — URL or None
# ---------------------------------------------------------------------------

class EventAnnouncement(BaseModel):
    """Structured representation of an event announcement."""

    # YOUR CODE HERE
    pass
