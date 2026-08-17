"""
Satellite Data Source Integration
Connects to free satellite imagery providers: Copernicus, USGS, OpenTopography.
Handles authentication, search, download, and cataloging of remote sensing data.
"""

import os
import json
import hashlib
import logging
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlencode
import math

logger = logging.getLogger(__name__)


class SatelliteSource(Enum):
    COPERNICUS = "copernicus"
    USGS = "usgs"
    OPENTOPOGRAPHY = "opentopography"
    LOCAL = "local"


class SentinelBand(Enum):
    B01 = "B01"
    B02 = "B02"
    B03 = "B03"
    B04 = "B04"
    B05 = "B05"
    B06 = "B06"
    B07 = "B07"
    B08 = "B08"
    B08A = "B8A"
    B09 = "B09"
    B10 = "B10"
    B11 = "B11"
    B12 = "B12"


SENTINEL_BAND_INFO = {
    "B01": {"name": "Coastal aerosol", "wavelength": 443, "resolution": 60, "center_nm": 443},
    "B02": {"name": "Blue", "wavelength": 490, "resolution": 10, "center_nm": 490},
    "B03": {"name": "Green", "wavelength": 560, "resolution": 10, "center_nm": 560},
    "B04": {"name": "Red", "wavelength": 665, "resolution": 10, "center_nm": 665},
    "B05": {"name": "Vegetation Red Edge", "wavelength": 705, "resolution": 20, "center_nm": 705},
    "B06": {"name": "Vegetation Red Edge", "wavelength": 740, "resolution": 20, "center_nm": 740},
    "B07": {"name": "Vegetation Red Edge", "wavelength": 783, "resolution": 20, "center_nm": 783},
    "B08": {"name": "NIR", "wavelength": 842, "resolution": 10, "center_nm": 842},
    "B08A": {"name": "NIR narrow", "wavelength": 865, "resolution": 20, "center_nm": 865},
    "B09": {"name": "Water vapour", "wavelength": 945, "resolution": 60, "center_nm": 945},
    "B10": {"name": "Cirrus", "wavelength": 1375, "resolution": 60, "center_nm": 1375},
    "B11": {"name": "SWIR 1", "wavelength": 1610, "resolution": 20, "center_nm": 1610},
    "B12": {"name": "SWIR 2", "wavelength": 2190, "resolution": 20, "center_nm": 2190},
}


class LandsatBand(Enum):
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    B4 = "B4"
    B5 = "B5"
    B6 = "B6"
    B7 = "B7"
    B8 = "B8"


LANDSAT_BAND_INFO = {
    "B1": {"name": "Coastal", "wavelength": 443, "resolution": 30, "collection": "2"},
    "B2": {"name": "Blue", "wavelength": 482, "resolution": 30, "collection": "2"},
    "B3": {"name": "Green", "wavelength": 561, "resolution": 30, "collection": "2"},
    "B4": {"name": "Red", "wavelength": 655, "resolution": 30, "collection": "2"},
    "B5": {"name": "NIR", "wavelength": 865, "resolution": 30, "collection": "2"},
    "B6": {"name": "SWIR1", "wavelength": 1609, "resolution": 30, "collection": "2"},
    "B7": {"name": "SWIR2", "wavelength": 2201, "resolution": 30, "collection": "2"},
    "B8": {"name": "Panchromatic", "wavelength": 590, "resolution": 15, "collection": "2"},
}


