import os
import re
from functools import partial
from typing import Dict, List, Match
from urllib.parse import quote

from .file_mapper import FileMapper
from .scanners.base_link_scanner import BaseLinkScanner
from .types import BrokenLink, EzLinksOptions, Link


class EzLinksReplacer:
    def __init__(self, root: str, file_map: FileMapper, use_directory_urls: bool, options: EzLinksOptions, logger):
        self.root = root
        self.file_map = file_map
        self.use_directory_urls = use_directory_urls
        self.options = options
        self.scanners = []
        self.target_scanners = []  # type: List[BaseLinkScanner]
        self.logger = logger

    def add_scanner(self, scanner: BaseLinkScanner) -> None:
        self.scanners.append(scanner)

    def add_target_scanner(self, scanner: BaseLinkScanner) -> None:
        self.target_scanners.append(scanner)

    def replace(self, path: str, markdown: str) -> str:
        self.path = path

        target_map = self._build_target_map(markdown)
        do_replace = partial(self._do_replace, target_map=target_map)

        # Multi-Pattern search pattern, to capture all link types at once
        return re.sub(self.regex, do_replace, markdown)

    # Compiles all scanner patterns as a multi-pattern search, with
    # built in code fence skipping (individual link scanners don't
    # have to worry about them.
    def compile(self):
        patterns = "|".join([scanner.pattern() for scanner in self.scanners])
        self.regex = re.compile(
            rf"""
            (?: # Attempt to match a code block
                [`]{{3}}
                (?:[\w\W]*?)
                [`]{{3}}$
            | # Match an inline code block
                `[\w\W]*?`
            )
            | # Attempt to match any one of the subpatterns
            (?:
                {patterns}
            )
            """,
            re.X | re.MULTILINE,
        )

        target_patterns = "|".join([scanner.pattern() for scanner in self.target_scanners])
        self.target_regex = re.compile(
            rf"""
            (?: # Attempt to match any one of the subpatterns
                {target_patterns}
            )
            """,
            re.X | re.MULTILINE,
        )

    def _build_target_map(self, markdown: str):
        target_map = {}

        abs_from = os.path.dirname(os.path.join(self.root, self.path))

        for match in re.finditer(self.target_regex, markdown):
            try:
                for scanner in self.target_scanners:
                    if scanner.match(match):
                        link = scanner.extract(match)

                        # Do some massaging of the extracted results
                        if not link:
                            raise BrokenLink(f"Could not extract link from '{match.group(0)}'")

                        # Handle case of local page anchor
                        if not link.target:
                            if link.anchor:
                                link.target = os.path.join(self.root, self.path)
                            else:
                                raise BrokenLink(f"No target for link '{match.group(0)}'")
                        else:
                            # Otherwise, search for the target through the file map
                            search_result = self.file_map.search(self.path, link.target)
                            if not self.use_directory_urls:
                                search_result = search_result + ".md" if "." not in search_result else search_result

                            if not search_result:
                                raise BrokenLink(f"'{link.target}' not found.")
                            link.target = search_result

                        link.target = os.path.relpath(link.target, abs_from)

                        target_map[link.text] = link
            except BrokenLink as ex:
                # Log these out as Debug messages, as the regular mkdocs
                # strict mode will log out broken links.
                self.logger.debug(f"[EzLinks] {ex}")

        return target_map

    def _do_replace(self, match: Match, target_map: Dict[str, Link]) -> str:
        abs_from = os.path.dirname(os.path.join(self.root, self.path))
        try:
            for scanner in self.scanners:
                if scanner.match(match):
                    link = scanner.extract(match)

                    # Do some massaging of the extracted results
                    if not link:
                        raise BrokenLink(f"Could not extract link from '{match.group(0)}'")

                    # Handle case of local page anchor
                    if not link.target:
                        if link.anchor:
                            link.target = os.path.join(self.root, self.path)
                        else:
                            raise BrokenLink(f"No target for link '{match.group(0)}'")
                    elif link.target in target_map:
                        return target_map[link.target].render(title_as_text=True)
                    else:
                        # Otherwise, search for the target through the file map
                        search_result = self.file_map.search(self.path, link.target)
                        if not self.use_directory_urls:
                            search_result = search_result + ".md" if "." not in search_result else search_result

                        if not search_result:
                            raise BrokenLink(f"'{link.target}' not found.")
                        link.target = search_result

                    link.target = quote(os.path.relpath(link.target, abs_from))
                    return link.render()
        except BrokenLink as ex:
            # Log these out as Debug messages, as the regular mkdocs
            # strict mode will log out broken links.
            self.logger.debug(f"[EzLinks] {ex}")

        # Fall through, return the original link unaltered, and let mkdocs handle it
        return match.group(0)
