from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.semantic import ApprovedQueryTemplate, SemanticDictionaryEntry


class SemanticRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_entries(self) -> list[SemanticDictionaryEntry]:
        return self.db.query(SemanticDictionaryEntry).order_by(SemanticDictionaryEntry.created_at.desc()).all()

    def create_entry(self, entry: SemanticDictionaryEntry) -> SemanticDictionaryEntry:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_templates(self) -> list[ApprovedQueryTemplate]:
        return self.db.query(ApprovedQueryTemplate).order_by(ApprovedQueryTemplate.created_at.desc()).all()

    def create_template(self, template: ApprovedQueryTemplate) -> ApprovedQueryTemplate:
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

