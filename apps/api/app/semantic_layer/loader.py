from __future__ import annotations

from pathlib import Path

import yaml

from app.core.config import settings
from app.semantic_layer.types import SemanticCatalog, TemplateCatalog


class SemanticLayerLoader:
    def __init__(self) -> None:
        self._catalog: SemanticCatalog | None = None
        self._templates: TemplateCatalog | None = None

    def load_catalog(self) -> SemanticCatalog:
        if self._catalog is None:
            path = Path(settings.semantic_catalog_path)
            with path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file)
            self._catalog = SemanticCatalog.model_validate(raw)
        return self._catalog

    def load_templates(self) -> TemplateCatalog:
        if self._templates is None:
            path = Path(settings.semantic_templates_path)
            with path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file)
            self._templates = TemplateCatalog.model_validate(raw)
        return self._templates

    def invalidate(self) -> None:
        self._catalog = None
        self._templates = None


semantic_loader = SemanticLayerLoader()

