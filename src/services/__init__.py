"""
The services provided in this package are mostly examples of how to use the
api's with the models.  I expect in most cases there has to be a custom service
module or a few of them.
"""

from .ad_user_service import ADUserService

__all__ = [
    "ADUserService",
]
