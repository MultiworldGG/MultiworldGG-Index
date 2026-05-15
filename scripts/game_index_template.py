# These constants will be generated during build
GAMES_DATA = GAMES_DATA_PLACEHOLDER  # type: ignore  # noqa: F821

GAMES_NAMES = GAMES_NAMES_PLACEHOLDER  # type: ignore  # noqa: F821

SEARCH_INDEX = SEARCH_INDEX_PLACEHOLDER  # type: ignore  # noqa: F821

class _GameIndexClass(object):
    """
    Pre-generated search index for games. This index is built separately via a tool and contains the basic
    game information for each game within the specified rating category.
    
    Attributes:
        _game_names: Dictionary with game names as keys and module names as values
        _search_index: Dictionary with search terms as keys and sets of module names as values
        _games: Dictionary with module names as keys and all available game data as values
    """
    _instance: '_GameIndexClass' = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._initialized:
            return cls._instance
        else:
            cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, *args, **kwargs):
        if self._initialized:
            return
        self._initialized = True
        self._game_names = GAMES_NAMES
        self._search_index = SEARCH_INDEX
        self._games = GAMES_DATA
        self._module_to_name = {module: name for name, module in self._game_names.items()}

    @property
    def game_names(self) -> dict:
        return self._game_names
    @game_names.setter
    def game_names(self, item: tuple[str, str]) -> None:
        key, value = item
        self._game_names[key] = value

    @property
    def search_index(self) -> dict:
        return self._search_index
    @search_index.setter
    def search_index(self, item: tuple[str, str]) -> None:
        key, value = item
        if key in self._search_index:
            self._search_index[key].add(value)
        else:
            self._search_index[key] = {value}

    @property
    def games(self) -> dict:
        return self._games
    @games.setter
    def games(self, item: tuple[str, dict]) -> None:
        key, value = item
        self._games[key] = value

    def search(self, query: str) -> dict:
        """
        Search for games matching the query.
        
        Args:
            query: The search query string
            
        Returns:
            Dictionary of matching games
        """
        if not query:
            return {}
            
        query_terms = query.lower().split()
        matching_games = None
        
        # First try exact matches from the search index (AND logic - all terms must match)
        exact_match_sets = []
        for term in query_terms:
            try:
                exact_match_sets.append(self.search_index[term])
            except KeyError:
                pass
        
        if exact_match_sets:
            # Intersect all sets to find games matching all terms
            matching_games = exact_match_sets[0].copy()
            for match_set in exact_match_sets[1:]:
                matching_games &= match_set
        
        # If no exact matches or we want to include partial matches, search index keys
        if not matching_games or len(matching_games) == 0:
            partial_match_games = set()
            # Use set view of search_index keys for efficient iteration
            index_keys = self.search_index.keys()
            
            for term in query_terms:
                # Find all indexed terms that contain this query term as a substring
                for indexed_term in index_keys:
                    if term in indexed_term:
                        # Union with games from matching indexed terms
                        partial_match_games |= self.search_index[indexed_term]
            
            if matching_games is None:
                matching_games = partial_match_games
            else:
                # Combine exact and partial matches (OR logic between exact and partial)
                matching_games |= partial_match_games
        
        # Return only matching games using dict view for efficiency
        if not matching_games:
            return {}
        return {name: self.games[name] for name in matching_games}

    def get_game(self, game_module: str) -> dict:
        """
        Get full game data for a specific game.
        
        Args:
            game_module: The module name of the game to retrieve
            
        Returns:
            Dictionary containing all game data
        """
        return self.games.get(game_module, {})

    _SEARCHABLE_FIELDS = (
        "igdb_name", "platforms", "genres", "themes", "keywords", "player_perspectives",
    )

    def _index_value(self, game_module: str, value) -> None:
        if value is None:
            return
        cleaned = str(value).lower()
        if not cleaned:
            return
        self.search_index = cleaned, game_module
        for word in cleaned.split():
            self.search_index = word, game_module

    def add_game(self, game_module: str, game_data: dict):
        """Add a game to the game index.

        Mirrors build_variants.build_search_index so a runtime-added custom
        world is searchable on the same surface as build-time indexed games.
        Also adds the module to the "popular" set so it shows up when the
        launcher's search bar is empty (popular is the fallback query).

        TODO: replace "popular" here with a dedicated "always_search" term,
        and have the empty-search-bar fallback union "popular" + "always_search".
        """
        self.games = game_module, game_data
        self.game_names = game_data['game_name'], game_module
        self._module_to_name[game_module] = game_data['game_name']

        # Empty-search-bar fallback — see TODO above for the proper term.
        self.search_index = "popular", game_module

        # Display name (full lowercased + each whitespace-split word).
        self._index_value(game_module, game_data.get('game_name', ''))

        # IGDB-style fields, if the manifest carries them.
        for field in self._SEARCHABLE_FIELDS:
            value = game_data.get(field)
            if isinstance(value, list):
                for item in value:
                    if item and not any(c in str(item) for c in "():"):
                        self._index_value(game_module, item)
            elif isinstance(value, (str, int, float, bool)) and value:
                self._index_value(game_module, value)

    def get_module_for_game(self, game_name: str, worlds: bool = False):
        """Resolve a display game name to its module apworld.

        With worlds=True, returns the dotted package path (e.g. "worlds.alttp")
        suitable for sys.modules lookup; otherwise returns the bare apworld.
        Returns None if the game name is unknown.
        """
        module = self._game_names.get(game_name)
        if module and worlds:
            return f"worlds.{module}"
        return module

    def get_game_name_for_module(self, module_name: str):
        """Resolve a module apworld (with or without 'worlds.' prefix) to its display name.
        Returns None if the apworld is unknown."""
        if module_name.startswith("worlds."):
            module_name = module_name[len("worlds."):]
        return self._module_to_name.get(module_name)

    def get_all_games(self) -> dict:
        """Return the full GAMES_DATA dict (apworld -> game data)."""
        return self._games

    def get_all_game_names(self) -> list:
        """Return all known display game names as a list."""
        return list(self._game_names.keys())

GameIndex = _GameIndexClass()