import folium
from folium import plugins
import requests

def get_route(start, end):
    #url = f"http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=false"
    url = 'http://router.project-osrm.org/route/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219?overview=false'
    response = requests.get(url)
    data = response.json()
    # coordinates = []
    print(data)
    # if 'routes' in data and len(data['routes']) > 0:
    #     coordinates = data['routes'][0]['geometry']['coordinates']
    return [start, end]
    #return coordinates

def main():
    # Coordonnées de départ et d'arrivée (latitude, longitude)
    start_coord = (48.8566, 2.3522)  # Paris
    end_coord = (45.7721915, 4.8631351) 

    # Récupération des points de l'itinéraire
    route_points = get_route(start_coord, end_coord)

    # Création de la carte
    map_center = ((start_coord[0] + end_coord[0]) / 2, (start_coord[1] + end_coord[1]) / 2)
    my_map = folium.Map(location=map_center, zoom_start=5)

    # Ajout des points de l'itinéraire à la carte
    folium.PolyLine(locations=route_points, color='blue').add_to(my_map)

    # Ajout des marqueurs de départ et d'arrivée à la carte
    folium.Marker(location=start_coord, popup='Départ', icon=folium.Icon(color='green')).add_to(my_map)
    folium.Marker(location=end_coord, popup='Arrivée', icon=folium.Icon(color='red')).add_to(my_map)

    # Sauvegarde de la carte dans un fichier HTML
    my_map.save("itineraire.html")

if __name__ == "__main__":
    main()
