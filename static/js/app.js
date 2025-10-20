let currentTab = 'pending';

function showTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Find and activate the clicked button
    const clickedButton = Array.from(document.querySelectorAll('.tab')).find(
        tab => tab.textContent.includes(tabName.charAt(0).toUpperCase() + tabName.slice(1)) ||
               tab.onclick.toString().includes(`'${tabName}'`)
    );
    if (clickedButton) {
        clickedButton.classList.add('active');
    }
    
    // Show/hide content
    ['pending', 'failed', 'completed', 'removed', 'logs', 'config'].forEach(name => {
        const tab = document.getElementById(`${name}-tab`);
        if (tab) {
            tab.classList.toggle('hidden', name !== tabName);
        }
    });
    
    // Load data for the active tab
    if (tabName === 'logs') {
        loadLogs();
    } else if (tabName === 'config') {
        loadConfig();
    } else {
        loadQueue(tabName);
    }
}

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        document.getElementById('stat-pending').textContent = stats.pending || 0;
        document.getElementById('stat-failed').textContent = stats.failed || 0;
        document.getElementById('stat-completed').textContent = stats.completed || 0;
        document.getElementById('stat-removed').textContent = stats.removed || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadQueue(queueName) {
    try {
        const response = await fetch(`/api/queue/${queueName}`);
        const movies = await response.json();
        
        const container = document.getElementById(`${queueName}-queue`);
        
        if (!movies || movies.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div>No movies in ${queueName} queue</div>
                </div>
            `;
            return;
        }
        
        container.innerHTML = movies.map(movie => createMovieItem(movie, queueName)).join('');
    } catch (error) {
        console.error(`Error loading ${queueName} queue:`, error);
    }
}

function createMovieItem(movie, queueName) {
    const title = movie.title || 'Unknown';
    const year = movie.year || '';
    const director = movie.director || '';
    const retryCount = movie.retry_count || 0;
    const lastError = movie.last_error || '';
    const skipped = movie.skipped || false;
    const failedReason = movie.failed_reason || '';
    
    let actions = '';
    
    if (queueName === 'failed') {
        actions = `
            <button class="btn btn-warning" onclick="retryMovie('${movie.id}')" title="Reset retry count">Reset Retry</button>
            <button class="btn btn-primary" onclick="moveMovie('${movie.id}', 'pending')" title="Move to pending queue">To Pending</button>
        `;
        // Add force download button only for space limit failures
        if (failedReason === 'space_limit') {
            actions += `
                <button class="btn btn-success" onclick="forceDownload('${movie.id}')" title="Download even if space limit exceeded">Force Download</button>
            `;
        }
    } else if (queueName === 'pending') {
        actions = `
            <button class="btn btn-success" onclick="forceDownload('${movie.id}')" title="Download even if space limit exceeded">Force Download</button>
        `;
    } else if (queueName === 'completed') {
        // For completed: move to removed instead of skip
        actions = `
            <button class="btn btn-warning" onclick="moveMovie('${movie.id}', 'removed')" title="Move to removed queue for deletion">Mark for Removal</button>
        `;
    } else if (queueName === 'removed') {
        // For removed: option to restore to completed or force delete
        actions = `
            <button class="btn btn-success" onclick="moveMovie('${movie.id}', 'completed')" title="Move back to completed queue">To Completed</button>
            <button class="btn btn-danger" onclick="forceDeleteMovie('${movie.id}')" title="Delete immediately without waiting for grace period">Force Delete Now</button>
        `;
    }
    
    // Add skip/unskip button for all queues except completed and removed
    if (queueName !== 'completed' && queueName !== 'removed') {
        if (skipped) {
            actions += `<button class="btn btn-secondary" onclick="unskipMovie('${movie.id}')" title="Remove skip flag and allow processing">Unskip</button>`;
        } else {
            actions += `<button class="btn btn-secondary" onclick="skipMovie('${movie.id}')" title="Keep in queue but skip all processing (downloads, retries, cleanup)">Skip</button>`;
        }
    }
    
    let badges = '';
    if (retryCount > 0) {
        badges += `<span class="badge badge-retry">Retry #${retryCount}</span>`;
    }
    if (lastError) {
        badges += `<span class="badge badge-error">Error</span>`;
    }
    if (skipped) {
        badges += `<span class="badge badge-skipped">⏸ Skipped</span>`;
    }
    if (failedReason === 'space_limit') {
        badges += `<span class="badge badge-warning">💾 Space Limit</span>`;
    }
    
    return `
        <div class="movie-item ${skipped ? 'skipped' : ''}" 
             draggable="true" 
             data-movie-id="${movie.id}"
             ondragstart="handleDragStart(event)"
             ondragend="handleDragEnd(event)"
             ondragover="handleDragOver(event)"
             ondrop="handleDrop(event)"
             ondragleave="handleDragLeave(event)">
            <div class="movie-content">
                <div class="movie-info">
                    <div class="movie-title">${title} ${badges}</div>
                    <div class="movie-meta">
                        ${director ? `Director: ${director}` : ''}
                        ${lastError ? `<br>Error: ${lastError}` : ''}
                    </div>
                </div>
            </div>
            <div class="movie-actions">
                ${actions}
            </div>
        </div>
    `;
}

async function moveMovie(movieId, targetQueue) {
    if (!confirm(`Move this movie to ${targetQueue} queue?`)) {
        return;
    }
    
    try {
        console.log(`Moving movie ${movieId} to ${targetQueue}`);
        const response = await fetch(`/api/movie/${movieId}/move`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ target_queue: targetQueue })
        });
        
        const result = await response.json();
        console.log('Move result:', result);
        
        if (result.success) {
            console.log('Refreshing data after successful move');
            await refreshData();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error moving movie:', error);
        alert('Failed to move movie');
    }
}

