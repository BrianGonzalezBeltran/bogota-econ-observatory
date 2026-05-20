"""
Agent tools that query the Observatory API endpoints.
Each tool wraps an HTTP call to the local FastAPI service.
"""

import os
import requests
from typing import Optional
from langchain_core.tools import tool

API_BASE = os.getenv("OBSERVATORY_API_URL", "http://localhost:8003/analytics")


def _get(path: str, params: dict = None):
    """Make a GET request to the Observatory API."""
    resp = requests.get(f"{API_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@tool
def get_summary() -> dict:
    """Get a high-level summary of all datasets: total active/created/cancelled businesses,
    latest unemployment and informality rates, and latest GDP total.
    Use this when the user asks for a general overview or broad economic indicators."""
    return _get("/summary")


@tool
def get_business_by_locality(year: Optional[int] = None, month: Optional[int] = None) -> list:
    """Get business metrics (active, created, cancelled) aggregated by locality (neighborhood).
    Returns all 20 localities of Bogotá sorted by active businesses.
    Use this when the user asks about businesses in a specific locality or wants to compare localities.

    Args:
        year: Filter by year (e.g. 2023, 2024). Optional.
        month: Filter by month (3=March, 9=September). Optional.
    """
    params = {}
    if year:
        params["year"] = year
    if month:
        params["month"] = month
    return _get("/business/by-locality", params)


@tool
def get_business_by_size(year: Optional[int] = None, locality: Optional[str] = None) -> list:
    """Get business metrics aggregated by company size (Microempresa, Pequeña, Mediana, Grande).
    Use this when the user asks about business distribution by size or about micro/small/medium/large enterprises.

    Args:
        year: Filter by year. Optional.
        locality: Filter by locality name (e.g. "Suba", "Kennedy", "Chapinero"). Optional. Case-insensitive partial match.
    """
    params = {}
    if year:
        params["year"] = year
    if locality:
        params["locality"] = locality
    return _get("/business/by-size", params)


@tool
def get_business_by_sector(
    year: Optional[int] = None,
    locality: Optional[str] = None,
    top_n: int = 10,
) -> list:
    """Get top economic sectors (ramas de actividad) by active businesses.
    Sectors include: Servicios, Comercio, Industria, Construcción, Agropecuaria.
    Use this when the user asks about which economic sectors have the most businesses.

    Args:
        year: Filter by year. Optional.
        locality: Filter by locality name. Optional.
        top_n: Number of top sectors to return (default 10, max 50).
    """
    params = {"top_n": top_n}
    if year:
        params["year"] = year
    if locality:
        params["locality"] = locality
    return _get("/business/by-sector", params)


@tool
def get_business_time_series(
    locality: Optional[str] = None,
    size: Optional[str] = None,
) -> list:
    """Get monthly time series of business creation and cancellation.
    Use this when the user asks about trends over time, growth, or evolution of businesses.

    Args:
        locality: Filter by locality name. Optional.
        size: Filter by company size (e.g. "Microempresa", "Pequeña"). Optional.
    """
    params = {}
    if locality:
        params["locality"] = locality
    if size:
        params["size"] = size
    return _get("/business/time-series", params)


@tool
def get_business_by_gender(
    year: Optional[int] = None,
    locality: Optional[str] = None,
) -> list:
    """Get business metrics by gender of legal representative (Masculino, Femenino, Indeterminado).
    Use this when the user asks about gender distribution in business ownership.

    Args:
        year: Filter by year. Optional.
        locality: Filter by locality name. Optional.
    """
    params = {}
    if year:
        params["year"] = year
    if locality:
        params["locality"] = locality
    return _get("/business/gender", params)


@tool
def get_labor_overview() -> list:
    """Get the full labor market time series for Bogotá: employment rate, unemployment rate,
    informality rate, and absolute numbers (ocupados, desocupados, informales).
    Data is quarterly from 2021 to 2025.
    Use this when the user asks about employment, unemployment, jobs, or labor market conditions."""
    return _get("/labor/overview")


@tool
def get_gdp_by_sector(
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    top_n: int = 10,
) -> list:
    """Get GDP (Producto Interno Bruto) by economic sector at constant 2015 prices.
    Use this when the user asks about the economy's size, GDP, economic output, or which sectors
    contribute the most to Bogotá's economy.

    Args:
        year: Filter by year (2005-2025). Optional.
        quarter: Filter by quarter (1-4). Optional.
        top_n: Number of top sectors (default 10).
    """
    params = {"top_n": top_n}
    if year:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter
    return _get("/gdp/by-sector", params)


@tool
def get_gdp_time_series(sector: Optional[str] = None) -> list:
    """Get quarterly GDP time series, optionally filtered by economic sector.
    Use this when the user asks about GDP trends, economic growth over time.

    Args:
        sector: Filter by sector name (partial match, e.g. "Comercio", "Industria"). Optional.
    """
    params = {}
    if sector:
        params["sector"] = sector
    return _get("/gdp/time-series", params)


@tool
def get_localities() -> list:
    """Get the list of all 20 localities (neighborhoods) in Bogotá with their codes.
    Use this when you need to verify a locality name or list available localities."""
    return _get("/dimensions/localities")


# All tools in a list for easy registration
ALL_TOOLS = [
    get_summary,
    get_business_by_locality,
    get_business_by_size,
    get_business_by_sector,
    get_business_time_series,
    get_business_by_gender,
    get_labor_overview,
    get_gdp_by_sector,
    get_gdp_time_series,
    get_localities,
]
