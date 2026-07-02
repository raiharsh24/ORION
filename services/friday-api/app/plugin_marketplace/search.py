from typing import List, Optional
from app.plugin_marketplace.base import PluginPackage, SearchResult


class PluginSearch:
    def __init__(self, repository) -> None:
        self._repo = repository

    def search(self, query: str, category: Optional[str] = None,
               tags: Optional[List[str]] = None, page: int = 1,
               page_size: int = 20) -> SearchResult:
        q = query.lower()
        results = []
        for pkg in self._repo.get_all_packages():
            if q and q not in pkg.id.lower() and q not in pkg.name.lower():
                continue
            if category and category.lower() not in [c.lower() for c in pkg.categories]:
                continue
            if tags:
                pkg_tags_lower = [t.lower() for t in pkg.tags]
                if not any(t.lower() in pkg_tags_lower for t in tags):
                    continue
            results.append(pkg)

        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        page_results = results[start:end]

        all_categories = set()
        all_tags = set()
        for pkg in results:
            all_categories.update(pkg.categories)
            all_tags.update(pkg.tags)

        return SearchResult(
            query=query,
            total=total,
            results=page_results,
            categories=sorted(all_categories),
            tags=sorted(all_tags),
            page=page,
            page_size=page_size,
            total_pages=max(1, (total + page_size - 1) // page_size),
        )

    def search_by_id(self, plugin_id: str) -> Optional[PluginPackage]:
        return self._repo.get_package(plugin_id)

    def list_by_category(self, category: str) -> List[PluginPackage]:
        return self._repo.get_by_category(category)

    def get_featured(self) -> List[PluginPackage]:
        return self._repo.get_featured()

    def get_installed(self, installed_ids) -> List[PluginPackage]:
        return self._repo.get_installed(installed_ids)

    def get_updates(self, installed: dict) -> List[PluginPackage]:
        return self._repo.get_available_updates(installed)
