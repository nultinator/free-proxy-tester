import requests
import csv
import os
from dataclasses import dataclass, fields, asdict
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class ProxyResult:
    proxy: str = ""
    status: int = 0
    location: str = ""
    real_location: str = ""
    error: str = ""

TARGET_URL = "https://ipinfo.io/json"

def read_csv(filename):
    """Read CSV file and return its rows as a list of dictionaries with stripped keys."""
    with open(filename, newline="") as file:
        reader = csv.DictReader(file)
        # Strip whitespace from field names
        reader.fieldnames = [field.strip() for field in reader.fieldnames]
        return list(reader)

def extract_status_from_error(error_message: str):
    """Extract HTTP status code from error messages if available."""
    # Look for a 3-digit number preceded by 'HTTP' or 'status'
    match = re.search(r"(?:HTTP|status)\s+(\d{3})", error_message, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def test_proxy(row, proxy_field, location_field=None, protocol_field=None):
    """Test a proxy and return the result."""
    proxy_url = row[proxy_field]
    if protocol_field:
        protocol = "https" if row[protocol_field].lower() == "yes" else "http"
        proxy_url = f"{protocol}://{row[proxy_field]}"

    print(f"testing: {proxy_url}")
    proxies = {"http": proxy_url, "https": proxy_url}
    real_location = None
    response = None
    status_code = 0  # Default status code for failed requests
    error_message = ""

    try:
        response = requests.get(TARGET_URL, proxies=proxies, timeout=5)
        real_location = response.json().get("timezone", "Unknown")
        status_code = response.status_code
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_message = f"HTTPError: {e}"
    except requests.exceptions.ProxyError as e:
        error_message = f"ProxyError: {e}"
        status_code = extract_status_from_error(str(e))
    except requests.exceptions.ConnectionError as e:
        error_message = f"ConnectionError: {e}"
        status_code = extract_status_from_error(str(e))
    except requests.exceptions.Timeout as e:
        error_message = f"TimeoutError: {e}"
    except requests.exceptions.RequestException as e:
        error_message = f"RequestException: {e}"
    finally:
        if status_code < 200:
            status_code = 0
        return ProxyResult(
            proxy=proxy_url,
            status=status_code,
            location=row.get(location_field, "Unknown") if location_field else "Unknown",
            real_location=real_location or "Failed",
            error=error_message,
        )

def process_proxies(input_file, output_file, proxy_field, location_field=None, protocol_field=None, limit=None):
    """Process proxies from a file and save results to an output file."""
    rows = read_csv(input_file)
    if limit:
        rows = rows[:limit]
    
    # Ensure the results folder exists
    os.makedirs("results", exist_ok=True)
    output_file = os.path.join("results", output_file)
    
    with open(output_file, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[f.name for f in fields(ProxyResult)])
        writer.writeheader()

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_row = {executor.submit(test_proxy, row, proxy_field, location_field, protocol_field): row for row in rows}

            for future in as_completed(future_to_row):
                try:
                    result = future.result()
                    writer.writerow(asdict(result))
                    print(f"Result saved: {result}")
                except Exception as e:
                    print(f"Error processing proxy: {e}")

if __name__ == "__main__":
    # Input files
    LIMIT = 20
    proxyscape_file = "proxyscape.csv"
    free_proxy_file = "free-proxy-list.csv"
    proxy_nova_file = "proxy-nova.csv"
    geonode_file = "geonode.csv"

    # Test Proxyscape proxies
    print("Processing Proxyscrape proxies...")
    process_proxies(proxyscape_file, "proxyscrape-results.csv", proxy_field="proxy", location_field="ip_data_timezone", limit=LIMIT)

    # Test Free Proxy List proxies
    print("Processing Free Proxy List proxies...")
    process_proxies(free_proxy_file, "free-proxy-list-results.csv", proxy_field="IP Address", location_field="Country", protocol_field="Https", limit=LIMIT)

    # Test Proxynova proxies
    print("Processing Proxynova proxies...")
    process_proxies(proxy_nova_file, "proxynova-results.csv", proxy_field="proxy", location_field="Proxy Country", protocol_field=None, limit=LIMIT)

    # Test Geonode proxies
    print("Processing Geonode proxies...")
    process_proxies(geonode_file, "geonode-results.csv", proxy_field="proxy", location_field="country", protocol_field=None, limit=LIMIT)
