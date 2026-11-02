from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SalesRecord(BaseModel):
    """Rules that every cleaned sales record must satisfy."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    date: Date

    region: Literal[
        "North",
        "South",
        "East",
        "West",
        "Central",
    ]

    product_category: str = Field(min_length=1, max_length=100)

    revenue: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    units_sold: int = Field(
        ge=0,
        strict=True,
    )

    customer_segment: str = Field(min_length=1, max_length=100)


# These checks run only when you run this file directly.
# They do not run when another file imports SalesRecord.
if __name__ == "__main__":
    sample_record = {
        "date": "2024-01-15",
        "region": "North",
        "product_category": "Electronics",
        "revenue": 1250.50,
        "units_sold": 45,
        "customer_segment": "Enterprise",
    }

    SalesRecord.model_validate(sample_record)
    print("SUCCESS: valid record accepted.")

    invalid_examples = [
        ("negative revenue", {"revenue": -100.0}),
        ("fractional units", {"units_sold": 2.5}),
    ]

    for description, changes in invalid_examples:
        invalid_record = {**sample_record, **changes}

        try:
            SalesRecord.model_validate(invalid_record)
        except ValidationError:
            print(f"SUCCESS: {description} rejected.")
        else:
            raise RuntimeError(
                f"CHECK FAILED: {description} should have been rejected."
            )