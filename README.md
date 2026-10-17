# EV Charging Station Finder

Django + OpenLayers app to show EV charging stations in Chennai on map, filter them, search stations in an area and see zone wise summary.

## Setup

1. Clone the repo

```
git clone https://github.com/panda-pritam/Ev_stations.git
cd Ev_stations
```

2. Create virtual env and activate it

```
python -m venv venv
venv\Scripts\activate
```

3. Install packages

```
cd ev_charging_station
pip install -r requirements.txt
```

4. Create `.env` file (same folder as manage.py)

```
copy .env.example .env
```

then put your own SECRET_KEY in it.

5. Run the server

```
python manage.py runserver
```

open http://127.0.0.1:8000/

## Import stations from CSV

CSV columns: station_id, name, operator, connector_type, power_kw, latitude, longitude

```
python manage.py import_stations path\to\stations.csv --check-existing
```

- `--check-existing` skip station_id which already exist
- `--json` print summary as json
- `--output file.geojson` save imported stations in separate file

Data is saved in `static/data/station.geojson`.

Example (how I ran it):

```
python manage.py import_stations "D:\EV_Station_Finder_Assessment_Pritam_Mondal\EV_Station_Finder_Assessment\ev_stations_raw.csv" --check-existing --output "D:\Ev_stations\ev_charging_station\static\data\imported.geojson"
```

## APIs

- GET /api/stations?connector=&min_kw=
- GET /api/connectors
- POST /api/search
- GET /api/zones/summary?connector=&min_kw=
- GET /api/address?lat=&lon=
