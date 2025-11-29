# -*- coding: utf-8 -*-
"""
Created on Thu Nov  6 15:17:04 2025

@author: I84584
"""

import os
import osmnx as ox
import geopandas as gpd
from shapely.geometry import box
import pandas as pd
import matplotlib.pyplot as plt
import contextily as ctx
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# PROXY CONFIGURATION
# ============================================================================
#proxies = {
#    'http': 'http://I84584:discipleinEDF2024!@vip-users.proxy.edf.fr:3131',
#    'https': 'http://I84584:discipleinEDF2024!@vip-users.proxy.edf.fr:3131'
#}

#os.environ['HTTP_PROXY'] = proxies['http']
#os.environ['HTTPS_PROXY'] = proxies['https']
#os.environ['http_proxy'] = proxies['http']
#os.environ['https_proxy'] = proxies['https']

#ox.settings.http_proxy = proxies['http']
#ox.settings.https_proxy = proxies['https']

#import requests
#session = requests.Session()
#session.proxies.update(proxies)

#try:
#    import contextily.tile as ctx_tile
#    ctx_tile.requests = session
#except:
#    pass

#print("✓ Proxy configured successfully")
# ============================================================================


def calculate_walkability_from_shapefile(shapefile_path, place_name, grid_size=500):
    """
    Calculate walkability score using a shapefile boundary
    
    Parameters:
    -----------
    shapefile_path : str
        Path to the shapefile (.shp)
    place_name : str
        Name for display purposes
    grid_size : int
        Size of grid cells in meters (default: 500)
    
    Returns:
    --------
    grid : GeoDataFrame
        Grid with walkability scores
    pois : GeoDataFrame
        Points of interest
    """
    print(f"Processing {place_name} from shapefile...")
    
    try:
        # Read shapefile
        study_area = gpd.read_file(shapefile_path)
        
        # Ensure it's in Web Mercator for distance calculations
        if study_area.crs != 'EPSG:3857':
            study_area = study_area.to_crs(epsg=3857)
        
        # If multiple polygons, union them
        if len(study_area) > 1:
            study_area = study_area.dissolve()
        
        # Generate grid cells
        minx, miny, maxx, maxy = study_area.total_bounds
        
        grid_cells = []
        x = minx
        while x < maxx:
            y = miny
            while y < maxy:
                grid_cells.append(box(x, y, x + grid_size, y + grid_size))
                y += grid_size
            x += grid_size
        
        # Convert to GeoDataFrame and clip to study area
        grid = gpd.GeoDataFrame({'geometry': grid_cells}, crs=study_area.crs)
        grid = gpd.overlay(grid, study_area, how='intersection')
        
        # Download POIs - convert to WGS84 for OSM query
        polygon = study_area.to_crs(epsg=4326).geometry.union_all()
        
        # Define public transport amenities
        transport_tags = {
            "public_transport": ["station", "stop_position", "stop_area"],
            "railway": ["station", "halt", "tram_stop", "subway_entrance"],
            "amenity": ["bus_station", "ferry_terminal"]
        }
        
        pois = ox.features_from_polygon(polygon, transport_tags)
        
        # Filter relevant public transport features
        valid_pois = []
        
        # Check for public_transport tag
        if 'public_transport' in pois.columns:
            public_transport_pois = pois[pois['public_transport'].isin(['station', 'stop_position', 'stop_area'])]
            valid_pois.append(public_transport_pois)
        
        # Check for railway tag
        if 'railway' in pois.columns:
            railway_pois = pois[pois['railway'].isin(['station', 'halt', 'tram_stop', 'subway_entrance'])]
            valid_pois.append(railway_pois)
        
        # Check for amenity tag
        if 'amenity' in pois.columns:
            amenity_pois = pois[pois['amenity'].isin(['bus_station', 'ferry_terminal'])]
            valid_pois.append(amenity_pois)
        
        # Combine all valid POIs and remove duplicates
        if valid_pois:
            pois = pd.concat(valid_pois).drop_duplicates(subset=['geometry'])
        else:
            # Create empty GeoDataFrame with same CRS if no POIs found
            pois = gpd.GeoDataFrame(geometry=[], crs=pois.crs)
        
        # Reproject POIs to match grid
        pois = pois.to_crs(epsg=3857)
        
        # Calculate walkability scores
        grid['centroid'] = grid.geometry.centroid
        grid['raw_score'] = 0
        
        for i, centroid in grid['centroid'].items():
            if len(pois) > 0:
                dists = pois.geometry.distance(centroid)
                score = 0
                
                for d in dists:
                    if d <= 400:  # 5-minute walk
                        score += 3
                    elif d <= 800:  # 10-minute walk
                        score += 2
                    elif d <= 1200:  # 15-minute walk
                        score += 1
                
                grid.at[i, 'raw_score'] = score
        
        # Normalize scores to 0-100
        if len(pois) > 0 and grid['raw_score'].max() > grid['raw_score'].min():
            grid["WAS"] = 100 * (grid['raw_score'] - grid['raw_score'].min()) / \
                          (grid['raw_score'].max() - grid['raw_score'].min())
        else:
            grid["WAS"] = 0
        
        print(f"  ✓ {place_name}: {len(pois)} transport POIs found, avg WAS = {grid['WAS'].mean():.2f}")
        
        return grid, pois
    
    except Exception as e:
        print(f"  ✗ Error processing {place_name}: {str(e)}")
        return None, None


