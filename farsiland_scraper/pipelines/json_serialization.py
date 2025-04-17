This pipeline runs before SaveToDatabasePipeline and ensures:
1. Lists are proper Python lists, not strings
2. Custom items (like VideoFileItem) are converted to dictionaries
3. Empty values are handled properly
4. Numeric fields have appropriate types
5. JSON fields are properly structured
6. Required fields are present and valid
"""

# Define required fields for each item type
REQUIRED_FIELDS = {
    'shows': ['url', 'title_en'],
    'episodes': ['url', 'show_url', 'season_number', 'episode_number'],
    'movies': ['url', 'title_en']
}

# Define fields that should be lists
LIST_FIELDS = ['genres', 'directors', 'cast', 'seasons', 'video_files']

# Define fields that should be numeric, with their types
NUMERIC_FIELDS = {
    'rating': float,
    'rating_count': int,
    'social_shares': int,
    'comments_count': int,
    'season_count': int,
    'episode_count': int,
    'season_number': int,
    'episode_number': int,
    'year': int,
    'is_new': int  # Boolean stored as integer
}

# Required fields for video_files items
VIDEO_FILE_REQUIRED_FIELDS = ['quality', 'url']

def process_item(self, item: Dict[str, Any], spider) -> Dict[str, Any]:
    """
    Process an item to ensure proper structure.
    
    Args:
        item: The scraped item to process
        spider: The spider that scraped the item
        
    Returns:
        The processed item with proper data structures
        
    Raises:
        DropItem: If a required field is missing or invalid
    """
    try:
        item_dict = dict(item)
        item_type = self._determine_item_type(item_dict)
        
        # Validate required fields
        if item_type:
            self._validate_required_fields(item_dict, item_type)
        
        # Process list fields, including video_files
        self._process_list_fields(item_dict)
        
        # Process numeric fields
        self._process_numeric_fields(item_dict)
        
        # Set defaults for boolean fields
        self._set_boolean_defaults(item_dict)
        
        # Update the item with our processed values
        for key, value in item_dict.items():
            item[key] = value
            
        return item
    except DropItem:
        # Re-raise DropItem exceptions
        raise
    except Exception as e:
        LOGGER.error(f"Unexpected error processing item: {e}", exc_info=True)
        # Return the original item if we can't process it
        return item

def _determine_item_type(self, item: Dict[str, Any]) -> Optional[str]:
    """
    Determine the type of item based on its fields.
    
    Args:
        item: The item dictionary
        
    Returns:
        The item type string or None if can't be determined
    """
    if 'show_url' in item and 'episode_number' in item:
        return 'episodes'
    elif 'seasons' in item or 'season_count' in item:
        return 'shows'
    elif 'release_date' in item or 'year' in item:
        return 'movies'
    
    # Try to determine by URL pattern
    url = item.get('url', '')
    if isinstance(url, str):
        if '/episodes/' in url:
            return 'episodes'
        elif '/tvshows/' in url or '/series' in url:
            return 'shows'
        elif '/movies/' in url:
            return 'movies'
    
    # Default to None if we can't determine
    return None

def _validate_required_fields(self, item: Dict[str, Any], item_type: str) -> None:
    """
    Validate that all required fields are present and valid.
    
    Args:
        item: The item dictionary
        item_type: The type of item
        
    Raises:
        DropItem: If a required field is missing or invalid
    """
    required_fields = self.REQUIRED_FIELDS.get(item_type, [])
    missing_fields = []
    
    for field in required_fields:
        if field not in item or item[field] is None or item[field] == '':
            missing_fields.append(field)
    
    if missing_fields:
        url = item.get('url', 'Unknown URL')
        LOGGER.warning(f"Item missing required fields {missing_fields}: {url}")
        if 'url' in missing_fields:
            # Drop items missing the URL field as it's essential
            raise DropItem(f"Missing required field 'url' for item")
        else:
            # For other fields, log a warning but continue processing
            LOGGER.warning(f"Item from {url} is missing required fields: {missing_fields}")

def _process_list_fields(self, item: Dict[str, Any]) -> None:
    """
    Process fields that should be lists, including video_files.
    
    Args:
        item: The item dictionary
    """
    # Process video_files specially due to its nested structure
    if 'video_files' in item:
        try:
            self._process_video_files(item)
        except Exception as e:
            LOGGER.error(f"Error processing video_files: {e}", exc_info=True)
            item['video_files'] = []
    
    # Process other list fields
    for field in self.LIST_FIELDS:
        if field in item and field != 'video_files':  # Skip video_files as we already processed it
            try:
                self._process_list_field(item, field)
            except Exception as e:
                LOGGER.error(f"Error processing list field {field}: {e}", exc_info=True)
                item[field] = []

def _process_video_files(self, item: Dict[str, Any]) -> None:
    """
    Process video_files field to ensure proper structure.
    
    Args:
        item: The item dictionary
    """
    video_files = item.get('video_files')
    
    # Handle different input types
    if isinstance(video_files, str):
        try:
            LOGGER.warning(f"video_files is a string - parsing: {video_files[:50]}...")
            video_files = json.loads(video_files)
        except json.JSONDecodeError as e:
            LOGGER.error(f"Could not parse video_files JSON: {e}")
            video_files = []
        except Exception as e:
            LOGGER.error(f"Unexpected error parsing video_files: {e}")
            video_files = []
    elif video_files is None:
        video_files = []
    
    # Ensure video_files is a list
    if not isinstance(video_files, list):
        LOGGER.warning(f"video_files is not a list: {type(video_files)}")
        video_files = [video_files] if video_files else []
    
    # Process each video file
    processed_files = []
    for vf in video_files:
        try:
            if hasattr(vf, 'keys'):  # If it's a dict-like object
                vf_dict = dict(vf)
                # Ensure required fields exist
                for field in self.VIDEO_FILE_REQUIRED_FIELDS:
                    if field not in vf_dict or not vf_dict[field]:
                        vf_dict[field] = 'unknown' if field == 'quality' else ''
                
                # Set defaults for optional fields
                vf_dict.setdefault('mirror_url', None)
                vf_dict.setdefault('size', '')
                
                processed_files.append(vf_dict)
            else:
                LOGGER.warning(f"Invalid video_files item: {vf}")
        except Exception as e:
            LOGGER.error(f"Error processing video file: {e}")
            # Skip invalid items
    
    item['video_files'] = processed_files

def _process_list_field(self, item: Dict[str, Any], field: str) -> None:
    """
    Process a field that should be a list.
    
    Args:
        item: The item dictionary
        field: The field name to process
    """
    value = item.get(field)
    
    # If it's a string, try to parse JSON
    if isinstance(value, str):
        try:
            LOGGER.warning(f"{field} is a string - parsing: {value[:50]}...")
            value = json.loads(value)
        except json.JSONDecodeError as e:
            LOGGER.error(f"Could not parse {field} JSON: {e}")
            value = []
        except Exception as e:
            LOGGER.error(f"Unexpected error parsing {field}: {e}")
            value = []
    
    # If it's None or not a list, convert to empty list
    if value is None:
        value = []
    elif not isinstance(value, list):
        LOGGER.warning(f"{field} is not a list: {type(value)}")
        value = [value] if value else []
    
    item[field] = value

def _process_numeric_fields(self, item: Dict[str, Any]) -> None:
    """
    Process fields that should be numeric.
    
    Args:
        item: The item dictionary
    """
    for field, field_type in self.NUMERIC_FIELDS.items():
        if field in item:
            try:
                value = item[field]
                if value is not None:
                    # For strings that might contain commas, spaces, etc.
                    if isinstance(value, str):
                        # Remove non-numeric characters except decimal point
                        clean_value = value.replace(',', '')
                        if field_type == float:
                            item[field] = float(clean_value)
                        else:
                            # For int, remove decimal part if present
                            item[field] = int(float(clean_value))
                    else:
                        item[field] = field_type(value)
            except (ValueError, TypeError) as e:
                LOGGER.warning(f"Could not convert {field} to {field_type.__name__}: {item.get(field)} - {e}")
                if field_type == int:
                    item[field] = 0
                elif field_type == float:
                    item[field] = 0.0
            except Exception as e:
                LOGGER.error(f"Unexpected error processing {field}: {e}")
                if field_type == int:
                    item[field] = 0
                elif field_type == float:
                    item[field] = 0.0

def _set_boolean_defaults(self, item: Dict[str, Any]) -> None:
    """
    Set defaults for boolean fields (stored as integers).
    
    Args:
        item: The item dictionary
    """
    boolean_fields = ['is_new']
    for field in boolean_fields:
        if field in item and item[field] is None:
            item[field] = 1  # Default to True (1)