async function deleteMovie(movieId) {
    if (!confirm('Are you sure you want to delete this movie from all queues?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/movie/${movieId}/delete`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            refreshData();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting movie:', error);
        alert('Failed to delete movie');
    }
}

async function retryMovie(movieId) {
    try {
        const response = await fetch(`/api/movie/${movieId}/retry`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            refreshData();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error resetting movie:', error);
        alert('Failed to reset movie');
    }
}

async function skipMovie(movieId) {
    try {
        const response = await fetch(`/api/movie/${movieId}/skip`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            refreshData();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error skipping movie:', error);
        alert('Failed to skip movie');
    }
}

async function unskipMovie(movieId) {
    try {
        const response = await fetch(`/api/movie/${movieId}/unskip`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            refreshData();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error unskipping movie:', error);
        alert('Failed to unskip movie');
    }
}

async function forceDownload(movieId) {
    if (!confirm('Force download this movie (ignoring space limit)?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/movie/${movieId}/force-download`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            refreshData();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error forcing download:', error);
        alert('Failed to force download');
    }
}

async function forceDeleteMovie(movieId) {
    if (!confirm('⚠️ Force delete this movie NOW? This will immediately delete files and torrents without waiting for the grace period. This action cannot be undone!')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/movie/${movieId}/force-delete`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            refreshData();
            alert(result.message || 'Movie deleted successfully');
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error force deleting movie:', error);
        alert('Failed to force delete movie');
    }
}

// Drag and drop handlers
let draggedItem = null;

function handleDragStart(event) {
    draggedItem = event.target;
    event.target.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(event) {
    event.target.classList.remove('dragging');
    // Remove drag-over class from all items
    document.querySelectorAll('.movie-item').forEach(item => {
        item.classList.remove('drag-over');
    });
}

function handleDragOver(event) {
    if (event.preventDefault) {
        event.preventDefault();
    }
    event.dataTransfer.dropEffect = 'move';
    
    const target = event.target.closest('.movie-item');
    if (target && target !== draggedItem) {
        target.classList.add('drag-over');
    }
    
    return false;
}

function handleDragLeave(event) {
    const target = event.target.closest('.movie-item');
    if (target) {
        target.classList.remove('drag-over');
    }
}

async function handleDrop(event) {
    if (event.stopPropagation) {
        event.stopPropagation();
    }
    
    const target = event.target.closest('.movie-item');
    if (!target || target === draggedItem) {
        return false;
    }
    
    target.classList.remove('drag-over');
    
    // Get movie IDs
    const draggedId = draggedItem.getAttribute('data-movie-id');
    const targetId = target.getAttribute('data-movie-id');
    
    // Reorder in backend
    try {
        const response = await fetch('/api/queue/reorder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                queue: currentTab,
                dragged_id: draggedId,
                target_id: targetId
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Refresh to show new order
            loadQueue(currentTab);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error reordering:', error);
        alert('Failed to reorder');
    }
    
    return false;
}

async function loadLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();
        
        const container = document.getElementById('logs');
        
        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div class="empty-state"><div>No logs available</div></div>';
            return;
        }
        
        container.innerHTML = data.logs.map(log => 
            `<div class="log-entry">${escapeHtml(log)}</div>`
        ).join('');
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function refreshData() {
    await loadStats();
    
    if (currentTab === 'logs') {
        await loadLogs();
    } else if (currentTab === 'config') {
        await loadConfig();
    } else {
        await loadQueue(currentTab);
    }
}

async function updateWatchlist() {
    const btn = document.querySelector('.update-watchlist-btn');
    btn.classList.add('updating');
    
    try {
        const response = await fetch('/api/update-watchlist', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Refresh the data to show any new movies
            await refreshData();
            
            // Show a brief success message
            const text = btn.querySelector('.text');
            const originalText = text.textContent;
            text.textContent = '✓ Updated!';
            
            setTimeout(() => {
                text.textContent = originalText;
            }, 2000);
        } else {
            alert('Error: ' + (result.error || 'Failed to update watchlist'));
        }
    } catch (error) {
        console.error('Error updating watchlist:', error);
        alert('Failed to update watchlist');
    } finally {
        btn.classList.remove('updating');
    }
}

// Config management
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        const container = document.getElementById('config-fields');
        container.innerHTML = '';
        
        const config = data.config;
        const meta = data.meta;
        
        for (const [key, value] of Object.entries(config)) {
            if (!meta[key]) continue; // Skip fields without metadata
            
            const fieldMeta = meta[key];
            const formGroup = document.createElement('div');
            formGroup.className = 'form-group';
            
            if (fieldMeta.type === 'boolean') {
                formGroup.innerHTML = `
                    <div class="checkbox-wrapper">
                        <input type="checkbox" 
                               id="config-${key}" 
                               name="${key}" 
                               ${value ? 'checked' : ''}>
                        <label for="config-${key}">${fieldMeta.label}</label>
                    </div>
                    <div class="help-text">${fieldMeta.description}</div>
                `;
            } else {
                formGroup.innerHTML = `
                    <label for="config-${key}">${fieldMeta.label}</label>
                    <input type="${fieldMeta.type}" 
                           id="config-${key}" 
                           name="${key}" 
                           value="${value}"
                           ${fieldMeta.min !== undefined ? `min="${fieldMeta.min}"` : ''}
                           ${fieldMeta.step !== undefined ? `step="${fieldMeta.step}"` : ''}>
                    <div class="help-text">${fieldMeta.description}</div>
                `;
            }
            
            container.appendChild(formGroup);
        }
    } catch (error) {
        console.error('Error loading config:', error);
        showConfigMessage('Error loading configuration', 'error');
    }
}

async function saveConfig(event) {
    event.preventDefault();
    
    const form = document.getElementById('config-form');
    const formData = new FormData(form);
    const config = {};
    
    for (const [key, value] of formData.entries()) {
        const input = form.elements[key];
        if (input.type === 'checkbox') {
            config[key] = input.checked;
        } else if (input.type === 'number') {
            config[key] = parseFloat(value);
        } else {
            config[key] = value;
        }
    }
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showConfigMessage('Configuration saved successfully! Changes will take effect immediately.', 'success');
        } else {
            showConfigMessage(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showConfigMessage('Error saving configuration', 'error');
    }
}

function showConfigMessage(message, type) {
    const msgEl = document.getElementById('config-message');
    msgEl.textContent = message;
    msgEl.className = `message ${type} show`;
    
    setTimeout(() => {
        msgEl.classList.remove('show');
    }, 5000);
}

// Auto-refresh every 10 seconds
setInterval(refreshData, 10000);

// Initial load
refreshData();
