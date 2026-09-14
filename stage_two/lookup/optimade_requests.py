"""
optimade_requests.py

Drop-in replacement for OptimadeClient that uses requests directly.
No Jupyter dependencies, no ipywidgets, no nglview.

Usage — replace:
    from optimade.client import OptimadeClient
    client = OptimadeClient(base_urls=[URL], use_async=False, silent=True)
    raw = client.get(filter=filter_str, response_fields=FIELDS)

With:
    from stage_two.lookup.optimade_requests import OptimadeClient
    client = OptimadeClient(base_urls=[URL])
    raw = client.get(filter=filter_str, response_fields=FIELDS)

The return format matches what OptimadeClient.get() returns so the
existing _extract_results() functions work without changes.
"""

import time
import requests


class OptimadeClient:
    """
    Minimal OPTIMADE client using requests.
    Matches the subset of OptimadeClient API used in oqmd_lookup_v2.py
    and alexandria_lookup_v2.py — specifically client.get() returning
    the nested dict structure those files expect.
    """

    def __init__(self, base_urls, use_async=False, silent=True,
                 timeout=30, page_limit=100):
        self.base_url = base_urls[0].rstrip('/')
        self.timeout = timeout
        self.page_limit = page_limit

    def get(self, filter: str, response_fields=None):
        """
        Query the OPTIMADE /structures endpoint.

        Returns a dict matching OptimadeClient.get() output:
            {
              "structures": {
                filter_str: {
                  base_url: {
                    "data": [...],
                    "errors": [...],
                  }
                }
              }
            }
        """
        params = {
            "filter": filter,
            "page_limit": self.page_limit,
        }
        if response_fields:
            params["response_fields"] = ",".join(response_fields)

        all_data = []
        errors = []
        url = f"{self.base_url}/structures"

        # Paginate through all results
        while url:
            try:
                r = requests.get(url, params=params, timeout=self.timeout)
                r.raise_for_status()
                body = r.json()
            except requests.exceptions.Timeout:
                errors.append(f"Timeout after {self.timeout}s")
                break
            except requests.exceptions.HTTPError as e:
                errors.append(str(e))
                break
            except Exception as e:
                errors.append(str(e))
                break

            all_data.extend(body.get("data") or [])

            # Follow pagination
            next_url = (body.get("links") or {}).get("next")
            if next_url and next_url != url:
                url = next_url
                params = {}   # params are baked into next_url
            else:
                break

        return {
            "structures": {
                filter: {
                    self.base_url: {
                        "data": all_data,
                        "errors": errors,
                    }
                }
            }
        }
