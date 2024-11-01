"""
Same base class for all the sql alchemy Models for better control over some things like to create
tables for all every defined table with the same base.
"""
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
