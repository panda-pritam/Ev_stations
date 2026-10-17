let searchTimer;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('upload-form').addEventListener('submit', uploadCsv);
    document.getElementById('search-input').addEventListener('input', onSearchInput);

    // enter key searches right away
    document.getElementById('search-form').addEventListener('submit', (e) => {
        e.preventDefault();
        clearTimeout(searchTimer);
        searchPlace(document.getElementById('search-input').value.trim());
    });
});

async function uploadCsv(e) {
    e.preventDefault();

    const file = document.getElementById('csv-file').files[0];
    if (!file) {
        alert('Please select a CSV file');
        return;
    }

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const formData = new FormData();
    formData.append('csv_file', file);

    const button = document.getElementById('upload-csv-btn');
    button.disabled = true;

    try {
        const response = await fetch('/upload-csv/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: formData
        });
        const data = await response.json();

        if (!response.ok) {
            alert(data.error);
            return;
        }

        // map is in 3857, geojson is in 4326
        // const features = new ol.format.GeoJSON().readFeatures(data.geojson, {
        //     featureProjection: 'EPSG:3857'
        // });
        // vectorSource.addFeatures(features);

        const s = data.summary;
        alert(`Read: ${s.total_rows}, Written: ${s.rows_written}, Skipped: ${s.rows_skipped}`);
        e.target.reset();
    } catch (err) {
        console.error(err);
        alert('Upload failed');
    } finally {
        button.disabled = false;
    }
}



// debounce the search while typing
function onSearchInput(e) {
    const query = e.target.value.trim();

    // cancel the previous timer on every key press
    clearTimeout(searchTimer);

    // too short to search
    if (query.length < 2) {
        hideResults();
        return;
    }

    // search only after the user stops typing
    searchTimer = setTimeout(() => searchPlace(query), 400);
}

// call nominatim and show the results
async function searchPlace(query) {
    if (!query) return;

    const resultsList = document.getElementById('search-results');
    resultsList.classList.remove('hidden');
    resultsList.innerHTML = '<li class="p-2">Searching...</li>';

    const url = `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`;

    try {
        const response = await fetch(url);
        const places = await response.json();

        // user typed something else while this was loading
        if (query !== document.getElementById('search-input').value.trim()) return;

        resultsList.innerHTML = '';

        if (places.length === 0) {
            resultsList.innerHTML = '<li class="p-2">No results found</li>';
            return;
        }

        // one list item per place
        for (const place of places) {
            const li = document.createElement('li');
            li.textContent = place.display_name;
            li.className = 'p-2 rounded cursor-pointer hover:bg-gray-300';
            li.addEventListener('click', () => goToPlace(place));
            resultsList.appendChild(li);
        }
    } catch (err) {
        console.error(err);
        resultsList.innerHTML = '<li class="p-2">Search failed</li>';
    }
}

// clear and hide the results list
function hideResults() {
    const resultsList = document.getElementById('search-results');
    resultsList.innerHTML = '';
    resultsList.classList.add('hidden');
}

// move the map to the selected place
function goToPlace(place) {
    // nominatim sends lat and lon as strings
    const lon = parseFloat(place.lon);
    const lat = parseFloat(place.lat);

    map.getView().animate({
        center: [lon, lat],
        zoom: 14,
        duration: 1000
    });

    document.getElementById('search-input').value = '';
    hideResults();
}


