let startHtml = logo.map((line, i) => {
    const colorIndex = rowColors[i] ?? 0;
    return `<span style="color:${colors[colorIndex]}">${line}</span>`;
}).join("<br>");

let currentSelection = 0;
const menuItems = ['Welcome', 'Search', 'Config'];

// Search state
let isInSearchMode = false;
let searchSelection = 0;
let searchItems = ['[Search Bar] '];
let searchQuery = '';
let currentPage = 1;
let lastSearchResults = [];
let previewTimer = null;
let currentPreviewPostId = null;

// Config state
let isInConfigMode = false;
let configSelection = 0;
let configItems = [
    'Preview Delay: 100ms',
    'Post Display: ID',
    'API Key: [Not Set]',
    'API Username: [Not Set]',
    'Back to Main Menu'
];

// Settings object to store current values
let settings = {
    previewDelay: 100,
    postDisplay: 'ID', // Options: 'ID', 'Creator', 'Tags', 'Fancy'
    apiKey: '',
    apiUsername: ''
};

const postDisplayOptions = ['ID', 'Creator', 'Tags', 'Fancy'];

// Load settings from localStorage
function loadSettings() {
    try {
        const savedSettings = localStorage.getItem('e26D.settings');
        if (savedSettings) {
            const parsed = JSON.parse(savedSettings);
            // Merge with default settings to handle new settings added in updates
            settings = { ...settings, ...parsed };
        }
    } catch (error) {
        console.warn('Failed to load settings from localStorage:', error);
    }
}

// Save settings to localStorage
function saveSettings() {
    try {
        localStorage.setItem('e26D.settings', JSON.stringify(settings));
    } catch (error) {
        console.warn('Failed to save settings to localStorage:', error);
    }
}

const searchAscii = [
    "  ░██████                                             ░██        ",
    " ░██   ░██                                            ░██        ",
    "░██          ░███████   ░██████   ░██░████  ░███████  ░████████  ",
    " ░████████  ░██    ░██       ░██  ░███     ░██    ░██ ░██    ░██ ",
    "        ░██ ░█████████  ░███████  ░██      ░██        ░██    ░██ ",
    " ░██   ░██  ░██        ░██   ░██  ░██      ░██    ░██ ░██    ░██ ",
    "  ░██████    ░███████   ░█████░██ ░██       ░███████  ░██    ░██ "
];

const configAscii = [
    "  ░██████                            ░████ ░██           ",
    " ░██   ░██                          ░██                  ",
    "░██         ░███████  ░████████  ░████████ ░██ ░████████ ",
    "░██        ░██    ░██ ░██    ░██    ░██    ░██░██    ░██ ",
    "░██        ░██    ░██ ░██    ░██    ░██    ░██░██    ░██ ",
    " ░██   ░██ ░██    ░██ ░██    ░██    ░██    ░██░██   ░███ ",
    "  ░██████   ░███████  ░██    ░██    ░██    ░██ ░█████░██ ",
    "                                                     ░██ ",
    "                                               ░███████  "
];

function getColoredAscii(asciiArt) {
    return asciiArt.map((line, i) => {
        let colorIndex;
        if (i < 7) {
            colorIndex = rowColors[i] ?? 0;
        } else {
            // For lines beyond 7, use the same color as the last (6th index) line
            colorIndex = rowColors[6] ?? 0;
        }
        return `<span style="color:${colors[colorIndex]}">${line}</span>`;
    }).join("<br>");
}

const menuDescriptions = {
    'Welcome': startHtml + "<br>Use up and down arrows to choose an option, press enter to select.<br>If any logos are wrapped, zoom out with <span style=\"color: #2f8ba7\">Ctrl</span>+<span style=\"color: #2f8ba7\">Minus</span><br>[Note: Welcome does not do anything]",
    'Search': getColoredAscii(searchAscii) + "<br>Search for images using the e621 api.<br>Please don't mind any lag.<br>Press <span style=\"color: #2f8ba7\">Escape</span> to return to main menu.",
    'Config': getColoredAscii(configAscii) + "<br>Change some settings, including user settings, and appearance settings.<br>Use arrow keys to navigate, Enter to modify values.<br>Press <span style=\"color: #2f8ba7\">Escape</span> to return to main menu."
};