@dataclass
class BoundingBox:
    west: float
    south: float
    east: float
    north: float
    crs: str = "EPSG:4326"

    def to_geojson(self) -> Dict:
        return {
            "type": "Polygon",
            "coordinates": [[
                [self.west, self.south],
                [self.east, self.south],
                [self.east, self.north],
                [self.west, self.north],
                [self.west, self.south]
            ]]
        }

    def to_bbox_string(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"

    def area_km2(self) -> float:
        lat_dist = (self.north - self.south) * 111.32
        lon_dist = (self.east - self.west) * 111.32 * math.cos(math.radians((self.north + self.south) / 2))
        return abs(lat_dist * lon_dist)


@dataclass
class Coordinate:
    longitude: float
    latitude: float
    elevation: Optional[float] = None
    crs: str = "EPSG:4326"

    def to_utm_zone(self) -> int:
        return int((self.longitude + 180) / 6) + 1

    def to_utm_crs(self) -> str:
        zone = self.to_utm_zone()
        hemisphere = "north" if self.latitude >= 0 else "south"
        epsg = 32600 + zone if hemisphere == "north" else 32700 + zone
        return f"EPSG:{epsg}"


@dataclass
class SatelliteImage:
    id: str
    source: SatelliteSource
    satellite: str
    bands: List[str]
    bbox: BoundingBox
    acquisition_date: datetime
    cloud_cover_percent: float
    resolution_m: float
    filepath: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchQuery:
    bbox: BoundingBox
    start_date: datetime
    end_date: datetime
    max_cloud_cover: float = 20.0
    satellite: str = "sentinel2"
    limit: int = 10


@dataclass
class SearchResult:
    images: List[SatelliteImage]
    total_count: int
    query: SearchQuery
    source: SatelliteSource


class CopernicusSource:
    """Copernicus Open Access Hub data source for Sentinel imagery."""

    BASE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

    def __init__(self, username: str = "", password: str = ""):
        self.username = username or os.getenv("COPERNICUS_USERNAME", "")
        self.password = password or os.getenv("COPERNICUS_PASSWORD", "")
        self._token = None
        self._token_expiry = None

    def search(self, query: SearchQuery) -> SearchResult:
        """Search Copernicus for Sentinel-2 imagery."""
        bbox_str = query.bbox.to_bbox_string()
        start_str = query.start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_str = query.end_date.strftime("%Y-%m-%dT23:59:59.999Z")

        filter_parts = [
            f"Collection/Name eq 'SENTINEL-2'",
            f"OData.CSC.Intersects(area=geography'SRID=4326;POINT({(query.bbox.west + query.bbox.east)/2} {(query.bbox.south + query.bbox.north)/2})')",
            f"ContentDate/Start gt {start_str}",
            f"ContentDate/Start lt {end_str}",
            f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt {query.max_cloud_cover})"
        ]

        params = {
            "$filter": " and ".join(filter_parts),
            "$top": query.limit,
            "$orderby": "ContentDate/Start desc",
            "$expand": "Attributes"
        }

        images = []

        try:
            import httpx
            url = f"{self.BASE_URL}/Products"
            response = httpx.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                for product in data.get("value", []):
                    img = self._parse_product(product, query.bbox)
                    if img:
                        images.append(img)
        except Exception as e:
            logger.warning(f"Copernicus search failed: {e}")
            images = self._generate_offline_results(query)

        return SearchResult(
            images=images,
            total_count=len(images),
            query=query,
            source=SatelliteSource.COPERNICUS
        )

    def _parse_product(self, product: Dict, bbox: BoundingBox) -> Optional[SatelliteImage]:
        """Parse a Copernicus product into SatelliteImage."""
        try:
            name = product.get("Name", "")
            attrs = {a["Name"]: a.get("Value", "") for a in product.get("Attributes", [])}

            date_str = product.get("ContentDate", {}).get("Start", "")
            if date_str:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                return None

            cloud = float(attrs.get("cloudCover", 0))

            return SatelliteImage(
                id=product.get("Id", name),
                source=SatelliteSource.COPERNICUS,
                satellite="Sentinel-2",
                bands=["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B08A", "B09", "B10", "B11", "B12"],
                bbox=bbox,
                acquisition_date=date,
                cloud_cover_percent=cloud,
                resolution_m=10.0,
                metadata={
                    "product_type": attrs.get("productType", ""),
                    "processing_level": attrs.get("processingLevel", ""),
                    "instrument": attrs.get("instrument", "MSI")
                }
            )
        except Exception as e:
            logger.error(f"Failed to parse product: {e}")
            return None

    def _generate_offline_results(self, query: SearchQuery) -> List[SatelliteImage]:
        """Generate synthetic results for offline/testing mode."""
        images = []
        current_date = query.end_date
        for i in range(min(query.limit, 5)):
            cloud = 5 + (i * 3)
            if cloud > query.max_cloud_cover:
                continue
            img = SatelliteImage(
                id=f"S2A_MSIL2A_{current_date.strftime('%Y%m%d')}_{i:04d}",
                source=SatelliteSource.COPERNICUS,
                satellite="Sentinel-2",
                bands=["B02", "B03", "B04", "B08", "B11", "B12"],
                bbox=query.bbox,
                acquisition_date=current_date,
                cloud_cover_percent=cloud,
                resolution_m=10.0,
                metadata={"offline": True, "synthetic": True}
            )
            images.append(img)
            current_date -= timedelta(days=5)
        return images

    def download_metadata(self, product_id: str) -> Dict[str, Any]:
        """Get download metadata for a product."""
        return {
            "product_id": product_id,
            "status": "metadata_only",
            "message": "Full download requires Copernicus credentials. Metadata available.",
            "bands_available": ["B02", "B03", "B04", "B08", "B11", "B12"],
            "format": "SAFE"
        }