def calculate_walkability(place_name, grid_size=500):
    """
    Calculate walkability score for a given place using geocoding
    
    Parameters:
    -----------
    place_name : str
        Name of the place to analyze
    grid_size : int
        Size of grid cells in meters (default: 500)
    
    Returns:
    --------
    grid : GeoDataFrame
        Grid with walkability scores
    pois : GeoDataFrame
        Points of interest
    """
    print(f"Processing {place_name}...")
    
    try:
        # Get the study area
        study_area = ox.geocode_to_gdf(place_name)
        study_area = study_area.to_crs(epsg=3857)
        
        # Generate grid cells
        minx, miny, maxx, maxy = study_area.total_bounds
        
        grid_cells = []
        x = minx
        while x < maxx:
            y = miny
            while y < maxy:
                grid_cells.append(box(x, y, x + grid_size, y + grid_size))
                y += grid_size
            x += grid_size
        
        grid = gpd.GeoDataFrame({'geometry': grid_cells}, crs=study_area.crs)
        grid = gpd.overlay(grid, study_area, how='intersection')
        
        polygon = study_area.to_crs(epsg=4326).geometry.union_all()
        
        # Define public transport amenities
        transport_tags = {
            "public_transport": ["station", "stop_position", "stop_area"],
            "railway": ["station", "halt", "tram_stop", "subway_entrance"],
            "amenity": ["bus_station", "ferry_terminal"]
        }
        
        pois = ox.features_from_polygon(polygon, transport_tags)
        
        # Filter relevant public transport features
        valid_pois = []
        
        # Check for public_transport tag
        if 'public_transport' in pois.columns:
            public_transport_pois = pois[pois['public_transport'].isin(['station', 'stop_position', 'stop_area'])]
            valid_pois.append(public_transport_pois)
        
        # Check for railway tag
        if 'railway' in pois.columns:
            railway_pois = pois[pois['railway'].isin(['station', 'halt', 'tram_stop', 'subway_entrance'])]
            valid_pois.append(railway_pois)
        
        # Check for amenity tag
        if 'amenity' in pois.columns:
            amenity_pois = pois[pois['amenity'].isin(['bus_station', 'ferry_terminal'])]
            valid_pois.append(amenity_pois)
        
        # Combine all valid POIs and remove duplicates
        if valid_pois:
            pois = pd.concat(valid_pois).drop_duplicates(subset=['geometry'])
        else:
            # Create empty GeoDataFrame with same CRS if no POIs found
            pois = gpd.GeoDataFrame(geometry=[], crs=pois.crs)
        
        # Reproject POIs to match grid
        pois = pois.to_crs(epsg=3857)
        
        # Calculate walkability scores
        grid['centroid'] = grid.geometry.centroid
        grid['raw_score'] = 0
        
        for i, centroid in grid['centroid'].items():
            if len(pois) > 0:
                dists = pois.geometry.distance(centroid)
                score = 0
                
                for d in dists:
                    if d <= 400:  # 5-minute walk
                        score += 3
                    elif d <= 800:  # 10-minute walk
                        score += 2
                    elif d <= 1200:  # 15-minute walk
                        score += 1
                
                grid.at[i, 'raw_score'] = score
        
        # Normalize scores to 0-100
        if len(pois) > 0 and grid['raw_score'].max() > grid['raw_score'].min():
            grid["WAS"] = 100 * (grid['raw_score'] - grid['raw_score'].min()) / \
                          (grid['raw_score'].max() - grid['raw_score'].min())
        else:
            grid["WAS"] = 0
        
        print(f"  ✓ {place_name}: {len(pois)} transport POIs found, avg WAS = {grid['WAS'].mean():.2f}")
        
        return grid, pois
    
    except Exception as e:
        print(f"  ✗ Error processing {place_name}: {str(e)}")
        return None, None


