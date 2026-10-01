"""Торговые площадки Беларуси: icetrade.by, goszakupki.by, zakupki.butb.by."""
from __future__ import annotations

from urllib.parse import urlparse

from .base import GenericSite, Http, SiteConfig, load_site_configs, tender_matches  # noqa: F401
from ..models import Tender


def make_sites(http: Http, log=print) -> dict[str, GenericSite]:
    return {k: GenericSite(cfg, http, log) for k, cfg in load_site_configs().items()}


def tender_from_url(url: str, sites: dict[str, GenericSite]) -> Tender:
    """Тендер, добавленный вручную по ссылке."""
    host = urlparse(url).netloc.lower()
    for key, site in sites.items():
        if urlparse(site.cfg.base_url).netloc.lower() in host:
            ext = site.ext_id(url) or url
            return Tender(site=key, ext_id=ext, url=url)
    return Tender(site="manual", ext_id=str(abs(hash(url)))[:12], url=url)
