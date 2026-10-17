import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
import requests

from .utils import import_stations, StationImportError, load_existing_stations,count_values,filter_stations,get_address,get_crs_bounds, search_stations, load_zones, zones_summary
from shapely.geometry import shape
from django.views.decorators.csrf import csrf_exempt

ALLOWED_RADIUS_KM = [2, 5, 10]

_stations = None
_zones = None

# Create your views here.
def home_page(request):
    return render(request, 'home.html')


@require_POST
def upload_csv(request):
    csv_file = request.FILES.get('csv_file')
  

    if not csv_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not csv_file.name.lower().endswith('.csv'):
        return JsonResponse({'error': 'Only CSV files are allowed'}, status=400)

    try:
        summary, new_gdf = import_stations(csv_file, check_existing=True)
    except StationImportError as e:
        return JsonResponse({'error': str(e)}, status=400)

    for row in summary['skipped']:
        print(f"Skipped {row['station_id']} (row {row['row']}): {row['reason']}")

    return JsonResponse({
        'summary': summary,
        'geojson': json.loads(new_gdf.to_json(drop_id=True)),
    })


# read the geojson once and keep it in memory
def get_stations():
    global _stations
    if _stations is None:
        _stations = load_existing_stations()
    return _stations


# next request will read the file again
def reload_stations():
    global _stations
    _stations = None


# zones are read once and kept in memory
def get_zones():
    global _zones
    if _zones is None:
        _zones = load_zones()
    return _zones


# read the optional filters from the url
# read the optional filters from url params or json body
def get_filters(params):
    connector = str(params.get('connector') or '').strip()
    operator = str(params.get('operator') or '').strip()
    min_kw = str(params.get('min_kw') or '').strip()

    if min_kw == '':
        min_kw = None
    else:
        try:
            min_kw = float(min_kw)
        except ValueError:
            raise ValueError('min_kw must be a number')

    return connector, min_kw, operator



@require_GET
def stations_api(request):
    try:
        connector, min_kw, operator = get_filters(request.GET)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    gdf = filter_stations(get_stations(), connector, min_kw, operator)

    geojson = json.loads(gdf.to_json(drop_id=True))
    geojson['message'] = 'Stations fetched successfully'
    geojson['count'] = len(gdf)

    return JsonResponse(geojson, status=200)


@csrf_exempt
@require_POST
def search_api(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body must be valid JSON'}, status=400)

    # geojson dict to shapely geometry
    try:
        geometry = shape(body['geometry'])
    except Exception:
        return JsonResponse({'error': 'geometry must be a GeoJSON Point or Polygon'}, status=400)

    if geometry.geom_type not in ('Point', 'Polygon'):
        return JsonResponse({'error': 'Only Point and Polygon are supported'}, status=400)

    if geometry.is_empty or not geometry.is_valid:
        return JsonResponse({'error': 'Geometry is empty or not valid'}, status=400)

    # drawn geometry must be in 4326
    min_lon, min_lat, max_lon, max_lat = get_crs_bounds(4326)
    g_min_lon, g_min_lat, g_max_lon, g_max_lat = geometry.bounds
    if g_min_lon < min_lon or g_max_lon > max_lon or g_min_lat < min_lat or g_max_lat > max_lat:
        return JsonResponse({'error': 'Coordinates outside EPSG:4326 range'}, status=400)

    radius_km = None
    if geometry.geom_type == 'Point':
        try:
            radius_km = float(body.get('radius_km'))
        except (TypeError, ValueError):
            radius_km = None

        if radius_km not in ALLOWED_RADIUS_KM:
            return JsonResponse({'error': 'radius_km is required for a point and must be 2, 5 or 10'}, status=400)

    try:
        connector, min_kw, operator = get_filters(body)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    stations = filter_stations(get_stations(), connector, min_kw, operator)
    result = search_stations(stations, geometry, radius_km)

    return JsonResponse(result, status=200)


@require_GET
def connectors_api(request):
    return JsonResponse(count_values(get_stations(), 'connector_type'), safe=False)


@require_GET
def operators_api(request):
    return JsonResponse(count_values(get_stations(), 'operator'), safe=False)


@require_GET
def power_levels_api(request):
    return JsonResponse(count_values(get_stations(), 'power_kw'), safe=False)

@require_GET
def address_api(request):
    try:
        lat = float(request.GET.get('lat', ''))
        lon = float(request.GET.get('lon', ''))
    except ValueError:
        return JsonResponse({'error': 'lat and lon must be numbers'}, status=400)

    min_lon, min_lat, max_lon, max_lat = get_crs_bounds(4326)
    if lon < min_lon or lon > max_lon or lat < min_lat or lat > max_lat:
        return JsonResponse({'error': 'lat/lon outside EPSG:4326 range'}, status=400)

    try:
        address = get_address(lat, lon)
    except requests.RequestException:
        return JsonResponse({'error': 'Address service not available'}, status=502)

    return JsonResponse({'address': address}, status=200)


@require_GET
def zones_summary_api(request):
    try:
        connector, min_kw, operator = get_filters(request.GET)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    stations = filter_stations(get_stations(), connector, min_kw, operator)
    summary = zones_summary(get_zones(), stations)

    geojson = json.loads(summary.to_json(drop_id=True))
    geojson['count'] = len(summary)

    return JsonResponse(geojson, status=200)