function updateConfigItems() {
    const apiKeyDisplay = settings.apiKey ? `[${settings.apiKey.substring(0, 8)}...]` : '[Not Set]';
    const apiUsernameDisplay = settings.apiUsername || '[Not Set]';
    
    configItems = [
        `Preview Delay: ${settings.previewDelay}ms`,
        `Post Display: ${settings.postDisplay}`,
        `API Key: ${apiKeyDisplay}`,
        `API Username: ${apiUsernameDisplay}`,
        'Back to Main Menu'
    ];
}

async function searchE621(query, page = 1) {
    try {
        const url = `https://e621.net/posts.json?tags=${encodeURIComponent(query)}&limit=50&page=${page}`;
        const headers = {
            'User-Agent': 'e26D/1.0 (by pugsbyy on e621)'
        };
        
        // Add authentication if both API key and username are provided
        if (settings.apiKey && settings.apiUsername) {
            const auth = btoa(`${settings.apiUsername}:${settings.apiKey}`);
            headers['Authorization'] = `Basic ${auth}`;
        }
        
        const response = await fetch(url, { headers });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data.posts || [];
    } catch (error) {
        console.error('Error searching e621:', error);
        return [];
    }
}

async function loadPreviewImage(postId) {
    try {
        const response = await fetch(`/api/previewImage/post/${postId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const asciiArt = await response.text();
        return asciiArt;
    } catch (error) {
        console.error('Error loading preview image:', error);
        return '<span style="color: #ff6b6b;">Error loading preview</span>';
    }
}

function startPreviewTimer(postId) {
    // Clear any existing timer
    if (previewTimer) {
        clearTimeout(previewTimer);
    }
    
    // Don't start timer for non-post items
    if (!postId) return;
    
    // Don't reload if it's the same post
    if (currentPreviewPostId === postId) return;
    
    previewTimer = setTimeout(async () => {
        currentPreviewPostId = postId;
        const rightPanel = document.getElementById("spr");
        
        rightPanel.style.fontSize = "0.4vw";
        rightPanel.innerHTML = '<span style="color: #888;">Loading preview...</span>';
        
        const asciiArt = await loadPreviewImage(postId);
        
        // Only update if this is still the current selection
        if (currentPreviewPostId === postId) {
            rightPanel.innerHTML = asciiArt;
        }
    }, settings.previewDelay);
}

function clearPreviewTimer() {
    if (previewTimer) {
        clearTimeout(previewTimer);
        previewTimer = null;
    }
}

function resetRightPanel() {
    const rightPanel = document.getElementById("spr");
    rightPanel.style.fontSize = "";
    rightPanel.style.lineHeight = "";
    rightPanel.style.fontFamily = "";
    currentPreviewPostId = null;
    
    if (!isInSearchMode && !isInConfigMode) {
        const selectedItem = menuItems[currentSelection];
        rightPanel.innerHTML = menuDescriptions[selectedItem];
    }
}

function getPostIdFromItem(item) {
    if (typeof item === 'string') {
        // Handle different display formats
        if (item.startsWith('Post ID: ')) {
            return item.replace('Post ID: ', '');
        }
        // Handle Fancy format: [{ID}] ~ @{Creator} ~ {Tags} ~ [{rating}]
        const fancyMatch = item.match(/^\[(\d+)\]/);
        if (fancyMatch) {
            return fancyMatch[1];
        }
        // Handle cases where the item might just be the ID
        const idMatch = item.match(/^\d+$/);
        if (idMatch) {
            return item;
        }
    }
    return null;
}

function formatPostDisplay(post) {
    switch (settings.postDisplay) {
        case 'ID':
            return `${post.id}`;
        case 'Creator':
            const artist = post.tags?.artist?.[0] || 'Unknown';
            return `@${artist}`;
        case 'Tags':
            const tags = post.tags?.general || [];
            const displayTags = tags.slice(0, 4).join(' | ');
            return displayTags || 'No tags';
        case 'Fancy':
            const fancyTags = (post.tags?.general || []).slice(0, 4).join(' | ');
            const creator = post.tags?.artist?.[0] || 'Unknown';
            const rating = post.rating || 'unknown';
            return `[${post.id}] ~ @${creator} ~ ${fancyTags} ~ [${rating}]`;
        default:
            return `${post.id}`;
    }
}

async function loadNextPage() {
    if (searchQuery.trim() === '') return;
    
    // Remove the [Next Page] entry temporarily
    const nextPageIndex = searchItems.findIndex(item => item === '[Next Page]');
    if (nextPageIndex !== -1) {
        searchItems.splice(nextPageIndex, 1);
    }
    
    // Add loading message
    searchItems.push('Loading more...');
    updateSearchMenu();
    
    try {
        currentPage++;
        const results = await searchE621(searchQuery, currentPage);
        
        // Remove loading message
        searchItems.pop();
        
        // Add new post IDs to search items
        results.forEach(post => {
            const displayText = formatPostDisplay(post);
            searchItems.push(displayText);
        });
        
        // Add next page option if we got a full page of results
        if (results.length === 50) {
            searchItems.push('[Next Page]');
        }
        
    } catch (error) {
        // Remove loading message and show error
        searchItems.pop();
        searchItems.push('Error loading more results');
    }
    
    updateSearchMenu();
}

function updateConfigMenu() {
    const configHtml = configItems.map((item, index) => {
        const color = index === configSelection ? '#ff75a2' : '#f0f8ff';
        const arrow = index === configSelection ? '> ' : '  ';
        return `<span style="color:${color}" data-index="${index}">${arrow}${item}</span>`;
    }).join('<br>');
    
    document.getElementById("spl").innerHTML = configHtml;
    
    // Update right panel with config description
    const rightPanel = document.getElementById("spr");
    const selectedItem = configItems[configSelection];
    
    let description = "";
    switch(configSelection) {
        case 0:
            description = "Preview Delay<br><br>Controls how long to wait before loading image previews.<br>Range: 50ms - 2000ms<br><br>Use Left/Right arrows to adjust.";
            break;
        case 1:
            description = "Post Display<br><br>How to display search results:<br>• ID - Shows the post ID<br>• Creator - Shows the post's creator<br>• Tags - Shows the first 4 tags separated by pipes<br>• Fancy - Shows [{ID}] ~ @{Creator} ~ {Tags} ~ [{rating}]<br><br>Use Left/Right arrows to cycle through options.";
            break;
        case 2:
            description = "API Key<br><br>Your e621 API key for authenticated requests.<br>This allows access to additional content and higher rate limits.<br><br>Press Enter to input your API key.";
            break;
        case 3:
            description = "API Username<br><br>Your e621 username for authenticated requests.<br>Must be used together with your API key.<br><br>Press Enter to input your username.";
            break;
        case 4:
            description = "Return to the main menu.";
            break;
        default:
            description = menuDescriptions['Config'];
    }
    
    rightPanel.innerHTML = description;
    scrollToSelection();
}

function updateSearchMenu() {
    const searchHtml = searchItems.map((item, index) => {
        const color = index === searchSelection ? '#ff75a2' : '#f0f8ff';
        const arrow = index === searchSelection ? '> ' : '  ';
        
        // Special formatting for search bar
        if (index === 0) {
            const displayText = searchQuery === '' ? '[Search Bar]' : searchQuery;
            return `<span style="color:${color}" data-index="${index}">${arrow}${displayText}</span>`;
        }
        
        return `<span style="color:${color}" data-index="${index}">${arrow}${item}</span>`;
    }).join('<br>');
    
    document.getElementById("spl").innerHTML = searchHtml;
    scrollToSelection();
    
    // Handle preview for selected post
    const selectedItem = searchItems[searchSelection];
    const postId = getPostIdFromItem(selectedItem);
    
    if (postId) {
        startPreviewTimer(postId);
    } else {
        clearPreviewTimer();
        if (searchSelection === 0 || selectedItem === '[Next Page]' || selectedItem === 'No results found' || selectedItem.includes('Error')) {
            resetRightPanel();
        }
    }
}

function updateMenu() {
    if (isInSearchMode) {
        updateSearchMenu();
        return;
    }
    
    if (isInConfigMode) {
        updateConfigMenu();
        return;
    }
    
    // Clear any preview timers when not in search mode
    clearPreviewTimer();
    
    const menuHtml = menuItems.map((item, index) => {
        const color = index === currentSelection ? '#ff75a2' : '#f0f8ff';
        const arrow = index === currentSelection ? '> ' : '  ';
        return `<span style="color:${color}" data-index="${index}">${arrow}${item}</span>`;
    }).join('<br>');
    
    document.getElementById("spl").innerHTML = menuHtml;
    
    // Update right panel with description
    const selectedItem = menuItems[currentSelection];
    document.getElementById("spr").innerHTML = menuDescriptions[selectedItem];
    scrollToSelection();
    
    // Reset right panel styling
    resetRightPanel();
}

async function handleSearchBarEnter() {
    if (searchQuery.trim() === '') return;
    
    // Reset page counter for new search
    currentPage = 1;
    
    // Show loading message
    searchItems = [searchQuery === '' ? '[Search Bar]' : searchQuery, 'Loading...'];
    updateSearchMenu();
    
    try {
        const results = await searchE621(searchQuery, currentPage);
        lastSearchResults = results;
        
        // Reset search items with just the search bar
        searchItems = [searchQuery === '' ? '[Search Bar]' : searchQuery];
        
        // Add post results to search items
        results.forEach(post => {
            const displayText = formatPostDisplay(post);
            searchItems.push(displayText);
        });
        
        if (results.length === 0) {
            searchItems.push('No results found');
        } else if (results.length === 50) {
            // Add next page option if we got a full page of results
            searchItems.push('[Next Page]');
        }
        
    } catch (error) {
        searchItems = [searchQuery === '' ? '[Search Bar]' : searchQuery, 'Error occurred while searching'];
    }
    
    updateSearchMenu();
}

function adjustConfigValue(direction) {
    switch(configSelection) {
        case 0: // Preview Delay
            if (direction === 'left') {
                settings.previewDelay = Math.max(50, settings.previewDelay - 50);
            } else {
                settings.previewDelay = Math.min(2000, settings.previewDelay + 50);
            }
            break;
        case 1: // Post Display
            const currentIndex = postDisplayOptions.indexOf(settings.postDisplay);
            if (direction === 'left') {
                const newIndex = (currentIndex - 1 + postDisplayOptions.length) % postDisplayOptions.length;
                settings.postDisplay = postDisplayOptions[newIndex];
            } else {
                const newIndex = (currentIndex + 1) % postDisplayOptions.length;
                settings.postDisplay = postDisplayOptions[newIndex];
            }
            break;
    }
    saveSettings(); // Save settings after any change
    updateConfigItems();
    updateConfigMenu();
}

function promptForInput(fieldName) {
    const currentValue = fieldName === 'API Key' ? settings.apiKey : settings.apiUsername;
    const placeholder = fieldName === 'API Key' ? 'Enter your e621 API key' : 'Enter your e621 username';
    
    const newValue = prompt(`${placeholder}:`, currentValue);
    
    if (newValue !== null) { // User didn't cancel
        if (fieldName === 'API Key') {
            settings.apiKey = newValue.trim();
        } else {
            settings.apiUsername = newValue.trim();
        }
        saveSettings(); // Save settings after any change
        updateConfigItems();
        updateConfigMenu();
    }
}

function handleKeyPress(event) {
    if (isInConfigMode) {
        switch(event.key) {
            case 'ArrowUp':
                event.preventDefault();
                configSelection = (configSelection - 1 + configItems.length) % configItems.length;
                updateConfigMenu();
                break;
            case 'ArrowDown':
                event.preventDefault();
                configSelection = (configSelection + 1) % configItems.length;
                updateConfigMenu();
                break;
            case 'ArrowLeft':
                event.preventDefault();
                if (configSelection < 2) { // Only Preview Delay and Post Display use arrows
                    adjustConfigValue('left');
                }
                break;
            case 'ArrowRight':
                event.preventDefault();
                if (configSelection < 2) { // Only Preview Delay and Post Display use arrows
                    adjustConfigValue('right');
                }
                break;
            case 'Enter':
                event.preventDefault();
                if (configSelection === 4) { // Back to Main Menu
                    isInConfigMode = false;
                    currentSelection = 2; // Keep "Config" selected
                    updateMenu();
                } else if (configSelection === 2) { // API Key
                    promptForInput('API Key');
                } else if (configSelection === 3) { // API Username
                    promptForInput('API Username');
                } else if (configSelection === 1) { // Post Display - can also use Enter to cycle
                    adjustConfigValue('right');
                }
                break;
            case 'Escape':
                event.preventDefault();
                // Return to main menu
                isInConfigMode = false;
                currentSelection = 2; // Keep "Config" selected
                updateMenu();
                break;
        }
        return;
    }

    if (isInSearchMode) {
        switch(event.key) {
            case 'ArrowUp':
                event.preventDefault();
                searchSelection = (searchSelection - 1 + searchItems.length) % searchItems.length;
                updateSearchMenu();
                break;
            case 'ArrowDown':
                event.preventDefault();
                searchSelection = (searchSelection + 1) % searchItems.length;
                updateSearchMenu();
                break;
            case 'Enter':
                event.preventDefault();
                if (searchSelection === 0) {
                    // Search bar selected - search immediately if there's a query
                    if (searchQuery.trim() !== '') {
                        handleSearchBarEnter();
                    }
                } else if (searchItems[searchSelection] === '[Next Page]') {
                    // Next page selected - load more results
                    loadNextPage();
                } else {
                    // Handle selection of search results here if needed
                    console.log(`Selected search result: ${searchItems[searchSelection]}`);
                }
                break;
            case 'Escape':
                event.preventDefault();
                // Return to main menu
                clearPreviewTimer();
                isInSearchMode = false;
                currentSelection = 1; // Keep "Search" selected
                updateMenu();
                break;
            default:
                // Handle typing in search bar when it's selected
                if (searchSelection === 0 && event.key.length === 1) {
                    event.preventDefault();
                    searchQuery += event.key;
                    updateSearchMenu();
                } else if (searchSelection === 0 && event.key === 'Backspace') {
                    event.preventDefault();
                    searchQuery = searchQuery.slice(0, -1);
                    updateSearchMenu();
                }
                break;
        }
        return;
    }
    
    switch(event.key) {
        case 'ArrowUp':
            event.preventDefault();
            currentSelection = (currentSelection - 1 + menuItems.length) % menuItems.length;
            updateMenu();
            break;
        case 'ArrowDown':
            event.preventDefault();
            currentSelection = (currentSelection + 1) % menuItems.length;
            updateMenu();
            break;
        case 'Enter':
            event.preventDefault();
            if (menuItems[currentSelection] === 'Search') {
                // Enter search mode
                isInSearchMode = true;
                searchSelection = 0;
                searchItems = ['[Search Bar]'];
                searchQuery = '';
                updateSearchMenu();
            } else if (menuItems[currentSelection] === 'Config') {
                // Enter config mode
                isInConfigMode = true;
                configSelection = 0;
                updateConfigItems();
                updateConfigMenu();
            } else {
                // Handle other selections
                console.log(`Selected: ${menuItems[currentSelection]}`);
            }
            break;
    }
}

function scrollToSelection() {
    const leftPanel = document.getElementById("spl");
    const spans = leftPanel.querySelectorAll('span');
    
    let selectedIndex;
    if (isInSearchMode) {
        selectedIndex = searchSelection;
    } else if (isInConfigMode) {
        selectedIndex = configSelection;
    } else {
        selectedIndex = currentSelection;
    }
    
    if (spans[selectedIndex]) {
        const selectedSpan = spans[selectedIndex];
        const panelRect = leftPanel.getBoundingClientRect();
        const spanRect = selectedSpan.getBoundingClientRect();
        
        // Calculate if the selected item is outside the visible area
        const isAboveView = spanRect.top < panelRect.top;
        const isBelowView = spanRect.bottom > panelRect.bottom;
        
        if (isAboveView || isBelowView) {
            // Calculate the offset needed to center the selected item
            const panelHeight = panelRect.height;
            const spanTop = selectedSpan.offsetTop;
            const newScrollTop = spanTop - (panelHeight / 2);
            
            leftPanel.scrollTop = Math.max(0, newScrollTop);
        }
    }
}

function e26Dinit() {
    // Load settings first
    loadSettings();
    
    document.getElementById("content").style.display = "none";
    document.getElementById("outerCommand").style.display = "none";

    var sidePanelL = document.createElement("div");
    document.body.appendChild(sidePanelL);
    sidePanelL.style.width = "50vw";
    sidePanelL.style.height = "100vh";
    sidePanelL.style.position = "absolute";
    sidePanelL.style.left = "0";
    sidePanelL.style.top = "0";
    sidePanelL.style.whiteSpace = "pre-wrap";
    sidePanelL.style.userSelect = "text";
    sidePanelL.style.overflow = "auto";
    sidePanelL.style.padding = "8px";

    var sidePanelR = document.createElement("div");
    document.body.appendChild(sidePanelR);
    sidePanelR.style.width = "50vw";
    sidePanelR.style.height = "100vh";
    sidePanelR.style.position = "absolute";
    sidePanelR.style.right = "0";
    sidePanelR.style.top = "0";
    sidePanelR.style.whiteSpace = "pre-wrap";
    sidePanelR.style.userSelect = "text";
    sidePanelR.style.overflow = "auto";
    sidePanelR.style.padding = "8px";

    sidePanelL.id = "spl";
    sidePanelR.id = "spr";
    
    startHtml += "";
    sidePanelR.innerHTML = menuDescriptions['Welcome'];
    
    // Initialize the menu
    updateMenu();
    
    // Add keyboard event listener
    document.addEventListener('keydown', handleKeyPress);
}