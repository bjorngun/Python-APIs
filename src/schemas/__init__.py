"""
Here the schemas for the Python-APIs models, if you are creating new services or
just using the models, I recommend using the schemas for validating data if the data
is being fetched from another source then the database.
"""

from .ad_user_schema import ADUserSchema

__all__ = [
    "ADUserSchema",
]
