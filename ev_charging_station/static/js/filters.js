document.addEventListener('DOMContentLoaded', () => {
    loadFilterOptions();
    loadStations();

    document.getElementById('connector-filter').addEventListener('change', loadStations);
    document.getElementById('operator-filter').addEventListener('change', loadStations);
    document.getElementById('power-filter').addEventListener('change', loadStations);
    document.getElementById('clear-filters').addEventListener('click', clearFilters);
});

// fill all three dropdowns
function loadFilterOptions() {
    loadDropdown('/api/connectors', 'connector-filter', '');
    loadDropdown('/api/operators', 'operator-filter', '');
    loadDropdown('/api/power-levels', 'power-filter', ' kW');
}

async function loadDropdown(url, selectId, unit) {
    const select = document.getElementById(selectId);

    try {
        const response = await fetch(url);
        const items = await response.json();

        // keep only the "All" option
        select.length = 1;

        for (const item of items) {
            select.add(new Option(`${item.value}${unit} (${item.count})`, item.value));
        }
    } catch (err) {
        console.error(err);
    }
}

// get stations with the selected filters and draw them
async function loadStations() {
    const params = new URLSearchParams();

    const connector = document.getElementById('connector-filter').value;
    const operator = document.getElementById('operator-filter').value;
    const minKw = document.getElementById('power-filter').value;

    if (connector) params.append('connector', connector);
    if (operator) params.append('operator', operator);
    if (minKw) params.append('min_kw', minKw);

    try {
        const response = await fetch(`/api/stations?${params}`);
        const geojson = await response.json();

        if (!response.ok) {
            console.error(geojson.error);
            return;
        }

        const features = new ol.format.GeoJSON().readFeatures(geojson);

        // replace old points with the filtered ones
        vectorSource.clear();
        vectorSource.addFeatures(features);
    } catch (err) {
        console.error(err);
    }
}

function clearFilters() {
    document.getElementById('connector-filter').value = '';
    document.getElementById('operator-filter').value = '';
    document.getElementById('power-filter').value = '';
    loadStations();
}
