/**
 * ResearchHub Pro - Main Application JavaScript
 * Handles API calls, authentication, and common UI interactions
 */

// Configuration
const API_BASE_URL = '/api/v1';

function sanitizeToken(token) {
    if (typeof token !== 'string') {
        return null;
    }
    const trimmed = token.trim();
    if (!trimmed || trimmed === 'null' || trimmed === 'undefined') {
        return null;
    }
    return trimmed;
}

let authToken = sanitizeToken(localStorage.getItem('access_token'));
const THEME_STORAGE_KEY = 'researchhub-theme';
const THEME_DEFAULT = 'dark';

const INTEGRATION_FIELD_MAP = {
    perplexity: 'perplexity_api_key',
    openai: 'openai_api_key',
    anthropic: 'anthropic_api_key',
    serpapi: 'serpapi_api_key'
};

const INTEGRATION_LABELS = {
    perplexity: 'Perplexity',
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    serpapi: 'SerpAPI'
};

class ApiError extends Error {
    constructor(message, status = 0, payload = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.payload = payload;
    }
}

let unauthorizedNotified = false;

function clearAuthTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setStoredUser(null);
    authToken = null;
}

function handleUnauthorized() {
    if (unauthorizedNotified) {
        return;
    }
    unauthorizedNotified = true;
    clearAuthTokens();
    showAlert('Your session has expired. Please sign in to continue.', 'warning');
    setTimeout(() => {
        window.location.href = '/login';
        unauthorizedNotified = false;
    }, 1200);
}

// API Helper Functions
const api = {
    async request(endpoint, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (authToken) {
            config.headers['Authorization'] = `Bearer ${authToken}`;
        }

        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
            const rawBody = await response.text();
            let data = {};

            if (rawBody) {
                try {
                    data = JSON.parse(rawBody);
                } catch (parseError) {
                    data = { raw: rawBody };
                }
            }

            if (!response.ok) {
                const message = data.error || data.message || data.msg || `Request failed (${response.status})`;
                const lowerMessage = typeof message === 'string' ? message.toLowerCase() : '';
                const looksLikeJwtError = lowerMessage.includes('authorization')
                    || lowerMessage.includes('jwt')
                    || lowerMessage.includes('token')
                    || lowerMessage.includes('segments')
                    || lowerMessage.includes('subject must be a string');

                if (response.status === 401 || (response.status === 422 && looksLikeJwtError)) {
                    handleUnauthorized();
                }
                throw new ApiError(message, response.status, data);
            }

            return data;
        } catch (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            console.error('API Error:', error);
            throw new ApiError('Network error. Please check your connection and try again.', 0);
        }
    },

    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
};

// Authentication Functions
async function login(identifier, password, integrationOverrides = '') {
    try {
        const payload = { email: identifier, password };
        applyIntegrationOverridesToPayload(payload, integrationOverrides);
        const data = await api.post('/auth/login', payload);
        authToken = sanitizeToken(data.access_token);
        unauthorizedNotified = false;
        if (authToken) {
            localStorage.setItem('access_token', authToken);
        }
        if (data.refresh_token) {
            localStorage.setItem('refresh_token', data.refresh_token);
        }
        setStoredUser(data.user);

        syncNavigationForAuth(data.user);
        showAlert('Welcome back to ResearchHub Pro!', 'success');
        handleIntegrationFeedback(data);
        setTimeout(() => window.location.href = '/dashboard', 800);
        return data;
    } catch (error) {
        const message = error instanceof ApiError ? error.message : 'Unable to sign in right now.';
        showAlert(message, error.status === 401 ? 'warning' : 'error');
        throw error;
    }
}

async function register(userData) {
    try {
        const payload = { ...userData };
        cleanIntegrationFields(payload);
        const data = await api.post('/auth/register', payload);
        authToken = sanitizeToken(data.access_token);
        unauthorizedNotified = false;
        if (authToken) {
            localStorage.setItem('access_token', authToken);
        }
        if (data.refresh_token) {
            localStorage.setItem('refresh_token', data.refresh_token);
        }
        setStoredUser(data.user);

        syncNavigationForAuth(data.user);
        showAlert('Account created successfully. Setting up your workspace…', 'success');
        handleIntegrationFeedback(data);
        setTimeout(() => window.location.href = '/dashboard', 900);
        return data;
    } catch (error) {
        const message = error instanceof ApiError ? error.message : 'Registration failed. Please try again later.';
        showAlert(message, error.status === 409 ? 'warning' : 'error');
        throw error;
    }
}

