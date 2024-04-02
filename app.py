import streamlit as st
import sqlite3
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import osmnx as ox
import networkx as nx
import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt
import folium
import geopandas as gpd
from geopy.distance import geodesic
import requests
import numpy as np
from streamlit_geolocation import streamlit_geolocation
import datetime

def get_user_location():
    # Obtenir les coordonnées de la localisation de l'utilisateur
    location = streamlit_geolocation()
    lat = location["latitude"]
    lon = location["longitude"]
    if lat != None and lon != None:
        return (lat,lon)
    else:
        return None


# Fonction pour géocoder une adresse et obtenir ses coordonnées
def geocoder_adresse(adresse):
    geolocator = Nominatim(user_agent="my_geocoder")
    location = geolocator.geocode(adresse)
    if location:
        return (location.latitude, location.longitude)
    else:
        return None


def afficher_adresse(lat, lon):
    geolocator = Nominatim(user_agent="my_geocoder")
    location = geolocator.reverse((lat, lon))
    return location.address

def get_nearest_pump(coord_reference, df,rayon_max,carburant):
    distances = []
    for index, row in df.iterrows():
        coord_pump = (row['latitude'], row['longitude'])
        distance_km = geodesic(coord_reference, coord_pump).kilometers
        type_carburant = carburant+"_prix"

        if distance_km <= rayon_max:
            distances.append((distance_km, row['adresse'], row[type_carburant], coord_pump,row['ville'],row['adresse_complete']))
    if distances:
        return distances
    else:
        return None


def charger_donnees(carburant):
    conn = sqlite3.connect("data.db")
    query = f"SELECT * FROM prix_carburants_actuels WHERE {carburant}_prix IS NOT NULL"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# Fonction pour charger les données depuis la base SQLite
def charger_donnees2(carburant):
    conn = sqlite3.connect("data.db")
    query = f"""
    SELECT *
    FROM prix_carburants_actuels
    JOIN (
        SELECT DISTINCT adresse_complete
        FROM prix_carburants_actuels
    ) AS adresses_uniques
    ON prix_carburants_actuels.adresse_complete = adresses_uniques.adresse_complete
    WHERE {carburant}_prix IS NOT NULL
    """
    # Exécution de la requête SQL avec les paramètres
    df = pd.read_sql_query(query, conn)

    # Fermer la connexion à la base de données
    conn.close()
    return df



def update_data():
    col1, col2 = st.columns(2)  # Diviser en deux colonnes
    with col1:
        if st.button("Update les dernières données"):
            with st.spinner("Récupération en cours..."):
                # Téléchargement des données JSON depuis l'URL
                url = "https://www.data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/exports/csv"
                
                response = requests.get(url)

                if response.status_code == 200:
                    res = response.content.decode('utf-8-sig')
                    with open("prix_carburants.csv", "w", encoding="utf-8") as f:
                        f.write(res)

                    df = pd.read_csv("prix_carburants.csv", sep=';')

                    df["adresse_complete"] = df["adresse"] + ", " + df["ville"] + ", "+df["code_departement"]

                    df[['latitude', 'longitude']] = df['geom'].str.split(', ', expand=True)

                    # Obtenir la date et l'heure actuelles
                    maintenant = datetime.datetime.now()
                    date_formattee = maintenant.strftime("%Y-%m-%d %H:%M")

                    df["date"] = date_formattee

                    # Supprimer les lignes où la valeur de la colonne "prix" est None => "station de gonflage etc..." => pas de carburant
                    df = df.dropna(subset=['prix'])

                    #df.to_csv("prix_carburants.csv",sep=";")

                    conn = sqlite3.connect("data.db")

                    df.to_sql("prix_carburants_historique", conn, if_exists="append", index=False)  # append dans l'historique
                    df.to_sql("prix_carburants_actuels", conn, if_exists="replace", index=False)  # replace dans la base actuelle
                    
                    conn.close()

                    msg = f"Vous disposez des dernières ({len(df)}) données :white_check_mark:"
                    st.success(msg)
                else:
                    st.write("Erreur lors du refresh des données")

    with col2:
        if st.button("Supprimer toute la base actuelle"):
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()

            cursor.execute(f"DROP TABLE IF EXISTS prix_carburants_actuels;")
            msg = f"La table prix_carburants_actuels a été supprimée :white_check_mark:"
            st.success(msg)

            conn.commit()
            conn.close()



