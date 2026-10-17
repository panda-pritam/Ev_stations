from pathlib import Path

import geopandas as gpd
import pandas as pd
from django.conf import settings
from pyproj import CRS
import requests
import json
import math
from shapely.geometry import mapping

STATIONS_GEOJSON = settings.BASE_DIR / 'static' / 'data' / 'station.geojson'
ZONES_GEOJSON = settings.BASE_DIR / 'static' / 'data' / 'zones.geojson'

STATION_COLUMNS = ['station_id', 'name', 'operator', 'connector_type',
                   'power_kw', 'latitude', 'longitude']
TEXT_COLUMNS = ['station_id', 'name', 'operator', 'connector_type']
NUMBER_COLUMNS = ['power_kw', 'latitude', 'longitude']

ALLOWED_RADIUS_KM = [2, 5, 10]
METRIC_CRS = 'EPSG:3857'


class StationImportError(Exception):
    pass


def read_stations_csv(csv_source):
    try:
        df = pd.read_csv(csv_source, dtype=str, encoding='utf-8-sig')
    except FileNotFoundError:
        raise StationImportError(f'File not found: {csv_source}')
    except pd.errors.EmptyDataError:
        raise StationImportError('CSV file is empty')
    except UnicodeDecodeError:
        raise StationImportError('CSV file must be UTF-8 encoded')
    except pd.errors.ParserError:
        raise StationImportError('CSV file format is not valid')

    df.columns = df.columns.str.strip().str.lower()

    for col in STATION_COLUMNS:
        if col not in df.columns:
            raise StationImportError(f'Missing column in CSV: {col}')

    return df[STATION_COLUMNS].copy()


def get_crs_bounds(epsg):
    # gives (min_lon, min_lat, max_lon, max_lat)
    return CRS.from_epsg(epsg).area_of_use.bounds


def skip_rows(df, bad_mask, reason, skipped):
    bad_rows = df[bad_mask]

    for index, row in bad_rows.iterrows():
        skipped.append({
            'row': int(index) + 2,
            'station_id': row['station_id'],
            'reason': reason,
        })

    good_rows = df[~bad_mask]
    return good_rows


def clean_stations(df):
    skipped = []

    # trim spaces
    for col in TEXT_COLUMNS:
        df[col] = df[col].fillna('').str.strip()

    df.loc[df['name'] == '', 'name'] = 'Unnamed Station'

    # invalid values become NaN
    for col in NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col].str.strip(), errors='coerce')

    df = skip_rows(df, df['station_id'] == '', 'missing station_id', skipped)
    df = skip_rows(df, df['latitude'].isna(), 'missing or invalid latitude', skipped)
    df = skip_rows(df, df['longitude'].isna(), 'missing or invalid longitude', skipped)

    min_lon, min_lat, max_lon, max_lat = get_crs_bounds(4326)
    out_of_range = (
        (df['longitude'] < min_lon) | (df['longitude'] > max_lon) |
        (df['latitude'] < min_lat) | (df['latitude'] > max_lat)
    )
    df = skip_rows(df, out_of_range, 'lat/lon outside EPSG:4326 range', skipped)

    df = skip_rows(df, df['station_id'].duplicated(), 'duplicate station_id in CSV', skipped)

    return df, skipped


def to_geodataframe(df):
    geometry = gpd.points_from_xy(df['longitude'], df['latitude'])
    return gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')


def empty_stations_gdf():
    return gpd.GeoDataFrame(columns=STATION_COLUMNS + ['geometry'],
                            geometry='geometry', crs='EPSG:4326')


def load_existing_stations(path=STATIONS_GEOJSON):
    path = Path(path)

    if not path.exists():
        return empty_stations_gdf()

    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        raise StationImportError(f'Could not read {path.name}: {e}')

    if gdf.empty:
        return empty_stations_gdf()

    # ids can come back as numbers
    gdf['station_id'] = gdf['station_id'].astype(str)
    return gdf


def remove_existing(new_gdf, existing_gdf, skipped):
    already_saved = new_gdf['station_id'].isin(existing_gdf['station_id'])
    return skip_rows(new_gdf, already_saved, 'station_id already exists', skipped)


