# Web Interface Structure

## Overview

The web interface has been reorganized to separate concerns and enable auto-reloading without restarting the Python script.

## File Organization

### Directory Structure

```
movie_sync/
├── templates/
│   └── index.html          # Main HTML template (minimal, references external files)
├── static/
│   ├── css/
│   │   └── style.css       # All CSS styles
│   └── js/
│       └── app.js          # All JavaScript code
└── web_interface.py        # Flask backend
```

### Files

#### `templates/index.html`
- Clean HTML structure with minimal inline code
- References external CSS and JavaScript files
- Uses Flask's `url_for()` for proper static file URLs

#### `static/css/style.css`
- All CSS styles including:
  - CSS custom properties (design tokens)
  - Component styles
  - Responsive breakpoints
  - Animations
  - Touch device support

#### `static/js/app.js`
- All JavaScript functionality including:
  - Tab management
  - Queue loading and display
  - Movie actions (move, skip, retry, etc.)
  - Drag and drop
  - Configuration management
  - Auto-refresh (every 10 seconds)

#### `web_interface.py`
- Flask backend with REST API
- Configured for auto-reload:
  - `TEMPLATES_AUTO_RELOAD = True` - Templates reload on change
  - `SEND_FILE_MAX_AGE_DEFAULT = 0` - Static files don't cache

## Auto-Reload Behavior

### What Auto-Reloads Without Restart

1. **HTML Changes** (`templates/index.html`):
   - Changes take effect immediately on page refresh
   - No Python restart needed

2. **CSS Changes** (`static/css/style.css`):
   - Changes visible on hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
   - Browser might cache - disable cache in dev tools for best experience
   - No Python restart needed

3. **JavaScript Changes** (`static/js/app.js`):
   - Changes visible on hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
   - Browser might cache - disable cache in dev tools for best experience
   - No Python restart needed

### What Requires Python Restart

1. **Python Backend Changes** (`web_interface.py`):
   - API endpoint changes
   - Route modifications
   - Configuration changes
   - **Requires full application restart**

2. **Configuration Changes** (`config.py`):
   - Application settings
   - **Requires full application restart**

## Development Tips

### Browser Cache Management

For the best development experience:

1. **Chrome/Edge DevTools**:
   - Open DevTools (F12)
   - Go to Network tab
   - Check "Disable cache" checkbox
   - Keep DevTools open while developing

2. **Firefox DevTools**:
   - Open DevTools (F12)
   - Go to Network tab
   - Check "Disable cache" checkbox
   - Keep DevTools open while developing

3. **Hard Refresh**:
   - Chrome/Edge/Firefox (Windows/Linux): `Ctrl + Shift + R`
   - Chrome/Edge/Firefox (Mac): `Cmd + Shift + R`
   - Safari (Mac): `Cmd + Option + R`

### Live Editing Workflow

1. **Editing CSS**:
   ```bash
   # Edit static/css/style.css
   # Hard refresh browser (Ctrl+Shift+R)
   # Changes appear immediately
   ```

2. **Editing JavaScript**:
   ```bash
   # Edit static/js/app.js
   # Hard refresh browser (Ctrl+Shift+R)
   # Changes appear immediately
   ```

3. **Editing HTML**:
   ```bash
   # Edit templates/index.html
   # Regular refresh (F5)
   # Changes appear immediately
   ```

4. **Editing Python**:
   ```bash
   # Edit web_interface.py or other Python files
   # Stop application (Ctrl+C)
   # Restart: python main.py
   ```

## Flask Configuration

The Flask app is configured in `web_interface.py`:

```python
self.app.config['TEMPLATES_AUTO_RELOAD'] = True
self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
```

- `TEMPLATES_AUTO_RELOAD`: Automatically reload Jinja2 templates when changed
- `SEND_FILE_MAX_AGE_DEFAULT = 0`: Disable browser caching for static files

## Static File URLs

Flask's `url_for()` function is used to generate URLs:

```html
<!-- CSS -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">

<!-- JavaScript -->
<script src="{{ url_for('static', filename='js/app.js') }}"></script>
```

This ensures proper URL generation even if the app is deployed under a URL prefix.

## Benefits

1. **Separation of Concerns**: HTML, CSS, and JavaScript are in separate files
2. **Easier Maintenance**: Each file has a single responsibility
3. **Hot Reload**: Frontend changes don't require Python restart
4. **Better Developer Experience**: Edit and see changes immediately
5. **Browser Dev Tools**: Can use browser dev tools to debug CSS and JS
6. **Code Organization**: Cleaner, more maintainable codebase
7. **Collaboration**: Team members can edit different files simultaneously

## Testing

After making changes:

1. **Test CSS changes**:
   - Edit `static/css/style.css`
   - Hard refresh browser
   - Verify styles are updated

2. **Test JavaScript changes**:
   - Edit `static/js/app.js`
   - Hard refresh browser
   - Open browser console to check for errors
   - Test functionality

3. **Test HTML changes**:
   - Edit `templates/index.html`
   - Regular refresh browser
   - Verify structure is correct

## Troubleshooting

### Changes not appearing

1. **Hard refresh**: Press `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
2. **Clear browser cache**: Settings > Privacy > Clear browsing data
3. **Disable cache in DevTools**: Keep DevTools open with "Disable cache" checked
4. **Check file was saved**: Ensure you saved the file after editing
5. **Check Flask is running**: Verify the Python script is still running
6. **Check for errors**: Look in browser console (F12) for JavaScript errors

### Static files not loading

1. **Check file paths**: Ensure files are in correct directories
2. **Check Flask static folder**: Should be `static/` in project root
3. **Check Flask app initialization**: `Flask(__name__, static_folder='static')`
4. **Check URL generation**: Use `url_for('static', filename='...')` not hardcoded paths

### Python changes not taking effect

- Python backend changes **always require restart**
- Stop with `Ctrl+C` and restart `python main.py`
