"""Sumber lowongan: LinkedIn, JobStreet Indonesia, dan Glints."""

from . import linkedin, jobstreet, glints

REGISTRY = {
    "linkedin": linkedin,
    "jobstreet": jobstreet,
    "glints": glints,
}

__all__ = ["linkedin", "jobstreet", "glints", "REGISTRY"]
