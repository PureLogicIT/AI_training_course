"""
schemas.py — Pydantic models for Exercise 2  (SOLUTION)
"""

from typing import Optional
from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Structured representation of a job posting."""

    job_title: str = Field(description="The job title or role name")
    company: str = Field(description="Company or organisation name")
    location: str = Field(description="City and country, or 'Remote'")
    salary_range: Optional[str] = Field(
        default=None,
        description="Salary range as a string (e.g. '$80,000 - $100,000'), or null if not stated",
    )
    required_skills: list[str] = Field(
        description="List of required technical skills or technologies"
    )
    experience_years: Optional[int] = Field(
        default=None,
        description="Minimum years of experience required as an integer, or null if not stated",
    )


class ProductDescription(BaseModel):
    """Structured representation of a product description."""

    product_name: str = Field(description="The product's marketing name")
    brand: str = Field(description="Manufacturer or brand name")
    price: Optional[str] = Field(
        default=None,
        description="Price as a string (e.g. '$49.99'), or null if not mentioned",
    )
    key_features: list[str] = Field(
        description="List of up to five key product features or selling points"
    )
    category: str = Field(
        description="Product category (e.g. 'Electronics', 'Kitchen Appliances', 'Clothing')"
    )
    in_stock: Optional[bool] = Field(
        default=None,
        description="True if the product is in stock, False if out of stock, null if not mentioned",
    )


class EventAnnouncement(BaseModel):
    """Structured representation of an event announcement."""

    event_name: str = Field(description="Full name of the event")
    organiser: str = Field(description="Person or organisation running the event")
    date: str = Field(description="Event date as a string (e.g. '14 June 2026')")
    location: str = Field(description="Venue name and/or city, or 'Online'")
    topics: list[str] = Field(
        description="List of topics, themes, or speaker names associated with the event"
    )
    registration_url: Optional[str] = Field(
        default=None,
        description="Registration URL if mentioned, or null",
    )
