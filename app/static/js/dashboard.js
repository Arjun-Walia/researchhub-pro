/**
 * Dashboard JavaScript
 */

let dashboardData = {
    stats: {
        searchesToday: 0,
        totalProjects: 0,
        totalCollections: 0,
        savedResults: 0
    },
    projects: [],
    collections: [],
    recentSearches: [],
    activity: [],
    capabilities: {}
};

let engagementChartInstance = null;

const ACTIVITY_COLOR_MAP = {
    search: '--color-accent',
    login: '--color-info',
    export: '--color-positive',
    project_created: '--color-warning',
    collection_created: '--color-critical'
};

const ACTIVITY_FALLBACK_PALETTE = ['#297EF6', '#38BDF8', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

const persistUserLocally = typeof window.setStoredUser === 'function'
    ? window.setStoredUser
    : (user) => {
        if (!user) {
            localStorage.removeItem('user');
            return;
        }
        localStorage.setItem('user', JSON.stringify(user));
    };

const EXCLUDED_ACTIVITY_TYPES = new Set(['registration']);

const notifyIconRefresh = (root) => {
    if (typeof window.refreshIconAccessibility === 'function') {
        window.refreshIconAccessibility(root || document);
    }
};

function animateCounter(element, targetValue) {
    if (!element) {
        return;
    }

    const startValue = Number(element.dataset.value || 0);
    const endValue = Number(targetValue || 0);
    const duration = 650;
    const startTime = performance.now();

    function updateFrame(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(startValue + (endValue - startValue) * eased);
        element.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(updateFrame);
        } else {
            element.textContent = endValue.toLocaleString();
            element.dataset.value = endValue;
        }
    }

    requestAnimationFrame(updateFrame);
}

function updateCounter(id, value) {
    const el = document.getElementById(id);
    if (el) {
        animateCounter(el, value);
    }
}

function renderCapabilityBanner() {
    const container = document.getElementById('dashboardCapabilityBanner');
    if (!container) {
        return;
    }

    const defaults = {
        powered_by: [],
        search_provider: null,
        ai_model_providers: [],
        enrichment_providers: [],
        has_premium_search: false,
        has_premium_ai: false,
        has_enrichment: false
    };
    const capabilities = {
        ...defaults,
        ...(dashboardData.capabilities || {})
    };

    const providers = capabilities.powered_by?.length
        ? capabilities.powered_by
        : (capabilities.search_provider ? [capabilities.search_provider] : []);

    const providerChips = providers.length
        ? providers.map(name => `<span class="chip">${escapeHtml(name)}</span>`).join('')
        : '<span class="chip text-muted">No providers linked</span>';

    const featureMap = [
        { key: 'has_premium_search', label: 'Premium search' },
        { key: 'has_premium_ai', label: 'AI drafting' },
        { key: 'has_enrichment', label: 'Web enrichment' }
    ];

    const featureBadges = featureMap.map(feature => {
        const active = capabilities[feature.key];
        const icon = active ? 'fas fa-check' : 'fas fa-plug';
        const text = active ? `${feature.label} ready` : `${feature.label} locked`;
        const badgeClass = active ? 'badge badge-positive' : 'badge badge-neutral';
        return `<span class="${badgeClass}"><i class="${icon}"></i>${escapeHtml(text)}</span>`;
    }).join('');

    const missing = featureMap.filter(feature => !capabilities[feature.key]);
    const message = missing.length
        ? `Connect keys in <a href="/settings">Settings > Integrations</a> to unlock ${missing.length === 1 ? missing[0].label.toLowerCase() : 'these features'}.`
        : 'All premium capabilities unlocked. Enjoy full-speed research.';

    container.innerHTML = `
        <div class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-3">
            <div>
                <span class="section-label d-block mb-2">Powered by</span>
                <div class="chip-group">
                    ${providerChips}
                </div>
            </div>
            <div class="d-flex flex-wrap gap-2">
                ${featureBadges}
            </div>
        </div>
        <p class="text-muted small mb-0 mt-2">${message}</p>
    `;
    container.classList.remove('d-none');
    notifyIconRefresh(container);
}

