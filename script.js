// This ensures the script runs only after the full HTML document has been loaded.
document.addEventListener('DOMContentLoaded', () => {

    // --- State Management ---
    let currentView = 'cards'; // The default view is 'cards'
    let lastFetchedBriefings = []; // A cache to store the last set of data from the API

    // --- Element References ---
    const fetchButton = document.getElementById('fetch-button');
    const resultsContainer = document.getElementById('results-container');
    const competitorSelect = document.getElementById('competitor-select');
    const productLineInput = document.getElementById('product-line-input');
    const productLineDropdown = document.getElementById('product-line-dropdown');
    const lastRunInfo = document.getElementById('last-run-info');
    const viewCardsBtn = document.getElementById('view-cards-btn');
    const viewTableBtn = document.getElementById('view-table-btn');
    const downloadCsvBtn = document.getElementById('download-csv-btn');
    const controlsContainer = document.getElementById('controls-container');

    // --- Data and Configuration ---
    const API_BASE_URL = 'https://ai-competition-scout-api.onrender.com'; // Your local Flask API URL
    const productLines = [
        "Push", "Email", "SMS", "WhatsApp", "RCS", "Other channels", "In-App", "OSM", "Cards",
        "Web Personalization (WebP)", "Content Management", "Settings", "Flows", "Segmentation",
        "Data", "Partner Integrations", "Miscellaneous & Others", "ML or AI", "Analyze", "Campaign Management"
    ];

    // --- Functions ---

    /**
     * Populates the product line dropdown with options, including a "Clear" button.
     */
    function populateDropdown() {
        productLineDropdown.innerHTML = ''; // Clear existing options

        const clearOption = document.createElement('a');
        clearOption.href = "#";
        clearOption.innerHTML = '&#10005; Clear Search'; // 'x' character
        clearOption.style.color = '#d9534f';
        clearOption.style.fontWeight = 'bold';
        clearOption.addEventListener('click', (e) => {
            e.preventDefault();
            productLineInput.value = '';
            productLineDropdown.style.display = 'none';
        });
        productLineDropdown.appendChild(clearOption);

        productLines.forEach(line => {
            const a = document.createElement('a');
            a.href = "#";
            a.textContent = line;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                productLineInput.value = line;
                productLineDropdown.style.display = 'none';
            });
            productLineDropdown.appendChild(a);
        });
    }

    /**
     * Fetches intelligence data from the backend API.
     * @param {string} competitor - The selected competitor.
     * @param {string} productLine - The searched product line.
     * @returns {Promise<Array>} - A promise that resolves to an array of briefing objects.
     */
    async function fetchBriefings(competitor, productLine) {
        fetchButton.classList.add('loading');
        fetchButton.disabled = true;
        resultsContainer.innerHTML = '<p>Fetching data from the server...</p>';

        let url = `${API_BASE_URL}/api/briefings/search?`;
        const params = new URLSearchParams();

        if (competitor && competitor !== 'All') {
            params.append('competitor', competitor);
        }
        if (productLine) {
            params.append('product_line', productLine);
        }
        url += params.toString();

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const data = await response.json();
            lastFetchedBriefings = data; // Cache the new data
            return data;
        } catch (error) {
            console.error('Error fetching briefings:', error);
            resultsContainer.innerHTML = '<p>An error occurred while fetching data from the API. Please ensure the backend server (app.py) is running.</p>';
            lastFetchedBriefings = []; // Clear cache on error
            return [];
        } finally {
            fetchButton.classList.remove('loading');
            fetchButton.disabled = false;
        }
    }

    /**
     * Main render function that decides which view to show and updates button states.
     */
    function renderResults() {
        resultsContainer.innerHTML = '';

        if (lastFetchedBriefings.length === 0) {
            resultsContainer.innerHTML = '<p>No intelligence briefings found for this search.</p>';
            lastRunInfo.textContent = 'No data found in the database.';
            controlsContainer.style.display = 'none'; // Hide controls if no data
            return;
        }

        controlsContainer.style.display = 'flex'; // Show controls if there is data
        const mostRecentDate = new Date(lastFetchedBriefings[0].processed_at);
        lastRunInfo.textContent = `Last intelligence gathered: ${mostRecentDate.toLocaleString()}`;
        downloadCsvBtn.disabled = false;

        if (currentView === 'cards') {
            renderCardsView(lastFetchedBriefings);
        } else {
            renderTableView(lastFetchedBriefings);
        }
    }

    /**
     * Renders the briefing data into HTML cards.
     * @param {Array} briefings - An array of briefing objects.
     */
    function renderCardsView(briefings) {
        briefings.forEach(briefing => {
            const card = document.createElement('div');
            card.className = 'briefing-card';
            card.innerHTML = `
                <h3>${briefing.feature_update || 'N/A'}</h3>
                <p><strong>Competitor:</strong> ${briefing.competitor || 'N/A'}</p>
                <p><strong>Product Line:</strong> ${briefing.product_line || 'N/A'}</p>
                <p><strong>Summary:</strong> ${briefing.summary || 'N/A'}</p>
                <p><strong>PM Analysis:</strong> ${briefing.pm_analysis || 'N/A'}</p>
                <a href="${briefing.source_url}" target="_blank" rel="noopener noreferrer">Source Link</a>
            `;
            resultsContainer.appendChild(card);
        });
    }

    /**
     * Renders the briefing data into a table.
     * @param {Array} briefings - An array of briefing objects.
     */
    function renderTableView(briefings) {
        const tableContainer = document.createElement('div');
        tableContainer.className = 'table-container';

        const table = document.createElement('table');
        table.id = 'results-table';

        table.innerHTML = `
            <thead>
                <tr>
                    <th>Competitor</th>
                    <th>Product Line</th>
                    <th>Feature/Update</th>
                    <th>Summary</th>
                    <th>PM Analysis</th>
                    <th>Source</th>
                </tr>
            </thead>
        `;

        const tbody = document.createElement('tbody');
        briefings.forEach(briefing => {
            const row = tbody.insertRow();
            row.insertCell().textContent = briefing.competitor || 'N/A';
            row.insertCell().textContent = briefing.product_line || 'N/A';
            row.insertCell().textContent = briefing.feature_update || 'N/A';
            row.insertCell().textContent = briefing.summary || 'N/A';
            row.insertCell().textContent = briefing.pm_analysis || 'N/A';

            const sourceCell = row.insertCell();
            const sourceLink = document.createElement('a');
            sourceLink.href = briefing.source_url;
            sourceLink.textContent = "View Source";
            sourceLink.target = "_blank";
            sourceLink.rel = "noopener noreferrer";
            sourceCell.appendChild(sourceLink);
        });

        table.appendChild(tbody);
        tableContainer.appendChild(table);
        resultsContainer.appendChild(tableContainer);
    }

    /**
     * Converts an array of objects to a CSV string and triggers a download.
     * @param {Array} briefings - The array of briefing data to download.
     */
    function downloadAsCSV(briefings) {
        if (briefings.length === 0) {
            alert("No data to download.");
            return;
        }

        const headers = ["Competitor", "Product Line", "Feature/Update", "Summary", "PM Analysis", "Source URL", "Processed At"];
        const rows = briefings.map(b => [
            `"${b.competitor || ''}"`, `"${b.product_line || ''}"`, `"${(b.feature_update || '').replace(/"/g, '""')}"`,
            `"${(b.summary || '').replace(/"/g, '""')}"`, `"${(b.pm_analysis || '').replace(/"/g, '""')}"`,
            `"${b.source_url || ''}"`, `"${b.processed_at || ''}"`
        ].join(','));

        const csvContent = [headers.join(','), ...rows].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", "ai_scout_briefings.csv");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // --- Event Listeners ---

    fetchButton.addEventListener('click', async () => {
        const competitor = competitorSelect.value;
        const productLine = productLineInput.value;
        await fetchBriefings(competitor, productLine);
        renderResults();
    });

    viewCardsBtn.addEventListener('click', () => {
        if (currentView === 'cards') return;
        currentView = 'cards';
        viewCardsBtn.classList.add('active');
        viewTableBtn.classList.remove('active');
        renderResults();
    });

    viewTableBtn.addEventListener('click', () => {
        if (currentView === 'table') return;
        currentView = 'table';
        viewTableBtn.classList.add('active');
        viewCardsBtn.classList.remove('active');
        renderResults();
    });

    downloadCsvBtn.addEventListener('click', () => {
        downloadAsCSV(lastFetchedBriefings);
    });

    productLineInput.addEventListener('focus', () => {
        productLineDropdown.style.display = 'block';
    });

    productLineInput.addEventListener('keyup', () => {
        const filter = productLineInput.value.toUpperCase();
        const links = productLineDropdown.getElementsByTagName('a');
        for (let i = 0; i < links.length; i++) {
            const txtValue = links[i].textContent || links[i].innerText;
            links[i].style.display = (txtValue.toUpperCase().indexOf(filter) > -1 || i === 0) ? "" : "none";
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.matches('#product-line-input')) {
            productLineDropdown.style.display = 'none';
        }
    });

    // --- Initial Setup ---
    populateDropdown();
    // Initially fetch all briefings to populate the page on load
    fetchBriefings('All', '').then(renderResults);
});
