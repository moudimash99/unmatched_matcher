# GitHub Copilot Instructions for Unmatched Matcher

## Project Overview

This is a Flask-based web application that provides matchup recommendations for the Unmatched board game. The application helps players find optimal fighter matchups based on win rates, playstyles, and game balance considerations.

## Technology Stack

- **Backend**: Python 3.11 with Flask 3.0.3
- **Frontend**: Vanilla JavaScript with HTML/CSS
- **Deployment**: Docker with Gunicorn, Nginx, and Cloudflare Tunnel
- **Data**: JSON files for fighter data and win rate matrices

## Project Structure

```
.
├── app.py                 # Main Flask application with routes
├── matchup_engine.py      # Core matchmaking algorithm and logic
├── win_calc.py           # Win rate calculation from Excel data
├── requirements.txt       # Python dependencies
├── dockerfile            # Docker configuration
├── docker-compose.yml    # Multi-container setup
├── input/                # JSON data files (fighters, win matrices)
├── static/               # CSS, JavaScript, images
├── templates/            # HTML templates (Jinja2)
└── nginx/                # Nginx configuration
```

## Core Components

### 1. Flask Application (`app.py`)
- Loads fighter data and win matrices from JSON files
- Provides REST API endpoints for matchup recommendations
- Handles filtering by sets, playstyles, and ranges
- Serves the single-page application

### 2. Matchup Engine (`matchup_engine.py`)
- Implements weighted random sampling for fighter selection
- Calculates fitness scores based on playstyle preferences
- Balances fairness using win rate matrices
- Uses configurable weights (60% fit, 40% fairness by default)

### 3. Win Calculator (`win_calc.py`)
- Processes Excel spreadsheet data
- Normalizes fighter names and win percentages
- Generates win rate matrices in JSON format

## Coding Standards

### Python Style
- Follow PEP 8 conventions
- Use descriptive variable names (e.g., `FIGHTERS_DATA`, `ALL_PLAYSTYLES`)
- Add docstrings for functions explaining purpose and parameters
- Handle file I/O errors gracefully with try-except blocks
- Use list comprehensions for filtering and transformations

### Code Organization
- Group related constants together with comment separators
- Keep helper functions clearly labeled and organized
- Use type hints where it improves code clarity
- Maintain consistent error handling patterns

### Example Patterns
```python
# Loading JSON with error handling
def load_json_data(filename, default):
    """Load JSON data from a file with error handling."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing {filename}: {e}")
        return default

# Filtering fighters
def get_available_fighters(owned_set_names):
    """Returns a list of fighters from the owned sets."""
    if not owned_set_names:
        return []
    return [f for f in FIGHTERS_DATA if f["set"] in owned_set_names]
```

## Data Model

### Fighter Object Structure
```json
{
  "id": "fighter_id",
  "name": "Fighter Name",
  "set": "Set Name",
  "playstyles": ["playstyle1", "playstyle2"],
  "range": "Melee|Reach|Hybrid|Ranged Assist|Ranged",
  "image": "path/to/image.jpg"
}
```

### Win Matrix Structure
```json
{
  "fighter_id_1": {
    "fighter_id_2": 55.5,  // Win percentage as float
    ...
  }
}
```

## Development Workflow

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py

# Or use Flask CLI
export FLASK_APP=app.py
export FLASK_DEBUG=1
flask run
```

### Docker Deployment
```bash
# Build and run with docker-compose
docker-compose up --build

# Access locally (if ports exposed)
curl http://localhost:8080
```

### Testing Changes
- Test the Flask routes with curl or browser
- Verify matchup recommendations make sense
- Check that filters work correctly (sets, playstyles, ranges)
- Ensure JSON data is loaded properly

## Key Algorithms

### Matchup Recommendation Flow
1. Filter available fighters based on owned sets
2. Calculate fitness scores for each fighter based on preferences
3. Apply fairness adjustments using win rate matrices
4. Use weighted random sampling to select diverse recommendations
5. Return pools for player 1 and opponent

### Weighted Random Sampling
- Uses `random.choices()` with score-based weights
- Ensures diversity by tracking selected IDs
- Falls back to uniform selection if all weights are zero

## API Endpoints

- `GET /` - Serve main application page
- `POST /recommend` - Get matchup recommendations
  - Parameters: owned sets, preferences (playstyles, ranges), constraints
  - Returns: pools of recommended fighters with metadata

## Best Practices

1. **Data Integrity**: Always validate JSON data structure before processing
2. **Error Handling**: Gracefully handle missing files, malformed data
3. **Performance**: Cache loaded data, avoid reloading on each request
4. **Maintainability**: Keep algorithms modular and well-documented
5. **Security**: Sanitize user inputs, avoid exposing sensitive data

## Common Tasks

### Adding a New Fighter
1. Update `input/fighters.json` with new fighter data
2. Add win rates to `input/win_matrix.json`
3. Add fighter image to `static/pics/`
4. Restart application to load new data

### Modifying Matchup Algorithm
1. Edit `matchup_engine.py`
2. Adjust weights (`WEIGHT_FIT`, `WEIGHT_FAIRNESS`)
3. Test with various fighter combinations
4. Validate balance and diversity of recommendations

### Updating UI
1. Modify `templates/index.html` for structure
2. Update `static/css/` for styling
3. Edit `static/js/` for behavior
4. Test responsive design across devices

## Deployment Notes

- Production uses Gunicorn with 3 workers
- Nginx serves as reverse proxy
- Cloudflare Tunnel provides external access
- Requires `TUNNEL_TOKEN` environment variable
- Container restarts automatically on failure

## Dependencies

Keep these up to date for security:
- Flask: Web framework
- Gunicorn: WSGI HTTP server
- Jinja2: Template engine
- Werkzeug: WSGI utilities
- MarkupSafe: HTML escaping

## Troubleshooting

- **Import errors**: Check `requirements.txt` and reinstall dependencies
- **Missing data**: Verify JSON files exist in `input/` directory
- **Port conflicts**: Adjust exposed ports in `docker-compose.yml`
- **Cloudflare issues**: Verify `TUNNEL_TOKEN` is set correctly
