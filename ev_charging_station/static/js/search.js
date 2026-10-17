let drawInteraction = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('draw-point').addEventListener('click', () => startDrawing('Point'));
    document.getElementById('draw-polygon').addEventListener('click', () => startDrawing('Polygon'));
    document.getElementById('clear-search').addEventListener('click', clearSearch);
});

// turn on drawing for a point or a polygon
function startDrawing(type) {
    clearSearch();

    drawInteraction = new ol.interaction.Draw({ type: type });
    map.addInteraction(drawInteraction);

    document.getElementById('station-search-hint').textContent =
        type === 'Point'
            ? 'Click on the map to search'
            : 'Click to add corners, double click to finish';

    drawInteraction.on('drawend', (e) => {
        // map is in 4326 so the geometry is already lon/lat
        const geometry = new ol.format.GeoJSON().writeGeometryObject(e.feature.getGeometry());
        searchStations(geometry);
    });
}

async function searchStations(geometry) {
    const body = { geometry: geometry };

    if (geometry.type === 'Point') {
        body.radius_km = Number(document.getElementById('radius-select').value);
    }

    // use the same filters as the filter panel
    const connector = document.getElementById('connector-filter').value;
    const minKw = document.getElementById('power-filter').value;
    if (connector) body.connector = connector;
    if (minKw) body.min_kw = Number(minKw);

    const summary = document.getElementById('station-search-summary');
    summary.classList.remove('hidden');
    summary.textContent = 'Searching...';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();

        if (!response.ok) {
            summary.textContent = data.error;
            return;
        }

        showSearchResult(data);
    } catch (err) {
        console.error(err);
        summary.textContent = 'Search failed';
    }
}

function showSearchResult(data) {
    const format = new ol.format.GeoJSON();

    // searched area and its centre
    searchAreaSource.clear();
    searchAreaSource.addFeature(new ol.Feature(format.readGeometry(data.area)));
    searchAreaSource.addFeature(new ol.Feature(new ol.geom.Point(data.centre)));

    // stations found, already sorted nearest first
    const features = format.readFeatures(data.stations);
    searchResultSource.clear();
    searchResultSource.addFeatures(features);

    document.getElementById('station-search-summary').textContent =
        `${data.count} stations found\nArea: ${data.area_km2} km²`;

    const list = document.getElementById('station-search-list');
    list.innerHTML = '';

    for (const feature of features) {
        const li = document.createElement('li');
        li.textContent = `${feature.get('name')} (${feature.get('distance_km')} km)`;
        li.className = 'p-2 rounded cursor-pointer hover:bg-gray-700';
        li.addEventListener('click', () => {
            map.getView().animate({
                center: feature.getGeometry().getCoordinates(),
                zoom: 16,
                duration: 800
            });
        });
        list.appendChild(li);
    }

    // zoom to the searched area
    map.getView().fit(searchAreaSource.getExtent(), { padding: [40, 40, 40, 40], duration: 800 });
}

// remove drawing tool, area, results and the list
function clearSearch() {
    if (drawInteraction) {
        map.removeInteraction(drawInteraction);
        drawInteraction = null;
    }

    searchAreaSource.clear();
    searchResultSource.clear();

    document.getElementById('station-search-hint').textContent = '';
    document.getElementById('station-search-summary').classList.add('hidden');
    document.getElementById('station-search-list').innerHTML = '';
}
