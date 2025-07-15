// This ensures the script runs only after the full HTML document has been loaded.
document.addEventListener('DOMContentLoaded', () => {

    // --- Element References ---
    const fetchButton = document.getElementById('fetch-button');
    const resultsContainer = document.getElementById('results-container');
    const competitorSelect = document.getElementById('competitor-select');
    const productLineInput = document.getElementById('product-line-input');
    const productLineDropdown = document.getElementById('product-line-dropdown');
    const lastRunInfo = document.getElementById('last-run-info');

    // --- Data and Configuration ---
    const API_BASE_URL = 'https://ai-competition-scout-api.onrender.com'; // The URL of our BE API in render
    const productLines = [
        "Push", "Email", "SMS", "WhatsApp", "RCS", "Other channels", "In-App", "OSM", "Cards","Web Personalization (WebP)","Content Management","Settings",
        "Flows", "Segmentation", "Data", "Partner Integrations", "Miscellaneous & Others", "ML or AI","Analyze","Campaign Management"
    ];

    // --- Functions ---

    /**
     * Populates the product line dropdown with options.
     */
    function populateDropdown() {
        productLineDropdown.innerHTML = ''; // Clear existing options

        // 1. Create and add the "Clear" option
        const clearOption = document.createElement('a');
        clearOption.href = "#";
        clearOption.innerHTML = '&#10005; Clear Search'; // Use innerHTML to render the 'x' character
        clearOption.style.color = '#d9534f'; // Optional: Style it to look distinct
        clearOption.style.fontWeight = 'bold';

        clearOption.addEventListener('click', (e) => {
            e.preventDefault();
            productLineInput.value = ''; // Clear the input field
            productLineDropdown.style.display = 'none'; // Hide the dropdown
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
     * Fetches intelligence data from the LIVE backend API.
     * @param {string} competitor - The selected competitor ('All', 'Braze', 'Iterable').
     * @param {string} productLine - The searched product line.
     * @returns {Promise<Array>} - A promise that resolves to an array of briefing objects.
     */
    async function fetchBriefings(competitor, productLine) {
        fetchButton.classList.add('loading');
        fetchButton.disabled = true;
        resultsContainer.innerHTML = '<p>Fetching data from the server...</p>';

        // Construct the search URL with query parameters
        let url = `${API_BASE_URL}/api/briefings/search?`;
        const params = new URLSearchParams();

        if (competitor && competitor !== 'All') {
            params.append('competitor', competitor);
        }
        if (productLine) {
            params.append('product_line', productLine);
        }

        url += params.toString();
        console.log(`Fetching data from: ${url}`);

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error fetching briefings:', error);
            resultsContainer.innerHTML = '<p>An error occurred while fetching data from the API. Is the Flask server (app.py) running?</p>';
            return []; // Return an empty array on error
        } finally {
            fetchButton.classList.remove('loading');
            fetchButton.disabled = false;
        }
    }

    /**
     * Renders the briefing data into HTML cards.
     * @param {Array} briefings - An array of briefing objects.
     */
    function renderBriefings(briefings) {
        resultsContainer.innerHTML = ''; // Clear previous results

        if (briefings.length === 0) {
            resultsContainer.innerHTML = '<p>No intelligence briefings found for this search.</p>';
            lastRunInfo.textContent = 'No data found in the database.';
            return;
        }

        // Update the "last run" info with the date of the most recent briefing
        const mostRecentDate = new Date(briefings[0].processed_at);
        lastRunInfo.textContent = `Last intelligence gathered: ${mostRecentDate.toLocaleString()}`;

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

    // --- Event Listeners ---

    // Main fetch button event
    fetchButton.addEventListener('click', async () => {
        const competitor = competitorSelect.value;
        const productLine = productLineInput.value;
        const briefings = await fetchBriefings(competitor, productLine);
        renderBriefings(briefings);
    });

    // Show dropdown on input focus
    productLineInput.addEventListener('focus', () => {
        productLineDropdown.style.display = 'block';
    });

    // Filter dropdown as user types
    productLineInput.addEventListener('keyup', () => {
        const filter = productLineInput.value.toUpperCase();
        const links = productLineDropdown.getElementsByTagName('a');
        for (let i = 0; i < links.length; i++) {
            const txtValue = links[i].textContent || links[i].innerText;
            // The check `i === 0` ensures the "Clear Search" option is always visible.
            links[i].style.display = (txtValue.toUpperCase().indexOf(filter) > -1 || i === 0) ? "" : "none";
        }
    });

    // Close dropdown if clicked outside
    document.addEventListener('click', (e) => {
        if (!e.target.matches('#product-line-input')) {
            productLineDropdown.style.display = 'none';
        }
    });

    // --- Initial Setup ---
    populateDropdown();
    // Initially fetch all briefings to populate the page on load
    fetchBriefings('All', '').then(renderBriefings);
});