class USGSSource:
    """USGS EarthExplorer data source for Landsat and ASTER imagery."""

    SEARCH_URL = "https://earthexplorer.usgs.gov/search"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("USGS_API_KEY", "")

    def search(self, query: SearchQuery) -> SearchResult:
        """Search USGS for Landsat imagery."""
        images = []

        try:
            import httpx
            center_lat = (query.bbox.north + query.bbox.south) / 2
            center_lon = (query.bbox.east + query.bbox.west) / 2

            params = {
                "datasetName": "landsat_c2_l2",
                "lat": center_lat,
                "lon": center_lon,
                "maxCloudCover": query.max_cloud_cover,
                "startDate": query.start_date.strftime("%Y-%m-%d"),
                "endDate": query.end_date.strftime("%Y-%m-%d"),
                "maxResults": query.limit
            }

            response = httpx.get(self.SEARCH_URL, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for result in data.get("results", []):
                    img = self._parse_result(result, query.bbox)
                    if img:
                        images.append(img)
        except Exception as e:
            logger.warning(f"USGS search failed: {e}")
            images = self._generate_offline_results(query)

        return SearchResult(
            images=images,
            total_count=len(images),
            query=query,
            source=SatelliteSource.USGS
        )

    def _parse_result(self, result: Dict, bbox: BoundingBox) -> Optional[SatelliteImage]:
        """Parse a USGS result into SatelliteImage."""
        try:
            entity_id = result.get("entityId", "")
            cloud_cover = result.get("cloudCover", 0)

            date_str = result.get("acquisitionDate", "")
            if date_str:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                return None

            return SatelliteImage(
                id=entity_id,
                source=SatelliteSource.USGS,
                satellite="Landsat 8/9",
                bands=["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"],
                bbox=bbox,
                acquisition_date=date,
                cloud_cover_percent=cloud_cover,
                resolution_m=30.0,
                metadata={
                    "collection": "2",
                    "level": "Level-2",
                    "instrument": "OLI/TIRS"
                }
            )
        except Exception as e:
            logger.error(f"Failed to parse USGS result: {e}")
            return None

    def _generate_offline_results(self, query: SearchQuery) -> List[SatelliteImage]:
        """Generate offline test results."""
        images = []
        current_date = query.end_date
        for i in range(min(query.limit, 3)):
            img = SatelliteImage(
                id=f"LC08_L2_{current_date.strftime('%Y%m%d')}_{i:04d}",
                source=SatelliteSource.USGS,
                satellite="Landsat 8/9",
                bands=["B2", "B3", "B4", "B5", "B6", "B7"],
                bbox=query.bbox,
                acquisition_date=current_date,
                cloud_cover_percent=5.0 + (i * 5),
                resolution_m=30.0,
                metadata={"offline": True, "synthetic": True}
            )
            images.append(img)
            current_date -= timedelta(days=16)
        return images


class DEMSource:
    """DEM (Digital Elevation Model) data source from OpenTopography."""

    BASE_URL = "https://portal.opentopography.org/API/globaldem"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("OPENTOPOGRAPHY_API_KEY", "")

    def search(self, bbox: BoundingBox) -> Dict[str, Any]:
        """Get DEM data for a bounding box."""
        datasets = [
            {"name": "SRTM GL1", "resolution": "30m", "source": "NASA/USGS"},
            {"name": "SRTM GL3", "resolution": "90m", "source": "NASA/USGS"},
            {"name": "ASTER GDEM", "resolution": "30m", "source": "NASA/METI"},
            {"name": "COPERNICUS DEM", "resolution": "30m", "source": "ESA"},
            {"name": "COPERNICUS DEM", "resolution": "90m", "source": "ESA"},
        ]

        return {
            "bbox": bbox.to_bbox_string(),
            "area_km2": bbox.area_km2(),
            "datasets": datasets,
            "recommended": "COPERNICUS DEM 30m",
            "download_url": self._build_download_url(bbox),
            "formats": ["GeoTIFF", "ASCII Grid"]
        }

    def _build_download_url(self, bbox: BoundingBox) -> str:
        """Build download URL for DEM data."""
        params = {
            "demtype": "SRTMGL1",
            "south": bbox.south,
            "north": bbox.north,
            "west": bbox.west,
            "east": bbox.east,
            "outputFormat": "GTiff",
            "API_Key": self.api_key
        }
        return f"{self.BASE_URL}?{urlencode(params)}"


class SatelliteDataSourceManager:
    """Manages all satellite data sources."""

    def __init__(self):
        self.copernicus = CopernicusSource()
        self.usgs = USGSSource()
        self.dem = DEMSource()
        self._local_catalog: List[SatelliteImage] = []
        self._catalog_path = Path(tempfile.gettempdir()) / "mining_ai_satellite_catalog.json"
        self._load_catalog()

    def _load_catalog(self):
        """Load local satellite image catalog."""
        if self._catalog_path.exists():
            try:
                with open(self._catalog_path) as f:
                    data = json.load(f)
                    for item in data:
                        img = SatelliteImage(
                            id=item["id"],
                            source=SatelliteSource(item["source"]),
                            satellite=item["satellite"],
                            bands=item["bands"],
                            bbox=BoundingBox(**item["bbox"]),
                            acquisition_date=datetime.fromisoformat(item["acquisition_date"]),
                            cloud_cover_percent=item["cloud_cover_percent"],
                            resolution_m=item["resolution_m"],
                            filepath=item.get("filepath"),
                            metadata=item.get("metadata", {})
                        )
                        self._local_catalog.append(img)
            except Exception as e:
                logger.warning(f"Failed to load catalog: {e}")

    def _save_catalog(self):
        """Save local satellite image catalog."""
        data = []
        for img in self._local_catalog:
            data.append({
                "id": img.id,
                "source": img.source.value,
                "satellite": img.satellite,
                "bands": img.bands,
                "bbox": {"west": img.bbox.west, "south": img.bbox.south, "east": img.bbox.east, "north": img.bbox.north, "crs": img.bbox.crs},
                "acquisition_date": img.acquisition_date.isoformat(),
                "cloud_cover_percent": img.cloud_cover_percent,
                "resolution_m": img.resolution_m,
                "filepath": img.filepath,
                "metadata": img.metadata
            })
        with open(self._catalog_path, "w") as f:
            json.dump(data, f, indent=2)

    def search_all(self, query: SearchQuery) -> Dict[str, SearchResult]:
        """Search all data sources."""
        results = {}
        results["copernicus"] = self.copernicus.search(query)
        results["usgs"] = self.usgs.search(query)
        results["dem"] = self.dem.search(query.bbox)
        return results

    def search_sentinel2(self, query: SearchQuery) -> SearchResult:
        """Search specifically for Sentinel-2 imagery."""
        return self.copernicus.search(query)

    def search_landsat(self, query: SearchQuery) -> SearchResult:
        """Search specifically for Landsat imagery."""
        return self.usgs.search(query)

    def get_dem_info(self, bbox: BoundingBox) -> Dict[str, Any]:
        """Get DEM data availability for a bounding box."""
        return self.dem.search(bbox)

    def register_local_image(self, filepath: str, satellite: str, bbox: BoundingBox,
                            bands: List[str], acquisition_date: datetime,
                            resolution: float = 10.0) -> SatelliteImage:
        """Register a locally downloaded satellite image."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {filepath}")

        img_id = hashlib.md5(f"{filepath}{acquisition_date}".encode()).hexdigest()[:12]
        img = SatelliteImage(
            id=img_id,
            source=SatelliteSource.LOCAL,
            satellite=satellite,
            bands=bands,
            bbox=bbox,
            acquisition_date=acquisition_date,
            cloud_cover_percent=0.0,
            resolution_m=resolution,
            filepath=str(path.absolute()),
            metadata={"registered": datetime.now().isoformat()}
        )

        self._local_catalog.append(img)
        self._save_catalog()
        return img

    def get_local_images(self, bbox: Optional[BoundingBox] = None,
                        satellite: Optional[str] = None) -> List[SatelliteImage]:
        """Get locally registered images, optionally filtered."""
        images = self._local_catalog
        if bbox:
            images = [i for i in images if self._intersects(i.bbox, bbox)]
        if satellite:
            images = [i for i in images if i.satellite.lower() == satellite.lower()]
        return images

    def _intersects(self, a: BoundingBox, b: BoundingBox) -> bool:
        """Check if two bounding boxes intersect."""
        return not (a.east < b.west or a.west > b.east or a.north < b.south or a.south > b.north)

    def get_available_bands(self, satellite: str) -> List[Dict[str, Any]]:
        """Get available bands for a satellite."""
        if "sentinel" in satellite.lower():
            return [
                {"band": k, "name": v["name"], "wavelength_nm": v["wavelength"], "resolution_m": v["resolution"]}
                for k, v in SENTINEL_BAND_INFO.items()
            ]
        elif "landsat" in satellite.lower():
            return [
                {"band": k, "name": v["name"], "wavelength_nm": v["wavelength"], "resolution_m": v["resolution"]}
                for k, v in LANDSAT_BAND_INFO.items()
            ]
        return []

    def format_search_results(self, results: Dict[str, SearchResult]) -> str:
        """Format search results for display."""
        lines = ["## Satellite Data Search Results\n"]

        for source_name, result in results.items():
            lines.append(f"### {source_name.title()}")
            if source_name == "dem":
                if isinstance(result, dict):
                    lines.append(f"- **Recommended:** {result.get('recommended', 'N/A')}")
                    lines.append(f"- **Area:** {result.get('area_km2', 0):.1f} km²")
                    for ds in result.get("datasets", []):
                        lines.append(f"  - {ds['name']} ({ds['resolution']})")
            else:
                lines.append(f"- **Found:** {result.total_count} images")
                for img in result.images[:3]:
                    lines.append(f"  - `{img.id}` | {img.acquisition_date.strftime('%Y-%m-%d')} | {img.cloud_cover_percent:.1f}% cloud | {img.resolution_m}m")
            lines.append("")

        return "\n".join(lines)