# ============================================================================
# CHOOSE YOUR APPROACH
# ============================================================================

# APPROACH 1: Using shapefiles for specific cities
#cities_with_shapefiles = {
#   'Sao Paolo': {
#        'shapefile': r"C:\Users\I84584\Downloads\sao_paolo.geojson",
#        'continent': 'South America'
#    }
#}

# APPROACH 2: Using improved place names
cities_with_names = {
    'Sao Paolo, Brazil' : 'South America',
    'Dakar, Senegal': 'Africa',
    'Los Angeles, California, USA': 'North America',
    'Jakarta, Indonesia': 'Asia',
    'Paris, France': 'Europe',
    'Sydney, Australia': 'Oceania'
}

# Calculate walkability for all cities
results = {}

# Process cities with shapefiles
for city_name, config in cities_with_shapefiles.items():
    grid, pois = calculate_walkability_from_shapefile(
        config['shapefile'], 
        city_name, 
        grid_size=500
    )
    if grid is not None:
        results[city_name] = {
            'grid': grid, 
            'pois': pois, 
            'continent': config['continent']
        }

# Process cities with place names
for city, continent in cities_with_names.items():
    grid, pois = calculate_walkability(city, grid_size=500)
    if grid is not None:
        results[city] = {'grid': grid, 'pois': pois, 'continent': continent}

# Create comparison plot
fig, axes = plt.subplots(2, 3, figsize=(20, 14))
axes = axes.flatten()

for idx, (city, data) in enumerate(results.items()):
    ax = axes[idx]
    grid = data['grid']
    continent = data['continent']
    
    grid.plot(
        column="WAS",
        cmap="RdYlGn",
        legend=True,
        ax=ax,
        alpha=0.7,
        edgecolor='black',
        linewidth=0.3,
        vmin=0,
        vmax=100,
        legend_kwds={'label': 'Walkability Score', 'shrink': 0.8}
    )
    
    try:
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, alpha=0.5)
    except:
        pass
    
    avg_score = grid['WAS'].mean()
    city_name = city.split(',')[0]
    ax.set_title(
        f"{city_name} ({continent})\nWAS Moyen: {avg_score:.1f} | POIs: {len(data['pois'])}",
        fontsize=12,
        fontweight='bold'
    )
    
    ax.set_xlabel("Easting (m)", fontsize=9)
    ax.set_ylabel("Northing (m)", fontsize=9)
    ax.tick_params(labelsize=8)

fig.suptitle(
    "Walkability Accessibility Score (WAS) - Comparaison des villes de chaque continent\n" + 
    "Accès aux transports publics",
    fontsize=16,
    fontweight='bold',
    y=0.995
)

plt.tight_layout()
plt.savefig('walkability_comparison_6cities_transport.png', dpi=300, bbox_inches='tight')
print("\n✓ Comparison plot saved as 'walkability_comparison_6cities_transport.png'")
plt.show()

# Print summary statistics
print("\n" + "="*70)
print("WALKABILITY SUMMARY STATISTICS (Public Transport)")
print("="*70)
for city, data in results.items():
    grid = data['grid']
    continent = data['continent']
    print(f"\n{city} ({continent}):")
    print(f"  Average WAS: {grid['WAS'].mean():.2f}")
    print(f"  Median WAS:  {grid['WAS'].median():.2f}")
    print(f"  Max WAS:     {grid['WAS'].max():.2f}")
    print(f"  Min WAS:     {grid['WAS'].min():.2f}")
    print(f"  Transport POI Count: {len(data['pois'])}")
    print(f"  Grid Cells:  {len(grid)}")