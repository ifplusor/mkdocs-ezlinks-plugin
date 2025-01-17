from dataclasses import dataclass


class BrokenLink(Exception):
    pass


@dataclass
class Link:
    """Dataclass to hold the contents required to form a complete Link."""

    image: bool
    text: str
    target: str
    anchor: str
    title: str

    # Render as a complete MD compatible link
    def render(self, title_as_text=False):
        img = "!" if self.image else ""
        anchor = f"#{self.anchor}" if self.anchor else ""
        title = f' "{self.title}"' if self.title else ""

        if title_as_text and self.title:
            return f"{img}[{self.title}]({self.target}{anchor})"
        else:
            return f"{img}[{self.text}]({self.target}{anchor}{title})"


@dataclass
class EzLinksOptions:
    """Dataclass to hold typed options from the configuration."""

    wikilinks: bool
    warn_ambiguities: bool
    reference_links: bool
