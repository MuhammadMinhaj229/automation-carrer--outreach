"""
Wikidata SPARQL Discovery Client.
Executes semantic queries on the Wikidata Knowledge Graph to discover registered organizations,
enterprises, and research institutes across specific countries and sectors.
"""

from typing import Dict, List, Optional
import urllib.parse
import urllib.request
import json


class WikidataClient:
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    GCC_COUNTRY_QIDS = {
        "AE": "Q878",   # United Arab Emirates
        "SA": "Q851",   # Saudi Arabia
        "OM": "Q842",   # Oman
        "QA": "Q1028",  # Qatar
        "BH": "Q398",   # Bahrain
        "KW": "Q810",   # Kuwait
    }

    @classmethod
    def query_companies_by_country(cls, country_code: str, limit: int = 25) -> List[Dict]:
        """
        Discovers registered companies, enterprises, or research entities based on country code.
        """
        qid = cls.GCC_COUNTRY_QIDS.get(country_code.upper())
        if not qid:
            raise ValueError(f"Country code {country_code} not mapped. Supported: {list(cls.GCC_COUNTRY_QIDS.keys())}")

        sparql_query = f"""
        SELECT ?item ?itemLabel ?inception ?website WHERE {{
          ?item wdt:P31/wdt:P279* wd:Q4830453 ; # instance of business enterprise
                wdt:P17 wd:{qid} .              # country
          OPTIONAL {{ ?item wdt:P571 ?inception . }}
          OPTIONAL {{ ?item wdt:P856 ?website . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,ar". }}
        }}
        LIMIT {limit}
        """

        params = {
            "query": sparql_query,
            "format": "json"
        }
        url = f"{cls.SPARQL_ENDPOINT}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url, 
            headers={
                "User-Agent": "ACIOS-CareerIntelligence/1.0 (minhajmuhammad229@gmail.com)",
                "Accept": "application/sparql-results+json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                bindings = data.get("results", {}).get("bindings", [])
                
                results = []
                for b in bindings:
                    results.append({
                        "wikidata_id": b.get("item", {}).get("value"),
                        "name": b.get("itemLabel", {}).get("value"),
                        "inception": b.get("inception", {}).get("value"),
                        "website": b.get("website", {}).get("value"),
                        "country_code": country_code.upper()
                    })
                return results
        except Exception as e:
            print(f"[WikidataClient Error] Query failed for {country_code}: {e}")
            return []
