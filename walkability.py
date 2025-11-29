# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 09:39:09 2025

@author: Kalma Hazara
"""

import osmnx as ox
import folium
import geopandas as gpd
from shapely.geometry import box 
from shapely.geometry import Point 
import pandas as pd
import utm
import branca.colormap as cm

###############################################################################
## ETAPE 1 : DEFINIR NOTRE VILLE ##

ville = "Paris, France"

###############################################################################
## ETAPE 2 : VISUALISATION DU CONTOUR DE LA VILLE ##

# Transformer notre polygone OSM en geodataframe
gdf = ox.geocode_to_gdf(ville)

# Obtenir les coordonnées centrales de la ville
lat, lon = gdf.geometry.centroid.y[0], gdf.geometry.centroid.x[0]

# Créer la carte avec et zoomer sur les coordonnées centrales de notre ville
contour_ville = folium.Map(location=[lat, lon], zoom_start = 15, tiles = 'OpenStreetMap')

# Ajouter notre couche polygone ville sur notre webmap
folium.GeoJson(gdf).add_to(contour_ville)

# Sauvegarder et visualiser la carte
contour_ville.save(r"C:\Users\Pc\Downloads\marchabilite.html")

###############################################################################
## ETAPE 3 : CREATION DES CARROYAGES POUR CARTE ##

# Je rappelle la polygone de la ville d'Open Street Map
ville_etude = ox.geocode_to_gdf(ville)

# Je détermine un epsg précis d'un pays donné   
utm_zone = utm.from_latlon(lat, lon)[2]
epsg = 32600 + utm_zone
ville_etude = ville_etude.to_crs (epsg=epsg)
                                
# Déterminer la taille de nos carrés
grid_size = 500 # 500m x 500m

# Dessiner une boîte autour de notre ville d'étude
minx, miny, maxx, maxy = ville_etude.total_bounds

# Créer les carrés automatiquement à l'intérieur de notre boîte
grid_cells = []
x = minx
while x < maxx :
    y = miny
    while y < maxy :
        grid_cells.append(box(x, y, x + grid_size, y + grid_size))
        y += grid_size
    x += grid_size
    
# Convertir nos carrés en géodataframe grâce à Geopandas
grid = gpd.GeoDataFrame({'geometry': grid_cells}, crs = ville_etude.crs)

# Découper notre carte carroyé selon la forme de notre polygone de la ville
grid = gpd.overlay(grid, ville_etude, how = 'intersection')

###############################################################################
## ETAPE 4 : RECUPERATION LES POIs D'OPEN STREET MAP

# M'assurer que ma couche de ville n'est pas segmenté
polygon = gdf.geometry.union_all()

# Ecrire la requête OSM pour récupérer les POIs transports en commun
tags = {
    "public_transport": ["station", "stop_position", "platform"],
    "railway": ["station", "halt", "tram_stop", "subway_entrance"],
    "highway": ["bus_stop"]}

# Télécharger les POIs d'Open Street Map
pois = ox.features_from_polygon(polygon, tags)

# Retirer les lignes vides
pois = pois.dropna(subset=["public_transport", "railway", "highway"], how="all")

# Reprojection vers l’UTM du grid carroyé
pois = pois.to_crs(epsg=epsg)

###############################################################################
## ETAPE 5 : CALCULER LE SCORE DE MARCHABILITE ##

# Créer un centroide sur chaque carreau pour pouvoir messurer les distances aux POIs
grid['centroid'] = grid.geometry.centroid

# Créer des seuils de distance pour la marchabilité
seuils = [400, 800, 1200] # ce sont des valeurs en mètres

# Création d'une colonne vide pour le score de la marchabilité de chaque carreau
grid['raw_score'] = 0

# Boucle de calcul de distance pour chaque centroïde du carré 
for i, centroid in grid['centroid'].items():
    # Mesurer la distance entre le centroïde et les POIs
    dists = pois.geometry.distance(centroid)
    
    # Reinitialise le score du carré
    score = 0
    
    # Selon sa distance, on lui attribue un score
    for d in dists:
        if d <= 400:
            score += 3 # Ajouter 3 points si très proche (inférieur ou égale à 400m)
        elif d <= 800:
            score += 2 # Ajouter 2 points si moyennement proche (entre 400 et 800m)
        elif d <= 1200:
            score += 1 # Ajouter 1 points si moins proche (entre 800 et 1200)
        else:
            score += 0 # Si la distance est au delà de 1200m, ajouter 0 point
            
    # Ajouter le score au carré
    grid.at[i, 'score_brut'] = score

###############################################################################
## ETAPE 6 : CONVERTIR EN VALEUR ENTRE 0 et 100

# Normalisation du résultat
# Inspiré de ce code : https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html
grid["score_final"] = 100 * (grid['score_brut']-grid['score_brut'].min()) / (grid["score_brut"].max()-grid["score_brut"].min())

###############################################################################
## ETAPE 7 : VISUALISATION DE LA CARTE FINALE AVEC FOLIUM ##

# Conversion des crs au WG84 pour folium
grid_wgs84 = grid.to_crs(epsg=4326)
pois_wgs84 = pois.to_crs(epsg=4326)

# Création de la carte de base
# J'utilise la CartoDB positron pour un fond de carte minimaliste
# Nous centrons la carte sur les coordonnées de la ville définies plus tôt.
carte_marchabilite = folium.Map(location=[lat, lon], zoom_start=13, tiles='CartoDB positron')

# Styling du titre avec du html
titre_html = f'''
<div style="
    position: fixed; 
    top: 20px; 
    left: 50px; 
    width: 350px; 
    background-color: rgba(255, 255, 255, 0.9); 
    border-left: 5px solid #2c3e50;
    z-index: 9999;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 22px;
    font-weight: bold;
    color: #2c3e50;
    padding: 15px;
    border-radius: 8px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    ">
    Marchabilité : {ville}
    <div style="font-size: 14px; font-weight: normal; margin-top: 5px; color: #7f8c8d;">
        Analyse de l'accessibilité aux transports
    </div>
</div>
'''
# On ajoute cet élément HTML sur la carte
carte_marchabilite.get_root().html.add_child(folium.Element(titre_html))

# Création de la légende avec colormap car je peux déterminer manuellement les couleurs
colormap = cm.LinearColormap(
    colors=['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'], # Rouge -> Vert
    vmin=grid_wgs84['score_final'].min(), # Valeur minimale de nos données
    vmax=grid_wgs84['score_final'].max(), # Valeur maximale de nos données
    caption='Score de Marchabilité (0 = Faible, 100 = Élevé)' # Titre de la légende
)

# Ajout des carreaux (grid) à la carte
# Je l'ajoute dans un Feature group pour que l'utilisateur puisse cocher/décocher cette couche
groupe_carreaux = folium.FeatureGroup(name='🟦 Score de Marchabilité', show=True)

# Parcours chaque carré de notre tableau de données pour l'ajouter à la carte
for idx, row in grid_wgs84.iterrows():
    # On récupère le score et la géométrie du carré
    score = row['score_final']
    geometry = row['geometry']
    
    # On détermine la couleur du carré grâce à notre palette (colormap) définie plus haut
    couleur_carre = colormap(score)
    
    # On ajoute le carré sous forme de GeoJson
    folium.GeoJson(
        geometry,
        style_function=lambda x, color=couleur_carre: {
            'fillColor': color,      # Couleur de remplissage selon le score
            'color': 'white',        # Couleur de la bordure du carré (blanc pour faire propre)
            'weight': 0.5,           # Épaisseur de la bordure
            'fillOpacity': 0.6       # légèrement transparent
        },
        # L'infobulle (tooltip) s'affiche au survol de la souris
        tooltip=f"Score: {score:.1f} / 100"
    ).add_to(groupe_carreaux)

# Une fois tous les carrés ajoutés au groupe, on ajoute le groupe à la carte principale
groupe_carreaux.add_to(carte_marchabilite)

# On fait la même chose pour les arrêts de transport
groupe_pois = folium.FeatureGroup(name='Arrêts de Transport', show=True)

# Parcours chaque point d'intérêt trouvé
for idx, row in pois_wgs84.iterrows():
    # On essaie de récupérer le nom de l'arrêt, sinon on met "Transport" par défaut
    nom = row.get('name', 'Transport')
    
    # On personnalise la couleur et l'icône selon le type de transport
    # Cela rend la carte plus lisible et informative
    if pd.notna(row.get('public_transport')):
        couleur = '#3498db' # Bleu pour les bus/trams génériques
        type_transport = "Transport Public"
    elif pd.notna(row.get('railway')):
        couleur = '#e74c3c' # Rouge pour les trains/métros
        type_transport = "Ferroviaire"
    else:
        couleur = '#2ecc71' # Vert pour les autres (arrêts de bus simples)
        type_transport = "Arrêt de Bus"
    
    # On veut récupérer que les points
    if row.geometry.geom_type == 'Point':
        # On ajoute un marqueur circulaire
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x], # Latitude, Longitude
            radius=5,                   # Taille du point
            popup=f"<b>{nom}</b><br><i>{type_transport}</i>", # Fenêtre qui s'ouvre au clic (avec du HTML)
            color='white',              # Bordure blanche pour bien ressortir
            weight=1,                   # Epaisseur de la bordure
            fill=True,                  # Remplir le cercle
            fillColor=couleur,          # Couleur intérieure définie plus haut
            fillOpacity=0.8             # Transparence
        ).add_to(groupe_pois)

# On ajoute le groupe de POIs à la carte
groupe_pois.add_to(carte_marchabilite)

# On ajoute la légende des couleurs en haut à droite de la carte
colormap.add_to(carte_marchabilite)

# On ajoute le panneau de contrôle des couches (en haut à droite)
folium.LayerControl(collapsed=False).add_to(carte_marchabilite)

# Enfin, on sauvegarde le résultat dans un fichier HTML interactif
chemin_sortie = r"C:\Users\Pc\Downloads\carte_marchabilite_finale.html"
carte_marchabilite.save(chemin_sortie)