# -*- coding: utf-8 -*-
"""
Created on Wed Nov 19 16:01:07 2025

@author: Pc
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 09:39:09 2025

@author: Pc
"""

import osmnx as ox
import folium
import geopandas as gpd
from shapely.geometry import box 
from shapely.geometry import Point 
import pandas as pd
import matplotlib.pyplot as plt
import contextily as ctx

###############################################################################
# ETAPE 1 : DEFINIR NOTRE VILLE

place = "Paris, France"

# Get centre coords
gdf = ox.geocode_to_gdf(place)
lat, lon = gdf.geometry.centroid.y[0], gdf.geometry.centroid.x[0]

###############################################################################
# Create folium map
area = folium.Map(location=[lat, lon], zoom_start = 15, tiles = 'OpenStreetMap')

# Add the area polygon to the map
folium.GeoJson(gdf).add_to(area)

# Save and view map
area.save(r"C:\Users\Pc\Downloads\walkability.html")
###############################################################################
# Reproject the study area to a metric coordinate system
study_area = ox.geocode_to_gdf(place)
study_area = study_area.to_crs (epsg=32640)
                                
# Grid cell in meters
grid_size = 1000 # 1km x 1km

# Bounding box of the study area
minx, miny, maxx, maxy = study_area.total_bounds

# Generate grid cells as boxes
grid_cells = []
x = minx
while x < maxx :
    y = miny
    while y < maxy :
        grid_cells.append(box(x, y, x + grid_size, y + grid_size))
        y += grid_size
    x += grid_size
    
# Convert list of boxes to GDF
grid = gpd.GeoDataFrame({'geometry': grid_cells}, crs = study_area.crs)

# Clip grid to the study area boundary
grid = gpd.overlay(grid, study_area, how = 'intersection')

# Display firstfew grid cells
grid.head(5)
###############################################################################
# Convert to a single polygon
polygon = gdf.geometry.union_all()

# Define tags (broad first to avoid missing data)
tags = {"amenity": True} # get all amenities

# Download POIs from OSM
pois = ox.features_from_polygon(polygon, tags)

pois.head
###############################################################################
# Check for missing values 
missing_values = pd.isnull(pois).sum()

# Remove rows where the amenity is missing
pois = pois.dropna(subset=['amenity'])

# Check again for missing values
pd.isnull(pois).sum()
###############################################################################
# Keep only pois that interest me
pois = pois[
    pois['amenity'].isin(['hospital', 'pharmacy', 'clinic', 'dentist', 'nursing_home', 'doctors', 'social_facility'])]

# Reproject POIs to the same UTM CRS as grid
utm_crs = grid.crs
pois = pois.to_crs(utm_crs)
###############################################################################
# Get the centroids of each grid cell
grid['centroid'] = grid.geometry.centroid

# Define distance thresholds (in meters)
bins = [400, 800, 1200]

# Initialise raw walkability scores
grid['raw_score'] = 0

# Loop through each centroid to calculate score
for i, centroid in grid['centroid'].items():
    # Compute distances from this centroid to all POIs
    dists = pois.geometry.distance(centroid)
    
    # Initialise score for this cell
    score = 0
    
    # Assign point based on distance to each POI
    for d in dists:
        if d <= 400:
            score += 3 # Very close - high contribution
        elif d <= 800:
            score += 2 # Medium distance - moderate contribution
        elif d <= 1200:
            score += 1 # Farther - moderlowate contribution
        else:
            score += 0 # Beyond 1200m - no contribution
            
    # Save score for this grid cell
    grid.at[i, 'raw_score'] = score
    
# Check the results
print(grid[['raw_score']].head())
###############################################################################
# Min-max normalisation to scale scores from 0 to 100
grid["WAS"] = 100 * (grid['raw_score']-grid['raw_score'].min()) / (grid["raw_score"].max()-grid["raw_score"].min())

###############################################################################
# Convert grid and POIs back to lat/lon for plotting
grid_latlon = grid.to_crs(epsg=4326)
pois_latlon = pois.to_crs(epsg=4326)

fig, ax = plt.subplots(figsize=(10,10))

# Plot grid cells coloured by WAS
grid_latlon.plot(column="WAS", cmap="viridis", legend=True, ax=ax)

# Overlay POIs
pois_latlon.plot(ax=ax, color="red", markersize=5, alpha=0.6)

# Set title and axis labels
plt.title("Walkable Accessibility Score (WAS)", fontsize=15)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

# Zoom to study area
minx, miny, maxx, maxy = grid_latlon.total_bounds
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)

plt.show()
###############################################################################
# Convert to Web Mercator for basemap compatibility
grid_3857 = grid.to_crs(epsg=3857)
pois_3857 = pois.to_crs(epsg=3857)

fig, ax = plt.subplots(figsize=(12,12))

# Plot grid with WAS
grid_3857.plot(
    column="WAS",
    cmap="viridis",
    legend=True,
    ax=ax,
    alpha=0.7,
    edgecolor='k',
    linewidth=0.2
    )

# Plot of POIs
#pois_3857.plot(ax=ax, color = "red", markersize = 8, alpha = 0.7, label = "POIs")

# Basemap
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

# Add title, legend, labels
plt.title("Walkable Accessibility Score (WAS)")
plt.legend()
plt.xlabel("Easting (meters)")
plt.ylabel("Northing (meters)")
plt.show()





