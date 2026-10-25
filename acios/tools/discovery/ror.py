"""
ROR (Research Organization Registry) Discovery Client.
Free, open-data global discovery engine for research centers, university labs, and institutes.
Supports ROR Schema v2.
"""

from typing import Dict, List, Optional
import urllib.parse
import urllib.request
import json


class RORClient:
    BASE_URL = "https://api.ror.org/organizations"

    @classmethod
    def search_organizations(cls, query: str, country_code: Optional[str] = None) -> List[Dict]:
        """
        Queries the ROR database for research organizations, universities, and government institutes.
        Example: search_organizations("United Arab Emirates University", country_code="AE")
        """
        params = {"query": query}
        if country_code:
            params["filter"] = f"locations.geonames_details.country_code:{country_code.upper()}"

        url = f"{cls.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "ACIOS-CareerIntelligence/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                
                results = []
                for item in items:
                    # Extract primary display name
                    display_name = None
                    names = item.get("names", [])
                    for n in names:
                        if "ror_display" in n.get("types", []):
                            display_name = n.get("value")
                            break
                    if not display_name and names:
                        display_name = names[0].get("value")

                    # Extract location details
                    loc_name, country_name, subdivision = None, None, None
                    locations = item.get("locations", [])
                    if locations:
                        geo = locations[0].get("geonames_details", {})
                        loc_name = geo.get("name")
                        country_name = geo.get("country_name")
                        subdivision = geo.get("country_subdivision_name")

                    # Extract official website
                    website = None
                    for link in item.get("links", []):
                        if link.get("type") == "website":
                            website = link.get("value")
                            break

                    results.append({
                        "ror_id": item.get("id"),
                        "name": display_name,
                        "city": loc_name,
                        "subdivision": subdivision,
                        "country": country_name,
                        "website": website
                    })
                return results
        except Exception as e:
            print(f"[RORClient Error] Search failed for '{query}': {e}")
            return []
