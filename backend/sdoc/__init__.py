"""Sentinel — shipping document verification pipeline.

inbox email  ->  classify  ->  read attachments  ->  extract 7 fields
             ->  normalise ->  compare  ->  OK | MISMATCH | NEEDS_REVIEW
"""
__version__ = "0.1.0"