async function logout({ silent = false } = {}) {
    try {
        if (authToken) {
            await api.post('/auth/logout', {});
        }
    } catch (error) {
        console.warn('Logout request failed:', error);
    } finally {
        clearAuthTokens();
        syncNavigationForAuth(null);
        if (!silent) {
            showAlert('You have been signed out.', 'info');
            setTimeout(() => window.location.href = '/login', 600);
        }
    }
}

async function requestPasswordReset(email) {
    try {
        const message = 'If an account exists, we sent reset instructions.';
        await api.post('/auth/password/forgot', { email });
        showAlert(message, 'info');
        return { message };
    } catch (error) {
        const message = error instanceof ApiError ? error.message : 'Unable to process password reset right now.';
        showAlert(message, 'error');
        throw error;
    }
}

async function resetPasswordWithToken({ token, password, confirmPassword }) {
    try {
        const payload = { token, password, confirm_password: confirmPassword ?? password };
        const response = await api.post('/auth/password/reset', payload);
        showAlert('Password updated. You may now sign in.', 'success');
        return response;
    } catch (error) {
        const message = error instanceof ApiError ? error.message : 'Failed to reset password.';
        showAlert(message, 'error');
        throw error;
    }
}

function isAuthenticated() {
    return !!authToken;
}

function getCurrentUser() {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
}

function setStoredUser(user) {
    try {
        if (user) {
            localStorage.setItem('user', JSON.stringify(user));
        } else {
            localStorage.removeItem('user');
        }
    } catch (error) {
        console.warn('Unable to persist user profile locally:', error);
    }

    try {
        window.dispatchEvent(new CustomEvent('user:updated', { detail: { user } }));
    } catch (error) {
        console.warn('Unable to notify listeners of user changes:', error);
    }
}

function applyIntegrationOverridesToPayload(payload, overrides) {
    if (!overrides) {
        return;
    }

    if (typeof overrides === 'string') {
        const trimmed = overrides.trim();
        if (trimmed) {
            payload.perplexity_api_key = trimmed;
        }
        return;
    }

    if (typeof overrides !== 'object') {
        return;
    }

    Object.entries(overrides).forEach(([key, value]) => {
        if (!value) {
            return;
        }
        if (INTEGRATION_FIELD_MAP[key]) {
            payload[INTEGRATION_FIELD_MAP[key]] = value;
        } else if (key.endsWith('_api_key')) {
            payload[key] = value;
        }
    });
}

function cleanIntegrationFields(payload) {
    Object.values(INTEGRATION_FIELD_MAP).forEach(field => {
        if (field in payload && !payload[field]) {
            delete payload[field];
        }
    });
}

function handleIntegrationFeedback(payload) {
    if (!payload) {
        return;
    }

    const updates = {};

    if (payload.perplexity_integration) {
        updates.perplexity = payload.perplexity_integration;
    }

    if (payload.integration_updates) {
        Object.assign(updates, payload.integration_updates);
    }

    if (!Object.keys(updates).length) {
        return;
    }

    Object.entries(updates).forEach(([provider, status]) => {
        if (!status) {
            return;
        }

        const label = INTEGRATION_LABELS[provider] || provider.charAt(0).toUpperCase() + provider.slice(1);
        if (provider === 'perplexity') {
            if (status.connected && status.just_linked) {
                showAlert(`${label} API key verified and linked to your workspace.`, 'success');
            } else if (status.status === 'removed' || !status.connected) {
                showAlert(`${label} API key removed from your account.`, 'info');
            } else if (status.connected) {
                showAlert(`${label} API key refreshed.`, 'info');
            }
            return;
        }

        if (status.connected) {
            showAlert(`${label} key saved for upcoming workflows.`, 'success');
        } else if (status.status === 'not_configured') {
            showAlert(`${label} key removed.`, 'info');
        }
    });
}

// UI Helper Functions
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    if (!alertContainer) return;

    const alert = document.createElement('div');
    const variant = type === 'error' ? 'danger' : type;
    alert.className = `alert alert-${variant} alert-dismissible fade show`;
    alert.setAttribute('role', 'alert');
    alert.setAttribute('aria-live', 'assertive');
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    alertContainer.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 5000);
}