def recherche():
    carburants = ["gazole","sp95","e85","gplc","e10","sp98"]

    col1, col2 = st.columns(2)  # Diviser en deux colonnes

    with col1:
        carburant_selectionne = st.selectbox("Sélectionner le type de carburant", carburants) 
        donnees = charger_donnees(carburant_selectionne)
    
    with col2:
        user_location = st.radio("Sélectionnez la méthode de localisation :", ("Utiliser la localisation automatique", "Entrer une adresse manuellement"))

    
    adresse_utilisateur = None

    if user_location == "Utiliser la localisation automatique":
        #  check si il a accepté la loc
        user_coords = get_user_location()
        if user_coords:
            adresse_utilisateur = afficher_adresse(user_coords[0], user_coords[1])
            if adresse_utilisateur:
                pass
            else:
                st.error("Adresse introuvable")
        else:
            st.error("Impossible de récupérer la localisation automatique.")
    else:
        adresse_utilisateur = st.text_input("Entrez votre adresse :")
    

    if adresse_utilisateur:
        rayon_maximal = st.slider("Rayon maximal (en kilomètres)", min_value=1, max_value=300,value=10, step=1)
        if st.slider:
            afficher_carte(donnees,adresse_utilisateur,rayon_maximal,carburant_selectionne) 



