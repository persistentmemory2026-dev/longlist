"""Longlist — Enrichment pipeline: search → enrich each company → generate Excel."""
import asyncio
import logging
import uuid
from typing import Any

from config import PACKAGES
from openregister_client import ENDPOINT_FETCHERS
from preview_search import run_preview_search
from anymailfinder_client import find_email
from excel_generator import generate_excel
from job_store import merge_job

logger = logging.getLogger("longlist.pipeline")


async def enrich_company(
    company_id: str,
    company_name: str,
    endpoints: list[str],
    include_email_lookup: bool = False,
) -> dict[str, Any]:
    """
    Enrich a single company by calling the specified OpenRegister endpoints.
    Optionally look up GF email via Anymailfinder.
    """
    result: dict[str, Any] = {
        "company_id": company_id,
        "name": company_name,
    }

    # Fetch all endpoints concurrently
    tasks = {}
    for ep in endpoints:
        fetcher = ENDPOINT_FETCHERS.get(ep)
        if fetcher:
            tasks[ep] = fetcher(company_id)

    if tasks:
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for ep_name, data in zip(tasks.keys(), gathered):
            if isinstance(data, Exception):
                logger.error("Endpoint %s failed for %s: %s", ep_name, company_id, data)
                result[ep_name] = {"error": str(data)}
            else:
                result[ep_name] = data

    # Email lookup (PREMIUM only)
    if include_email_lookup:
        details = result.get("details", {})

        # Get first representative name from details.representation
        reps = details.get("representation") or details.get("representatives") or []
        gf_name = None
        if isinstance(reps, list) and reps:
            rep = reps[0]
            if isinstance(rep, dict):
                gf_name = rep.get("name") or f"{rep.get('first_name', '')} {rep.get('last_name', '')}".strip()
            elif isinstance(rep, str):
                gf_name = rep

        # Get domain from details.contact (Details endpoint includes contact data)
        contact_data = details.get("contact", {})
        if isinstance(contact_data, dict):
            domain = contact_data.get("website") or ""
        else:
            domain = ""
        # Fallback to top-level website
        if not domain:
            domain = details.get("website") or ""

        if gf_name and domain:
            email_result = await find_email(gf_name, domain)
            result["gf_email"] = email_result.get("email")
        else:
            result["gf_email"] = None
            logger.info("Skipping email lookup for %s: name=%s, domain=%s", company_id, gf_name, domain)

    return result


async def run_pipeline(
    job_id: str,
    service_type: str,
    package: str,
    parsed_briefing: dict[str, Any],
    max_companies: int = 500,
) -> dict[str, Any]:
    """
    Full enrichment pipeline:
    1. Search companies (longlist) or use provided list (enrichment)
    2. Enrich each company according to package tier
    3. Generate Excel

    Returns: {"excel_path": str, "total_found": int, "enriched_count": int, "job_id": str}
    """
    pkg_config = PACKAGES[package]
    endpoints = pkg_config["endpoints"]
    include_email = pkg_config["includes_email_lookup"]

    logger.info("Pipeline started: job=%s, service=%s, package=%s", job_id, service_type, package)

    # Step 1: Get company list
    companies_to_enrich: list[dict[str, str]] = []

    if service_type == "longlist":
        # Search via OpenRegister
        query = parsed_briefing.get("query", "")
        filters = parsed_briefing.get("filters", [])
        location = parsed_briefing.get("location")

        # Fetch all results (paginate)
        page = 1
        per_page = 50
        total_fetched = 0

        while total_fetched < max_companies:
            from openregister import Openregister
            from config import OPENREGISTER_API_KEY

            client = Openregister(api_key=OPENREGISTER_API_KEY)
            search_kwargs: dict[str, Any] = {
                "query": {"value": query},
                "pagination": {"page": page, "per_page": per_page},
            }
            if filters:
                search_kwargs["filters"] = filters
            if location:
                search_kwargs["location"] = location

            result = client.search.find_companies_v1(**search_kwargs)
            total_available = result.pagination.total_results if hasattr(result, "pagination") else 0

            for r in result.results or []:
                companies_to_enrich.append({
                    "company_id": getattr(r, "company_id", ""),
                    "name": getattr(r, "name", ""),
                })
                total_fetched += 1
                if total_fetched >= max_companies:
                    break

            # Check if more pages
            if not result.results or total_fetched >= total_available:
                break
            page += 1

        logger.info("Search complete: %d companies to enrich (of %d total)", len(companies_to_enrich), total_available)

    elif service_type == "enrichment":
        # Use provided company list — search each name to get company_id
        company_names = parsed_briefing.get("company_list", []) or []
        from openregister import Openregister
        from config import OPENREGISTER_API_KEY

        client = Openregister(api_key=OPENREGISTER_API_KEY)
        for name in company_names:
            try:
                result = client.search.find_companies_v1(
                    query={"value": name},
                    filters=[{"field": "status", "value": "active"}],
                    pagination={"page": 1, "per_page": 1},
                )
                if result.results:
                    r = result.results[0]
                    companies_to_enrich.append({
                        "company_id": getattr(r, "company_id", ""),
                        "name": getattr(r, "name", name),
                    })
                else:
                    logger.warning("Company not found: %s", name)
            except Exception as e:
                logger.error("Search failed for %s: %s", name, e)

    if not companies_to_enrich:
        logger.warning("No companies to enrich for job %s", job_id)
        return {
            "excel_path": None,
            "total_found": 0,
            "enriched_count": 0,
            "job_id": job_id,
        }

    # Step 2: Enrich companies (concurrent, batched to avoid rate limits)
    enriched: list[dict[str, Any]] = []
    batch_size = 10  # Process 10 companies concurrently

    for i in range(0, len(companies_to_enrich), batch_size):
        batch = companies_to_enrich[i : i + batch_size]
        tasks = [
            enrich_company(
                company_id=c["company_id"],
                company_name=c["name"],
                endpoints=endpoints,
                include_email_lookup=include_email,
            )
            for c in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.error("Enrichment failed: %s", r)
            else:
                enriched.append(r)

        logger.info("Enriched %d / %d companies", len(enriched), len(companies_to_enrich))

    # Persist enriched data to job store (survives redeployments with PG)
    merge_job(job_id, {
        "status": "enriched",
        "enriched_data": enriched,
        "total_companies": len(companies_to_enrich),
    })
    logger.info("Enriched data persisted for job %s", job_id)

    # Step 3: Generate Excel
    excel_path = generate_excel(
        companies=enriched,
        package=package,
        job_id=job_id,
        output_dir="/tmp",
    )

    # Persist final pipeline result
    merge_job(job_id, {
        "status": "excel_ready",
        "pipeline_result": {
            "excel_path": excel_path,
            "total_found": len(companies_to_enrich),
            "enriched_count": len(enriched),
        },
    })

    logger.info("Pipeline complete: job=%s, %d companies enriched", job_id, len(enriched))

    return {
        "excel_path": excel_path,
        "total_found": len(companies_to_enrich),
        "enriched_count": len(enriched),
        "job_id": job_id,
    }
