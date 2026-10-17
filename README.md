# EV Charging Station Finder

A small web app to view and search EV charging stations in Chennai on a map.

Built with Django, GeoPandas, OpenLayers and Tailwind.

## Tech stack

- Python 3.14
- Django 6.1
- GeoPandas 1.2 / Shapely 2.2 / pyproj 3.8
- OpenLayers 10 (map)
- Tailwind CSS v4 (browser CDN)
- Nominatim (OpenStreetMap) for place search and reverse geocoding

## Project structure

```
ev_charging_station/
    manage.py
    requirements.txt
    ev_charging_station/        settings, main urls
    stations/
        views.py                pages + all API views
        utils.py                csv cleaning, geojson read/write, spatial logic
        urls.py
        management/commands/
            import_stations.py  csv import command
    templates/
        base.html
        home.html
    static/
        data/
            station.geojson     stations (works like the db table)
            zones.geojson       zone polygons (given, not changed)
        js/
            map.js              map, layers, hover popup, address box
            home.js             csv upload, place search
            filters.js          filter dropdowns, load stations
            search.js           draw point / polygon and search stations
            zones.js            zones layer and summary
        css/
```

## Setup

```
python -m venv venv
venv\Scripts\activate
cd ev_charging_station
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000/

There is no database model for stations. All data lives in the GeoJSON files in `static/data/`. They are read once on the first request and kept in memory.

## Importing stations from CSV

Expected columns:

```
station_id, name, operator, connector_type, power_kw, latitude, longitude
```

Run the import command from the folder that has `manage.py`:

```
python manage.py import_stations path\to\stations.csv
python manage.py import_stations path\to\stations.csv --check-existing
python manage.py import_stations path\to\stations.csv --check-existing --json
python manage.py import_stations path\to\stations.csv --check-existing --output path\to\imported.geojson
python manage.py help import_stations
```

| Flag | What it does |
|---|---|
| `--check-existing` | skip rows whose `station_id` is already in `station.geojson` |
| `--json` | print the summary as JSON |
| `--output <file>` | also save only the stations from this run to a separate GeoJSON file |

Cleaning rules:

- empty name becomes `Unnamed Station`
- missing or invalid latitude / longitude: row is skipped, station_id and reason are printed
- latitude / longitude outside the EPSG:4326 range: row is skipped (range comes from pyproj, not hardcoded)
- missing station_id or duplicate station_id inside the CSV: row is skipped
- `latitude`, `longitude` and `power_kw` are stored as numbers

At the end it prints total rows read, rows written and rows skipped.

The same functions are used by the upload button in the sidebar (`POST /upload-csv/`), so the web upload and the command clean the data the same way.

## API

All coordinates are WGS 84 lon/lat (EPSG:4326).

| Endpoint | Description |
|---|---|
| `GET /api/stations?connector=&min_kw=&operator=` | all stations as a GeoJSON FeatureCollection, filters are optional |
| `GET /api/connectors` | connector types with station count |
| `GET /api/operators` | operators with station count |
| `GET /api/power-levels` | power values with station count |
| `POST /api/search` | stations inside a circle (point + radius) or a polygon |
| `GET /api/zones/summary?connector=&min_kw=` | each zone with area and station count by power class |
| `GET /api/address?lat=&lon=` | address of a point from Nominatim |

### POST /api/search

Point search (`radius_km` must be 2, 5 or 10):

```json
{
  "geometry": { "type": "Point", "coordinates": [80.2206, 13.0067] },
  "radius_km": 5,
  "connector": "CCS2",
  "min_kw": 22
}
```

Polygon search (no radius needed):

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[80.20, 13.00], [80.28, 13.00], [80.28, 13.07], [80.20, 13.07], [80.20, 13.00]]]
  }
}
```

Response has `area_km2`, `centre` ([lon, lat]), `count`, `stations` (FeatureCollection sorted by distance, each with `distance_km`) and `area` (the searched area as a GeoJSON Polygon).

Quick test from PowerShell:

```
$body = '{"geometry": {"type": "Point", "coordinates": [80.2206, 13.0067]}, "radius_km": 5}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/search -Method Post -Body $body -ContentType 'application/json'
```

`/api/search` is csrf exempt. It does not change any data, it only uses POST because a polygon is too big for a query string.

### GET /api/zones/summary

Power classes:

- `kw_below_15`: less than 15 kW
- `kw_15_to_50`: 15 to 50 kW (both included)
- `kw_above_50`: more than 50 kW

Stations are matched to zones with a spatial join (`sjoin`, `within`). Filters are applied before counting.

### GET /api/address

Returns `{"address": "..."}`, or `{"address": null}` when Nominatim has no address for that place (for example in the sea). Returns 502 if Nominatim can't be reached.

## Distances and areas

Data and map are in EPSG:4326 (degrees), so measuring is done after reprojecting with GeoPandas `to_crs()`:

1. drawn geometry and stations are converted to a metric CRS
2. buffer, distance and area are calculated in meters
3. results are converted back to EPSG:4326 for the response

The metric CRS is set in one place, `METRIC_CRS` in `stations/utils.py`. I used EPSG:3857 (Web Mercator). It is in meters but it stretches by 1 / cos(latitude), at Chennai (~13°N) that is about 2.6% on distances and about 5% on areas. For exact ground values it can be switched to the local UTM zone, `EPSG:32644`, nothing else needs to change.

For a point search the stations are picked by `distance <= radius` (not by the buffer polygon) and the area is `π r²`, so the result doesn't depend on how many segments the buffer circle has.

## Frontend

- OpenLayers map with Google satellite base layer, view in EPSG:4326
- filter panel (connector, operator, min power) built from the API
- hover popup with station details
- click a station to see its address (top right box)
- place search with Nominatim, debounced while typing
- station search: draw a point (with 2 / 5 / 10 km radius) or a polygon, results are listed nearest first
- zones layer with a summary per zone, counts follow the filters
- CSV upload from the sidebar

## Notes

- Nominatim allows max 1 request per second and asks to identify the app with a User-Agent. The place search waits 800 ms after typing and needs at least 3 letters.
- Stations are cached in memory. `reload_stations()` in `views.py` clears the cache so the next request reads the file again.
- `zones.geojson` is treated as static input.