def afficher_carte(df,adresse_utilisateur,rayon_maximal,carburant):
    m = folium.Map(location=[48.8566, 2.3522], zoom_start=5)
    marker_cluster = MarkerCluster().add_to(m)
    coords_adresse = geocoder_adresse(adresse_utilisateur)

    min_price = float('inf')
    min_dist = float('inf')
    min_address = None
    min_coords = None
    
    near_dist=None
    near_address=None 
    near_carburant=None
    near_point_destination = None

    liste_adresse_distinct = []
    if coords_adresse:
        all_pump = get_nearest_pump(coords_adresse, df,rayon_maximal,carburant)
        nearest_pump = min(all_pump)

        near_dist, near_address,near_carburant,near_point_destination,near_ville,near_full_adress = nearest_pump
        
        # Parcourir le DataFrame et ajouter des marqueurs pour chaque station
        for item in all_pump:
            full_adress = item[5]
            ville = item[4]
            coord_station = item[3]
            prix_gazole = item[2]
            adresse = item[1]
            dist = item[0]
            
            if prix_gazole < min_price:
                min_price = prix_gazole
                min_address = adresse
                min_coords = coord_station
                min_dist = dist

            # pour ne pas repasser 2 fois sur la station la plus proche
            if coord_station != (near_point_destination[0], near_point_destination[1]) or full_adress not in liste_adresse_distinct:
                liste_adresse_distinct.append(full_adress)

                lat_station, lon_station = coord_station
                popup_text = f"Adresse: {adresse}<br>Prix: {prix_gazole}"
                if len(all_pump) >= 200:
                    # mettre dans un cluster
                    folium.Marker(location=[lat_station, lon_station], popup=popup_text).add_to(marker_cluster)
                else:
                    folium.Marker(location=[lat_station, lon_station], popup=popup_text).add_to(m)


        # Afficher station la moins chère
        lat_min,long_min = min_coords
        folium.Marker(location=[lat_min, long_min], popup='Station la moins chère', icon=folium.Icon(color='pink')).add_to(m)
        folium.Marker(location=[coords_adresse[0], coords_adresse[1]], popup='Vous êtes içi', icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(location=[near_point_destination[0], near_point_destination[1]], popup='Station la plus proche', icon=folium.Icon(color='red')).add_to(m)
      

    col1, col2 = st.columns(2)  # Diviser en deux colonnes

    with col1:
        with st.expander("Informations sur la station la moins chère"):
            st.write("Adresse :world_map: :", min_address,", ",ville)
            st.write("Distance :car: :", round(min_dist, 2), "kilomètres")
            st.write("Prix ", carburant, " :euro: :", min_price, " €")

    with col2:
        with st.expander("Informations sur la station la plus proche"):
            st.write("Adresse :world_map: :", near_address,", ",near_ville)
            st.write("Distance :car: :", round(near_dist, 2), "kilomètres")
            st.write("Prix ", carburant, " :euro: :", near_carburant, " €")
    

    #ajouter le tracer chemin en voiture ... ???
    folium_static(m)
    


def accueil():
    conn = sqlite3.connect("data.db")

    query = "SELECT * FROM prix_carburants_actuels"
    df = pd.read_sql_query(query, conn)
   
    query = "SELECT * FROM prix_carburants_historique"
    df_h = pd.read_sql_query(query, conn)

    # Fermer la connexion à la base de données
    conn.close()

    col1, col2 = st.columns(2)  # Diviser en deux colonnes

    with col1:
        st.write("Nombre de lignes dans la base :",len(df))
    with col2:
        st.write("Nombre de lignes dans l'historique :",len(df_h))

    # Calcul des prix moyens de chaque type d'essence
    prix_moyen_gazole = df['gazole_prix'].mean()
    prix_moyen_sp95 = df['sp95_prix'].mean()
    prix_moyen_e85 = df['e85_prix'].mean()
    prix_moyen_gplc = df['gplc_prix'].mean()
    prix_moyen_e10 = df['e10_prix'].mean()
    prix_moyen_sp98 = df['sp98_prix'].mean()

    # Création d'un DataFrame pour les prix moyens
    data = {
        'Type d\'essence': ['Gazole', 'SP95', 'E85', 'GPLC', 'E10', 'SP98'],
        'Prix moyen (€ / L)': [prix_moyen_gazole, prix_moyen_sp95, prix_moyen_e85, prix_moyen_gplc, prix_moyen_e10, prix_moyen_sp98]
    }

    df_prix_moyens = pd.DataFrame(data)
    # Création du graphique à barres avec Seaborn
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Type d\'essence', y='Prix moyen (€ / L)', data=df_prix_moyens, palette='viridis')
    plt.title('Prix moyen de chaque type d\'essence en France')
    plt.xticks(rotation=45)
    # Affichage du graphique dans Streamlit
    st.pyplot(plt)



    ####### Carte Dep / Region ######

    #choisir le type carburant 
    carburants = ["gazole","sp95","e85","gplc","e10","sp98"]
    carburant_selectionne = st.selectbox("Sélectionner le type de carburant", carburants) 
    
    type_carburant = carburant_selectionne+"_prix"

    caption = carburant_selectionne+" (€ / L) moyen"

    
    # Création d'une carte Folium centrée sur la France
    m = folium.Map(location=[46.603354, 1.888334], zoom_start=6)
    on = st.toggle('Vue Départements / Régions')
    if on:
        regions_france = gpd.read_file("regionsChloro.geojson")
        df_agg_regions = df.groupby('region').agg({type_carburant: 'mean'}).reset_index()
        df_agg_regions.rename(columns={'region': 'nom'}, inplace=True)
        gdf_regions = pd.merge(regions_france, df_agg_regions, on='nom')

        colormap = folium.LinearColormap(colors=['green', 'yellow', 'red'], vmin=gdf_regions[type_carburant].min(), vmax=gdf_regions[type_carburant].max())
        colormap.caption = caption

        # Ajouter les données du GeoDataFrame à la carte avec la couleur définie par les prix du gazole
        folium.GeoJson(
            gdf_regions,
            style_function=lambda feature: {
                'fillColor': get_color(feature['properties'][type_carburant],colormap),
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.7
            }
        ).add_to(m)
        # Ajouter une légende à la carte
        colormap.add_to(m)

    else:
        #txt = f"Prix moyen du {carburant_selectionne} par départements"
        #st.info(txt)
        departements_france = gpd.read_file("departementsChloro.geojson")
        df_agg_departements = df.groupby('departement').agg({type_carburant: 'mean'}).reset_index()
        df_agg_departements.rename(columns={'departement': 'nom'}, inplace=True)
        gdf_dep = pd.merge(departements_france, df_agg_departements, on='nom')

        colormap = folium.LinearColormap(colors=['green', 'yellow', 'red'], vmin=gdf_dep[type_carburant].min(), vmax=gdf_dep[type_carburant].max())
        colormap.caption = caption
    
        # Ajouter les données du GeoDataFrame à la carte avec la couleur définie par les prix du gazole
        folium.GeoJson(
            gdf_dep,
            style_function=lambda feature: {
                'fillColor': get_color(feature['properties'][type_carburant],colormap),
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.7
            }
        ).add_to(m)
        # Ajouter une légende à la carte
        colormap.add_to(m)

    folium_static(m)

    
    conn = sqlite3.connect("data.db")
    query = "SELECT * FROM prix_carburants_historique"

    # # Exécution de la requête SQL avec les paramètres
    df = pd.read_sql_query(query, conn)
    # Fermer la connexion à la base de données
    conn.close()


    df_aggregated = df.groupby('date')[type_carburant].mean().reset_index()
    df_aggregated['date'] = pd.to_datetime(df_aggregated['date'])  # Convertir la colonne de date en format datetime

    # # Tracer le graphique avec Seaborn
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df_aggregated, x='date', y=type_carburant, marker='o')
    txt = f"Évolution des prix du {carburant_selectionne}"
    plt.title(txt)
    plt.xlabel('Date')
    txt = f"Prix moyen (€ / L)"
    plt.ylabel(txt)
    plt.xticks(rotation=45)
    plt.grid(True)
    st.pyplot(plt)  # Afficher le graphique dans Streamlit

        
def get_color(value,colormap):
    if value is None:
        return 'gray'  # Couleur grise pour les valeurs None
    else:
        return colormap(value)


def main():
    # Titre de l'application
    st.markdown("<h1 style='text-align: center;'>&#x26FD; Fuel Pump Finder &#x26FD;</h1>", unsafe_allow_html=True)
    
    onglets = ["Accueil", "Recherche","Base de données"]
    onglet_selectionne = st.sidebar.radio("Navigation", onglets)

    if onglet_selectionne == "Accueil":
        accueil()
    elif onglet_selectionne == "Recherche":
        recherche()
    elif onglet_selectionne =="Base de données":
        update_data()


if __name__ == "__main__":
    main()

#https://fuelpumpfinder.streamlit.app/