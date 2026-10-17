document.addEventListener('DOMContentLoaded', () => {
    loadZones();

    document.getElementById('show-zones').addEventListener('change', (e) => {
        zonesLayer.setVisible(e.target.checked);
    });

    // zone counts follow the same filters as the stations
    document.getElementById('connector-filter').addEventListener('change', loadZones);
    document.getElementById('operator-filter').addEventListener('change', loadZones);
    document.getElementById('power-filter').addEventListener('change', loadZones);
    document.getElementById('clear-filters').addEventListener('click', loadZones);
});

// get zones with station counts for the selected filters
async function loadZones() {
    const params = new URLSearchParams();

    const connector = document.getElementById('connector-filter').value;
    const operator = document.getElementById('operator-filter').value;
    const minKw = document.getElementById('power-filter').value;

    if (connector) params.append('connector', connector);
    if (operator) params.append('operator', operator);
    if (minKw) params.append('min_kw', minKw);

    try {
        const response = await fetch(`/api/zones/summary?${params}`);
        const geojson = await response.json();

        if (!response.ok) {
            console.error(geojson.error);
            return;
        }

        const features = new ol.format.GeoJSON().readFeatures(geojson);

        zonesSource.clear();
        zonesSource.addFeatures(features);

        showZoneList(features);
    } catch (err) {
        console.error(err);
    }
}

// same text for the hover popup and the sidebar list
function zoneSummaryText(feature) {
    return `${feature.get('name')} (${feature.get('zone_id')})\n` +
        `Area: ${feature.get('area_km2')} km²\n` +
        `Below 15 kW: ${feature.get('kw_below_15')}\n` +
        `15 to 50 kW: ${feature.get('kw_15_to_50')}\n` +
        `Above 50 kW: ${feature.get('kw_above_50')}\n` +
        `Total: ${feature.get('total')}`;
}

function showZoneList(features) {
    const list = document.getElementById('zone-list');
    list.innerHTML = '';

    for (const feature of features) {
        const li = document.createElement('li');
        li.textContent = zoneSummaryText(feature);
        li.className = 'p-2 rounded bg-gray-900 cursor-pointer hover:bg-gray-700 whitespace-pre-line';

        // zoom to the zone
        li.addEventListener('click', () => {
            map.getView().fit(feature.getGeometry().getExtent(), {
                padding: [40, 40, 40, 40],
                duration: 800
            });
        });

        list.appendChild(li);
    }
}