def write_geojson(gdf, path):
    path = Path(path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(gdf.to_json(drop_id=True, indent=2), encoding='utf-8')
    except OSError as e:
        raise StationImportError(f'Could not write {path.name}: {e}')


def save_stations(existing_gdf, new_gdf, path=STATIONS_GEOJSON):
    if existing_gdf.empty:
        combined = new_gdf
    else:
        combined = pd.concat([existing_gdf, new_gdf], ignore_index=True)
        combined = gpd.GeoDataFrame(combined, geometry='geometry', crs='EPSG:4326')

    write_geojson(combined, path)


def import_stations(csv_source, geojson_path=STATIONS_GEOJSON, check_existing=True):
    df = read_stations_csv(csv_source)
    total_rows = len(df)

    clean_df, skipped = clean_stations(df)
    new_gdf = to_geodataframe(clean_df)

    existing_gdf = load_existing_stations(geojson_path)
    if check_existing:
        new_gdf = remove_existing(new_gdf, existing_gdf, skipped)

    if not new_gdf.empty:
        save_stations(existing_gdf, new_gdf, geojson_path)

    summary = {
        'total_rows': total_rows,
        'rows_written': len(new_gdf),
        'rows_skipped': len(skipped),
        'skipped': skipped,
    }
    return summary, new_gdf


def filter_stations(gdf, connector=None, min_kw=None, operator=None):
    if connector:
        gdf = gdf[gdf['connector_type'].str.lower() == connector.lower()]

    if operator:
        gdf = gdf[gdf['operator'].str.lower() == operator.lower()]

    if min_kw is not None:
        gdf = gdf[gdf['power_kw'] >= min_kw]

    return gdf


# unique values of a column with how many stations have each
def count_values(gdf, column):
    counts = gdf[column].value_counts().sort_index()

    result = []
    for value, count in counts.items():
        if value == '':
            continue
        result.append({'value': value, 'count': int(count)})

    return result


def get_address(lat, lon):
    url = 'https://nominatim.openstreetmap.org/reverse'
    params = {'format': 'json', 'lat': lat, 'lon': lon}
    headers = {'User-Agent': 'EVStationFinder/1.0 (assessment project)'}

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    # no display_name means no address for that place
    return data.get('display_name')


# convert one geometry from meters back to 4326
def to_wgs84(geometry, from_crs):
    return gpd.GeoSeries([geometry], crs=from_crs).to_crs('EPSG:4326').iloc[0]


def search_stations(stations, geometry, radius_km=None):
    # drawn geometry comes from the map in 4326
    search_gdf = gpd.GeoDataFrame(geometry=[geometry], crs='EPSG:4326')

    # web mercator, units in meters
    search_m = search_gdf.to_crs(METRIC_CRS)
    stations_m = stations.to_crs(METRIC_CRS)

    if geometry.geom_type == 'Point':
        centre_m = search_m.geometry.iloc[0]
        area_m = centre_m.buffer(radius_km * 1000)

        stations_m['distance_km'] = stations_m.distance(centre_m) / 1000
        inside = stations_m[stations_m['distance_km'] <= radius_km].copy()

        area_km2 = math.pi * radius_km ** 2
    else:
        area_m = search_m.geometry.iloc[0]
        centre_m = area_m.centroid

        stations_m['distance_km'] = stations_m.distance(centre_m) / 1000
        inside = stations_m[stations_m.intersects(area_m)].copy()

        area_km2 = area_m.area / 1_000_000

    # nearest first, back to 4326 for the map
    inside['distance_km'] = inside['distance_km'].round(3)
    inside = inside.sort_values('distance_km').to_crs('EPSG:4326')

    centre = to_wgs84(centre_m, METRIC_CRS)
    area = to_wgs84(area_m, METRIC_CRS)

    return {
        'area_km2': round(area_km2, 3),
        'centre': [round(centre.x, 6), round(centre.y, 6)],
        'count': len(inside),
        'stations': json.loads(inside.to_json(drop_id=True)),
        'area': mapping(area),
    }


def load_zones(path=ZONES_GEOJSON):
    try:
        return gpd.read_file(path)
    except Exception as e:
        raise StationImportError(f'Could not read {Path(path).name}: {e}')


def zones_summary(zones, stations):
    result = zones.copy()

    # area needs meters
    zones_m = zones.to_crs(METRIC_CRS)
    result['area_km2'] = (zones_m.area / 1_000_000).round(3)

    # which zone each station falls in
    joined = gpd.sjoin(stations, zones[['zone_id', 'geometry']], predicate='within')
    power = joined['power_kw']

    below_15 = joined[power < 15].groupby('zone_id').size()
    from_15_to_50 = joined[(power >= 15) & (power <= 50)].groupby('zone_id').size()
    above_50 = joined[power > 50].groupby('zone_id').size()

    result['kw_below_15'] = result['zone_id'].map(below_15).fillna(0).astype(int)
    result['kw_15_to_50'] = result['zone_id'].map(from_15_to_50).fillna(0).astype(int)
    result['kw_above_50'] = result['zone_id'].map(above_50).fillna(0).astype(int)
    result['total'] = result['kw_below_15'] + result['kw_15_to_50'] + result['kw_above_50']

    return result
