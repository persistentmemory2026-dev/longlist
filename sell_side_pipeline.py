"""Longlist — Sell-side pipeline: multi-group search → enrich → multi-tab Excel."""
import logging
from typing import Any

from config import APP_URL, PACKAGES
from openregister_client import ENDPOINT_FETCHERS
from pipeline import enrich_company
from preview_search import run_preview_search
from sell_side_excel import generate_sell_side_excel
from job_store import merge_job

logger = logging.getLogger("longlist.sell_side_pipeline")


async def run_sell_side_pipeline(
    job_id: str,
    package: str,
    buyer_groups: list[dict[str, Any]],
    target_name: str = "",
) -> dict[str, Any]:
    """
    Full sell-side enrichment pipeline:
    1. Per buyer group: paginated search up to selected_count
    2. Deduplicate across groups (by company_id)
    3. Enrich each company (batched)
    4. Generate multi-tab Excel
    """
    from openregister import Openregister
    from config import OPENREGISTER_API_KEY

    pkg_config = PACKAGES[package]
    endpoints = pkg_config["endpoints"]
    include_email = pkg_config["includes_email_lookup"]

    all_enriched: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for group in buyer_groups:
        target_count = group.get("selected_count", 0)
        if target_count == 0:
            group["companies"] = []
            continue

        # Search (paginated) for this buyer group
        companies_to_enrich: list[dict[str, str]] = []
        client = Openregister(api_key=OPENREGISTER_API_KEY)
        page = 1
        per_page = 50

        while len(companies_to_enrich) < target_count:
            try:
                search_kwargs: dict[str, Any] = {
                    "query": {"value": group.get("query", "")},
                    "pagination": {"page": page, "per_page": per_page},
                }
                # Sanitize filters (all values must be strings)
                filters = []
                for f in group.get("filters") or []:
                    sf = dict(f)
                    for k, v in sf.items():
                        if isinstance(v, (int, float, bool)):
                            sf[k] = str(v)
                    filters.append(sf)
                if filters:
                    search_kwargs["filters"] = filters
                if group.get("location"):
                    search_kwargs["location"] = group["location"]

                result = client.search.find_companies_v1(**search_kwargs)

                if not result.results:
                    break

                for r in result.results:
                    cid = getattr(r, "company_id", "")
                    if cid and cid not in seen_ids:
                        companies_to_enrich.append({
                            "company_id": cid,
                            "name": getattr(r, "name", ""),
                        })
                        seen_ids.add(cid)
                    if len(companies_to_enrich) >= target_count:
                        break

                total_available = result.pagination.total_results if hasattr(result, "pagination") else 0
                if len(companies_to_enrich) >= total_available:
                    break
                page += 1

            except Exception as e:
                logger.error("Search failed for group '%s': %s", group.get("name"), e)
                break

        logger.info("Group '%s': found %d companies to enrich (target: %d)",
                     group.get("name"), len(companies_to_enrich), target_count)

        # Enrich companies (batched)
        import asyncio
        enriched: list[dict[str, Any]] = []
        batch_size = 10

        for i in range(0, len(companies_to_enrich), batch_size):
            batch = companies_to_enrich[i:i + batch_size]
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

        group["companies"] = enriched
        all_enriched.extend(enriched)

        logger.info("Group '%s': enriched %d / %d", group.get("name"),
                     len(enriched), len(companies_to_enrich))

    # Persist enriched data
    merge_job(job_id, {
        "status": "enriched",
        "enriched_data": all_enriched,
        "total_companies": len(all_enriched),
    })

    if not all_enriched:
        logger.warning("Sell-side pipeline produced 0 enriched companies for job %s", job_id)
        return {
            "excel_path": None,
            "total_found": 0,
            "enriched_count": 0,
            "job_id": job_id,
        }

    # Generate multi-tab Excel
    excel_path = generate_sell_side_excel(
        buyer_groups=buyer_groups,
        package=package,
        job_id=job_id,
        target_name=target_name,
        app_url=APP_URL,
    )

    merge_job(job_id, {
        "status": "excel_ready",
        "pipeline_result": {
            "excel_path": excel_path,
            "total_found": len(all_enriched),
            "enriched_count": len(all_enriched),
        },
    })

    logger.info("Sell-side pipeline complete: job=%s, %d companies across %d groups",
                job_id, len(all_enriched), len(buyer_groups))

    return {
        "excel_path": excel_path,
        "total_found": len(all_enriched),
        "enriched_count": len(all_enriched),
        "job_id": job_id,
    }