function showLoading(element, message = 'Loading...') {
    element.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary mb-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="text-muted">${message}</p>
        </div>
    `;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 10) return 'just now';
    if (seconds < 60) return `${seconds} seconds ago`;
    if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
    }
    if (seconds < 86400) {
        const hours = Math.floor(seconds / 3600);
        const remainingSeconds = seconds - hours * 3600;
        const minutes = Math.floor(remainingSeconds / 60);
        if (hours >= 6) {
            return `${hours} hour${hours === 1 ? '' : 's'} ago`;
        }
        if (hours >= 1) {
            if (minutes === 0) {
                return `${hours} hour${hours === 1 ? '' : 's'} ago`;
            }
            return `${hours}h ${minutes}m ago`;
        }
    }
    if (seconds < 604800) {
        const days = Math.floor(seconds / 86400);
        const timePart = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        if (days === 1) {
            return `Yesterday at ${timePart}`;
        }
        return `${days} days ago at ${timePart}`;
    }
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Search Functions
async function performSearch(query, options = {}) {
    try {
        const searchData = {
            query: query,
            num_results: options.num_results || 10,
            search_type: options.search_type || 'auto',
            enhance_query: options.enhance_query || false,
            save_results: options.save_results !== false
        };

        const data = await api.post('/research/search', searchData);
        return data;
    } catch (error) {
        console.error('Search failed:', error);
        throw error;
    }
}

async function getSearchHistory(page = 1, perPage = 20) {
    try {
        const data = await api.get(`/research/queries?page=${page}&per_page=${perPage}`);
        return data;
    } catch (error) {
        console.error('Failed to get search history:', error);
        throw error;
    }
}

// Collection Functions
async function createCollection(title, description) {
    try {
        const data = await api.post('/collections', { title, description });
        showAlert('Collection created successfully!', 'success');
        return data;
    } catch (error) {
        console.error('Failed to create collection:', error);
        throw error;
    }
}

async function getCollections() {
    try {
        const data = await api.get('/collections');
        return data;
    } catch (error) {
        console.error('Failed to get collections:', error);
        throw error;
    }
}

async function addToCollection(collectionId, resultId, { notify = true } = {}) {
    try {
        const response = await api.post(`/collections/${collectionId}/results/${resultId}`);
        if (notify) {
            showAlert('Added to collection!', 'success');
        }
        return response;
    } catch (error) {
        console.error('Failed to add to collection:', error);
        throw error;
    }
}

// Export Functions
async function exportResults(queryId, format = 'json') {
    try {
        window.location.href = `${API_BASE_URL}/export/query/${queryId}?format=${format}`;
        showAlert(`Exporting as ${format.toUpperCase()}...`, 'info');
    } catch (error) {
        console.error('Export failed:', error);
        throw error;
    }
}

// Initialize on page load
function applyTheme(theme) {
    const resolvedTheme = theme === 'light' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', resolvedTheme);
    localStorage.setItem(THEME_STORAGE_KEY, resolvedTheme);

    const toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.setAttribute('aria-pressed', resolvedTheme === 'dark' ? 'true' : 'false');
        toggle.innerHTML = resolvedTheme === 'dark'
            ? '<i class="fas fa-sun"></i>'
            : '<i class="fas fa-moon"></i>';
    }

    const themeMeta = document.getElementById('themeColorMeta');
    if (themeMeta) {
        themeMeta.setAttribute('content', resolvedTheme === 'dark' ? '#111215' : '#F4F6FB');
    }

    const navbar = document.getElementById('primaryNavbar');
    if (navbar) {
        navbar.classList.toggle('navbar-dark', resolvedTheme === 'dark');
        navbar.classList.toggle('navbar-light', resolvedTheme === 'light');
    }
}

function initializeTheme() {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    const initialTheme = stored || THEME_DEFAULT;
    applyTheme(initialTheme);

    const toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.addEventListener('click', () => {
            const current = document.body.getAttribute('data-theme') || THEME_DEFAULT;
            const nextTheme = current === 'dark' ? 'light' : 'dark';
            applyTheme(nextTheme);
        });
    }
}

function syncNavigationForAuth(user) {
    const loginLink = document.getElementById('navLoginLink');
    const accountDropdown = document.getElementById('navAccountDropdown');
    const dropdownTrigger = document.getElementById('userDropdown');

    if (user) {
        if (loginLink) {
            loginLink.classList.add('d-none');
        }
        if (accountDropdown) {
            accountDropdown.classList.remove('d-none');
        }
        if (dropdownTrigger) {
            const displayName = user.first_name || user.full_name || user.username || 'Account';
            dropdownTrigger.innerHTML = `<i class="fas fa-user-circle me-2"></i>${displayName}`;
        }
    } else {
        if (accountDropdown) {
            accountDropdown.classList.add('d-none');
        }
        if (loginLink) {
            loginLink.classList.remove('d-none');
        }
    }
}

function highlightActiveNavigation() {
    const path = window.location.pathname.replace(/\/+$/, '') || '/';
    const navLinks = document.querySelectorAll('.app-navbar .nav-link');

    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (!href || href.startsWith('http')) {
            return;
        }

    const normalizedHref = href.replace(/\/+$/, '') || '/';
    const isDropdownItem = link.closest('.dropdown-menu');
    const hierarchicalMatch = normalizedHref !== '/' && path.startsWith(`${normalizedHref}/`);
    const isActive = path === normalizedHref || hierarchicalMatch;

        link.classList.toggle('active', isActive);

        if (isDropdownItem) {
            const parentToggle = link.closest('.dropdown')?.querySelector('.nav-link.dropdown-toggle');
            if (parentToggle) {
                parentToggle.classList.toggle('active', isActive);
            }
        }
    });
}

function initializeNavbarAutoHide() {
    const navbar = document.getElementById('primaryNavbar');
    if (!navbar) {
        return;
    }

    const collapse = document.getElementById('primaryNav');
    const toggler = document.querySelector('.navbar-toggler');
    const HIDE_DELAY = 200;
    let lastScrollY = window.scrollY;
    let lastDirection = null;
    let directionStart = performance.now();
    let ticking = false;

    const collapseIsOpen = () => collapse && collapse.classList.contains('show');

    const showNavbar = () => {
        navbar.classList.remove('app-navbar-hidden');
    };

    const hideNavbar = () => {
        navbar.classList.add('app-navbar-hidden');
    };

    const updateNavbarVisibility = () => {
        const current = window.scrollY;
        const direction = current > lastScrollY ? 'down' : 'up';
        const atTop = current <= 0;

        if (collapseIsOpen()) {
            showNavbar();
            lastScrollY = current;
            ticking = false;
            return;
        }

        if (direction !== lastDirection) {
            lastDirection = direction;
            directionStart = performance.now();
        }

        const elapsed = performance.now() - directionStart;

        if (direction === 'down' && !atTop) {
            if (elapsed >= HIDE_DELAY) {
                hideNavbar();
            }
        } else {
            if (elapsed >= HIDE_DELAY || atTop) {
                showNavbar();
            }
        }

        lastScrollY = Math.max(current, 0);
        ticking = false;
    };

    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(updateNavbarVisibility);
            ticking = true;
        }
    }, { passive: true });

    window.addEventListener('resize', () => {
        if (window.innerWidth >= 992) {
            showNavbar();
        }
    });

    if (toggler) {
        toggler.addEventListener('click', () => {
            showNavbar();
        });
    }
}

function applyIconAccessibility(root) {
    const scope = root instanceof Element ? root : document;

    scope.querySelectorAll('i[class*="fa-"]').forEach(icon => {
        if (!icon.hasAttribute('aria-hidden')) {
            icon.setAttribute('aria-hidden', 'true');
        }
        icon.setAttribute('focusable', 'false');
    });

    scope.querySelectorAll('.btn-icon, .icon-button').forEach(button => {
        const ariaLabel = button.getAttribute('aria-label');
        if (!ariaLabel) {
            const label = button.getAttribute('title') || button.dataset.iconLabel;
            if (label) {
                button.setAttribute('aria-label', label);
            }
        }
    });
}

window.refreshIconAccessibility = (root) => applyIconAccessibility(root);

window.addEventListener('user:updated', (event) => {
    const updatedUser = event?.detail?.user ?? getCurrentUser();
    syncNavigationForAuth(updatedUser);
});

document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();

    const user = getCurrentUser();
    syncNavigationForAuth(user);
    highlightActiveNavigation();
    initializeNavbarAutoHide();
    applyIconAccessibility(document);
});

window.addEventListener('storage', (event) => {
    if (!event.key || !['access_token', 'user'].includes(event.key)) {
        return;
    }
    authToken = sanitizeToken(localStorage.getItem('access_token'));
    const user = getCurrentUser();
    syncNavigationForAuth(user);
    window.dispatchEvent(new CustomEvent('user:updated', { detail: { user } }));
});

// Export functions for use in other scripts
window.api = api;
window.showAlert = showAlert;
window.showLoading = showLoading;
window.login = login;
window.register = register;
window.logout = logout;
window.requestPasswordReset = requestPasswordReset;
window.resetPasswordWithToken = resetPasswordWithToken;
window.isAuthenticated = isAuthenticated;
window.getCurrentUser = getCurrentUser;
window.setStoredUser = setStoredUser;
window.handleIntegrationFeedback = handleIntegrationFeedback;
window.handlePerplexityIntegrationFeedback = handleIntegrationFeedback;
window.performSearch = performSearch;
window.getSearchHistory = getSearchHistory;
window.createCollection = createCollection;
window.getCollections = getCollections;
window.addToCollection = addToCollection;
window.exportResults = exportResults;
window.formatDate = formatDate;
window.formatRelativeTime = formatRelativeTime;
window.debounce = debounce;