function renderNotifications() {
    const container = document.getElementById('dashboardNotifications');
    if (!container) {
        return;
    }

    const items = [];
    const { searchesToday, totalProjects, totalCollections } = dashboardData.stats;
    const capabilities = dashboardData.capabilities || {};

    if (!capabilities.has_premium_search) {
        items.push({
            icon: 'fas fa-plug',
            title: 'Unlock AI search.',
            message: 'Connect a Perplexity, Gemini, or SerpAPI key in Settings > Integrations.',
            badge: { label: 'Action needed', type: 'badge-neutral' }
        });
    } else if (!capabilities.has_premium_ai) {
        items.push({
            icon: 'fas fa-robot',
            title: 'Boost answers with AI models.',
            message: 'Link OpenAI, Anthropic, or Gemini for summaries and drafting support.',
            badge: { label: 'Optional', type: 'badge-neutral' }
        });
    }

    if (searchesToday === 0) {
        items.push({
            icon: 'fas fa-magnifying-glass-plus',
            title: 'Kick off your first search today.',
            message: 'Use advanced filters to surface the most relevant intelligence instantly.',
            badge: { label: 'Try now', type: 'badge-accent' }
        });
    } else {
        items.push({
            icon: 'fas fa-fire',
            title: `Team has completed ${searchesToday} searches today.`,
            message: 'Summaries and exports are ready to distribute to stakeholders.',
            badge: { label: 'Active', type: 'badge-positive' }
        });
    }

    if (totalProjects > 0 && dashboardData.projects.length) {
        const latestProject = dashboardData.projects[0];
        items.push({
            icon: 'fas fa-lightbulb',
            title: `${latestProject.name || 'New project'} ready for review.`,
            message: latestProject.description || 'Add collaborators and assign deliverables.',
            badge: { label: 'Project', type: 'badge-neutral' }
        });
    }

    if (totalCollections > 0 && dashboardData.collections.length) {
        items.push({
            icon: 'fas fa-share-nodes',
            title: 'Share your freshest collection.',
            message: 'Export in PDF, Markdown, or CSV so directors can review immediately.',
            badge: { label: 'Share', type: 'badge-accent' }
        });
    }

    if (!items.length) {
        container.innerHTML = `
            <div class="feed-item">
                <span class="feed-icon"><i class="fas fa-bell"></i></span>
                <div class="feed-body">
                    <strong>No notifications yet.</strong>
                    <p class="mb-0 text-muted">Track new assignments, approvals, and AI briefings here.</p>
                </div>
            </div>
        `;
        return;
    }

    container.innerHTML = items.slice(0, 3).map(item => `
        <div class="feed-item">
            <span class="feed-icon"><i class="${item.icon}"></i></span>
            <div class="feed-body">
                <strong>${escapeHtml(item.title)}</strong>
                <p class="mb-0 text-muted">${escapeHtml(item.message)}</p>
            </div>
            <span class="badge ${item.badge.type}">${item.badge.label}</span>
        </div>
    `).join('');
    notifyIconRefresh(container);
}

function getCssVariable(prop, fallback = '') {
    const styles = window.getComputedStyle(document.body || document.documentElement);
    const value = styles.getPropertyValue(prop);
    return value ? value.trim() : fallback;
}

function resolveActivityColor(activityKey, index) {
    const palette = Object.values(ACTIVITY_COLOR_MAP);
    const cssVar = ACTIVITY_COLOR_MAP[activityKey] || palette[index % palette.length];
    const colorValue = cssVar ? getCssVariable(cssVar) : '';
    if (colorValue) {
        return colorValue;
    }
    return ACTIVITY_FALLBACK_PALETTE[index % ACTIVITY_FALLBACK_PALETTE.length];
}

