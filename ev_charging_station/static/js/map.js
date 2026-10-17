let map, baseLayer, vectorSource, vectorLayer,popupOverlay,searchAreaSource, searchAreaLayer, searchResultSource, searchResultLayer;
let zonesSource, zonesLayer;


const stationStyle = new ol.style.Style({
    image: new ol.style.Circle({
        radius: 7,
        fill: new ol.style.Fill({ color: '#22c55e' }),
        stroke: new ol.style.Stroke({ color: '#ffffff', width: 2 })
    })
});

// searched circle or polygon, plus its centre point
const searchAreaStyle = new ol.style.Style({
    fill: new ol.style.Fill({ color: 'rgba(59, 130, 246, 0.15)' }),
    stroke: new ol.style.Stroke({ color: '#3b82f6', width: 2 }),
    image: new ol.style.Circle({
        radius: 5,
        fill: new ol.style.Fill({ color: '#3b82f6' })
    })
});

// stations found by the search
const searchResultStyle = new ol.style.Style({
    image: new ol.style.Circle({
        radius: 9,
        fill: new ol.style.Fill({ color: '#f97316' }),
        stroke: new ol.style.Stroke({ color: '#ffffff', width: 2 })
    })
});

// zone polygon with its name in the middle
function zoneStyle(feature) {
    return new ol.style.Style({
        fill: new ol.style.Fill({ color: 'rgba(255, 255, 255, 0.12)' }),
        stroke: new ol.style.Stroke({ color: '#ffffff', width: 2 }),
        text: new ol.style.Text({
            text: feature.get('name'),
            font: 'bold 12px sans-serif',
            fill: new ol.style.Fill({ color: '#ffffff' }),
            stroke: new ol.style.Stroke({ color: '#000000', width: 3 })
        })
    });
}


function initMap() {
    baseLayer = new ol.layer.Tile({
        properties: { id: 'google_base' },
        source: new ol.source.XYZ({ url: 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}' })
    });

    vectorSource = new ol.source.Vector();
    vectorLayer = new ol.layer.Vector({
        properties: { id: 'stations_layer' },
        source: vectorSource,
        style: stationStyle
    });
    zonesSource = new ol.source.Vector();
    zonesLayer = new ol.layer.Vector({
        properties: { id: 'zones_layer' },
        source: zonesSource,
        style: zoneStyle
    });

    searchAreaSource = new ol.source.Vector();
    searchAreaLayer = new ol.layer.Vector({
        properties: { id: 'search_area_layer' },
        source: searchAreaSource,
        style: searchAreaStyle
    });

    searchResultSource = new ol.source.Vector();
    searchResultLayer = new ol.layer.Vector({
        properties: { id: 'search_result_layer' },
        source: searchResultSource,
        style: searchResultStyle
    });


    map = new ol.Map({
        target: 'map',
        layers: [baseLayer, zonesLayer, vectorLayer, searchAreaLayer, searchResultLayer],

        view: new ol.View({
            center: [78.9629, 22.5937],
            zoom: 5,
            projection: 'EPSG:4326',
        }),
        
    });
}

function showLoader(show) {
    document.getElementById('map-loader').classList.toggle('hidden', !show);
}

// show station details on hover
function showPopup(e) {
    // only stations and zones, not the draw cursor or the search area
    const feature = map.forEachFeatureAtPixel(e.pixel, (f, layer) => {
        if (layer === vectorLayer || layer === searchResultLayer || layer === zonesLayer) return f;
    });

    const popup = document.getElementById('popup');

    if (!feature) {
        popup.classList.add('hidden');
        map.getTargetElement().style.cursor = '';
        return;
    }

    // zones have a zone_id, stations don't
    if (feature.get('zone_id')) {
        popup.textContent = zoneSummaryText(feature);
        map.getTargetElement().style.cursor = '';
    } else {
        popup.textContent =
            `${feature.get('name')}\n` +
            `Operator: ${feature.get('operator')}\n` +
            `Connector: ${feature.get('connector_type')}\n` +
            `Power: ${feature.get('power_kw') ?? 'N/A'} kW`;
        map.getTargetElement().style.cursor = 'pointer';
    }

    popupOverlay.setPosition(e.coordinate);
    popup.classList.remove('hidden');
}

// show the address of the clicked station in the top right box
async function showAddress(e) {
    // map clicks are for drawing while search is on
    if (drawInteraction) return;

    // only stations have an address to show
    const feature = map.forEachFeatureAtPixel(e.pixel, (f) => f, {
        layerFilter: (layer) => layer === vectorLayer || layer === searchResultLayer
    });

    const box = document.getElementById('address-box');
    const text = document.getElementById('address-text');


    if (!feature) {
        box.classList.add('hidden');
        return;
    }

    const lat = feature.get('latitude');
    const lon = feature.get('longitude');

    box.classList.remove('hidden');
    text.textContent = 'Loading address...';


    try {
        const response = await fetch(`/api/address?lat=${lat}&lon=${lon}`);
        const data = await response.json();

        if (!response.ok) {
            text.textContent = data.error;
            return;
        }

        text.textContent = `${feature.get('name')}\n${data.address || 'No address found for this place'}`;
    } catch (err) {
        console.error(err);
        text.textContent = 'Could not load address';
    }
}


document.addEventListener('DOMContentLoaded', ()=>{
    initMap();
    popupOverlay = new ol.Overlay({
        element: document.getElementById('popup'),
        offset: [10, -10],
        positioning: 'bottom-left'
    });

    if(map){
        map.addOverlay(popupOverlay);
        map.on('pointermove', showPopup);
        map.on('click', showAddress);
    }
    document.getElementById('address-close').addEventListener('click', () => {
        document.getElementById('address-box').classList.add('hidden');
    });

});
