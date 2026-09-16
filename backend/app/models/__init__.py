"""Importing this package registers every ORM model with Base.metadata — required so
SQLAlchemy can resolve cross-table foreign keys (e.g. Document.company_profile_id ->
company_profiles.id) regardless of which specific model module a caller imported
directly. Without this, code that only imports `app.models.document` can fail with
NoReferencedTableError the moment it touches a foreign key to a table whose model was
never imported anywhere in the process.
"""

from app.models import (  # noqa: F401
    boilerplate_cache,
    chunk,
    chunk_extraction,
    company_profile,
    document,
    document_analysis,
    export_bronze_silver_gold,
    extracted_table,
    page,
)
