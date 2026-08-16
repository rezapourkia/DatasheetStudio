"""Domain model for page annotations (colored notes on PDF pages)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AnnotationColor(Enum):
    """Available colors for page annotations."""

    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PINK = "pink"
    ORANGE = "orange"
    PURPLE = "purple"


@dataclass
class PageAnnotation:
    """Represents a colored note annotation on a specific position of a PDF page."""

    page_number: int
    x_percent: float  # 0.0 to 1.0 (relative to page width)
    y_percent: float  # 0.0 to 1.0 (relative to page height)
    text: str = ""
    color: AnnotationColor = AnnotationColor.YELLOW
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def display_text(self) -> str:
        """Return display text or placeholder."""
        return self.text if self.text.strip() else "Click to edit..."

    @property
    def color_stylesheet(self) -> str:
        """Return Qt stylesheet for this annotation color."""
        color_map = {
            AnnotationColor.YELLOW: "background-color: #FFEB3B; border: 2px solid #FBC02D;",
            AnnotationColor.GREEN: "background-color: #8BC34A; border: 2px solid #689F38;",
            AnnotationColor.BLUE: "background-color: #64B5F6; border: 2px solid #1E88E5;",
            AnnotationColor.PINK: "background-color: #F48FB1; border: 2px solid #E91E63;",
            AnnotationColor.ORANGE: "background-color: #FFB74D; border: 2px solid #F57C00;",
            AnnotationColor.PURPLE: "background-color: #CE93D8; border: 2px solid #8E24AA;",
        }
        return color_map.get(self.color, color_map[AnnotationColor.YELLOW])