function renderEngagementChart(breakdown, periodDays) {
    const canvas = document.getElementById('engagementChart');
    const emptyState = document.getElementById('engagementChartEmpty');

    if (!canvas) {
        return;
    }

    const hasData = breakdown && Object.keys(breakdown).length > 0;

    if (!hasData || typeof Chart === 'undefined') {
        if (engagementChartInstance) {
            engagementChartInstance.destroy();
            engagementChartInstance = null;
        }
        canvas.classList.add('d-none');
        if (emptyState) {
            emptyState.classList.remove('d-none');
        }
        return;
    }

    const entries = Object.entries(breakdown)
        .filter(([type, value]) => !EXCLUDED_ACTIVITY_TYPES.has(type) && value && Number.isFinite(Number(value)))
        .map(([type, value]) => ({ type, count: Number(value) }))
        .sort((a, b) => b.count - a.count);

    if (!entries.length) {
        if (engagementChartInstance) {
            engagementChartInstance.destroy();
            engagementChartInstance = null;
        }
        canvas.classList.add('d-none');
        if (emptyState) {
            emptyState.classList.remove('d-none');
        }
        return;
    }

    const labels = entries.map(entry => formatActivityType(entry.type));
    const dataPoints = entries.map(entry => entry.count);
    const backgroundColors = entries.map((entry, index) => resolveActivityColor(entry.type, index));
    const borderRadius = 18;

    if (engagementChartInstance) {
        engagementChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    const textColor = getCssVariable('--color-text-soft', '#94A3B8');
    const gridColor = getCssVariable('--color-border-subtle', 'rgba(148, 163, 184, 0.3)');
    const accentColor = getCssVariable('--color-accent', '#297EF6');
    const periodLabel = periodDays ? `Last ${periodDays} days` : 'Recent activity';

    engagementChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: periodLabel,
                data: dataPoints,
                backgroundColor: backgroundColors,
                borderWidth: 0,
                borderRadius,
                maxBarThickness: 32,
                barPercentage: 0.8,
                categoryPercentage: 0.6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            animation: {
                duration: 600,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: getCssVariable('--color-surface-primary', '#111827'),
                    titleColor: textColor,
                    bodyColor: '#FFFFFF',
                    borderColor: accentColor,
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label(context) {
                            const value = context.parsed.x || context.parsed.y || 0;
                            return `${value.toLocaleString()} event${value === 1 ? '' : 's'}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        color: gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        color: textColor,
                        precision: 0,
                        callback(value) {
                            return Number(value).toLocaleString();
                        }
                    }
                },
                y: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        color: textColor
                    }
                }
            }
        }
    });

    canvas.classList.remove('d-none');
    if (emptyState) {
        emptyState.classList.add('d-none');
    }
}

// Load dashboard data
async function loadDashboard() {
    try {
        // Load stats
        await Promise.all([
            loadUserStats(),
            loadRecentSearches(),
            loadActivity()
        ]);
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showAlert('Failed to load dashboard data', 'danger');
    }
}

async function loadUserStats() {
    try {
        let user = getCurrentUser();
        try {
            const response = await api.get('/auth/me');
            user = response.user || response;
            if (user) {
                persistUserLocally(user);
            }
        } catch (error) {
            console.warn('Unable to refresh user profile for dashboard:', error);
        }

        const firstNameTarget = document.getElementById('dashboardFirstName');
        if (user && firstNameTarget) {
            const friendlyName = user.first_name || user.full_name || user.username || 'Researcher';
            firstNameTarget.textContent = friendlyName;
        }

        dashboardData.capabilities = user?.integration_capabilities || {};
        renderCapabilityBanner();

        const usage = user?.usage || {};
        dashboardData.stats.searchesToday = usage.searches_today ?? user?.searches_today ?? 0;
        updateCounter('searchesTodayValue', dashboardData.stats.searchesToday);

        const projectsData = await api.get('/research/projects');
        dashboardData.projects = projectsData.projects || [];
    dashboardData.stats.totalProjects = dashboardData.projects.length;
        updateCounter('totalProjectsValue', dashboardData.stats.totalProjects);

        const collectionsData = await api.get('/collections/');
        dashboardData.collections = collectionsData.collections || [];
    dashboardData.stats.totalCollections = dashboardData.collections.length;
        updateCounter('totalCollectionsValue', dashboardData.stats.totalCollections);

        const queriesData = await api.get('/research/queries?per_page=100');
    dashboardData.stats.savedResults = queriesData.total || 0;
        updateCounter('savedResultsValue', dashboardData.stats.savedResults);
        dashboardData.recentSearches = queriesData.queries || [];

        const trendText = document.getElementById('searchesTrendText');
        if (trendText) {
            trendText.textContent = dashboardData.stats.searchesToday > 0
                ? 'Great momentum—keep surfacing emerging insights.'
                : 'No live searches logged yet today. Your AI copilot is ready.';
        }

        renderNotifications();
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadRecentSearches() {
    try {
        const data = await api.get('/research/queries?per_page=5');
        const tbody = document.querySelector('#recentSearchesTable tbody');

        if (!tbody) {
            return;
        }

        if (!data.queries.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4">
                        <div class="empty-state">
                            <div class="icon"><i class="fas fa-inbox"></i></div>
                            <p class="mb-0 text-muted">No searches yet. <a href="/search">Start your first query.</a></p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        dashboardData.recentSearches = data.queries;
        tbody.innerHTML = data.queries.map(query => `
            <tr>
                <td>
                    <strong>${escapeHtml(query.query_text)}</strong>
                    ${query.enhanced_query ? '<span class="badge badge-accent ms-2">AI enhanced</span>' : ''}
                </td>
                <td>${(query.total_results || 0).toLocaleString()} results</td>
                <td><span class="relative-time" data-timestamp="${query.created_at}">${formatRelativeTime(query.created_at)}</span></td>
                <td>
                    <div class="action-group">
                        <button class="btn-icon" type="button" onclick="viewQuery(${query.id})" title="Open query">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn-icon" type="button" onclick="exportResults(${query.id}, 'pdf')" title="Export results">
                            <i class="fas fa-file-arrow-down"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        notifyIconRefresh(tbody);
        if (typeof window.refreshRelativeTimes === 'function') {
            window.refreshRelativeTimes(tbody);
        }

    } catch (error) {
        console.error('Failed to load recent searches:', error);
    }
}

async function loadActivity() {
    try {
        const data = await api.get('/analytics/dashboard?days=7');
        const activityFeed = document.getElementById('activityFeed');

        if (!activityFeed) {
            renderEngagementChart(data.activity_summary?.activity_breakdown, data.period_days);
            return;
        }

        if (!data.activity_summary || !data.activity_summary.activity_breakdown) {
            activityFeed.innerHTML = `
                <div class="empty-state">
                    <div class="icon"><i class="fas fa-info-circle"></i></div>
                    <p class="mb-0 text-muted">No recent events. Your activity stream will appear here.</p>
                </div>
            `;
            renderEngagementChart(null);
            return;
        }

        const activities = Object.entries(data.activity_summary.activity_breakdown)
            .sort((a, b) => b[1] - a[1]);

        if (!activities.length) {
            activityFeed.innerHTML = `
                <div class="empty-state">
                    <div class="icon"><i class="fas fa-info-circle"></i></div>
                    <p class="mb-0 text-muted">No recent activity logged. Run searches or manage projects to see updates.</p>
                </div>
            `;
            renderEngagementChart(null);
            return;
        }

        dashboardData.activity = activities;
        activityFeed.innerHTML = activities.map(([type, count]) => {
            const icon = getActivityIcon(type);
            return `
                <div class="feed-item">
                    <span class="feed-icon"><i class="${icon}"></i></span>
                    <div class="feed-body">
                        <strong>${formatActivityType(type)}</strong>
                        <p class="mb-0 text-muted">Recorded ${count} time${count === 1 ? '' : 's'} this week.</p>
                    </div>
                </div>
            `;
        }).join('');
        notifyIconRefresh(activityFeed);
        renderEngagementChart(data.activity_summary.activity_breakdown, data.period_days);

    } catch (error) {
        console.error('Failed to load activity:', error);
        renderEngagementChart(null);
    }
}

function getActivityIcon(type) {
    const icons = {
        'search': 'fas fa-search',
        'login': 'fas fa-sign-in-alt',
        'export': 'fas fa-file-export',
        'project_created': 'fas fa-folder-plus',
        'collection_created': 'fas fa-bookmark'
    };
    return icons[type] || 'fas fa-circle';
}

function formatActivityType(type) {
    const names = {
        'search': 'Searches',
        'login': 'Logins',
        'export': 'Exports',
        'project_created': 'Projects Created',
        'collection_created': 'Collections Created'
    };
    return names[type] || type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function viewQuery(queryId) {
    window.location.href = `/search-history/${queryId}`;
}

function exportData() {
    showAlert('Export feature coming soon!', 'info');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.addEventListener('user:updated', (event) => {
    const user = event?.detail?.user || getCurrentUser();
    dashboardData.capabilities = user?.integration_capabilities || {};
    renderCapabilityBanner();
    renderNotifications();
    notifyIconRefresh(document);
});

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    const initialUser = getCurrentUser();
    dashboardData.capabilities = initialUser?.integration_capabilities || {};
    renderCapabilityBanner();
    renderNotifications();
    loadDashboard();
    
    // Refresh stats every 30 seconds
    setInterval(loadUserStats, 30000);
});
